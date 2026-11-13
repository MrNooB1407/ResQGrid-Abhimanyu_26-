"""ResQGrid Routing and Travel-Time Estimation Engine

Provides pure-Python distance and travel time computations for emergency dispatch:
1. Haversine great-circle distance calculation.
2. Road distance estimation based on urban circuity / detour modeling.
3. Traffic-adjusted travel time modeling utilizing real-time traffic zones.
4. Multi-candidate route comparison and dispatch ranking.

Note: Great-circle distance measures straight-line geographical displacement across
the globe and is distinct from actual navigable road distance. Road distances are
estimated using calibrated urban network circuity factors.
"""

import math
from typing import Any, Dict, List, Optional, Tuple, Union

# Earth mean radius in kilometers
EARTH_RADIUS_KM = 6371.0088

# Default urban emergency navigation parameters
DEFAULT_BASE_SPEED_KMH = 40.0        # Average emergency transit speed without severe traffic
DEFAULT_DETOUR_FACTOR = 1.35          # Urban street grid tortuosity multiplier
DEFAULT_ZONE_INFLUENCE_KM = 2.5      # Spatial influence radius of traffic congestion zones


def validate_coordinates(lat: float, lon: float, label: str = "Coordinate") -> None:
    """Validate latitude and longitude ranges.
    
    Raises:
        ValueError: If lat or lon values are outside geographical boundaries.
        TypeError: If coordinates cannot be cast to floats.
    """
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (ValueError, TypeError) as e:
        raise TypeError(f"{label} values must be numbers: lat={lat}, lon={lon}") from e

    if not (-90.0 <= lat_f <= 90.0):
        raise ValueError(f"{label} latitude {lat_f} must be within [-90.0, 90.0].")
    if not (-180.0 <= lon_f <= 180.0):
        raise ValueError(f"{label} longitude {lon_f} must be within [-180.0, 180.0].")


def haversine_distance(
    coord1: Union[Tuple[float, float], List[float]],
    coord2: Union[Tuple[float, float], List[float]],
) -> float:
    """Calculate the great-circle geographical distance between two points in kilometers.

    Args:
        coord1: (latitude, longitude) of origin.
        coord2: (latitude, longitude) of destination.

    Returns:
        float: Straight-line distance in kilometers rounded to 3 decimal places.
    """
    if len(coord1) != 2 or len(coord2) != 2:
        raise ValueError("Coordinates must be 2-element tuples or lists (latitude, longitude).")

    lat1, lon1 = float(coord1[0]), float(coord1[1])
    lat2, lon2 = float(coord2[0]), float(coord2[1])

    validate_coordinates(lat1, lon1, "Origin")
    validate_coordinates(lat2, lon2, "Destination")

    # Identical coordinates check
    if lat1 == lat2 and lon1 == lon2:
        return 0.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    # Clamp to avoid numerical floating-point inaccuracies
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return round(EARTH_RADIUS_KM * c, 3)


def estimate_road_distance(
    straight_line_km: float,
    detour_factor: float = DEFAULT_DETOUR_FACTOR,
) -> float:
    """Estimate actual driving road distance from straight-line geographical distance.

    Args:
        straight_line_km: Great-circle distance in kilometers.
        detour_factor: Grid tortuosity multiplier (typical urban index: 1.25–1.45).

    Returns:
        float: Estimated road distance in kilometers.
    """
    if straight_line_km < 0:
        raise ValueError("Distance cannot be negative.")
    if detour_factor < 1.0:
        raise ValueError("Detour factor cannot be less than 1.0 (straight-line shortest path).")
    return round(straight_line_km * detour_factor, 3)


def get_traffic_multiplier_for_route(
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    traffic_zones: Optional[List[Dict[str, Any]]] = None,
    zone_influence_km: float = DEFAULT_ZONE_INFLUENCE_KM,
) -> float:
    """Select the governing traffic multiplier along a route corridor.

    Samples points along the straight corridor between origin and destination,
    checks proximity to provided traffic congestion zones, and extracts the maximum
    multiplier encountered.

    Args:
        origin: (lat, lon)
        destination: (lat, lon)
        traffic_zones: List of traffic zone dicts with lat, lon, traffic_multiplier
        zone_influence_km: Radius in kilometers within which a traffic zone impacts the route.

    Returns:
        float: Traffic slowdown multiplier (>= 1.0).
    """
    if not traffic_zones:
        return 1.0

    # Sample points along the trajectory: 0%, 25%, 50%, 75%, 100%
    lat1, lon1 = origin[0], origin[1]
    lat2, lon2 = destination[0], destination[1]

    sample_ratios = [0.0, 0.25, 0.5, 0.75, 1.0]
    sample_points = [
        (lat1 + r * (lat2 - lat1), lon1 + r * (lon2 - lon1)) for r in sample_ratios
    ]

    max_multiplier = 1.0
    for zone in traffic_zones:
        try:
            z_lat = float(zone["latitude"])
            z_lon = float(zone["longitude"])
            z_mult = float(zone.get("traffic_multiplier", 1.0))
        except (KeyError, ValueError, TypeError):
            continue

        # Check if any sampled route point falls within the zone's influence radius
        for pt in sample_points:
            dist = haversine_distance(pt, (z_lat, z_lon))
            if dist <= zone_influence_km:
                if z_mult > max_multiplier:
                    max_multiplier = z_mult
                break

    return round(max_multiplier, 2)


