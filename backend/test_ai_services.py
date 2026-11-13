"""ResQGrid AI Engine Test Suite

Unit tests for severity assessment and routing services using Python's built-in unittest.
"""

import math
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.routing import (
    calculate_route,
    compare_routes,
    estimate_road_distance,
    estimate_travel_time,
    get_traffic_multiplier_for_route,
    haversine_distance,
    validate_coordinates,
)
from backend.services.severity import estimate_severity


class TestSeverityEngine(unittest.TestCase):
    """Test suite for the rule-based emergency severity scoring engine."""

    def test_critical_cardiac_emergency(self):
        """Test critical cardiac arrest scenario."""
        cardiac_incident = {
            "incident_type": "CARDIAC_EMERGENCY",
            "injured_people": 1,
            "affected_people": 1,
            "critical_symptoms": ["cardiac arrest", "unresponsive", "severe chest pain"],
            "environmental_danger": [],
            "description": "Elderly patient collapsed, CPR in progress.",
        }
        res = estimate_severity(cardiac_incident)

        self.assertGreaterEqual(res["severity_score"], 85.0)
        self.assertEqual(res["severity_level"], "CRITICAL")
        self.assertEqual(res["resource_requirements"]["ambulance_type"], "ALS")
        self.assertTrue(res["resource_requirements"]["icu_required"])
        self.assertGreaterEqual(res["resource_requirements"]["estimated_icu_beds"], 1)

        # Explanation audit verification
        explanation_text = " ".join(res["explanation"])
        self.assertIn("CARDIAC_EMERGENCY", explanation_text)
        self.assertIn("Critical symptoms detected", explanation_text)
        self.assertIn("Disclaimer", explanation_text)

    def test_multi_person_road_accident(self):
        """Test multi-casualty highway traffic collision."""
        accident_incident = {
            "incident_type": "ROAD_ACCIDENT",
            "injured_people": 5,
            "affected_people": 5,
            "critical_symptoms": ["polytrauma", "heavy bleeding", "fracture"],
            "environmental_danger": ["highway traffic"],
            "description": "Multi-car collision on ORR with 5 casualties trapped in vehicle.",
        }
        res = estimate_severity(accident_incident)

        self.assertGreaterEqual(res["severity_score"], 65.0)  # High or Critical
        self.assertIn(res["severity_level"], ["HIGH", "CRITICAL"])
        # Should recommend multiple ambulances for 5 injured
        self.assertGreaterEqual(res["resource_requirements"]["estimated_ambulances"], 2)
        self.assertEqual(res["resource_requirements"]["general_beds_required"], 5)
        self.assertEqual(res["resource_requirements"]["ambulance_type"], "ALS")

    def test_urban_flooding(self):
        """Test urban flooding disaster with trapped citizens."""
        flood_incident = {
            "incident_type": "URBAN_FLOODING",
            "injured_people": 4,
            "affected_people": 14,
            "critical_symptoms": ["hypothermia"],
            "environmental_danger": ["flash flood", "rising floodwater", "trapped"],
            "description": "Tenement flooding with elderly and children trapped in rising waters.",
        }
        res = estimate_severity(flood_incident)

        self.assertGreaterEqual(res["severity_score"], 65.0)
        self.assertIn(res["severity_level"], ["HIGH", "CRITICAL"])
        # Rescue units must be deployed for water trapping
        self.assertGreaterEqual(res["resource_requirements"]["rescue_units_required"], 1)
        explanation_text = " ".join(res["explanation"])
        self.assertIn("Environmental hazards detected", explanation_text)

    def test_low_severity_incident(self):
        """Test minor sprain/abrasion incident."""
        minor_incident = {
            "incident_type": "MINOR_INJURY",
            "injured_people": 1,
            "affected_people": 1,
            "critical_symptoms": ["sprain", "mild pain"],
            "environmental_danger": [],
            "description": "Twisted ankle while walking in park.",
        }
        res = estimate_severity(minor_incident)

        self.assertLess(res["severity_score"], 35.0)
        self.assertEqual(res["severity_level"], "LOW")
        self.assertFalse(res["resource_requirements"]["icu_required"])
        self.assertEqual(res["resource_requirements"]["rescue_units_required"], 0)
        self.assertEqual(res["resource_requirements"]["estimated_ambulances"], 1)

    def test_missing_and_empty_inputs(self):
        """Test that missing or unexpected inputs are safely handled."""
        # Completely empty dict
        empty_res = estimate_severity({})
        self.assertIn("severity_score", empty_res)
        self.assertIn("severity_level", empty_res)
        self.assertIn("resource_requirements", empty_res)
        self.assertIsInstance(empty_res["explanation"], list)

        # None input
        none_res = estimate_severity(None)
        self.assertIn("severity_score", none_res)
        self.assertEqual(none_res["severity_level"], "LOW")

        # Invalid types for numbers
        bad_types_res = estimate_severity({
            "injured_people": "invalid_number",
            "affected_people": None,
            "critical_symptoms": 12345,
        })
        self.assertIsInstance(bad_types_res["severity_score"], float)


