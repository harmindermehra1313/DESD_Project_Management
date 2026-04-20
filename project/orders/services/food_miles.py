# added food miles - joe
import json
import math
import os
import sys
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

from django.conf import settings
from django.core.cache import cache

from accounts.models import Address

POSTCODES_IO_BASE_URL = "https://api.postcodes.io"
POSTCODE_CACHE_TTL_SECONDS = 60 * 60 * 24
MILES_ROUND_DP = Decimal("0.01")


def _api_enabled() -> bool:
    if hasattr(settings, "FOOD_MILES_ENABLE_API"):
        return bool(settings.FOOD_MILES_ENABLE_API)

    if "PYTEST_CURRENT_TEST" in os.environ:
        return False

    if any(arg.lower().startswith("test") for arg in sys.argv):
        return False

    return True


def normalize_postcode(postcode: Optional[str]) -> Optional[str]:
    if not postcode:
        return None

    normalized = "".join(str(postcode).upper().split())
    return normalized or None


def _postcode_cache_key(normalized_postcode: str) -> str:
    return f"food_miles:postcode:{normalized_postcode}"


def _fetch_postcode_coordinates(normalized_postcode: str) -> Optional[Tuple[float, float]]:
    if not _api_enabled():
        return None

    cache_key = _postcode_cache_key(normalized_postcode)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url = f"{POSTCODES_IO_BASE_URL}/postcodes/{quote(normalized_postcode)}"

    try:
        with urlopen(url, timeout=2.0) as response:
            raw = response.read()
    except (HTTPError, URLError, TimeoutError, ValueError):
        cache.set(cache_key, False, timeout=60)
        return None

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        cache.set(cache_key, False, timeout=60)
        return None

    result = payload.get("result") or {}
    latitude = result.get("latitude")
    longitude = result.get("longitude")

    if latitude is None or longitude is None:
        cache.set(cache_key, False, timeout=60)
        return None

    coords = (float(latitude), float(longitude))
    cache.set(cache_key, coords, timeout=POSTCODE_CACHE_TTL_SECONDS)
    return coords


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> Decimal:
    radius_miles = 3958.7613

    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = Decimal(str(radius_miles * c))
    return distance.quantize(MILES_ROUND_DP, rounding=ROUND_HALF_UP)


def calculate_food_miles(
    farm_postcode: Optional[str], customer_postcode: Optional[str]
) -> Optional[Decimal]:
    farm_norm = normalize_postcode(farm_postcode)
    customer_norm = normalize_postcode(customer_postcode)

    if not farm_norm or not customer_norm:
        return None

    farm_coords = _fetch_postcode_coordinates(farm_norm)
    customer_coords = _fetch_postcode_coordinates(customer_norm)

    if not farm_coords or not customer_coords:
        return None

    return _haversine_miles(
        farm_coords[0],
        farm_coords[1],
        customer_coords[0],
        customer_coords[1],
    )


def get_default_delivery_postcode(user) -> Optional[str]:
    if not user or not getattr(user, "is_authenticated", False):
        return None

    addresses = Address.objects.filter(user=user)
    default = addresses.filter(is_default_delivery=True).first() or addresses.first()

    if not default:
        return None

    return default.postcode
