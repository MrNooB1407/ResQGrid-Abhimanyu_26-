"""ResQGrid Flask API & Health Check Test Suite

Verifies application factory initialization, CORS policies, centralized error handlers,
health diagnostics, Resource Read APIs (Incidents, Ambulances, Hospitals),
and Incident Lifecycle Mutation APIs (Creation & Status Transition Safety)
using an isolated temporary SQLite database.
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure project root is present in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import DEFAULT_DB_PATH, get_db, init_db, query_db
from backend.main import create_app


class TestHealthAndAppFactory(unittest.TestCase):
    """Test suite for application factory, health endpoint, and CORS policies."""

    @classmethod
    def setUpClass(cls):
        """Set up an isolated temporary database for test suite execution."""
        cls.test_dir = tempfile.mkdtemp(prefix="resqgrid_api_test_")
        cls.temp_db_path = Path(cls.test_dir) / "test_api_resqgrid.db"
        # Initialize schema and benchmark seeds in the isolated temporary database
        init_db(db_path=cls.temp_db_path, seed_if_empty=True)

    @classmethod
    def tearDownClass(cls):
        """Clean up temporary test directory."""
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        """Create a new Flask test client bound to the isolated temporary database."""
        self.app = create_app(test_config={
            "DATABASE": str(self.temp_db_path),
            "TESTING": True,
        })
        self.client = self.app.test_client()

    def test_01_app_factory_initialization(self):
        """1. Verify application factory initializes successfully with custom config."""
        self.assertIsNotNone(self.app)
        self.assertTrue(self.app.config["TESTING"])
        self.assertEqual(self.app.config["DATABASE"], str(self.temp_db_path))

    def test_02_health_endpoint_success(self):
        """2. Verify GET /api/health returns HTTP 200 when database is healthy."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json")

    def test_03_health_response_structure(self):
        """3. Verify health response contains expected diagnostic JSON keys and metadata."""
        response = self.client.get("/api/health")
        data = response.get_json()

        self.assertIsInstance(data, dict)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("status"), "HEALTHY")
        self.assertIn("ResQGrid", data.get("application", ""))

        db_info = data.get("database", {})
        self.assertTrue(db_info.get("connected"))
        self.assertEqual(db_info.get("status"), "CONNECTED")

        details = db_info.get("details", {})
        self.assertGreaterEqual(details.get("tables_count", 0), 6)
        tables = details.get("tables", [])
        for required_table in ("incidents", "ambulances", "hospitals", "allocations", "traffic_zones"):
            self.assertIn(required_table, tables)

    def test_04_health_endpoint_missing_database(self):
        """4. Verify health endpoint detects a missing database and returns HTTP 503."""
        nonexistent_db = Path(self.test_dir) / "nonexistent_absent.db"
        if nonexistent_db.exists():
            nonexistent_db.unlink()

        failing_app = create_app(test_config={
            "DATABASE": str(nonexistent_db),
            "TESTING": True,
        })
        failing_client = failing_app.test_client()

        response = failing_client.get("/api/health")
        self.assertEqual(response.status_code, 503)

        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("status"), "UNHEALTHY")
        self.assertFalse(data["database"]["connected"])
        self.assertEqual(data["database"]["status"], "UNAVAILABLE")

    def test_05_cors_headers_permit_vite_origin(self):
        """5. Verify CORS headers allow the Vite frontend origin (http://localhost:5173)."""
        response = self.client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("Access-Control-Allow-Origin"),
            "http://localhost:5173",
        )

        options_response = self.client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type,Authorization",
            },
        )
        self.assertEqual(options_response.status_code, 200)
        self.assertEqual(
            options_response.headers.get("Access-Control-Allow-Origin"),
            "http://localhost:5173",
        )
        allowed_methods = options_response.headers.get("Access-Control-Allow-Methods", "")
        for method in ("GET", "POST", "PATCH", "OPTIONS"):
            self.assertIn(method, allowed_methods)

    def test_06_nonexistent_route_returns_json_404(self):
        """6. Verify nonexistent routes return a structured JSON 404 error without HTML leak."""
        response = self.client.get("/api/nonexistent_route_endpoint")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content_type, "application/json")

        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], 404)
        self.assertEqual(data["error"]["name"], "Not Found")
        self.assertIn("message", data["error"])