def estimate_travel_time(
    road_distance_km: float,
    base_speed_kmh: float = DEFAULT_BASE_SPEED_KMH,
    traffic_multiplier: float = 1.0,
) -> Dict[str, float]:
    """Calculate baseline and traffic-adjusted emergency transit times.

    Args:
        road_distance_km: Driving road distance in km.
        base_speed_kmh: Free-flow cruising speed in km/h.
        traffic_multiplier: Slowdown factor (>= 1.0).

    Returns:
        Dict containing durations in minutes, speeds, and traffic delay.
    """
    if road_distance_km < 0:
        raise ValueError("Road distance cannot be negative.")
    if base_speed_kmh <= 0:
        raise ValueError("Base speed must be greater than zero.")
    if traffic_multiplier < 1.0:
        traffic_multiplier = 1.0

    # Effective transit speed with traffic congestion
    effective_speed = max(6.0, base_speed_kmh / traffic_multiplier)

    base_minutes = (road_distance_km / base_speed_kmh) * 60.0
    adjusted_minutes = (road_distance_km / effective_speed) * 60.0
    delay_minutes = max(0.0, adjusted_minutes - base_minutes)

    return {
        "road_distance_km": round(road_distance_km, 2),
        "base_speed_kmh": round(base_speed_kmh, 1),
        "effective_speed_kmh": round(effective_speed, 1),
        "traffic_multiplier": round(traffic_multiplier, 2),
        "base_duration_minutes": round(base_minutes, 1),
        "traffic_adjusted_duration_minutes": round(adjusted_minutes, 1),
        "delay_minutes": round(delay_minutes, 1),
    }


def calculate_route(
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    traffic_zones: Optional[List[Dict[str, Any]]] = None,
    base_speed_kmh: float = DEFAULT_BASE_SPEED_KMH,
    detour_factor: float = DEFAULT_DETOUR_FACTOR,
) -> Dict[str, Any]:
    """Compute a complete route summary including straight-line, road, and travel time.

    Clearly distinguishes straight-line displacement from road distance.
    """
    straight_km = haversine_distance(origin, destination)
    road_km = estimate_road_distance(straight_km, detour_factor=detour_factor)
    multiplier = get_traffic_multiplier_for_route(origin, destination, traffic_zones)
    timing = estimate_travel_time(road_km, base_speed_kmh=base_speed_kmh, traffic_multiplier=multiplier)

    return {
        "origin": origin,
        "destination": destination,
        "straight_line_distance_km": straight_km,
        "estimated_road_distance_km": road_km,
        "detour_factor": detour_factor,
        "traffic_multiplier": multiplier,
        "base_duration_minutes": timing["base_duration_minutes"],
        "traffic_adjusted_duration_minutes": timing["traffic_adjusted_duration_minutes"],
        "delay_minutes": timing["delay_minutes"],
        "effective_speed_kmh": timing["effective_speed_kmh"],
        "notes": (
            "Straight-line distance is computed via great-circle Haversine formula. "
            "Road distance and travel times are simulated estimates based on urban grid circuity "
            "and traffic zone multipliers, not turn-by-turn navigation telemetry."
        ),
    }


def compare_routes(
    candidates: List[Dict[str, Any]],
    traffic_zones: Optional[List[Dict[str, Any]]] = None,
    base_speed_kmh: float = DEFAULT_BASE_SPEED_KMH,
    detour_factor: float = DEFAULT_DETOUR_FACTOR,
) -> List[Dict[str, Any]]:
    """Compare multiple resource routes and rank candidates by traffic-adjusted arrival time.

    Each candidate in candidates must supply:
    - 'id': identifier
    - 'name': display label
    - 'origin': (latitude, longitude)
    - 'destination': (latitude, longitude)
    Optional metadata in each candidate will be preserved in the output.

    Returns:
        List[Dict[str, Any]]: Candidates sorted ascending by traffic_adjusted_duration_minutes.
    """
    evaluated = []
    for cand in candidates:
        orig = cand["origin"]
        dest = cand["destination"]
        route_info = calculate_route(
            origin=orig,
            destination=dest,
            traffic_zones=traffic_zones,
            base_speed_kmh=base_speed_kmh,
            detour_factor=detour_factor,
        )
        combined = {**cand, "route": route_info}
        evaluated.append(combined)

    # Sort ascending: lowest traffic_adjusted_duration_minutes ranks first
    evaluated.sort(
        key=lambda item: item["route"]["traffic_adjusted_duration_minutes"]
    )

    # Assign rank
    for rank, item in enumerate(evaluated, start=1):
        item["dispatch_rank"] = rank

    return evaluated

