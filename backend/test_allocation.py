"""ResQGrid Allocation Engine Verification Suite

Tests resource allocation workflows in an isolated test database:
1. find_suitable_ambulances (capability matching, active allocation exclusion).
2. find_suitable_hospitals (capacity checks, ICU/ventilator matching, specialty scoring).
3. allocate_incident (happy path, state transitions, capacity decrements, event logs).
4. Duplicate active allocation prevention.
5. Nonexistent and cancelled incident rejection.
6. Resource shortage handling.
7. Test A: Hospital capacity rollback on concurrent depletion.
8. Test B: Controlled mid-transaction failure rollback.
9. Test C: Missing resources do not consume hospital capacity.
10. Ambulance uniqueness constraint (only 1 active allocation allowed per ambulance).
11. Transparent capacity reservation semantics (partial fulfillment reporting).
"""

import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import get_db, init_db, query_db
from backend.services.allocation import (
    allocate_incident,
    find_suitable_ambulances,
    find_suitable_hospitals,
)
from backend.services.severity import estimate_severity

TEMP_TEST_DB = Path(__file__).resolve().parent / "data" / "test_allocation_isolated.db"


class TestAllocationEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Remove any old test db and initialize clean seed dataset
        if TEMP_TEST_DB.exists():
            TEMP_TEST_DB.unlink()
        init_db(db_path=TEMP_TEST_DB, seed_if_empty=True)

    @classmethod
    def tearDownClass(cls):
        # Clean up temporary test database
        if TEMP_TEST_DB.exists():
            try:
                TEMP_TEST_DB.unlink()
            except Exception:
                pass

    def test_01_find_suitable_ambulances_als_requirement(self):
        """Verify strict capability matching: ALS requirement only returns ALS units."""
        incident = query_db("SELECT * FROM incidents WHERE id = 1;", db_path=TEMP_TEST_DB, one=True)
        reqs = {"ambulance_type": "ALS"}
        candidates = find_suitable_ambulances(incident, reqs, db_path=TEMP_TEST_DB)

        self.assertGreater(len(candidates), 0)
        for cand in candidates:
            self.assertEqual(cand["capability"], "ALS")
            self.assertIn("estimated_arrival_minutes", cand)
            self.assertIn("road_distance_km", cand)
            self.assertIn("selection_explanation", cand)

        # Check sorting by shortest ETA
        etas = [c["estimated_arrival_minutes"] for c in candidates]
        self.assertEqual(etas, sorted(etas))

    def test_02_find_suitable_hospitals_capacity_and_specialty(self):
        """Verify hospital filtering requires ICU and matches specialty."""
        incident = query_db("SELECT * FROM incidents WHERE id = 2;", db_path=TEMP_TEST_DB, one=True)
        reqs = {"icu_required": True, "ambulance_type": "ALS"}
        candidates = find_suitable_hospitals(incident, reqs, db_path=TEMP_TEST_DB)

        self.assertGreater(len(candidates), 0)
        for cand in candidates:
            self.assertGreaterEqual(cand["available_beds"], 1)
            self.assertGreaterEqual(cand["available_icu_beds"], 1)
            self.assertIn("specialties", cand)

        # For Incident #2 (CARDIAC_EMERGENCY), cardiology-specialized hospitals should rank top
        top_hospital = candidates[0]
        self.assertGreater(top_hospital["compatibility_score"], 0)
        self.assertTrue(
            "cardio" in top_hospital["specialties"].lower() or "cath lab" in top_hospital["specialties"].lower()
        )

    def test_03_allocate_incident_happy_path(self):
        """Verify successful atomic allocation, state change, and event logging."""
        # Incident #1: Road accident (5 injured, requires 3 ambulances in triage estimate)
        incident_before = query_db("SELECT * FROM incidents WHERE id = 1;", db_path=TEMP_TEST_DB, one=True)
        self.assertEqual(incident_before["status"], "REPORTED")

        result = allocate_incident(1, db_path=TEMP_TEST_DB)
        self.assertTrue(result["success"])
        self.assertEqual(result["incident_id"], 1)
        self.assertIsNotNone(result["allocation_id"])
        self.assertIsNotNone(result["ambulance"])
        self.assertIsNotNone(result["hospital"])
        self.assertIn("Dispatched", result["decision_reason"])

        # Capacity reservation semantics: multi-casualty incident is explicitly marked PARTIAL
        self.assertEqual(result["fulfillment_status"], "PARTIAL")
        self.assertEqual(result["resources_reserved"]["ambulances"], 1)
        self.assertEqual(result["resources_reserved"]["general_beds"], 1)
        self.assertGreater(result["unfulfilled_requirements"]["ambulances"], 0)
        self.assertIn("Fulfillment: PARTIAL", result["decision_reason"])

        # Verify incident status updated to ASSIGNED
        incident_after = query_db("SELECT * FROM incidents WHERE id = 1;", db_path=TEMP_TEST_DB, one=True)
        self.assertEqual(incident_after["status"], "ASSIGNED")

        # Verify assigned ambulance status updated to DISPATCHED
        amb_id = result["ambulance"]["id"]
        amb_after = query_db("SELECT * FROM ambulances WHERE id = ?;", (amb_id,), db_path=TEMP_TEST_DB, one=True)
        self.assertEqual(amb_after["status"], "DISPATCHED")
        self.assertEqual(amb_after["assigned_incident_id"], 1)

        # Verify allocation record exists
        alloc = query_db("SELECT * FROM allocations WHERE id = ?;", (result["allocation_id"],), db_path=TEMP_TEST_DB, one=True)
        self.assertEqual(alloc["allocation_status"], "ACTIVE")
        self.assertEqual(alloc["incident_id"], 1)
        self.assertEqual(alloc["ambulance_id"], amb_id)

        # Verify event log entry
        log_entry = query_db(
            "SELECT * FROM event_logs WHERE related_incident_id = 1 AND event_type = 'RESOURCE_ALLOCATED';",
            db_path=TEMP_TEST_DB,
            one=True,
        )
        self.assertIsNotNone(log_entry)

    def test_04_duplicate_active_allocation_rejected(self):
        """Verify allocating the same incident again is rejected without side-effects."""
        # Incident #1 is already ASSIGNED and has an ACTIVE allocation from test_03
        result = allocate_incident(1, db_path=TEMP_TEST_DB)
        self.assertFalse(result["success"])
        self.assertIn("already has an active allocation", result["error"])

    def test_05_nonexistent_and_cancelled_incidents_rejected(self):
        """Verify nonexistent or cancelled incidents return clear errors."""
        res_none = allocate_incident(9999, db_path=TEMP_TEST_DB)
        self.assertFalse(res_none["success"])
        self.assertIn("not found", res_none["error"])

        # Mark incident #3 as CANCELLED to test rejection
        with get_db(TEMP_TEST_DB) as conn:
            conn.execute("UPDATE incidents SET status = 'CANCELLED' WHERE id = 3;")

        res_cancelled = allocate_incident(3, db_path=TEMP_TEST_DB)
        self.assertFalse(res_cancelled["success"])
        self.assertIn("CANCELLED", res_cancelled["error"])

        # Restore incident #3
        with get_db(TEMP_TEST_DB) as conn:
            conn.execute("UPDATE incidents SET status = 'REPORTED' WHERE id = 3;")

    def test_06_resource_shortage_handling(self):
        """Verify allocation fails gracefully when required ambulances are unavailable."""
        # Temporarily make all ALS ambulances unavailable
        with get_db(TEMP_TEST_DB) as conn:
            conn.execute("UPDATE ambulances SET status = 'BUSY' WHERE capability = 'ALS';")

        try:
            # Incident #2 requires ALS (cardiac)
            res = allocate_incident(2, db_path=TEMP_TEST_DB)
            self.assertFalse(res["success"])
            self.assertIn("Resource shortage", res["error"])
        finally:
            # Restore ambulances (except ambulance #1 which was legitimately dispatched in test_03)
            with get_db(TEMP_TEST_DB) as conn:
                conn.execute("UPDATE ambulances SET status = 'AVAILABLE' WHERE capability = 'ALS' AND id != 1;")

    def test_07_hospital_capacity_rollback(self):
        """Test A — Hospital capacity rollback on concurrent depletion.
        
        Arrange a candidate hospital that appears eligible, but has its capacity
        exhausted right before the conditional update executes.
        Verify full transaction rollback (no allocation, ambulance AVAILABLE, incident REPORTED, beds unchanged).
        """
        # Create an isolated test incident
        with get_db(TEMP_TEST_DB) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO incidents (title, incident_type, latitude, longitude, injured_people, status)
                VALUES ('[TEST] Minor Injury', 'MINOR_INJURY', 17.4300, 78.4100, 1, 'REPORTED');
                """
            )
            test_inc_id = cur.lastrowid

            # Select an available BLS ambulance
            cur.execute("SELECT id FROM ambulances WHERE status = 'AVAILABLE' AND capability = 'BLS' LIMIT 1;")
            test_amb_id = cur.fetchone()[0]

            # Record baseline hospital state for hospital #3 (Yashoda Malakpet)
            cur.execute("SELECT available_beds, available_icu_beds FROM hospitals WHERE id = 3;")
            hosp_baseline = dict(cur.fetchone())

        # Mock find_suitable_hospitals to return hospital #3, but set its capacity to 0 in DB
        with get_db(TEMP_TEST_DB) as conn:
            conn.execute("UPDATE hospitals SET available_beds = 0 WHERE id = 3;")

        fake_hospital_candidate = [{
            "hospital_id": 3,
            "name": "Yashoda Hospitals, Malakpet",
            "estimated_arrival_minutes": 12.0,
            "road_distance_km": 6.5,
            "traffic_multiplier": 1.2,
            "available_beds": 0,
            "available_icu_beds": 0,
            "available_ventilators": 0,
            "emergency_capacity": 40,
            "specialties": "Emergency",
            "compatibility_score": 5,
            "selection_explanation": "Test mock candidate with exhausted beds",
        }]

        with patch("backend.services.allocation.find_suitable_hospitals", return_value=fake_hospital_candidate):
            result = allocate_incident(test_inc_id, db_path=TEMP_TEST_DB)

        # 1. Allocation must fail
        self.assertFalse(result["success"])
        self.assertIn("capacity was exhausted concurrently", result["error"])

        # 2. No allocation record created
        alloc_count = query_db(
            "SELECT COUNT(*) AS c FROM allocations WHERE incident_id = ?;",
            (test_inc_id,),
            db_path=TEMP_TEST_DB,
            one=True,
        )["c"]
        self.assertEqual(alloc_count, 0)

        # 3. Ambulance remains AVAILABLE
        amb_state = query_db("SELECT status, assigned_incident_id FROM ambulances WHERE id = ?;", (test_amb_id,), db_path=TEMP_TEST_DB, one=True)
        self.assertEqual(amb_state["status"], "AVAILABLE")
        self.assertIsNone(amb_state["assigned_incident_id"])

        # 4. Incident remains REPORTED (not ASSIGNED)
        inc_state = query_db("SELECT status FROM incidents WHERE id = ?;", (test_inc_id,), db_path=TEMP_TEST_DB, one=True)
        self.assertEqual(inc_state["status"], "REPORTED")

        # 5. Restore hospital #3 baseline capacity
        with get_db(TEMP_TEST_DB) as conn:
            conn.execute(
                "UPDATE hospitals SET available_beds = ?, available_icu_beds = ? WHERE id = 3;",
                (hosp_baseline["available_beds"], hosp_baseline["available_icu_beds"]),
            )

    def test_08_transaction_failure_rollback(self):
        """Test B — Transaction failure rollback.
        
        Cause an artificial failure right after ambulance and hospital updates,
        before committing the allocation record using an atomic SQLite trigger.
        Verify all updates are rolled back cleanly.
        """
        # Create a test incident
        with get_db(TEMP_TEST_DB) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO incidents (title, incident_type, latitude, longitude, injured_people, status)
                VALUES ('[TEST] Fall Incident', 'FALL_FROM_HEIGHT', 17.4350, 78.4150, 1, 'REPORTED');
                """
            )
            test_inc_id = cur.lastrowid

        # Snapshot baseline ambulance and hospital states
        hosp_before = query_db("SELECT available_beds FROM hospitals WHERE id = 1;", db_path=TEMP_TEST_DB, one=True)["available_beds"]
        amb_state_before = query_db("SELECT id, status FROM ambulances WHERE status = 'AVAILABLE' LIMIT 1;", db_path=TEMP_TEST_DB, one=True)
        target_amb_id = amb_state_before["id"]

        # Install a temporary SQLite trigger that aborts when inserting into allocations
        with get_db(TEMP_TEST_DB) as conn:
            conn.execute(
                """
                CREATE TRIGGER test_fail_alloc_trigger
                BEFORE INSERT ON allocations
                BEGIN
                    SELECT RAISE(ABORT, 'Controlled test failure during allocation INSERT');
                END;
                """
            )

        try:
            result = allocate_incident(test_inc_id, db_path=TEMP_TEST_DB)
        finally:
            # Drop the test trigger
            with get_db(TEMP_TEST_DB) as conn:
                conn.execute("DROP TRIGGER IF EXISTS test_fail_alloc_trigger;")

        # 1. Allocation must fail
        self.assertFalse(result["success"])
        self.assertIn("Controlled test failure", result["error"])

        # 2. No active allocation exists
        active_allocs = query_db(
            "SELECT COUNT(*) AS c FROM allocations WHERE incident_id = ?;",
            (test_inc_id,),
            db_path=TEMP_TEST_DB,
            one=True,
        )["c"]
        self.assertEqual(active_allocs, 0)

        # 3. Ambulance remains AVAILABLE
        amb_after = query_db("SELECT status, assigned_incident_id FROM ambulances WHERE id = ?;", (target_amb_id,), db_path=TEMP_TEST_DB, one=True)
        self.assertEqual(amb_after["status"], "AVAILABLE")
        self.assertIsNone(amb_after["assigned_incident_id"])

        # 4. Incident status remains REPORTED
        inc_after = query_db("SELECT status FROM incidents WHERE id = ?;", (test_inc_id,), db_path=TEMP_TEST_DB, one=True)
        self.assertEqual(inc_after["status"], "REPORTED")

        # 5. Hospital capacity remains unchanged
        hosp_after = query_db("SELECT available_beds FROM hospitals WHERE id = 1;", db_path=TEMP_TEST_DB, one=True)["available_beds"]
        self.assertEqual(hosp_before, hosp_after)

    def test_09_missing_resource_no_capacity_consumed(self):
        """Test C — Missing resource does not consume hospital capacity.
        
        When no ambulance is available, verify zero hospital capacity is deducted.
        """
        # Snapshot capacities of all hospitals
        capacities_before = query_db("SELECT id, available_beds, available_icu_beds FROM hospitals ORDER BY id;", db_path=TEMP_TEST_DB)

        # Make all ambulances unavailable
        with get_db(TEMP_TEST_DB) as conn:
            conn.execute("UPDATE ambulances SET status = 'BUSY';")

        try:
            res = allocate_incident(2, db_path=TEMP_TEST_DB)
            self.assertFalse(res["success"])
            self.assertIn("Resource shortage", res["error"])

            # Verify hospital capacities did not change by even 1 bed
            capacities_after = query_db("SELECT id, available_beds, available_icu_beds FROM hospitals ORDER BY id;", db_path=TEMP_TEST_DB)
            self.assertEqual(capacities_before, capacities_after)
        finally:
            # Restore ambulances
            with get_db(TEMP_TEST_DB) as conn:
                conn.execute("UPDATE ambulances SET status = 'AVAILABLE' WHERE id != 1;")

    def test_10_ambulance_uniqueness_single_active_allocation(self):
        """Verify ambulance uniqueness: an ambulance cannot have two active allocations.
        
        Tested via allocation engine and confirmed by SQLite partial unique index.
        """
        # Create two separate test incidents
        with get_db(TEMP_TEST_DB) as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO incidents (title, incident_type, latitude, longitude, status) VALUES ('Incident X', 'MINOR_INJURY', 17.41, 78.42, 'REPORTED');")
            inc_x_id = cur.lastrowid
            cur.execute("INSERT INTO incidents (title, incident_type, latitude, longitude, status) VALUES ('Incident Y', 'MINOR_INJURY', 17.42, 78.43, 'REPORTED');")
            inc_y_id = cur.lastrowid

            # Set all ambulances to BUSY except ambulance #4
            cur.execute("UPDATE ambulances SET status = 'BUSY' WHERE id != 4;")
            cur.execute("UPDATE ambulances SET status = 'AVAILABLE', assigned_incident_id = NULL WHERE id = 4;")

        try:
            # 1. Allocate Incident X -> must succeed using ambulance #4
            res_x = allocate_incident(inc_x_id, db_path=TEMP_TEST_DB)
            self.assertTrue(res_x["success"])
            self.assertEqual(res_x["ambulance"]["id"], 4)

            # 2. Allocate Incident Y -> must fail because ambulance #4 is now active and no other unit exists
            res_y = allocate_incident(inc_y_id, db_path=TEMP_TEST_DB)
            self.assertFalse(res_y["success"])
            self.assertIn("Resource shortage", res_y["error"])

            # 3. Direct DB test: attempt to insert a second active allocation for ambulance #4
            with self.assertRaises(sqlite3.IntegrityError):
                with get_db(TEMP_TEST_DB) as conn:
                    conn.execute(
                        """
                        INSERT INTO allocations (incident_id, ambulance_id, hospital_id, estimated_arrival_minutes, allocation_status)
                        VALUES (?, 4, 1, 10.0, 'ACTIVE');
                        """,
                        (inc_y_id,),
                    )
        finally:
            # Restore ambulances
            with get_db(TEMP_TEST_DB) as conn:
                conn.execute("UPDATE ambulances SET status = 'AVAILABLE' WHERE id NOT IN (1, 4);")


if __name__ == "__main__":
    unittest.main()
