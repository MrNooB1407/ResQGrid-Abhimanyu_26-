"""ResQGrid Seed Data Module

Populates the SQLite database with simulated Hyderabad benchmark emergency data
including hospitals, ambulances, active incidents, and traffic congestion zones.
All entries are explicitly flagged as simulated data.
"""

import sqlite3
import sys
from pathlib import Path
from typing import Dict, Optional, Union

# Handle module imports both directly and as part of the package
try:
    from backend.database import get_db, get_db_connection
except ImportError:
    # If run directly as script from root or backend folder
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from backend.database import get_db, get_db_connection

# ---------------------------------------------------------------------------
# Simulated Datasets (Hyderabad Plausible Coordinates)
# ---------------------------------------------------------------------------

SIMULATED_HOSPITALS = [
    (
        "[SIMULATED] Apollo Hospitals, Jubilee Hills",
        17.4325,
        78.4071,
        350,   # total_beds
        42,    # available_beds
        60,    # total_icu_beds
        5,     # available_icu_beds (scarce!)
        3,     # available_ventilators
        50,    # emergency_capacity
        "Level-1 Trauma, Cardiology, Neurology, Pulmonology, Orthopedics",
    ),
    (
        "[SIMULATED] KIMS Hospitals, Secunderabad",
        17.4419,
        78.4883,
        400,
        58,
        70,
        8,
        4,
        60,
        "Cardiology, Critical Care, Polytrauma, Organ Transplant",
    ),
    (
        "[SIMULATED] Yashoda Hospitals, Malakpet",
        17.3756,
        78.5028,
        300,
        35,
        45,
        4,
        2,
        40,
        "Emergency Medicine, Cardiology, Neurology, General Surgery",
    ),
    (
        "[SIMULATED] Osmania General Hospital, Afzal Gunj",
        17.3776,
        78.4764,
        650,
        120,
        80,
        14,
        6,
        100,
        "Public Level-1 Trauma, Mass Casualty, Burn Center, General Surgery",
    ),
    (
        "[SIMULATED] CARE Hospitals, Banjara Hills",
        17.4184,
        78.4487,
        280,
        22,
        40,
        3,     # available_icu_beds (highly contested!)
        2,
        35,
        "Cardiology, Cardiac Surgery, Interventional Cath Lab, Nephrology",
    ),
]

SIMULATED_AMBULANCES = [
    ("AMB-HYD-01", 17.4401, 78.3489, "AVAILABLE", "ALS", None, 0.0),  # Gachibowli Junction
    ("AMB-HYD-02", 17.4300, 78.4111, "AVAILABLE", "ALS", None, 0.0),  # Jubilee Hills Check Post
    ("AMB-HYD-03", 17.4125, 78.4350, "AVAILABLE", "BLS", None, 0.0),  # Banjara Hills Rd 12
    ("AMB-HYD-04", 17.4265, 78.4528, "AVAILABLE", "ALS", None, 0.0),  # Punjagutta Circle
    ("AMB-HYD-05", 17.4411, 78.4983, "AVAILABLE", "BLS", None, 0.0),  # Secunderabad Clock Tower
    ("AMB-HYD-06", 17.3616, 78.4747, "AVAILABLE", "BLS", None, 0.0),  # Charminar South
    ("AMB-HYD-07", 17.4444, 78.4682, "AVAILABLE", "PATIENT_TRANSPORT", None, 0.0),  # Begumpet
    ("AMB-HYD-08", 17.3688, 78.5247, "AVAILABLE", "ALS", None, 0.0),  # Dilsukhnagar Metro
]

SIMULATED_INCIDENTS = [
    (
        "[SIMULATED] Multi-Vehicle Collision on Gachibowli ORR",
        "ROAD_ACCIDENT",
        "[SIMULATED] Severe collision involving two cars and a passenger van near Gachibowli ORR exit. 5 passengers with polytrauma and heavy bleeding; requires ALS ambulances and immediate Level-1 trauma/ICU beds.",
        17.4422,
        78.3512,
        5,      # affected_people
        5,      # injured_people
        88.0,   # severity_score
        "CRITICAL",
        "REPORTED",
    ),
    (
        "[SIMULATED] Acute STEMI & Refractory Cardiac Emergency",
        "CARDIAC_EMERGENCY",
        "[SIMULATED] 64-year-old patient collapsed at residence on Banjara Hills Road No. 10. Bystander CPR initiated; acute myocardial infarction suspected; requires immediate ALS ambulance with defibrillator and emergency cardiac catheterization.",
        17.4172,
        78.4415,
        1,      # affected_people
        1,      # injured_people
        94.0,   # severity_score
        "CRITICAL",
        "REPORTED",
    ),
    (
        "[SIMULATED] Low-Lying Flash Flooding & Tenement Structural Inundation",
        "URBAN_FLOODING",
        "[SIMULATED] Stormwater inundation in Begumpet Nala basin. 12 residents trapped, 4 injured including hypothermic elderly citizens and trauma from debris. Requires multiple transport units and emergency triage capacity.",
        17.4468,
        78.4639,
        12,     # affected_people
        4,      # injured_people
        76.0,   # severity_score
        "HIGH",
        "REPORTED",
    ),
]