class TestResourceReadAPIs(unittest.TestCase):
    """Test suite for Resource Read endpoints (Incidents, Ambulances, Hospitals)."""

    @classmethod
    def setUpClass(cls):
        """Set up an isolated temporary database with seeded benchmark records."""
        cls.test_dir = tempfile.mkdtemp(prefix="resqgrid_resource_test_")
        cls.temp_db_path = Path(cls.test_dir) / "test_resources.db"
        init_db(db_path=cls.temp_db_path, seed_if_empty=True)

    @classmethod
    def tearDownClass(cls):
        """Clean up temporary test directory."""
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        """Initialize Flask test client bound to the seeded test database."""
        self.app = create_app(test_config={
            "DATABASE": str(self.temp_db_path),
            "TESTING": True,
        })
        self.client = self.app.test_client()

    # -----------------------------------------------------------------------
    # Incidents Read API Tests
    # -----------------------------------------------------------------------
    def test_10_get_incidents_collection(self):
        """10. Verify GET /api/incidents returns all seeded incidents (count=3)."""
        res = self.client.get("/api/incidents")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("count"), 3)
        self.assertEqual(len(data.get("data")), 3)

        first = data["data"][0]
        for field in ("id", "title", "incident_type", "severity_score", "severity_level", "status"):
            self.assertIn(field, first)

    def test_11_get_incident_by_id(self):
        """11. Verify GET /api/incidents/<id> returns single incident details."""
        res = self.client.get("/api/incidents/1")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertTrue(data.get("success"))
        inc = data.get("data")
        self.assertEqual(inc["id"], 1)
        self.assertIn("Gachibowli", inc["title"])
        self.assertEqual(inc["severity_level"], "CRITICAL")
        self.assertIn("current_allocation", inc)

    def test_12_get_incident_not_found(self):
        """12. Verify GET /api/incidents/<id> returns 404 for nonexistent ID."""
        res = self.client.get("/api/incidents/999")
        self.assertEqual(res.status_code, 404)
        data = res.get_json()

        self.assertFalse(data.get("success"))
        self.assertEqual(data["error"]["code"], 404)
        self.assertIn("999", data["error"]["message"])

    def test_13_filter_incidents_by_status(self):
        """13. Verify filtering incidents by status query parameter."""
        res_rep = self.client.get("/api/incidents?status=REPORTED")
        self.assertEqual(res_rep.status_code, 200)
        data_rep = res_rep.get_json()
        self.assertEqual(data_rep["count"], 3)

        res_res = self.client.get("/api/incidents?status=RESOLVED")
        self.assertEqual(res_res.status_code, 200)
        data_res = res_res.get_json()
        self.assertEqual(data_res["count"], 0)
        self.assertEqual(data_res["data"], [])

    def test_14_filter_incidents_by_severity(self):
        """14. Verify filtering incidents by severity_level."""
        res_crit = self.client.get("/api/incidents?severity=CRITICAL")
        self.assertEqual(res_crit.status_code, 200)
        self.assertEqual(res_crit.get_json()["count"], 2)

        res_high = self.client.get("/api/incidents?severity=HIGH")
        self.assertEqual(res_high.status_code, 200)
        self.assertEqual(res_high.get_json()["count"], 1)

        res_low = self.client.get("/api/incidents?severity=LOW")
        self.assertEqual(res_low.status_code, 200)
        self.assertEqual(res_low.get_json()["count"], 0)

    # -----------------------------------------------------------------------
    # Ambulances Read API Tests
    # -----------------------------------------------------------------------
    def test_20_get_ambulances_collection(self):
        """20. Verify GET /api/ambulances returns all 8 seeded units."""
        res = self.client.get("/api/ambulances")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("count"), 8)
        self.assertEqual(len(data.get("data")), 8)

        amb1 = data["data"][0]
        for field in ("id", "ambulance_number", "latitude", "longitude", "status", "capability"):
            self.assertIn(field, amb1)

    def test_21_get_ambulance_by_id(self):
        """21. Verify GET /api/ambulances/<id> returns single ambulance details."""
        res = self.client.get("/api/ambulances/1")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertTrue(data.get("success"))
        amb = data.get("data")
        self.assertEqual(amb["id"], 1)
        self.assertEqual(amb["ambulance_number"], "AMB-HYD-01")
        self.assertEqual(amb["capability"], "ALS")
        self.assertEqual(amb["status"], "AVAILABLE")
        self.assertIn("current_allocation", amb)

    def test_22_get_ambulance_not_found(self):
        """22. Verify GET /api/ambulances/<id> returns 404 for nonexistent ID."""
        res = self.client.get("/api/ambulances/999")
        self.assertEqual(res.status_code, 404)
        data = res.get_json()

        self.assertFalse(data.get("success"))
        self.assertEqual(data["error"]["code"], 404)
        self.assertIn("999", data["error"]["message"])

    def test_23_filter_ambulances_by_capability(self):
        """23. Verify filtering ambulances by capability (ALS: 4, BLS: 3, PT: 1)."""
        res_als = self.client.get("/api/ambulances?capability=ALS")
        self.assertEqual(res_als.status_code, 200)
        self.assertEqual(res_als.get_json()["count"], 4)

        res_bls = self.client.get("/api/ambulances?capability=BLS")
        self.assertEqual(res_bls.status_code, 200)
        self.assertEqual(res_bls.get_json()["count"], 3)

        res_pt = self.client.get("/api/ambulances?capability=PATIENT_TRANSPORT")
        self.assertEqual(res_pt.status_code, 200)
        self.assertEqual(res_pt.get_json()["count"], 1)

    def test_24_filter_ambulances_by_status(self):
        """24. Verify filtering ambulances by operational status."""
        res_avail = self.client.get("/api/ambulances?status=AVAILABLE")
        self.assertEqual(res_avail.status_code, 200)
        self.assertEqual(res_avail.get_json()["count"], 8)

        res_oos = self.client.get("/api/ambulances?status=OUT_OF_SERVICE")
        self.assertEqual(res_oos.status_code, 200)
        self.assertEqual(res_oos.get_json()["count"], 0)

    # -----------------------------------------------------------------------
    # Hospitals Read API Tests
    # -----------------------------------------------------------------------
    def test_30_get_hospitals_collection(self):
        """30. Verify GET /api/hospitals returns all 5 seeded trauma centers."""
        res = self.client.get("/api/hospitals")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("count"), 5)
        self.assertEqual(len(data.get("data")), 5)

        hosp1 = data["data"][0]
        for field in ("id", "name", "total_beds", "available_beds", "total_icu_beds", "available_icu_beds", "occupancy_percentage"):
            self.assertIn(field, hosp1)

    def test_31_get_hospital_by_id(self):
        """31. Verify GET /api/hospitals/<id> returns single hospital with capacity details."""
        res = self.client.get("/api/hospitals/1")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertTrue(data.get("success"))
        hosp = data.get("data")
        self.assertEqual(hosp["id"], 1)
        self.assertIn("Apollo", hosp["name"])
        self.assertEqual(hosp["total_beds"], 350)
        self.assertEqual(hosp["available_beds"], 42)
        self.assertIn("incoming_transports", hosp)
        self.assertIsInstance(hosp["incoming_transports"], list)

    def test_32_get_hospital_not_found(self):
        """32. Verify GET /api/hospitals/<id> returns 404 for nonexistent ID."""
        res = self.client.get("/api/hospitals/999")
        self.assertEqual(res.status_code, 404)
        data = res.get_json()

        self.assertFalse(data.get("success"))
        self.assertEqual(data["error"]["code"], 404)
        self.assertIn("999", data["error"]["message"])

    def test_33_search_hospitals_by_name(self):
        """33. Verify hospital search by substring (case-insensitive)."""
        res_apollo = self.client.get("/api/hospitals?name=apollo")
        self.assertEqual(res_apollo.status_code, 200)
        data_apollo = res_apollo.get_json()
        self.assertEqual(data_apollo["count"], 1)
        self.assertIn("Apollo", data_apollo["data"][0]["name"])

        res_sec = self.client.get("/api/hospitals?name=secunderabad")
        self.assertEqual(res_sec.status_code, 200)
        data_sec = res_sec.get_json()
        self.assertEqual(data_sec["count"], 1)
        self.assertIn("KIMS", data_sec["data"][0]["name"])

        res_none = self.client.get("/api/hospitals?name=NonExistentClinicXYZ")
        self.assertEqual(res_none.status_code, 200)
        self.assertEqual(res_none.get_json()["count"], 0)
        self.assertEqual(res_none.get_json()["data"], [])

    # -----------------------------------------------------------------------
    # Active Allocation Read Enrichment Test
    # -----------------------------------------------------------------------
    def test_40_active_allocation_enrichment(self):
        """40. Verify active allocation data appears in incident, ambulance, and hospital responses."""
        with get_db(self.temp_db_path) as conn:
            conn.execute(
                """
                INSERT INTO allocations (
                    incident_id, ambulance_id, hospital_id, estimated_arrival_minutes,
                    allocation_status, decision_reason
                ) VALUES (1, 1, 1, 5.5, 'ACTIVE', 'Primary test dispatch');
                """
            )
            conn.execute("UPDATE ambulances SET status = 'DISPATCHED', assigned_incident_id = 1 WHERE id = 1;")
            conn.execute("UPDATE incidents SET status = 'ASSIGNED' WHERE id = 1;")

        # A. Check Incident #1 has active allocation enriched
        res_inc = self.client.get("/api/incidents/1")
        self.assertEqual(res_inc.status_code, 200)
        inc_data = res_inc.get_json()["data"]
        self.assertIsNotNone(inc_data["current_allocation"])
        self.assertEqual(inc_data["current_allocation"]["ambulance_number"], "AMB-HYD-01")
        self.assertEqual(inc_data["current_allocation"]["estimated_arrival_minutes"], 5.5)

        # B. Check Ambulance #1 has active allocation enriched
        res_amb = self.client.get("/api/ambulances/1")
        self.assertEqual(res_amb.status_code, 200)
        amb_data = res_amb.get_json()["data"]
        self.assertEqual(amb_data["status"], "DISPATCHED")
        self.assertIsNotNone(amb_data["current_allocation"])
        self.assertEqual(amb_data["current_allocation"]["incident_id"], 1)

        # C. Check Hospital #1 shows active incoming transport
        res_hosp = self.client.get("/api/hospitals/1")
        self.assertEqual(res_hosp.status_code, 200)
        hosp_data = res_hosp.get_json()["data"]
        self.assertEqual(hosp_data["active_incoming_transports_count"], 1)
        self.assertEqual(len(hosp_data["incoming_transports"]), 1)
        self.assertEqual(hosp_data["incoming_transports"][0]["ambulance_number"], "AMB-HYD-01")


