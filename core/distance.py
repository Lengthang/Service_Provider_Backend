from math import asin, cos, radians, sin, sqrt
from typing import Optional

EARTH_RADIUS_KM = 6371.0


def haversine_km(
    lat1: Optional[float],
    lon1: Optional[float],
    lat2: Optional[float],
    lon2: Optional[float],
) -> Optional[float]:
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None

    lat1_r, lat2_r = radians(float(lat1)), radians(float(lat2))
    dlat = lat2_r - lat1_r
    dlon = radians(float(lon2) - float(lon1))

    a = sin(dlat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(dlon / 2) ** 2
    return round(2 * EARTH_RADIUS_KM * asin(sqrt(a)), 2)