class TestRoutingEngine(unittest.TestCase):
    """Test suite for coordinate math, travel times, and route rankings."""

    def setUp(self):
        # Hyderabad landmark coordinates
        self.apollo_jubilee = (17.4325, 78.4071)
        self.care_banjara = (17.4184, 78.4487)
        self.punjagutta = (17.4265, 78.4528)
        self.gachibowli = (17.4401, 78.3489)

        self.traffic_zones = [
            {"zone_name": "Punjagutta", "latitude": 17.4265, "longitude": 78.4528, "traffic_multiplier": 2.30},
            {"zone_name": "Gachibowli", "latitude": 17.4401, "longitude": 78.3489, "traffic_multiplier": 1.35},
            {"zone_name": "Dilsukhnagar", "latitude": 17.3688, "longitude": 78.5247, "traffic_multiplier": 1.10},
        ]

    def test_haversine_distance_calculation(self):
        """Verify Haversine calculations against known distances."""
        # Distance between Apollo Jubilee Hills and CARE Banjara Hills is ~4.6 to 4.8 km
        dist = haversine_distance(self.apollo_jubilee, self.care_banjara)
        self.assertGreater(dist, 4.0)
        self.assertLess(dist, 5.2)

        # Distance to itself must be zero
        zero_dist = haversine_distance(self.apollo_jubilee, self.apollo_jubilee)
        self.assertEqual(zero_dist, 0.0)

        # Symmetry: dist(A, B) == dist(B, A)
        dist_rev = haversine_distance(self.care_banjara, self.apollo_jubilee)
        self.assertAlmostEqual(dist, dist_rev, places=3)

    def test_road_distance_estimation(self):
        """Verify detour multiplier applied to straight line distance."""
        straight_km = 10.0
        road_km = estimate_road_distance(straight_km, detour_factor=1.35)
        self.assertEqual(road_km, 13.5)

        # Negative distance should raise ValueError
        with self.assertRaises(ValueError):
            estimate_road_distance(-5.0)

    def test_traffic_adjusted_travel_time(self):
        """Verify base speed vs traffic-adjusted travel time."""
        dist_km = 20.0
        base_speed = 40.0
        # Multiplier of 2.0 cuts effective speed in half (20 km/h) -> doubles travel time
        timing = estimate_travel_time(dist_km, base_speed_kmh=base_speed, traffic_multiplier=2.0)

        self.assertEqual(timing["base_duration_minutes"], 30.0)
        self.assertEqual(timing["traffic_adjusted_duration_minutes"], 60.0)
        self.assertEqual(timing["delay_minutes"], 30.0)
        self.assertEqual(timing["effective_speed_kmh"], 20.0)

    def test_traffic_multiplier_selection(self):
        """Verify traffic multiplier is selected when route intersects congested zone."""
        # Origin and destination right around congested Punjagutta (multiplier 2.30)
        near_punjagutta_origin = (17.4260, 78.4520)
        near_punjagutta_dest = (17.4270, 78.4535)

        mult = get_traffic_multiplier_for_route(
            near_punjagutta_origin, near_punjagutta_dest, self.traffic_zones
        )
        self.assertEqual(mult, 2.30)

        # Route far away in non-congested zone
        remote_origin = (17.2000, 78.2000)
        remote_dest = (17.2100, 78.2100)
        free_flow_mult = get_traffic_multiplier_for_route(
            remote_origin, remote_dest, self.traffic_zones
        )
        self.assertEqual(free_flow_mult, 1.0)

    def test_comparison_of_two_ambulance_routes(self):
        """Verify route comparison ranks the fastest traffic-adjusted resource first."""
        target_incident = (17.4200, 78.4450)  # Near Banjara Hills

        # Ambulance A: Slightly closer in straight line, but stuck inside severe Punjagutta traffic
        amb_a = {
            "id": "AMB-A",
            "name": "Ambulance A (Traversing Severe Traffic)",
            "origin": (17.4265, 78.4528),  # Right at Punjagutta (multiplier 2.30)
            "destination": target_incident,
        }

        # Ambulance B: A bit further away, but in free flow traffic
        amb_b = {
            "id": "AMB-B",
            "name": "Ambulance B (Free Flow Route)",
            "origin": (17.4000, 78.4450),  # Further south, clear corridor
            "destination": target_incident,
        }

        ranked = compare_routes([amb_a, amb_b], traffic_zones=self.traffic_zones)
        self.assertEqual(len(ranked), 2)
        # Check ranks assigned
        self.assertEqual(ranked[0]["dispatch_rank"], 1)
        self.assertEqual(ranked[1]["dispatch_rank"], 2)
        # Verify sorted ascending by traffic-adjusted time
        self.assertLessEqual(
            ranked[0]["route"]["traffic_adjusted_duration_minutes"],
            ranked[1]["route"]["traffic_adjusted_duration_minutes"],
        )

    def test_invalid_coordinates_and_inputs(self):
        """Verify boundary validations for coordinates."""
        # Latitude out of bounds
        with self.assertRaises(ValueError):
            validate_coordinates(95.0, 78.0)
        with self.assertRaises(ValueError):
            validate_coordinates(-91.0, 78.0)

        # Longitude out of bounds
        with self.assertRaises(ValueError):
            validate_coordinates(17.0, 185.0)
        with self.assertRaises(ValueError):
            validate_coordinates(17.0, -181.0)

        # Non-numeric coordinate
        with self.assertRaises(TypeError):
            validate_coordinates("invalid", 78.0)


if __name__ == "__main__":
    unittest.main()

