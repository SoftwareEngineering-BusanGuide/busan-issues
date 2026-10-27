"""이슈 분류값. SRS 1.2 범위(재난·사고·교통 통제·공사·단수정전·행사 등)를 기준으로 정했다."""

CATEGORIES = ("재난·안전", "사건·사고", "교통", "공사·생활", "행정", "행사")

# importance가 high인 이슈는 위치와 관계없이 '부산 주요 이슈'로 보여준다 (FR-003)
IMPORTANCE_HIGH = "high"
IMPORTANCE_NORMAL = "normal"

# 주변 이슈 기본 반경 (FR-002)
DEFAULT_RADIUS_KM = 2.0
MAX_RADIUS_KM = 20.0
