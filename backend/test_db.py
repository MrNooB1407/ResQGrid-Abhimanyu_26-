"""ResQGrid Database Verification and Test Suite

Verifies:
1. Creation of all six tables.
2. Correct seeding counts (8 ambulances, 5 hospitals, 3 incidents, 8 traffic zones).
3. SQLite foreign key constraint enforcement.
4. Unique active allocation constraint for ambulances.
5. Idempotent initialization (no duplication on subsequent runs).
6. Helper query functions.
"""

import os
import sqlite3
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import (
    DEFAULT_DB_PATH,
    create_tables,
    execute_db,
    get_db,
    get_db_connection,
    init_db,
    query_db,
)
from backend.seed import seed_data


def run_tests() -> bool:
    print("=" * 60)
    print("ResQGrid Database Verification Suite")
    print(f"Target Database: {DEFAULT_DB_PATH}")
    print("=" * 60)

    # 1. Initialize and Seed Database
    print("\n[Step 1] Initializing database and applying seeds...")
    seeded = init_db()
    print(f"-> init_db() executed. First-time seed occurred: {seeded}")

    # 2. Verify Table Existence
    print("\n[Step 2] Verifying table existence...")
    expected_tables = {
        "incidents",
        "ambulances",
        "hospitals",
        "allocations",
        "traffic_zones",
        "event_logs",
    }
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        found_tables = {row[0] for row in cursor.fetchall()}

    missing_tables = expected_tables - found_tables
    if missing_tables:
        print(f"FAILED: Missing tables: {missing_tables}")
        return False
    print(f"SUCCESS: All {len(expected_tables)} required tables exist: {sorted(list(found_tables))}")

    # 3. Verify Seed Counts
    print("\n[Step 3] Verifying seed records...")
    counts = {
        "ambulances": query_db("SELECT COUNT(*) AS c FROM ambulances", one=True)["c"],
        "hospitals": query_db("SELECT COUNT(*) AS c FROM hospitals", one=True)["c"],
        "incidents": query_db("SELECT COUNT(*) AS c FROM incidents", one=True)["c"],
        "traffic_zones": query_db("SELECT COUNT(*) AS c FROM traffic_zones", one=True)["c"],
        "event_logs": query_db("SELECT COUNT(*) AS c FROM event_logs", one=True)["c"],
    }

    assert counts["ambulances"] == 8, f"Expected 8 ambulances, got {counts['ambulances']}"
    assert counts["hospitals"] == 5, f"Expected 5 hospitals, got {counts['hospitals']}"
    assert counts["incidents"] == 3, f"Expected 3 incidents, got {counts['incidents']}"
    assert counts["traffic_zones"] == 8, f"Expected 8 traffic zones, got {counts['traffic_zones']}"
    assert counts["event_logs"] >= 1, f"Expected at least 1 event log, got {counts['event_logs']}"

    print(f"SUCCESS: Seed counts match specification:")
    print(f"  - Ambulances: {counts['ambulances']}/8")
    print(f"  - Hospitals: {counts['hospitals']}/5")
    print(f"  - Incidents: {counts['incidents']}/3")
    print(f"  - Traffic Zones: {counts['traffic_zones']}/8")
    print(f"  - Event Logs: {counts['event_logs']}")

    # 4. Verify Foreign Key Enforcement
    print("\n[Step 4] Verifying Foreign Key Enforcement...")
    fk_enforced = False
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Attempt to insert an allocation pointing to non-existent IDs
            cursor.execute(
                """
                INSERT INTO allocations (
                    incident_id, ambulance_id, hospital_id, estimated_arrival_minutes, decision_reason
                ) VALUES (99999, 1, 1, 10.5, 'Test Invalid Foreign Key');
                """
            )
        except sqlite3.IntegrityError as e:
            fk_enforced = True
            print(f"SUCCESS: Foreign key violation caught as expected -> {e}")

    if not fk_enforced:
        print("FAILED: Foreign key constraint was not enforced!")
        return False

    # 5. Verify Ambulance Single Active Assignment Constraint
    print("\n[Step 5] Verifying single active allocation constraint for ambulances...")
    active_constraint_enforced = False
    with get_db() as conn:
        cursor = conn.cursor()
        # Insert a valid active allocation
        cursor.execute(
            """
            INSERT INTO allocations (
                incident_id, ambulance_id, hospital_id, estimated_arrival_minutes, allocation_status, decision_reason
            ) VALUES (1, 1, 1, 8.0, 'ACTIVE', 'Primary dispatch');
            """
        )
        allocation_id = cursor.lastrowid
        try:
            # Attempt to insert a second active allocation for the same ambulance (id=1)
            cursor.execute(
                """
                INSERT INTO allocations (
                    incident_id, ambulance_id, hospital_id, estimated_arrival_minutes, allocation_status, decision_reason
                ) VALUES (2, 1, 2, 15.0, 'ACTIVE', 'Conflicting second active assignment');
                """
            )
        except sqlite3.IntegrityError as e:
            active_constraint_enforced = True
            print(f"SUCCESS: Multiple active assignment prevented as expected -> {e}")
        finally:
            # Clean up the test allocation to keep seed dataset clean
            cursor.execute("DELETE FROM allocations WHERE id = ?", (allocation_id,))

    if not active_constraint_enforced:
        print("FAILED: Ambulance active assignment uniqueness not enforced!")
        return False

    # 6. Verify Idempotence (Re-running does not duplicate seed data)
    print("\n[Step 6] Verifying Idempotence of initialization and seeding...")
    reseed_result = seed_data()
    print(f"-> Reseed execution result: {reseed_result}")

    recheck_counts = {
        "ambulances": query_db("SELECT COUNT(*) AS c FROM ambulances", one=True)["c"],
        "hospitals": query_db("SELECT COUNT(*) AS c FROM hospitals", one=True)["c"],
        "incidents": query_db("SELECT COUNT(*) AS c FROM incidents", one=True)["c"],
        "traffic_zones": query_db("SELECT COUNT(*) AS c FROM traffic_zones", one=True)["c"],
    }

    assert recheck_counts == {
        "ambulances": 8,
        "hospitals": 5,
        "incidents": 3,
        "traffic_zones": 8,
    }, f"Count changed after re-running seed: {recheck_counts}"
    print("SUCCESS: Reseed was safely skipped, no duplicate records created.")

    # 7. Verify Data Quality & Simulated Flag
    print("\n[Step 7] Verifying simulated tags and sample data...")
    incident = query_db("SELECT * FROM incidents WHERE id = 1", one=True)
    assert "[SIMULATED]" in incident["title"], "Incident title missing [SIMULATED] tag"
    print(f"Sample Incident: #{incident['id']} '{incident['title']}' | Severity: {incident['severity_level']} ({incident['severity_score']})")

    hospital = query_db("SELECT * FROM hospitals WHERE id = 1", one=True)
    assert "[SIMULATED]" in hospital["name"], "Hospital name missing [SIMULATED] tag"
    print(f"Sample Hospital: #{hospital['id']} '{hospital['name']}' | Beds: {hospital['available_beds']}/{hospital['total_beds']} | ICU: {hospital['available_icu_beds']}/{hospital['total_icu_beds']}")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY! Database layer is verified and ready.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)