SIMULATED_TRAFFIC_ZONES = [
    ("Hitec City Corridor", 17.4474, 78.3762, "HEAVY", 1.85),
    ("Gachibowli Flyover Hub", 17.4401, 78.3489, "MODERATE", 1.35),
    ("Punjagutta Intersection", 17.4265, 78.4528, "SEVERE", 2.30),
    ("Begumpet Main Road", 17.4444, 78.4682, "HEAVY", 1.70),
    ("Secunderabad Station Road", 17.4339, 78.5015, "MODERATE", 1.40),
    ("Charminar Heritage Zone", 17.3616, 78.4747, "SEVERE", 2.10),
    ("Mehdipatnam Ring Road", 17.3916, 78.4398, "MODERATE", 1.45),
    ("Dilsukhnagar Commercial Zone", 17.3688, 78.5247, "LOW", 1.10),
]


def seed_data(
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> Dict[str, int]:
    """Insert simulated benchmark records into the database.
    
    Checks if records already exist to ensure idempotency and prevent duplicate records.
    """
    def _execute_seeding(connection: sqlite3.Connection) -> Dict[str, int]:
        cursor = connection.cursor()

        # Idempotency check: verify if database already contains records
        cursor.execute("SELECT COUNT(*) FROM hospitals")
        if cursor.fetchone()[0] > 0:
            return {
                "hospitals": 0,
                "ambulances": 0,
                "incidents": 0,
                "traffic_zones": 0,
                "event_logs": 0,
                "status": "SKIPPED_ALREADY_SEEDED",
            }

        # 1. Seed Hospitals
        cursor.executemany(
            """
            INSERT INTO hospitals (
                name, latitude, longitude, total_beds, available_beds,
                total_icu_beds, available_icu_beds, available_ventilators,
                emergency_capacity, specialties
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            SIMULATED_HOSPITALS,
        )
        hospitals_count = len(SIMULATED_HOSPITALS)

        # 2. Seed Ambulances
        cursor.executemany(
            """
            INSERT INTO ambulances (
                ambulance_number, latitude, longitude, status, capability,
                assigned_incident_id, current_speed
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            SIMULATED_AMBULANCES,
        )
        ambulances_count = len(SIMULATED_AMBULANCES)

        # 3. Seed Incidents
        cursor.executemany(
            """
            INSERT INTO incidents (
                title, incident_type, description, latitude, longitude,
                affected_people, injured_people, severity_score, severity_level, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            SIMULATED_INCIDENTS,
        )
        incidents_count = len(SIMULATED_INCIDENTS)

        # 4. Seed Traffic Zones
        cursor.executemany(
            """
            INSERT INTO traffic_zones (
                zone_name, latitude, longitude, congestion_level, traffic_multiplier
            ) VALUES (?, ?, ?, ?, ?);
            """,
            SIMULATED_TRAFFIC_ZONES,
        )
        traffic_count = len(SIMULATED_TRAFFIC_ZONES)

        # 5. Seed Initial System Event Log
        cursor.execute(
            """
            INSERT INTO event_logs (event_type, description, related_incident_id)
            VALUES (?, ?, ?);
            """,
            (
                "SYSTEM_INIT",
                "[SIMULATED] ResQGrid database initialized with benchmark Hyderabad emergency response dataset.",
                None,
            ),
        )

        return {
            "hospitals": hospitals_count,
            "ambulances": ambulances_count,
            "incidents": incidents_count,
            "traffic_zones": traffic_count,
            "event_logs": 1,
            "status": "SUCCESS",
        }

    if conn is not None:
        return _execute_seeding(conn)
    else:
        with get_db(db_path) as managed_conn:
            return _execute_seeding(managed_conn)


if __name__ == "__main__":
    from backend.database import create_tables, get_db_connection

    print("Running ResQGrid seed script...")
    with get_db() as connection:
        create_tables(connection)
        summary = seed_data(connection)
    print("Seed complete. Summary:", summary)

