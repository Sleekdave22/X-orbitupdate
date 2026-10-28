"""Coarse advert coordinates and approximate search distances; no geocoding.

Used by listing validation and Plaza lexical search. Coordinates are optional,
rounded to two decimal places, and must never imply a precise delivery location.
"""
import math


def coordinates(latitude, longitude):
    """Validate an optional pair of degree values and keep existing precision."""
    if latitude in (None, '') and longitude in (None, ''):
        return None, None
    try:
        # bool is numerically convertible in Python but is not a coordinate.
        if isinstance(latitude, bool) or isinstance(longitude, bool):
            raise ValueError()
        lat, lon = float(latitude), float(longitude)
        if (
            not math.isfinite(lat)
            or not math.isfinite(lon)
            or not -90 <= lat <= 90
            or not -180 <= lon <= 180
        ):
            raise ValueError()
        return round(lat, 2), round(lon, 2)
    except (ValueError, TypeError):
        raise ValueError('Supply valid approximate latitude and longitude together')


def distance(a, b, c, d):
    """Return kilometres between two degree-valued (latitude, longitude) pairs.

    Uses the existing spherical-earth estimate, not road/travel distance. Public
    argument names remain unchanged for callers that may use keyword arguments.
    """
    lat_a, lon_a, lat_b, lon_b = map(math.radians, (a, b, c, d))
    haversine = (
        math.sin((lat_b - lat_a) / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin((lon_b - lon_a) / 2) ** 2
    )
    # Floating-point rounding near antipodal points can put this just above one.
    return round(6371 * 2 * math.asin(min(1, math.sqrt(haversine))), 1)


def refine(items, q, mode):
    """Annotate copies in input order; only radius mode excludes unknown pins.

    q is the parse_qs-style mapping used by market_search.search: each value is a
    list and only its first element is read. Sorting remains the caller's job.
    """
    def arg(name, default=''):
        return q.get(name, [default])[0]

    lat, lon = coordinates(arg('latitude'), arg('longitude'))
    if mode == 'distance' and lat is None:
        raise ValueError('Choose your approximate search location first')

    radius = None
    if mode == 'distance':
        try:
            radius = float(arg('radius_km', '50'))
            if not math.isfinite(radius) or not 1 <= radius <= 20000:
                raise ValueError()
        except ValueError:
            raise ValueError('Choose a distance between 1 and 20,000 km')

    result = []
    for original in items:
        # Distance belongs to this search origin, not the persisted listing or a
        # previous caller's result. Unknown distance stays None, never zero.
        item = dict(original)
        item['distance_km'] = None
        if lat is not None and item.get('latitude') is not None and item.get('longitude') is not None:
            item['distance_km'] = distance(lat, lon, item['latitude'], item['longitude'])
        if radius is None or (item['distance_km'] is not None and item['distance_km'] <= radius):
            result.append(item)
    return result
