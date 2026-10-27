"""NAVER API HUB 검색 (뉴스, 지역). 2026-07-31부터 개발자센터 대신 네이버 클라우드의 API HUB로 제공된다."""

import html
import re

import httpx

BASE_URL = "https://naverapihub.apigw.ntruss.com/search/v1"
SOURCE = "네이버 뉴스 검색 (NAVER API HUB)"

_TAG = re.compile(r"<[^>]+>")


def clean_text(text: str) -> str:
    """검색 결과의 <b> 강조 태그와 &quot; 같은 HTML 엔티티를 없앤다."""
    return html.unescape(_TAG.sub("", text or "")).strip()


class NaverSearchClient:
    def __init__(self, client_id: str, client_secret: str, client: httpx.Client | None = None):
        self._headers = {"X-NCP-APIGW-API-KEY-ID": client_id, "X-NCP-APIGW-API-KEY": client_secret}
        self._client = client or httpx.Client(timeout=10)

    def _get(self, kind: str, params: dict) -> list[dict]:
        res = self._client.get(f"{BASE_URL}/{kind}", params={**params, "format": "json"}, headers=self._headers)
        res.raise_for_status()
        return res.json().get("items", [])

    def search_news(self, query: str, display: int = 100, start: int = 1) -> list[dict]:
        """최신순 뉴스. 항목: title, originallink, link, description, pubDate"""
        return self._get("news", {"query": query, "display": display, "start": start, "sort": "date"})

    def search_local(self, query: str, display: int = 5) -> list[dict]:
        """지역(장소) 검색. 항목: title, address, roadAddress, mapx·mapy(경위도 × 10^7)"""
        return self._get("local", {"query": query, "display": display})
