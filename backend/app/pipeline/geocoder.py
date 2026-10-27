"""4단계: 장소명 → 좌표 (AI-REQ-02). 네이버 지역 검색으로 찾고, 못 찾으면 구·군 중심으로 대신한다."""

import logging

import httpx

from app.constants import BUSAN_BBOX, DISTRICT_CENTERS
from app.pipeline.naver import NaverSearchClient

log = logging.getLogger(__name__)

CITY_WIDE = {"부산", "부산시", "부산광역시", "부산전역", "부산일대", "부산지역"}
# 장소 끝에 붙어 검색을 방해하는 말 (예: "동아대 승학캠퍼스 인근 도로")
VAGUE_WORDS = {"인근", "일대", "주변", "앞", "부근", "근처", "도로", "일원", "앞바다", "해상"}


def _in_busan(lat: float, lng: float) -> bool:
    south, west, north, east = BUSAN_BBOX
    return south <= lat <= north and west <= lng <= east


class Geocoder:
    def __init__(self, naver: NaverSearchClient):
        self._naver = naver
        self._cache: dict[str, tuple[float, float] | None] = {}

    def locate(self, place: str | None) -> tuple[float, float] | None:
        # "부산", "부산시"처럼 부산 전체를 뜻하면 지도에 찍지 않는다 (시청 위치로 잘못 보이지 않게)
        if not place or place.replace(" ", "") in CITY_WIDE:
            return None
        if place not in self._cache:
            self._cache[place] = self._search_progressively(place) or self._district_center(place)
        return self._cache[place]

    def _search_progressively(self, place: str) -> tuple[float, float] | None:
        """전체 장소명으로 못 찾으면 모호한 말을 빼고, 뒤에서부터 한 단어씩 줄여 다시 찾는다.
        예: "사하구 동아대 승학캠퍼스 인근 도로" → "사하구 동아대 승학캠퍼스" → ..."""
        words = [w for w in place.split() if w not in VAGUE_WORDS]
        candidates = [place]
        for end in range(len(words), 0, -1):
            candidate = " ".join(words[:end])
            # 구·군 이름만 남으면 검색 대신 구·군청 좌표를 쓴다
            if candidate and candidate not in candidates and candidate.removeprefix("부산").strip() not in DISTRICT_CENTERS:
                candidates.append(candidate)
        for candidate in candidates[:4]:  # 지역 검색 호출 수 제한
            coords = self._search(candidate)
            if coords:
                return coords
        return None

    def _search(self, place: str) -> tuple[float, float] | None:
        query = place if place.startswith("부산") else f"부산 {place}"
        try:
            items = self._naver.search_local(query)
        except httpx.HTTPError as e:
            log.warning("지역 검색 실패 (%s): %s", place, e)
            return None
        for item in items:
            address = f"{item.get('roadAddress', '')} {item.get('address', '')}"
            try:
                lng, lat = int(item["mapx"]) / 1e7, int(item["mapy"]) / 1e7
            except (KeyError, TypeError, ValueError):
                continue
            if "부산" in address and _in_busan(lat, lng):
                return round(lat, 6), round(lng, 6)
        return None

    @staticmethod
    def _district_center(place: str) -> tuple[float, float] | None:
        # "강서구"가 "서구"로 잘못 잡히지 않도록 긴 이름부터 찾는다
        for name in sorted(DISTRICT_CENTERS, key=len, reverse=True):
            if name in place:
                return DISTRICT_CENTERS[name]
        return None
