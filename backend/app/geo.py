from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 좌표 사이 거리 (하버사인 공식)."""
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))