class TestIncidentMutations(unittest.TestCase):
    """Test suite for POST /api/incidents and PATCH /api/incidents/<id>/status."""

    @classmethod
    def setUpClass(cls):
        """Set up an isolated temporary database for mutation tests."""
        cls.test_dir = tempfile.mkdtemp(prefix="resqgrid_mutation_test_")
        cls.temp_db_path = Path(cls.test_dir) / "test_mutations.db"
        init_db(db_path=cls.temp_db_path, seed_if_empty=True)

    @classmethod
    def tearDownClass(cls):
        """Clean up temporary test directory."""
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        """Reset test database to pristine seed state before each test for complete isolation."""
        if self.temp_db_path.exists():
            try:
                self.temp_db_path.unlink()
            except Exception:
                pass
        init_db(db_path=self.temp_db_path, seed_if_empty=True)

        self.app = create_app(test_config={
            "DATABASE": str(self.temp_db_path),
            "TESTING": True,
        })
        self.client = self.app.test_client()

    # -----------------------------------------------------------------------
    # POST /api/incidents Tests
    # -----------------------------------------------------------------------
    def test_50_create_incident_success_with_auto_triage(self):
        """50. Verify successful incident creation with automated severity triage and event log."""
        payload = {
            "title": "Severe Cardiac Arrest at Jubilee Hills Residence",
            "incident_type": "CARDIAC_EMERGENCY",
            "description": "68-year-old patient collapsed at residence, unconscious and unresponsive.",
            "latitude": 17.4325,
            "longitude": 78.4071,
            "injured_people": 1,
            "affected_people": 1,
            "critical_symptoms": ["cardiac arrest", "unresponsive"],
            "environmental_danger": [],
        }

        res = self.client.post(
            "/api/incidents",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()

        self.assertTrue(data.get("success"))
        self.assertIn("created and triaged successfully", data.get("message", ""))

        incident = data.get("data")
        new_id = incident["id"]
        self.assertGreater(new_id, 3)  # Greater than seeded 3
        self.assertEqual(incident["title"], payload["title"])
        self.assertEqual(incident["incident_type"], "CARDIAC_EMERGENCY")
        self.assertEqual(incident["status"], "REPORTED")

        # Verify automated triage calculation
        self.assertGreaterEqual(incident["severity_score"], 85.0)
        self.assertEqual(incident["severity_level"], "CRITICAL")

        # Verify assessment details
        assessment = incident["severity_assessment"]
        self.assertEqual(assessment["severity_level"], "CRITICAL")
        self.assertEqual(assessment["resource_requirements"]["ambulance_type"], "ALS")
        self.assertTrue(assessment["resource_requirements"]["icu_required"])
        self.assertGreater(len(assessment["explanation"]), 0)

        # Verify SQLite event log record
        with get_db(self.temp_db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM event_logs WHERE related_incident_id = ? AND event_type = 'INCIDENT_REPORTED';",
                (new_id,),
            )
            logs = cur.fetchall()
            self.assertEqual(len(logs), 1)
            self.assertIn("CRITICAL", logs[0]["description"])

    def test_51_create_incident_validation_missing_fields(self):
        """51. Verify 400 Bad Request when required fields are missing."""
        # A. Missing title
        res = self.client.post("/api/incidents", json={
            "incident_type": "FIRE",
            "latitude": 17.41,
            "longitude": 78.42,
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("title", res.get_json()["error"]["message"])

        # B. Empty string title
        res = self.client.post("/api/incidents", json={
            "title": "   ",
            "incident_type": "FIRE",
            "latitude": 17.41,
            "longitude": 78.42,
        })
        self.assertEqual(res.status_code, 400)

        # C. Missing incident_type
        res = self.client.post("/api/incidents", json={
            "title": "Apartment Blaze",
            "latitude": 17.41,
            "longitude": 78.42,
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("incident_type", res.get_json()["error"]["message"])

        # D. Missing coordinates
        res = self.client.post("/api/incidents", json={
            "title": "Apartment Blaze",
            "incident_type": "FIRE",
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("coordinates", res.get_json()["error"]["message"])

    def test_52_create_incident_validation_invalid_coordinates(self):
        """52. Verify 400 Bad Request on out-of-bounds or non-numeric coordinates."""
        base_payload = {
            "title": "Collision",
            "incident_type": "ROAD_ACCIDENT",
        }

        # Latitude > 90
        res = self.client.post("/api/incidents", json={**base_payload, "latitude": 95.5, "longitude": 78.4})
        self.assertEqual(res.status_code, 400)
        self.assertIn("Latitude", res.get_json()["error"]["message"])

        # Longitude < -180
        res = self.client.post("/api/incidents", json={**base_payload, "latitude": 17.4, "longitude": -190.0})
        self.assertEqual(res.status_code, 400)
        self.assertIn("Longitude", res.get_json()["error"]["message"])

        # Non-numeric string coordinate
        res = self.client.post("/api/incidents", json={**base_payload, "latitude": "invalid_lat", "longitude": 78.4})
        self.assertEqual(res.status_code, 400)

        # Boolean coordinate (rejected)
        res = self.client.post("/api/incidents", json={**base_payload, "latitude": True, "longitude": 78.4})
        self.assertEqual(res.status_code, 400)

    def test_53_create_incident_validation_invalid_data_types(self):
        """53. Verify 400 Bad Request on negative casualties and non-dict payload."""
        base_payload = {
            "title": "Factory Mishap",
            "incident_type": "INDUSTRIAL_HAZARD",
            "latitude": 17.44,
            "longitude": 78.36,
        }

        # Negative injured
        res = self.client.post("/api/incidents", json={**base_payload, "injured_people": -3})
        self.assertEqual(res.status_code, 400)
        self.assertIn("negative", res.get_json()["error"]["message"])

        # Negative affected
        res = self.client.post("/api/incidents", json={**base_payload, "affected_people": -1})
        self.assertEqual(res.status_code, 400)

        # Boolean for injured (rejected)
        res = self.client.post("/api/incidents", json={**base_payload, "injured_people": False})
        self.assertEqual(res.status_code, 400)

        # Non-dict JSON payload
        res = self.client.post("/api/incidents", data=json.dumps(["not", "a", "dict"]), content_type="application/json")
        self.assertEqual(res.status_code, 400)

    # -----------------------------------------------------------------------
    # PATCH /api/incidents/<id>/status Tests
    # -----------------------------------------------------------------------
    def test_54_patch_status_nonexistent_incident(self):
        """54. Verify PATCH /api/incidents/<id>/status returns 404 for missing incident."""
        res = self.client.patch("/api/incidents/999/status", json={"status": "CANCELLED"})
        self.assertEqual(res.status_code, 404)
        self.assertFalse(res.get_json()["success"])

    def test_55_patch_status_invalid_value(self):
        """55. Verify PATCH /api/incidents/<id>/status returns 400 on invalid status strings."""
        # Unrecognized status
        res = self.client.patch("/api/incidents/2/status", json={"status": "EXPLODED"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("Allowed statuses", res.get_json()["error"]["message"])

        # Missing status field
        res = self.client.patch("/api/incidents/2/status", json={"wrong_key": "CANCELLED"})
        self.assertEqual(res.status_code, 400)

        # Empty status
        res = self.client.patch("/api/incidents/2/status", json={"status": "  "})
        self.assertEqual(res.status_code, 400)

    def test_56_patch_status_valid_transition(self):
        """56. Verify valid transition (REPORTED -> CANCELLED) with event logging."""
        # Create fresh incident
        create_res = self.client.post("/api/incidents", json={
            "title": "False Alarm Smell of Smoke",
            "incident_type": "FIRE",
            "latitude": 17.41,
            "longitude": 78.43,
        })
        inc_id = create_res.get_json()["data"]["id"]

        # Transition to CANCELLED
        res = self.client.patch(f"/api/incidents/{inc_id}/status", json={"status": "CANCELLED"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertTrue(data.get("success"))
        self.assertEqual(data["data"]["status"], "CANCELLED")

        # Verify DB updated
        with get_db(self.temp_db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT status FROM incidents WHERE id = ?;", (inc_id,))
            self.assertEqual(cur.fetchone()["status"], "CANCELLED")

            # Verify event log entry
            cur.execute(
                "SELECT * FROM event_logs WHERE related_incident_id = ? AND event_type = 'INCIDENT_STATUS_UPDATED';",
                (inc_id,),
            )
            logs = cur.fetchall()
            self.assertEqual(len(logs), 1)
            self.assertIn("CANCELLED", logs[0]["description"])

    def test_57_patch_status_invalid_transition(self):
        """57. Verify 409 Conflict when attempting invalid lifecycle transition (REPORTED -> IN_TRANSIT)."""
        create_res = self.client.post("/api/incidents", json={
            "title": "Unassigned Trauma Case",
            "incident_type": "ROAD_ACCIDENT",
            "latitude": 17.42,
            "longitude": 78.45,
        })
        inc_id = create_res.get_json()["data"]["id"]

        # Transition directly from REPORTED to IN_TRANSIT without assignment
        res = self.client.patch(f"/api/incidents/{inc_id}/status", json={"status": "IN_TRANSIT"})
        self.assertEqual(res.status_code, 409)
        self.assertIn("Invalid lifecycle transition", res.get_json()["error"]["message"])

    def test_58_patch_status_terminal_state_protection(self):
        """58. Verify 409 Conflict when attempting to mutate an incident in a terminal state."""
        create_res = self.client.post("/api/incidents", json={
            "title": "Aborted Call",
            "incident_type": "NON_CRITICAL",
            "latitude": 17.41,
            "longitude": 78.41,
        })
        inc_id = create_res.get_json()["data"]["id"]

        # Cancel it
        self.client.patch(f"/api/incidents/{inc_id}/status", json={"status": "CANCELLED"})

        # Try to reopen or transition
        res_reopen = self.client.patch(f"/api/incidents/{inc_id}/status", json={"status": "REPORTED"})
        self.assertEqual(res_reopen.status_code, 409)
        self.assertIn("terminal state", res_reopen.get_json()["error"]["message"])

    def test_59_patch_status_active_allocation_protection(self):
        """59. Verify 409 Conflict when resolving or cancelling an incident with an active allocation."""
        # Create an incident and assign an active allocation to it
        create_res = self.client.post("/api/incidents", json={
            "title": "Active Transport Emergency",
            "incident_type": "ROAD_ACCIDENT",
            "latitude": 17.43,
            "longitude": 78.46,
        })
        inc_id = create_res.get_json()["data"]["id"]

        with get_db(self.temp_db_path) as conn:
            conn.execute(
                """
                INSERT INTO allocations (
                    incident_id, ambulance_id, hospital_id, estimated_arrival_minutes,
                    allocation_status, decision_reason
                ) VALUES (?, 2, 2, 7.0, 'ACTIVE', 'Active unit in field');
                """,
                (inc_id,),
            )
            conn.execute("UPDATE incidents SET status = 'ASSIGNED' WHERE id = ?;", (inc_id,))

        # A. Attempting to RESOLVE while allocation is ACTIVE -> 409 Conflict
        res_resolve = self.client.patch(f"/api/incidents/{inc_id}/status", json={"status": "RESOLVED"})
        self.assertEqual(res_resolve.status_code, 409)
        self.assertIn("active resource allocation", res_resolve.get_json()["error"]["message"])

        # B. Attempting to CANCEL while allocation is ACTIVE -> 409 Conflict
        res_cancel = self.client.patch(f"/api/incidents/{inc_id}/status", json={"status": "CANCELLED"})
        self.assertEqual(res_cancel.status_code, 409)
        self.assertIn("active resource allocation", res_cancel.get_json()["error"]["message"])

        # C. Transition to IN_TRANSIT during active dispatch -> 200 OK
        res_transit = self.client.patch(f"/api/incidents/{inc_id}/status", json={"status": "IN_TRANSIT"})
        self.assertEqual(res_transit.status_code, 200)
        self.assertEqual(res_transit.get_json()["data"]["status"], "IN_TRANSIT")

    def test_60_production_database_untouched(self):
        """60. Verify the production SQLite database was not touched or modified during tests."""
        prod_incidents = query_db("SELECT COUNT(*) AS c FROM incidents;", db_path=DEFAULT_DB_PATH, one=True)["c"]
        prod_ambulances = query_db("SELECT COUNT(*) AS c FROM ambulances;", db_path=DEFAULT_DB_PATH, one=True)["c"]
        prod_hospitals = query_db("SELECT COUNT(*) AS c FROM hospitals;", db_path=DEFAULT_DB_PATH, one=True)["c"]

        self.assertEqual(prod_incidents, 3)
        self.assertEqual(prod_ambulances, 8)
        self.assertEqual(prod_hospitals, 5)


class TestAllocationAndReallocationAPIs(unittest.TestCase):
    """Test suite for Step 6.5: POST /api/allocations/<id> and dynamic reallocation endpoints."""

    @classmethod
    def setUpClass(cls):
        """Set up an isolated temporary database for allocation and reallocation tests."""
        cls.test_dir = tempfile.mkdtemp(prefix="resqgrid_alloc_api_test_")
        cls.temp_db_path = Path(cls.test_dir) / "test_alloc_api.db"
        init_db(db_path=cls.temp_db_path, seed_if_empty=True)

    @classmethod
    def tearDownClass(cls):
        """Clean up temporary test directory."""
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        """Reset test database to pristine seed state before each test for complete isolation."""
        if self.temp_db_path.exists():
            try:
                self.temp_db_path.unlink()
            except Exception:
                pass
        init_db(db_path=self.temp_db_path, seed_if_empty=True)

        self.app = create_app(test_config={
            "DATABASE": str(self.temp_db_path),
            "TESTING": True,
        })
        self.client = self.app.test_client()

    # -----------------------------------------------------------------------
    # Task 1: POST /api/allocations/<int:incident_id> Tests
    # -----------------------------------------------------------------------
    def test_70_allocation_success(self):
        """70. Verify successful atomic resource allocation returns 201 with full details and event log."""
        inc_res = self.client.post("/api/incidents", json={
            "title": "Severe Highway Pileup near Hitec City",
            "incident_type": "ROAD_ACCIDENT",
            "latitude": 17.4450,
            "longitude": 78.3800,
            "injured_people": 2,
            "affected_people": 3,
        })
        self.assertEqual(inc_res.status_code, 201)
        inc_id = inc_res.get_json()["data"]["id"]

        alloc_res = self.client.post(f"/api/allocations/{inc_id}")
        self.assertEqual(alloc_res.status_code, 201)
        data = alloc_res.get_json()

        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("incident_id"), inc_id)
        self.assertIsNotNone(data.get("allocation_id"))
        self.assertIsNotNone(data.get("ambulance"))
        self.assertIsNotNone(data.get("hospital"))
        self.assertGreater(data.get("estimated_arrival_minutes"), 0)
        self.assertIn(data.get("fulfillment_status"), ("FULFILLED", "PARTIAL"))
        self.assertIsNotNone(data.get("decision_reason"))

        # Verify SQLite state
        with get_db(self.temp_db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT status FROM incidents WHERE id = ?;", (inc_id,))
            self.assertEqual(cur.fetchone()["status"], "ASSIGNED")

            cur.execute("SELECT allocation_status FROM allocations WHERE id = ?;", (data["allocation_id"],))
            self.assertEqual(cur.fetchone()["allocation_status"], "ACTIVE")

            cur.execute("SELECT status FROM ambulances WHERE id = ?;", (data["ambulance"]["id"],))
            self.assertEqual(cur.fetchone()["status"], "DISPATCHED")

            cur.execute("SELECT * FROM event_logs WHERE related_incident_id = ? AND event_type = 'RESOURCE_ALLOCATED';", (inc_id,))
            logs = cur.fetchall()
            self.assertEqual(len(logs), 1)

    def test_71_allocation_nonexistent_incident(self):
        """71. Verify allocating a nonexistent incident returns 404 Not Found."""
        res = self.client.post("/api/allocations/99999")
        self.assertEqual(res.status_code, 404)
        data = res.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data["error"]["code"], 404)
        self.assertIn("not found", data["error"]["message"].lower())

    def test_72_allocation_already_allocated_incident(self):
        """72. Verify allocating an incident with an existing ACTIVE allocation returns 409 Conflict."""
        inc_res = self.client.post("/api/incidents", json={
            "title": "Industrial Boiler Rupture",
            "incident_type": "FIRE",
            "latitude": 17.43,
            "longitude": 78.41,
        })
        inc_id = inc_res.get_json()["data"]["id"]

        res1 = self.client.post(f"/api/allocations/{inc_id}")
        self.assertEqual(res1.status_code, 201)

        # Attempt to allocate the same incident again
        res2 = self.client.post(f"/api/allocations/{inc_id}")
        self.assertEqual(res2.status_code, 409)
        data = res2.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data["error"]["code"], 409)
        self.assertIn("active allocation", data["error"]["message"].lower())

    def test_73_allocation_resource_shortage(self):
        """73. Verify resource shortage returns 422 Unprocessable Entity without partial allocation."""
        inc_res = self.client.post("/api/incidents", json={
            "title": "Critical Cardiac Arrest During Outage",
            "incident_type": "CARDIAC_EMERGENCY",
            "latitude": 17.42,
            "longitude": 78.43,
            "critical_symptoms": ["cardiac arrest", "unresponsive"],
        })
        inc_id = inc_res.get_json()["data"]["id"]

        # Temporarily make all ambulances busy
        with get_db(self.temp_db_path) as conn:
            conn.execute("UPDATE ambulances SET status = 'BUSY';")

        try:
            res = self.client.post(f"/api/allocations/{inc_id}")
            self.assertEqual(res.status_code, 422)
            data = res.get_json()
            self.assertFalse(data.get("success"))
            self.assertEqual(data["error"]["code"], 422)
            self.assertIn("shortage", data["error"]["message"].lower())

            # Incident remains in REPORTED status
            inc = query_db("SELECT status FROM incidents WHERE id = ?;", (inc_id,), db_path=self.temp_db_path, one=True)
            self.assertEqual(inc["status"], "REPORTED")

            # No active allocation was created
            alloc = query_db("SELECT * FROM allocations WHERE incident_id = ? AND allocation_status = 'ACTIVE';", (inc_id,), db_path=self.temp_db_path, one=True)
            self.assertIsNone(alloc)
        finally:
            with get_db(self.temp_db_path) as conn:
                conn.execute("UPDATE ambulances SET status = 'AVAILABLE' WHERE assigned_incident_id IS NULL;")

    # -----------------------------------------------------------------------
    # Task 2: POST /api/reallocation/breakdown Tests
    # -----------------------------------------------------------------------
    def test_74_breakdown_success_with_replacement(self):
        """74. Verify ambulance breakdown replaces vehicle, updates statuses, and logs event."""
        inc_res = self.client.post("/api/incidents", json={
            "title": "Traffic Injury at Dilsukhnagar Commercial Zone",
            "incident_type": "ROAD_ACCIDENT",
            "latitude": 17.37,
            "longitude": 78.52,
        })
        inc_id = inc_res.get_json()["data"]["id"]

        alloc_res = self.client.post(f"/api/allocations/{inc_id}")
        self.assertEqual(alloc_res.status_code, 201)
        alloc_data = alloc_res.get_json()["data"]
        broken_amb_id = alloc_data["ambulance"]["id"]
        old_alloc_id = alloc_data["allocation_id"]

        bd_res = self.client.post("/api/reallocation/breakdown", json={
            "ambulance_id": broken_amb_id,
            "reason": "Alternator failure during transit",
        })
        self.assertEqual(bd_res.status_code, 200)
        bd_data = bd_res.get_json()

        self.assertTrue(bd_data.get("success"))
        self.assertEqual(bd_data.get("broken_ambulance_id"), broken_amb_id)
        self.assertNotEqual(bd_data.get("replacement_ambulance", {}).get("id"), broken_amb_id)
        self.assertEqual(bd_data.get("old_allocation_id"), old_alloc_id)
        self.assertIsNotNone(bd_data.get("new_allocation_id"))

        # Broken ambulance is now OUT_OF_SERVICE with assigned incident cleared
        broken_row = query_db("SELECT status, assigned_incident_id FROM ambulances WHERE id = ?;", (broken_amb_id,), db_path=self.temp_db_path, one=True)
        self.assertEqual(broken_row["status"], "OUT_OF_SERVICE")
        self.assertIsNone(broken_row["assigned_incident_id"])

        # Old allocation is REALLOCATED, new allocation is ACTIVE
        old_alloc_row = query_db("SELECT allocation_status FROM allocations WHERE id = ?;", (old_alloc_id,), db_path=self.temp_db_path, one=True)
        self.assertEqual(old_alloc_row["allocation_status"], "REALLOCATED")

        new_alloc_row = query_db("SELECT allocation_status FROM allocations WHERE id = ?;", (bd_data["new_allocation_id"],), db_path=self.temp_db_path, one=True)
        self.assertEqual(new_alloc_row["allocation_status"], "ACTIVE")

        # Event log recorded
        logs = query_db("SELECT * FROM event_logs WHERE related_incident_id = ? AND event_type = 'AMBULANCE_BREAKDOWN';", (inc_id,), db_path=self.temp_db_path)
        self.assertGreaterEqual(len(logs), 1)

    def test_75_breakdown_no_replacement_available(self):
        """75. Verify breakdown with no available replacement returns 422, resets incident to REPORTED and restores hospital bed."""
        inc_res = self.client.post("/api/incidents", json={
            "title": "Electrical Substation Flashover",
            "incident_type": "FIRE",
            "latitude": 17.39,
            "longitude": 78.44,
        })
        inc_id = inc_res.get_json()["data"]["id"]

        alloc_res = self.client.post(f"/api/allocations/{inc_id}")
        self.assertEqual(alloc_res.status_code, 201)
        alloc_data = alloc_res.get_json()["data"]
        broken_amb_id = alloc_data["ambulance"]["id"]
        hosp_id = alloc_data["hospital"]["id"]

        hosp_beds_before = query_db("SELECT available_beds FROM hospitals WHERE id = ?;", (hosp_id,), db_path=self.temp_db_path, one=True)["available_beds"]

        # Take all other available ambulances offline
        with get_db(self.temp_db_path) as conn:
            conn.execute("UPDATE ambulances SET status = 'OUT_OF_SERVICE' WHERE id != ?;", (broken_amb_id,))

        try:
            bd_res = self.client.post("/api/reallocation/breakdown", json={
                "ambulance_id": broken_amb_id,
                "reason": "Complete transmission blowout",
            })
            self.assertEqual(bd_res.status_code, 422)
            bd_data = bd_res.get_json()

            self.assertFalse(bd_data.get("success"))
            self.assertEqual(bd_data["error"]["code"], 422)
            self.assertIn("no replacement ambulance available", bd_data["error"]["message"].lower())

            # Broken ambulance transitioned to OUT_OF_SERVICE
            broken_row = query_db("SELECT status, assigned_incident_id FROM ambulances WHERE id = ?;", (broken_amb_id,), db_path=self.temp_db_path, one=True)
            self.assertEqual(broken_row["status"], "OUT_OF_SERVICE")
            self.assertIsNone(broken_row["assigned_incident_id"])

            # Incident returned to REPORTED queue
            inc_row = query_db("SELECT status FROM incidents WHERE id = ?;", (inc_id,), db_path=self.temp_db_path, one=True)
            self.assertEqual(inc_row["status"], "REPORTED")

            # Receiving hospital bed restored
            hosp_beds_after = query_db("SELECT available_beds FROM hospitals WHERE id = ?;", (hosp_id,), db_path=self.temp_db_path, one=True)["available_beds"]
            self.assertEqual(hosp_beds_after, hosp_beds_before + 1)

            # Audit log records SHORTAGE_UNRESOLVED
            short_logs = query_db("SELECT * FROM event_logs WHERE related_incident_id = ? AND event_type = 'SHORTAGE_UNRESOLVED';", (inc_id,), db_path=self.temp_db_path)
            self.assertGreaterEqual(len(short_logs), 1)
        finally:
            with get_db(self.temp_db_path) as conn:
                conn.execute("UPDATE ambulances SET status = 'AVAILABLE' WHERE assigned_incident_id IS NULL;")

    # -----------------------------------------------------------------------
    # Task 3: POST /api/reallocation/hospital Tests
    # -----------------------------------------------------------------------
    def test_76_hospital_exhaustion_diversion_success(self):
        """76. Verify hospital capacity exhaustion diverts transports to alternative facility while preserving ambulance."""
        inc_res = self.client.post("/api/incidents", json={
            "title": "Urban Flooding Trauma Rescue",
            "incident_type": "FLOOD_RESCUE",
            "latitude": 17.36,
            "longitude": 78.47,
        })
        inc_id = inc_res.get_json()["data"]["id"]

        alloc_res = self.client.post(f"/api/allocations/{inc_id}")
        self.assertEqual(alloc_res.status_code, 201)
        alloc_data = alloc_res.get_json()["data"]
        old_hosp_id = alloc_data["hospital"]["id"]
        amb_id = alloc_data["ambulance"]["id"]
        old_alloc_id = alloc_data["allocation_id"]

        div_res = self.client.post("/api/reallocation/hospital", json={
            "hospital_id": old_hosp_id,
            "reason": "Mass casualty wave arrival",
            "exhausted_resource": "FULL",
        })
        self.assertEqual(div_res.status_code, 200)
        div_data = div_res.get_json()

        self.assertTrue(div_data.get("success"))
        self.assertGreaterEqual(div_data.get("reallocated_count"), 1)
        self.assertEqual(div_data.get("unresolved_count"), 0)

        # Ambulance remains assigned to incident
        amb_state = query_db("SELECT status, assigned_incident_id FROM ambulances WHERE id = ?;", (amb_id,), db_path=self.temp_db_path, one=True)
        self.assertEqual(amb_state["status"], "DISPATCHED")
        self.assertEqual(amb_state["assigned_incident_id"], inc_id)

        # Old allocation is REALLOCATED
        old_alloc = query_db("SELECT allocation_status FROM allocations WHERE id = ?;", (old_alloc_id,), db_path=self.temp_db_path, one=True)
        self.assertEqual(old_alloc["allocation_status"], "REALLOCATED")

        # Event log contains HOSPITAL_SATURATED
        sat_logs = query_db("SELECT * FROM event_logs WHERE related_incident_id = ? AND event_type = 'HOSPITAL_SATURATED';", (inc_id,), db_path=self.temp_db_path)
        self.assertGreaterEqual(len(sat_logs), 1)

    def test_77_hospital_saturation_without_alternative(self):
        """77. Verify hospital saturation without an alternative returns 422 and preserves active allocation."""
        inc_res = self.client.post("/api/incidents", json={
            "title": "Severe Burn Trauma Call",
            "incident_type": "FIRE",
            "latitude": 17.44,
            "longitude": 78.37,
        })
        inc_id = inc_res.get_json()["data"]["id"]

        alloc_res = self.client.post(f"/api/allocations/{inc_id}")
        self.assertEqual(alloc_res.status_code, 201)
        alloc_data = alloc_res.get_json()["data"]
        old_hosp_id = alloc_data["hospital"]["id"]
        alloc_id = alloc_data["allocation_id"]

        # Squeeze all other hospitals to 0 available beds
        with get_db(self.temp_db_path) as conn:
            conn.execute("UPDATE hospitals SET available_beds = 0 WHERE id != ?;", (old_hosp_id,))

        try:
            sat_res = self.client.post("/api/reallocation/hospital", json={
                "hospital_id": old_hosp_id,
                "reason": "Complete facility decontamination lockdown",
                "exhausted_resource": "FULL",
            })
            self.assertEqual(sat_res.status_code, 422)
            sat_data = sat_res.get_json()

            self.assertFalse(sat_data.get("success"))
            self.assertEqual(sat_data["error"]["code"], 422)
            self.assertGreaterEqual(sat_data.get("unresolved_count", 0), 1)

            # Active allocation is preserved and NOT prematurely dropped
            active = query_db("SELECT allocation_status FROM allocations WHERE id = ?;", (alloc_id,), db_path=self.temp_db_path, one=True)
            self.assertEqual(active["allocation_status"], "ACTIVE")
        finally:
            with get_db(self.temp_db_path) as conn:
                conn.execute("UPDATE hospitals SET available_beds = 40 WHERE available_beds = 0;")

    # -----------------------------------------------------------------------
    # Task 4: POST /api/reallocation/traffic Tests
    # -----------------------------------------------------------------------
    def test_78_traffic_update_success(self):
        """78. Verify successful traffic congestion update updates database and logs TRAFFIC_SPIKE."""
        res = self.client.post("/api/reallocation/traffic", json={
            "traffic_zone_id": 2,
            "new_multiplier": 2.15,
            "new_congestion_level": "HEAVY",
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("new_multiplier"), 2.15)
        self.assertEqual(data.get("traffic_zone", {}).get("congestion_level"), "HEAVY")

        # Verify in SQLite database
        zone = query_db("SELECT traffic_multiplier, congestion_level FROM traffic_zones WHERE id = 2;", db_path=self.temp_db_path, one=True)
        self.assertEqual(zone["traffic_multiplier"], 2.15)
        self.assertEqual(zone["congestion_level"], "HEAVY")

        # Verify TRAFFIC_SPIKE event log
        log_entry = query_db("SELECT * FROM event_logs WHERE event_type = 'TRAFFIC_SPIKE' ORDER BY id DESC LIMIT 1;", db_path=self.temp_db_path, one=True)
        self.assertIsNotNone(log_entry)

    def test_79_traffic_invalid_multiplier(self):
        """79. Verify invalid traffic multipliers (< 1.0, > 20.0, non-numeric, boolean) return 400 Bad Request."""
        # A. Less than 1.0
        res_low = self.client.post("/api/reallocation/traffic", json={"traffic_zone_id": 1, "new_multiplier": 0.5})
        self.assertEqual(res_low.status_code, 400)
        self.assertIn("new_multiplier", res_low.get_json()["error"]["message"])

        # B. Greater than 20.0
        res_high = self.client.post("/api/reallocation/traffic", json={"traffic_zone_id": 1, "new_multiplier": 25.0})
        self.assertEqual(res_high.status_code, 400)
        self.assertIn("new_multiplier", res_high.get_json()["error"]["message"])

        # C. Non-numeric string
        res_nan = self.client.post("/api/reallocation/traffic", json={"traffic_zone_id": 1, "new_multiplier": "congested"})
        self.assertEqual(res_nan.status_code, 400)
        self.assertIn("new_multiplier", res_nan.get_json()["error"]["message"])

        # D. Boolean
        res_bool = self.client.post("/api/reallocation/traffic", json={"traffic_zone_id": 1, "new_multiplier": True})
        self.assertEqual(res_bool.status_code, 400)
        self.assertIn("new_multiplier", res_bool.get_json()["error"]["message"])

    def test_80_traffic_minor_congestion_no_reallocation(self):
        """80. Verify minor traffic increments below the hysteresis threshold do NOT trigger reallocation."""
        with get_db(self.temp_db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO incidents (title, incident_type, latitude, longitude, injured_people, status)
                VALUES ('[TEST] Minor Intersection Delay', 'ROAD_ACCIDENT', 17.4265, 78.4528, 1, 'REPORTED');
                """
            )
            test_inc_id = cur.lastrowid
            cur.execute("UPDATE ambulances SET status = 'BUSY' WHERE id NOT IN (3, 4);")
            cur.execute("UPDATE ambulances SET status = 'AVAILABLE', assigned_incident_id = NULL WHERE id IN (3, 4);")

        try:
            alloc_res = self.client.post(f"/api/allocations/{test_inc_id}")
            self.assertEqual(alloc_res.status_code, 201)
            init_alloc_id = alloc_res.get_json()["data"]["allocation_id"]

            # Minor multiplier bump on Punjagutta (Zone #3)
            spike_res = self.client.post("/api/reallocation/traffic", json={
                "traffic_zone_id": 3,
                "new_multiplier": 2.35,
                "new_congestion_level": "SEVERE",
                "min_improvement_minutes": 5.0,
            })
            self.assertEqual(spike_res.status_code, 200)
            self.assertEqual(spike_res.get_json()["reallocations_performed"], 0)

            # Active allocation remains unchanged
            active = query_db("SELECT id, allocation_status FROM allocations WHERE incident_id = ? AND allocation_status = 'ACTIVE';", (test_inc_id,), db_path=self.temp_db_path, one=True)
            self.assertEqual(active["id"], init_alloc_id)
        finally:
            with get_db(self.temp_db_path) as conn:
                conn.execute("UPDATE ambulances SET status = 'AVAILABLE' WHERE status = 'BUSY';")

    def test_81_traffic_major_congestion_triggers_reallocation(self):
        """81. Verify major traffic congestion exceeding hysteresis threshold reallocates ambulance and preserves hospital."""
        with get_db(self.temp_db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO incidents (title, incident_type, latitude, longitude, injured_people, status)
                VALUES ('[TEST] Major Congestion Corridor', 'ROAD_ACCIDENT', 17.4200, 78.4500, 2, 'REPORTED');
                """
            )
            test_inc_id = cur.lastrowid
            cur.execute("UPDATE ambulances SET status = 'BUSY' WHERE id NOT IN (3, 8);")
            cur.execute("UPDATE ambulances SET status = 'AVAILABLE', assigned_incident_id = NULL WHERE id IN (3, 8);")
            cur.execute("UPDATE ambulances SET status = 'BUSY' WHERE id = 3;")

        alloc_res = self.client.post(f"/api/allocations/{test_inc_id}")
        self.assertEqual(alloc_res.status_code, 201)
        old_alloc_id = alloc_res.get_json()["data"]["allocation_id"]
        initial_hosp_id = alloc_res.get_json()["data"]["hospital"]["id"]

        # Make closer Ambulance 3 available
        with get_db(self.temp_db_path) as conn:
            conn.execute("UPDATE ambulances SET status = 'AVAILABLE', assigned_incident_id = NULL WHERE id = 3;")

        try:
            # Severe traffic spike on Punjagutta (Zone #3) to multiplier 5.0
            spike_res = self.client.post("/api/reallocation/traffic", json={
                "traffic_zone_id": 3,
                "new_multiplier": 5.0,
                "new_congestion_level": "GRIDLOCK",
                "min_improvement_minutes": 5.0,
            })
            self.assertEqual(spike_res.status_code, 200)
            self.assertGreaterEqual(spike_res.get_json()["reallocations_performed"], 1)

            # Old allocation retired to REALLOCATED
            old_alloc = query_db("SELECT allocation_status FROM allocations WHERE id = ?;", (old_alloc_id,), db_path=self.temp_db_path, one=True)
            self.assertEqual(old_alloc["allocation_status"], "REALLOCATED")

            # New active allocation with Ambulance 3 and hospital preserved
            new_alloc = query_db(
                "SELECT id, ambulance_id, hospital_id, allocation_status FROM allocations WHERE incident_id = ? AND allocation_status = 'ACTIVE';",
                (test_inc_id,),
                db_path=self.temp_db_path,
                one=True,
            )
            self.assertIsNotNone(new_alloc)
            self.assertEqual(new_alloc["ambulance_id"], 3)
            self.assertEqual(new_alloc["hospital_id"], initial_hosp_id)
        finally:
            with get_db(self.temp_db_path) as conn:
                conn.execute("UPDATE ambulances SET status = 'AVAILABLE' WHERE status = 'BUSY';")

    # -----------------------------------------------------------------------
    # Malformed Payloads & Missing Entity Tests
    # -----------------------------------------------------------------------
    def test_82_malformed_and_missing_payloads(self):
        """82. Verify 400 Bad Request on missing required fields, non-JSON bodies, and invalid options."""
        # A. Non-JSON body
        res_non_json = self.client.post(
            "/api/reallocation/breakdown",
            data="not json",
            content_type="text/plain",
        )
        self.assertEqual(res_non_json.status_code, 400)

        # B. Breakdown missing ambulance_id
        res_no_amb = self.client.post("/api/reallocation/breakdown", json={"reason": "Mechanical failure"})
        self.assertEqual(res_no_amb.status_code, 400)
        self.assertIn("ambulance_id", res_no_amb.get_json()["error"]["message"])

        # C. Breakdown boolean ambulance_id
        res_bool_amb = self.client.post("/api/reallocation/breakdown", json={"ambulance_id": True, "reason": "Mechanical failure"})
        self.assertEqual(res_bool_amb.status_code, 400)

        # D. Breakdown missing reason
        res_no_reason = self.client.post("/api/reallocation/breakdown", json={"ambulance_id": 1})
        self.assertEqual(res_no_reason.status_code, 400)
        self.assertIn("reason", res_no_reason.get_json()["error"]["message"])

        # E. Hospital missing hospital_id
        res_no_hosp = self.client.post("/api/reallocation/hospital", json={"reason": "Over capacity"})
        self.assertEqual(res_no_hosp.status_code, 400)
        self.assertIn("hospital_id", res_no_hosp.get_json()["error"]["message"])

        # F. Hospital invalid exhausted_resource
        res_bad_res = self.client.post("/api/reallocation/hospital", json={
            "hospital_id": 1,
            "reason": "Over capacity",
            "exhausted_resource": "SUPER_HEURISTIC_RESOURCE",
        })
        self.assertEqual(res_bad_res.status_code, 400)
        self.assertIn("exhausted_resource", res_bad_res.get_json()["error"]["message"])

        # G. Traffic missing traffic_zone_id
        res_no_zone = self.client.post("/api/reallocation/traffic", json={"new_multiplier": 2.0})
        self.assertEqual(res_no_zone.status_code, 400)
        self.assertIn("traffic_zone_id", res_no_zone.get_json()["error"]["message"])

        # H. Traffic invalid congestion level
        res_bad_cong = self.client.post("/api/reallocation/traffic", json={
            "traffic_zone_id": 1,
            "new_multiplier": 2.0,
            "new_congestion_level": "APOCALYPSE",
        })
        self.assertEqual(res_bad_cong.status_code, 400)
        self.assertIn("new_congestion_level", res_bad_cong.get_json()["error"]["message"])

    def test_83_missing_entities_and_invalid_operational_states(self):
        """83. Verify 404 for missing resources and 409 for invalid operational states."""
        # Nonexistent ambulance for breakdown -> 404 Not Found
        res_no_amb = self.client.post("/api/reallocation/breakdown", json={"ambulance_id": 99999, "reason": "Flat tire"})
        self.assertEqual(res_no_amb.status_code, 404)

        # Available ambulance with no active allocation for breakdown -> 409 Conflict
        res_idle_amb = self.client.post("/api/reallocation/breakdown", json={"ambulance_id": 1, "reason": "Flat tire"})
        self.assertEqual(res_idle_amb.status_code, 409)
        self.assertIn("no active allocation", res_idle_amb.get_json()["error"]["message"].lower())

        # Nonexistent hospital for diversion -> 404 Not Found
        res_no_hosp = self.client.post("/api/reallocation/hospital", json={"hospital_id": 99999, "reason": "Surge"})
        self.assertEqual(res_no_hosp.status_code, 404)

        # Nonexistent traffic zone -> 404 Not Found
        res_no_zone = self.client.post("/api/reallocation/traffic", json={"traffic_zone_id": 99999, "new_multiplier": 2.0})
        self.assertEqual(res_no_zone.status_code, 404)

    def test_84_production_database_isolation(self):
        """84. Verify the production SQLite database was not touched or modified during allocation and reallocation tests."""
        prod_incidents = query_db("SELECT COUNT(*) AS c FROM incidents;", db_path=DEFAULT_DB_PATH, one=True)["c"]
        prod_ambulances = query_db("SELECT COUNT(*) AS c FROM ambulances;", db_path=DEFAULT_DB_PATH, one=True)["c"]
        prod_hospitals = query_db("SELECT COUNT(*) AS c FROM hospitals;", db_path=DEFAULT_DB_PATH, one=True)["c"]
        prod_zones = query_db("SELECT COUNT(*) AS c FROM traffic_zones;", db_path=DEFAULT_DB_PATH, one=True)["c"]

        self.assertEqual(prod_incidents, 3)
        self.assertEqual(prod_ambulances, 8)
        self.assertEqual(prod_hospitals, 5)
        self.assertEqual(prod_zones, 8)


class TestEventsAndAnalyticsAPIs(unittest.TestCase):
    """Test suite for Step 6.7: GET /api/events and GET /api/analytics/overview."""

    @classmethod
    def setUpClass(cls):
        """Set up an isolated temporary database for events and analytics tests."""
        cls.test_dir = tempfile.mkdtemp(prefix="resqgrid_events_analytics_test_")
        cls.temp_db_path = Path(cls.test_dir) / "test_events_analytics.db"
        init_db(db_path=cls.temp_db_path, seed_if_empty=True)

    @classmethod
    def tearDownClass(cls):
        """Clean up temporary test directory."""
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        """Reset test database to pristine seed state before each test for complete isolation."""
        if self.temp_db_path.exists():
            try:
                self.temp_db_path.unlink()
            except Exception:
                pass
        init_db(db_path=self.temp_db_path, seed_if_empty=True)

        self.app = create_app(test_config={
            "DATABASE": str(self.temp_db_path),
            "TESTING": True,
        })
        self.client = self.app.test_client()

    # -----------------------------------------------------------------------
    # Events API Tests
    # -----------------------------------------------------------------------
    def test_90_events_returns_seeded_events(self):
        """90. Verify GET /api/events returns initial seeded system events."""
        res = self.client.get("/api/events")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertTrue(data.get("success"))
        self.assertGreaterEqual(data.get("count"), 1)
        self.assertIsInstance(data.get("data"), list)

        first_event = data["data"][-1]  # Oldest event in seed
        self.assertEqual(first_event["event_type"], "SYSTEM_INIT")
        self.assertIn("initialized", first_event["description"])
        self.assertIsInstance(first_event["created_at"], str)

    def test_91_events_ordering_newest_first(self):
        """91. Verify GET /api/events orders entries newest first (descending ID)."""
        # Create two incidents to trigger INCIDENT_REPORTED logs
        self.client.post("/api/incidents", json={
            "title": "First Test Incident",
            "incident_type": "FIRE",
            "latitude": 17.41,
            "longitude": 78.41,
        })
        self.client.post("/api/incidents", json={
            "title": "Second Test Incident",
            "incident_type": "ROAD_ACCIDENT",
            "latitude": 17.42,
            "longitude": 78.42,
        })

        res = self.client.get("/api/events")
        self.assertEqual(res.status_code, 200)
        events = res.get_json()["data"]

        self.assertGreaterEqual(len(events), 3)
        # Verify descending order
        for i in range(len(events) - 1):
            self.assertGreater(events[i]["id"], events[i + 1]["id"])

    def test_92_events_filter_by_type(self):
        """92. Verify filtering events by event_type (case-insensitive)."""
        # Create an incident to ensure INCIDENT_REPORTED exists
        self.client.post("/api/incidents", json={
            "title": "Filtered Incident Event",
            "incident_type": "ROAD_ACCIDENT",
            "latitude": 17.43,
            "longitude": 78.43,
        })

        # Filter exact case
        res_exact = self.client.get("/api/events?event_type=INCIDENT_REPORTED")
        self.assertEqual(res_exact.status_code, 200)
        data_exact = res_exact.get_json()
        self.assertGreaterEqual(data_exact["count"], 1)
        for ev in data_exact["data"]:
            self.assertEqual(ev["event_type"], "INCIDENT_REPORTED")

        # Filter lower case
        res_lower = self.client.get("/api/events?event_type=incident_reported")
        self.assertEqual(res_lower.status_code, 200)
        data_lower = res_lower.get_json()
        self.assertEqual(data_lower["count"], data_exact["count"])

    def test_93_events_limit_validation(self):
        """93. Verify limit parameter bounds enforcement and validation."""
        # Insert additional events
        for i in range(5):
            self.client.post("/api/incidents", json={
                "title": f"Batch Incident {i}",
                "incident_type": "ROAD_ACCIDENT",
                "latitude": 17.41 + i * 0.01,
                "longitude": 78.41 + i * 0.01,
            })

        # A. Valid limit: 2
        res_2 = self.client.get("/api/events?limit=2")
        self.assertEqual(res_2.status_code, 200)
        self.assertEqual(len(res_2.get_json()["data"]), 2)
        self.assertEqual(res_2.get_json()["count"], 2)

        # B. Non-numeric limit -> 400
        res_str = self.client.get("/api/events?limit=abc")
        self.assertEqual(res_str.status_code, 400)
        self.assertIn("limit", res_str.get_json()["error"]["message"])

        # C. Zero limit -> 400
        res_zero = self.client.get("/api/events?limit=0")
        self.assertEqual(res_zero.status_code, 400)
        self.assertIn("limit", res_zero.get_json()["error"]["message"])

        # D. Negative limit -> 400
        res_neg = self.client.get("/api/events?limit=-10")
        self.assertEqual(res_neg.status_code, 400)

        # E. Limit exceeding 200 -> 400
        res_large = self.client.get("/api/events?limit=250")
        self.assertEqual(res_large.status_code, 400)

    def test_94_events_empty_results(self):
        """94. Verify querying for a nonexistent event_type returns 200 with empty list."""
        res = self.client.get("/api/events?event_type=NONEXISTENT_EVENT_CATEGORY")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["data"], [])

    # -----------------------------------------------------------------------
    # Analytics API Tests
    # -----------------------------------------------------------------------
    def test_95_analytics_counts_match_seeded_database(self):
        """95. Verify GET /api/analytics/overview matches seeded benchmark records."""
        res = self.client.get("/api/analytics/overview")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertTrue(data.get("success"))
        metrics = data.get("data")
        self.assertIsNotNone(metrics)

        # Incidents
        self.assertEqual(metrics["incidents"]["total"], 3)
        self.assertEqual(metrics["incidents"]["active"], 3)
        self.assertEqual(metrics["incidents"]["critical"], 2)

        # Ambulances
        self.assertEqual(metrics["ambulances"]["total"], 8)
        self.assertEqual(metrics["ambulances"]["available"], 8)
        self.assertEqual(metrics["ambulances"]["by_status"]["AVAILABLE"], 8)

        # Hospitals
        self.assertEqual(metrics["hospitals"]["total"], 5)
        self.assertEqual(metrics["hospitals"]["total_beds"], 1980)
        self.assertEqual(metrics["hospitals"]["available_beds"], 277)
        self.assertEqual(metrics["hospitals"]["total_icu_beds"], 295)
        self.assertEqual(metrics["hospitals"]["available_icu_beds"], 34)

        # Response time check: unrecorded in current prototype, returns null
        self.assertIsNone(metrics["response_time"]["average_minutes"])
        self.assertFalse(metrics["response_time"]["recorded"])
        self.assertIn("not yet recorded", metrics["response_time"]["explanation"].lower())

        # KPIs object
        kpis = metrics["kpis"]
        self.assertEqual(kpis["activeEmergencies"], 3)
        self.assertEqual(kpis["criticalIncidents"], 2)
        self.assertEqual(kpis["availableAmbulances"], 8)
        self.assertEqual(kpis["totalAmbulances"], 8)
        self.assertEqual(kpis["hospitalsOnline"], 5)
        self.assertEqual(kpis["totalHospitals"], 5)
        self.assertIsNone(kpis["avgResponseTimeMin"])

    def test_96_analytics_values_update_after_incident_creation(self):
        """96. Verify analytics counts reflect dynamically created incidents."""
        # Create a new critical incident
        create_res = self.client.post("/api/incidents", json={
            "title": "Severe Industrial Chemical Explosion",
            "incident_type": "FIRE",
            "latitude": 17.43,
            "longitude": 78.43,
            "injured_people": 6,
            "affected_people": 12,
            "critical_symptoms": ["cardiac arrest", "severe burns", "unresponsive"],
        })
        self.assertEqual(create_res.status_code, 201)

        res = self.client.get("/api/analytics/overview")
        self.assertEqual(res.status_code, 200)
        metrics = res.get_json()["data"]

        self.assertEqual(metrics["incidents"]["total"], 4)
        self.assertEqual(metrics["incidents"]["active"], 4)
        self.assertEqual(metrics["incidents"]["critical"], 3)
        self.assertEqual(metrics["incidents"]["by_severity"]["CRITICAL"], 3)
        self.assertEqual(metrics["kpis"]["activeEmergencies"], 4)
        self.assertEqual(metrics["kpis"]["criticalIncidents"], 3)

    def test_97_analytics_reflects_ambulance_allocation_changes(self):
        """97. Verify analytics metrics update when an ambulance is allocated."""
        inc_res = self.client.post("/api/incidents", json={
            "title": "Road Accident for Dispatch Test",
            "incident_type": "ROAD_ACCIDENT",
            "latitude": 17.44,
            "longitude": 78.38,
            "injured_people": 1,
        })
        inc_id = inc_res.get_json()["data"]["id"]

        alloc_res = self.client.post(f"/api/allocations/{inc_id}")
        self.assertEqual(alloc_res.status_code, 201)

        res = self.client.get("/api/analytics/overview")
        self.assertEqual(res.status_code, 200)
        metrics = res.get_json()["data"]

        # Available ambulances decremented from 8 to 7
        self.assertEqual(metrics["ambulances"]["available"], 7)
        self.assertEqual(metrics["ambulances"]["by_status"]["DISPATCHED"], 1)
        self.assertEqual(metrics["kpis"]["availableAmbulances"], 7)

        # Active allocations count is 1
        self.assertEqual(metrics["allocations"]["active"], 1)

        # Available hospital beds decremented by 1
        self.assertEqual(metrics["hospitals"]["available_beds"], 276)

    def test_98_invalid_query_parameters_return_json_errors(self):
        """98. Verify invalid query parameters on events and analytics return 400 Bad Request."""
        # A. Unsupported query parameter on events
        res_ev = self.client.get("/api/events?unexpected_query_param=123")
        self.assertEqual(res_ev.status_code, 400)
        self.assertIn("Unsupported query parameter", res_ev.get_json()["error"]["message"])

        # B. Empty event_type parameter on events
        res_ev_empty = self.client.get("/api/events?event_type=")
        self.assertEqual(res_ev_empty.status_code, 400)
        self.assertIn("event_type", res_ev_empty.get_json()["error"]["message"])

        # C. Query parameter passed to analytics overview (which expects none)
        res_ana = self.client.get("/api/analytics/overview?filter=active")
        self.assertEqual(res_ana.status_code, 400)
        self.assertIn("does not accept query parameters", res_ana.get_json()["error"]["message"])

    def test_99_production_database_untouched(self):
        """99. Verify the production SQLite database was not modified during events and analytics tests."""
        prod_incidents = query_db("SELECT COUNT(*) AS c FROM incidents;", db_path=DEFAULT_DB_PATH, one=True)["c"]
        prod_ambulances = query_db("SELECT COUNT(*) AS c FROM ambulances;", db_path=DEFAULT_DB_PATH, one=True)["c"]
        prod_hospitals = query_db("SELECT COUNT(*) AS c FROM hospitals;", db_path=DEFAULT_DB_PATH, one=True)["c"]
        prod_zones = query_db("SELECT COUNT(*) AS c FROM traffic_zones;", db_path=DEFAULT_DB_PATH, one=True)["c"]
        prod_logs = query_db("SELECT COUNT(*) AS c FROM event_logs;", db_path=DEFAULT_DB_PATH, one=True)["c"]

        self.assertEqual(prod_incidents, 3)
        self.assertEqual(prod_ambulances, 8)
        self.assertEqual(prod_hospitals, 5)
        self.assertEqual(prod_zones, 8)
        self.assertEqual(prod_logs, 1)


if __name__ == "__main__":
    unittest.main()


