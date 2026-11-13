"""ResQGrid Services Package

Exports core algorithmic engines for triage severity estimation, emergency routing,
resource allocation, and dynamic reallocation.
"""

from backend.services.allocation import (
    allocate_incident,
    find_suitable_ambulances,
    find_suitable_hospitals,
)
from backend.services.reallocation import (
    handle_ambulance_breakdown,
    handle_hospital_capacity_exhausted,
    handle_traffic_congestion_spike,
    reallocate_incident,
)
from backend.services.routing import (
    calculate_route,
    compare_routes,
    estimate_road_distance,
    estimate_travel_time,
    get_traffic_multiplier_for_route,
    haversine_distance,
)
from backend.services.severity import estimate_severity

__all__ = [
    "estimate_severity",
    "haversine_distance",
    "estimate_road_distance",
    "get_traffic_multiplier_for_route",
    "estimate_travel_time",
    "calculate_route",
    "compare_routes",
    "allocate_incident",
    "find_suitable_ambulances",
    "find_suitable_hospitals",
    "reallocate_incident",
    "handle_ambulance_breakdown",
    "handle_hospital_capacity_exhausted",
    "handle_traffic_congestion_spike",
]
