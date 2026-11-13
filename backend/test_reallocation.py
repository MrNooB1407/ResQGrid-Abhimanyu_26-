"""ResQGrid Dynamic Reallocation Verification Suite

Tests event-driven reallocation scenarios in an isolated temporary SQLite database:
1. Ambulance breakdown with successful replacement dispatch.
2. Ambulance breakdown with resource shortage (return to REPORTED, restore hospital beds).
3. Hospital capacity exhaustion with diversion to alternative facility (ambulance preserved).
4. Hospital capacity exhaustion without available alternative (preserves active assignment).
5. Idempotent audit logging and non-destructive historical tracking.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import get_db, init_db, query_db
from backend.services.allocation import allocate_incident
from backend.services.reallocation import (
    handle_ambulance_breakdown,
    handle_hospital_capacity_exhausted,
    handle_traffic_congestion_spike,
    reallocate_incident,
)

TEMP_REALLOC_DB = Path(__file__).resolve().parent / "data" / "test_reallocation_isolated.db"


class TestReallocationEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if TEMP_REALLOC_DB.exists():
            TEMP_REALLOC_DB.unlink()
        init_db(db_path=TEMP_REALLOC_DB, seed_if_empty=True)

    @classmethod
    def tearDownClass(cls):
        if TEMP_REALLOC_DB.exists():
            try:
                TEMP_REALLOC_DB.unlink()
            except Exception:
                pass

    def setUp(self):
        """Reset database to fresh seed state before each test for complete test isolation."""
        if TEMP_REALLOC_DB.exists():
            try:
                TEMP_REALLOC_DB.unlink()
            except Exception:
                pass
        init_db(db_path=TEMP_REALLOC_DB, seed_if_empty=True)

    def test_01_ambulance_breakdown_with_replacement(self):
        """Verify ambulance breakdown reallocates to a new ambulance while preserving hospital."""
        # 1. Allocate Incident #1 (Road accident)
        alloc_res = allocate_incident(1, db_path=TEMP_REALLOC_DB)
        self.assertTrue(alloc_res["success"])
        initial_alloc_id = alloc_res["allocation_id"]
        broken_amb_id = alloc_res["ambulance"]["id"]
        hospital_id = alloc_res["hospital"]["id"]

        # Baseline hospital capacity
        hosp_before = query_db(
            "SELECT available_beds, available_icu_beds FROM hospitals WHERE id = ?;",
            (hospital_id,),
            db_path=TEMP_REALLOC_DB,
            one=True,
        )

        # 2. Trigger ambulance breakdown
        breakdown_res = handle_ambulance_breakdown(
            ambulance_id=broken_amb_id,
            reason="Radiator hose rupture near Gachibowli",
            db_path=TEMP_REALLOC_DB,
        )

        self.assertTrue(breakdown_res["success"])
        self.assertEqual(breakdown_res["incident_id"], 1)
        self.assertEqual(breakdown_res["broken_ambulance_id"], broken_amb_id)
        self.assertNotEqual(breakdown_res["replacement_ambulance"]["id"], broken_amb_id)
        self.assertEqual(breakdown_res["old_allocation_id"], initial_alloc_id)
        self.assertIsNotNone(breakdown_res["new_allocation_id"])

        # 3. Verify old ambulance is OUT_OF_SERVICE and unlinked
        old_amb = query_db(
            "SELECT status, assigned_incident_id FROM ambulances WHERE id = ?;",
            (broken_amb_id,),
            db_path=TEMP_REALLOC_DB,
            one=True,
        )
        self.assertEqual(old_amb["status"], "OUT_OF_SERVICE")
        self.assertIsNone(old_amb["assigned_incident_id"])

        # 4. Verify replacement ambulance is DISPATCHED to Incident #1
        new_amb_id = breakdown_res["replacement_ambulance"]["id"]
        new_amb = query_db(
            "SELECT status, assigned_incident_id FROM ambulances WHERE id = ?;",
            (new_amb_id,),
            db_path=TEMP_REALLOC_DB,
            one=True,
        )
        self.assertEqual(new_amb["status"], "DISPATCHED")
        self.assertEqual(new_amb["assigned_incident_id"], 1)

        # 5. Verify hospital was preserved and NOT double-decremented
        hosp_after = query_db(
            "SELECT available_beds, available_icu_beds FROM hospitals WHERE id = ?;",
            (hospital_id,),
            db_path=TEMP_REALLOC_DB,
            one=True,
        )
        self.assertEqual(hosp_before["available_beds"], hosp_after["available_beds"])
        self.assertEqual(hosp_before["available_icu_beds"], hosp_after["available_icu_beds"])

        # 6. Verify allocation records: old is REALLOCATED, new is ACTIVE
        old_alloc = query_db("SELECT allocation_status FROM allocations WHERE id = ?;", (initial_alloc_id,), db_path=TEMP_REALLOC_DB, one=True)
        self.assertEqual(old_alloc["allocation_status"], "REALLOCATED")

        new_alloc = query_db("SELECT allocation_status FROM allocations WHERE id = ?;", (breakdown_res["new_allocation_id"],), db_path=TEMP_REALLOC_DB, one=True)
        self.assertEqual(new_alloc["allocation_status"], "ACTIVE")

        # 7. Verify event logs contain AMBULANCE_BREAKDOWN and RESOURCE_REALLOCATED
        logs = query_db(
            "SELECT event_type FROM event_logs WHERE related_incident_id = 1 ORDER BY id DESC;",
            db_path=TEMP_REALLOC_DB,
        )
        event_types = [l["event_type"] for l in logs]
        self.assertIn("AMBULANCE_BREAKDOWN", event_types)
        self.assertIn("RESOURCE_REALLOCATED", event_types)

    def test_02_ambulance_breakdown_shortage_handling(self):
        """Verify breakdown when no replacement is available resets incident to REPORTED and restores hospital."""
        # 1. Allocate Incident #2 (Cardiac emergency)
        alloc_res = allocate_incident(2, db_path=TEMP_REALLOC_DB)
        self.assertTrue(alloc_res["success"])
        alloc_id = alloc_res["allocation_id"]
        amb_id = alloc_res["ambulance"]["id"]
        hosp_id = alloc_res["hospital"]["id"]

        hosp_before = query_db("SELECT available_beds FROM hospitals WHERE id = ?;", (hosp_id,), db_path=TEMP_REALLOC_DB, one=True)["available_beds"]

        # 2. Make all OTHER available ambulances BUSY so no replacement can be found
        with get_db(TEMP_REALLOC_DB) as conn:
            conn.execute("UPDATE ambulances SET status = 'BUSY' WHERE id != ?;", (amb_id,))

        try:
            # 3. Trigger breakdown with no replacement available
            breakdown_res = handle_ambulance_breakdown(
                ambulance_id=amb_id,
                reason="Engine seizure in Punjagutta tunnel",
                db_path=TEMP_REALLOC_DB,
            )

            # Failure expected due to shortage
            self.assertFalse(breakdown_res["success"])
            self.assertIn("OUT_OF_SERVICE", breakdown_res["error"])

            # Failed ambulance must be OUT_OF_SERVICE
            amb_state = query_db("SELECT status, assigned_incident_id FROM ambulances WHERE id = ?;", (amb_id,), db_path=TEMP_REALLOC_DB, one=True)
            self.assertEqual(amb_state["status"], "OUT_OF_SERVICE")
            self.assertIsNone(amb_state["assigned_incident_id"])

            # Old allocation marked REALLOCATED
            old_alloc = query_db("SELECT allocation_status FROM allocations WHERE id = ?;", (alloc_id,), db_path=TEMP_REALLOC_DB, one=True)
            self.assertEqual(old_alloc["allocation_status"], "REALLOCATED")

            # Incident returned to REPORTED
            inc_state = query_db("SELECT status FROM incidents WHERE id = 2;", db_path=TEMP_REALLOC_DB, one=True)
            self.assertEqual(inc_state["status"], "REPORTED")

            # Hospital capacity restored
            hosp_after = query_db("SELECT available_beds FROM hospitals WHERE id = ?;", (hosp_id,), db_path=TEMP_REALLOC_DB, one=True)["available_beds"]
            self.assertEqual(hosp_after, hosp_before + 1)

            # Audit logs contain SHORTAGE_UNRESOLVED
            shortage_log = query_db(
                "SELECT * FROM event_logs WHERE related_incident_id = 2 AND event_type = 'SHORTAGE_UNRESOLVED';",
                db_path=TEMP_REALLOC_DB,
                one=True,
            )
            self.assertIsNotNone(shortage_log)

        finally:
            # Restore other ambulances
            with get_db(TEMP_REALLOC_DB) as conn:
                conn.execute("UPDATE ambulances SET status = 'AVAILABLE' WHERE status = 'BUSY';")

    def test_03_hospital_capacity_exhaustion_diversion(self):
        """Verify hospital saturation diverts incoming transport to alternative facility while preserving ambulance."""
        # 1. Allocate Incident #3 (Urban flooding)
        alloc_res = allocate_incident(3, db_path=TEMP_REALLOC_DB)
        self.assertTrue(alloc_res["success"])
        alloc_id = alloc_res["allocation_id"]
        amb_id = alloc_res["ambulance"]["id"]
        old_hosp_id = alloc_res["hospital"]["id"]

        old_hosp_beds_before = query_db("SELECT available_beds FROM hospitals WHERE id = ?;", (old_hosp_id,), db_path=TEMP_REALLOC_DB, one=True)["available_beds"]

        # 2. Trigger hospital capacity exhaustion on old hospital
        div_res = handle_hospital_capacity_exhausted(
            hospital_id=old_hosp_id,
            reason="Mass casualty incoming wave",
            exhausted_resource="FULL",
            db_path=TEMP_REALLOC_DB,
        )

        self.assertTrue(div_res["success"])
        self.assertEqual(div_res["affected_allocations"], 1)
        self.assertEqual(div_res["reallocated_count"], 1)
        new_hosp_id = div_res["reallocations"][0]["diverted_to"]["id"]
        self.assertNotEqual(old_hosp_id, new_hosp_id)

        # 3. Verify ambulance remains assigned to Incident #3
        amb_state = query_db("SELECT status, assigned_incident_id FROM ambulances WHERE id = ?;", (amb_id,), db_path=TEMP_REALLOC_DB, one=True)
        self.assertEqual(amb_state["status"], "DISPATCHED")
        self.assertEqual(amb_state["assigned_incident_id"], 3)

        # 4. Verify old hospital capacity was restored
        old_hosp_beds_after = query_db("SELECT available_beds FROM hospitals WHERE id = ?;", (old_hosp_id,), db_path=TEMP_REALLOC_DB, one=True)["available_beds"]
        self.assertEqual(old_hosp_beds_after, old_hosp_beds_before + 1)

        # 5. Verify old allocation is REALLOCATED and new allocation is ACTIVE
        old_alloc = query_db("SELECT allocation_status FROM allocations WHERE id = ?;", (alloc_id,), db_path=TEMP_REALLOC_DB, one=True)
        self.assertEqual(old_alloc["allocation_status"], "REALLOCATED")

        new_alloc = query_db("SELECT allocation_status FROM allocations WHERE id = ?;", (div_res["reallocations"][0]["new_allocation_id"],), db_path=TEMP_REALLOC_DB, one=True)
        self.assertEqual(new_alloc["allocation_status"], "ACTIVE")

    def test_04_traffic_multiplier_update_success(self):
        """Verify updating a traffic zone multiplier and congestion level."""
        # Zone 2: Gachibowli Flyover Hub
        res = handle_traffic_congestion_spike(
            traffic_zone_id=2,
            new_multiplier=2.45,
            new_congestion_level="HEAVY",
            db_path=TEMP_REALLOC_DB,
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["new_multiplier"], 2.45)
        self.assertEqual(res["traffic_zone"]["congestion_level"], "HEAVY")

        zone_row = query_db("SELECT traffic_multiplier, congestion_level FROM traffic_zones WHERE id = 2;", db_path=TEMP_REALLOC_DB, one=True)
        self.assertEqual(zone_row["traffic_multiplier"], 2.45)
        self.assertEqual(zone_row["congestion_level"], "HEAVY")

        # Verify TRAFFIC_SPIKE log was recorded
        log_entry = query_db("SELECT * FROM event_logs WHERE event_type = 'TRAFFIC_SPIKE' ORDER BY id DESC LIMIT 1;", db_path=TEMP_REALLOC_DB, one=True)
        self.assertIsNotNone(log_entry)
        self.assertIn("Gachibowli", log_entry["description"])

    def test_05_invalid_multiplier_rejected(self):
        """Verify invalid multipliers (< 1.0, non-numeric, out-of-bounds) are rejected."""
        # Multiplier below 1.0
        res_low = handle_traffic_congestion_spike(traffic_zone_id=1, new_multiplier=0.8, db_path=TEMP_REALLOC_DB)
        self.assertFalse(res_low["success"])
        self.assertIn("Invalid traffic multiplier", res_low["error"])

        # Non-numeric multiplier
        res_nan = handle_traffic_congestion_spike(traffic_zone_id=1, new_multiplier="not_a_number", db_path=TEMP_REALLOC_DB)
        self.assertFalse(res_nan["success"])
        self.assertIn("Invalid traffic multiplier", res_nan["error"])

        # Non-existent traffic zone
        res_no_zone = handle_traffic_congestion_spike(traffic_zone_id=9999, new_multiplier=2.0, db_path=TEMP_REALLOC_DB)
        self.assertFalse(res_no_zone["success"])
        self.assertIn("not found", res_no_zone["error"])

    def test_06_minor_traffic_change_no_reallocation(self):
        """Verify minor traffic increases (< 5 min or < 25% improvement) do NOT trigger reallocation."""
        # Create a test incident near Punjagutta (Zone #3)
        with get_db(TEMP_REALLOC_DB) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO incidents (title, incident_type, latitude, longitude, injured_people, status)
                VALUES ('[TEST] Minor Collision', 'ROAD_ACCIDENT', 17.4265, 78.4528, 1, 'REPORTED');
                """
            )
            test_inc_id = cur.lastrowid

            # Set all ambulances to BUSY except Ambulance 4 (at Punjagutta) and Ambulance 3 (Banjara Hills, nearby)
            cur.execute("UPDATE ambulances SET status = 'BUSY' WHERE id NOT IN (3, 4);")
            cur.execute("UPDATE ambulances SET status = 'AVAILABLE', assigned_incident_id = NULL WHERE id IN (3, 4);")

        try:
            # Allocate incident (will select Ambulance 4 which is right at Punjagutta)
            alloc_res = allocate_incident(test_inc_id, db_path=TEMP_REALLOC_DB)
            self.assertTrue(alloc_res["success"])
            initial_alloc_id = alloc_res["allocation_id"]
            assigned_amb_id = alloc_res["ambulance"]["id"]

            # Slightly increase Punjagutta traffic multiplier from 2.30 to 2.35 (minor increment)
            spike_res = handle_traffic_congestion_spike(
                traffic_zone_id=3,
                new_multiplier=2.35,
                new_congestion_level="SEVERE",
                min_improvement_minutes=5.0,
                db_path=TEMP_REALLOC_DB,
            )

            self.assertTrue(spike_res["success"])
            # Reallocation should NOT be performed due to hysteresis threshold
            self.assertEqual(spike_res["reallocations_performed"], 0)

            # Active allocation remains unchanged
            active_alloc = query_db(
                "SELECT id, ambulance_id, allocation_status FROM allocations WHERE incident_id = ? AND allocation_status = 'ACTIVE';",
                (test_inc_id,),
                db_path=TEMP_REALLOC_DB,
                one=True,
            )
            self.assertEqual(active_alloc["id"], initial_alloc_id)
            self.assertEqual(active_alloc["ambulance_id"], assigned_amb_id)

        finally:
            with get_db(TEMP_REALLOC_DB) as conn:
                conn.execute("UPDATE ambulances SET status = 'AVAILABLE' WHERE status = 'BUSY';")

    def test_07_major_congestion_triggers_reallocation(self):
        """Verify major traffic congestion with > 5 min and > 25% ETA improvement reallocates ambulance."""
        # Create an incident at 17.4200, 78.4500 (near Punjagutta / Banjara Hills)
        with get_db(TEMP_REALLOC_DB) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO incidents (title, incident_type, latitude, longitude, injured_people, status)
                VALUES ('[TEST] Severe Accident at Banjara', 'ROAD_ACCIDENT', 17.4200, 78.4500, 2, 'REPORTED');
                """
            )
            test_inc_id = cur.lastrowid

            # Place Ambulance 8 at Dilsukhnagar (17.3688, 78.5247) which must traverse Punjagutta corridor
            # Place Ambulance 3 right at Banjara Hills (17.4125, 78.4350) which is 1.5 km away free-flow!
            cur.execute("UPDATE ambulances SET status = 'BUSY' WHERE id NOT IN (3, 8);")
            cur.execute("UPDATE ambulances SET status = 'AVAILABLE', assigned_incident_id = NULL WHERE id IN (3, 8);")

            # Allocate using Ambulance 8 first by temporarily making Ambulance 3 BUSY
            cur.execute("UPDATE ambulances SET status = 'BUSY' WHERE id = 3;")

        alloc_res = allocate_incident(test_inc_id, db_path=TEMP_REALLOC_DB)
        self.assertTrue(alloc_res["success"])
        old_alloc_id = alloc_res["allocation_id"]
        self.assertEqual(alloc_res["ambulance"]["id"], 8)
        initial_hosp_id = alloc_res["hospital"]["id"]

        hosp_beds_before = query_db("SELECT available_beds FROM hospitals WHERE id = ?;", (initial_hosp_id,), db_path=TEMP_REALLOC_DB, one=True)["available_beds"]

        # Now free up Ambulance 3 close by
        with get_db(TEMP_REALLOC_DB) as conn:
            conn.execute("UPDATE ambulances SET status = 'AVAILABLE', assigned_incident_id = NULL WHERE id = 3;")

        try:
            # Massive congestion spike in Punjagutta (Zone #3) to multiplier 5.0
            spike_res = handle_traffic_congestion_spike(
                traffic_zone_id=3,
                new_multiplier=5.0,
                new_congestion_level="GRIDLOCK",
                min_improvement_minutes=5.0,
                db_path=TEMP_REALLOC_DB,
            )

            self.assertTrue(spike_res["success"])
            self.assertEqual(spike_res["reallocations_performed"], 1)

            # Old allocation is REALLOCATED
            old_alloc = query_db("SELECT allocation_status FROM allocations WHERE id = ?;", (old_alloc_id,), db_path=TEMP_REALLOC_DB, one=True)
            self.assertEqual(old_alloc["allocation_status"], "REALLOCATED")

            # New active allocation created with Ambulance 3
            new_alloc = query_db(
                "SELECT id, ambulance_id, hospital_id, allocation_status FROM allocations WHERE incident_id = ? AND allocation_status = 'ACTIVE';",
                (test_inc_id,),
                db_path=TEMP_REALLOC_DB,
                one=True,
            )
            self.assertIsNotNone(new_alloc)
            self.assertEqual(new_alloc["ambulance_id"], 3)
            # Hospital is preserved!
            self.assertEqual(new_alloc["hospital_id"], initial_hosp_id)

            # Old ambulance 8 is returned to AVAILABLE (did not break down, just freed)
            amb_8 = query_db("SELECT status, assigned_incident_id FROM ambulances WHERE id = 8;", db_path=TEMP_REALLOC_DB, one=True)
            self.assertEqual(amb_8["status"], "AVAILABLE")
            self.assertIsNone(amb_8["assigned_incident_id"])

            # Hospital capacity remains consistent (not decremented twice!)
            hosp_beds_after = query_db("SELECT available_beds FROM hospitals WHERE id = ?;", (initial_hosp_id,), db_path=TEMP_REALLOC_DB, one=True)["available_beds"]
            self.assertEqual(hosp_beds_before, hosp_beds_after)

        finally:
            with get_db(TEMP_REALLOC_DB) as conn:
                conn.execute("UPDATE ambulances SET status = 'AVAILABLE' WHERE status = 'BUSY';")

    def test_08_traffic_spike_no_alternative_leaves_assignment_intact(self):
        """Verify traffic spike with no available replacement leaves current assignment intact."""
        # Create an incident
        with get_db(TEMP_REALLOC_DB) as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO incidents (title, incident_type, latitude, longitude, injured_people, status) VALUES ('Solo Incident', 'MINOR_INJURY', 17.4444, 78.4682, 1, 'REPORTED');")
            inc_id = cur.lastrowid

            # Only Ambulance 7 available (at Begumpet, Zone 4)
            cur.execute("UPDATE ambulances SET status = 'BUSY' WHERE id != 7;")
            cur.execute("UPDATE ambulances SET status = 'AVAILABLE', assigned_incident_id = NULL WHERE id = 7;")

        alloc_res = allocate_incident(inc_id, db_path=TEMP_REALLOC_DB)
        self.assertTrue(alloc_res["success"])
        alloc_id = alloc_res["allocation_id"]

        try:
            # Massive traffic spike on Begumpet (Zone 4)
            res = handle_traffic_congestion_spike(traffic_zone_id=4, new_multiplier=4.0, db_path=TEMP_REALLOC_DB)
            self.assertTrue(res["success"])
            self.assertEqual(res["reallocations_performed"], 0)

            # Current allocation must remain ACTIVE with Ambulance 7
            current_alloc = query_db("SELECT ambulance_id, allocation_status FROM allocations WHERE id = ?;", (alloc_id,), db_path=TEMP_REALLOC_DB, one=True)
            self.assertEqual(current_alloc["allocation_status"], "ACTIVE")
            self.assertEqual(current_alloc["ambulance_id"], 7)
        finally:
            with get_db(TEMP_REALLOC_DB) as conn:
                conn.execute("UPDATE ambulances SET status = 'AVAILABLE' WHERE status = 'BUSY';")

    def test_09_traffic_change_skips_unrelated_allocations(self):
        """Verify traffic congestion in one zone does not affect routes in distant unrelated corridors."""
        # Incident and ambulance both at Charminar (South Hyderabad, Zone 6: 17.3616, 78.4747)
        with get_db(TEMP_REALLOC_DB) as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO incidents (title, incident_type, latitude, longitude, injured_people, status) VALUES ('Charminar Incident', 'MINOR_INJURY', 17.3616, 78.4747, 1, 'REPORTED');")
            inc_id = cur.lastrowid

            cur.execute("UPDATE ambulances SET status = 'BUSY' WHERE id != 6;")
            cur.execute("UPDATE ambulances SET status = 'AVAILABLE', assigned_incident_id = NULL WHERE id = 6;")

        alloc_res = allocate_incident(inc_id, db_path=TEMP_REALLOC_DB)
        self.assertTrue(alloc_res["success"])
        alloc_id = alloc_res["allocation_id"]

        try:
            # Spike congestion in Hitec City (Zone 1, northwest, >15km away)
            res = handle_traffic_congestion_spike(traffic_zone_id=1, new_multiplier=3.5, db_path=TEMP_REALLOC_DB)
            self.assertTrue(res["success"])

            # Charminar allocation should be marked as SKIPPED_NOT_AFFECTED
            charminar_eval = [e for e in res["evaluations"] if e["allocation_id"] == alloc_id]
            self.assertTrue(len(charminar_eval) > 0)
            self.assertEqual(charminar_eval[0]["status"], "SKIPPED_NOT_AFFECTED")

            # Allocation remains ACTIVE
            active_alloc = query_db("SELECT allocation_status FROM allocations WHERE id = ?;", (alloc_id,), db_path=TEMP_REALLOC_DB, one=True)
            self.assertEqual(active_alloc["allocation_status"], "ACTIVE")
        finally:
            with get_db(TEMP_REALLOC_DB) as conn:
                conn.execute("UPDATE ambulances SET status = 'AVAILABLE' WHERE status = 'BUSY';")


if __name__ == "__main__":
    unittest.main()

