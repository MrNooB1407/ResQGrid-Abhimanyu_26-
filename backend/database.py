"""ResQGrid Database Module

Manages SQLite database connections, schema initialization, foreign key enforcement,
and parameterized helper operations using Python's built-in sqlite3.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Base directories
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "resqgrid.db"


def get_db_path(db_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolve and ensure the directory exists for the database file."""
    target_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    return target_path


def get_db_connection(db_path: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
    """Create and configure a SQLite connection with foreign keys and Row factory enabled."""
    resolved_path = get_db_path(db_path)
    conn = sqlite3.connect(
        str(resolved_path),
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        timeout=10.0,
    )
    # Enable dict-like column access
    conn.row_factory = sqlite3.Row
    # Strictly enforce foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_db(db_path: Optional[Union[str, Path]] = None):
    """Context manager for database connections, handling commit, rollback and cleanup."""
    conn = get_db_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query_db(
    query: str,
    args: Union[tuple, list, dict] = (),
    one: bool = False,
    db_path: Optional[Union[str, Path]] = None,
) -> Union[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Execute a parameterized SELECT query and return rows as standard Python dictionaries."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, args)
        rows = cursor.fetchall()
        if not rows:
            return None if one else []
        results = [dict(row) for row in rows]
        return results[0] if one else results


def execute_db(
    query: str,
    args: Union[tuple, list, dict] = (),
    db_path: Optional[Union[str, Path]] = None,
) -> int:
    """Execute a parameterized INSERT/UPDATE/DELETE query and return the lastrowid."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, args)
        return cursor.lastrowid


def executemany_db(
    query: str,
    seq_of_args: List[Union[tuple, list, dict]],
    db_path: Optional[Union[str, Path]] = None,
) -> int:
    """Execute a batch parameterized query and return total affected rows."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.executemany(query, seq_of_args)
        return cursor.rowcount


def create_tables(conn: sqlite3.Connection) -> None:
    """Create all required ResQGrid tables and constraints if they do not exist."""
    cursor = conn.cursor()

    # 1. Incidents Table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            incident_type TEXT NOT NULL,
            description TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            affected_people INTEGER NOT NULL DEFAULT 0,
            injured_people INTEGER NOT NULL DEFAULT 0,
            severity_score REAL NOT NULL DEFAULT 0.0,
            severity_level TEXT NOT NULL DEFAULT 'LOW',
            status TEXT NOT NULL DEFAULT 'REPORTED',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 2. Ambulances Table
    # Constraint: An ambulance has at most one assigned_incident_id (inherent to column design)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ambulances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ambulance_number TEXT UNIQUE NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'AVAILABLE',
            capability TEXT NOT NULL,
            assigned_incident_id INTEGER,
            current_speed REAL NOT NULL DEFAULT 0.0,
            FOREIGN KEY (assigned_incident_id) REFERENCES incidents(id) ON DELETE SET NULL
        );
        """
    )

    # 3. Hospitals Table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS hospitals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            total_beds INTEGER NOT NULL DEFAULT 0,
            available_beds INTEGER NOT NULL DEFAULT 0,
            total_icu_beds INTEGER NOT NULL DEFAULT 0,
            available_icu_beds INTEGER NOT NULL DEFAULT 0,
            available_ventilators INTEGER NOT NULL DEFAULT 0,
            emergency_capacity INTEGER NOT NULL DEFAULT 0,
            specialties TEXT NOT NULL DEFAULT ''
        );
        """
    )

    # 4. Allocations Table
    # Constraint: Prevent multiple active allocations for the same ambulance
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            ambulance_id INTEGER NOT NULL,
            hospital_id INTEGER NOT NULL,
            estimated_arrival_minutes REAL NOT NULL,
            allocation_status TEXT NOT NULL DEFAULT 'ACTIVE',
            decision_reason TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE,
            FOREIGN KEY (ambulance_id) REFERENCES ambulances(id) ON DELETE CASCADE,
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE CASCADE
        );
        """
    )

    # Partial unique index: ensure an ambulance cannot have multiple active assignments
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_active_ambulance_allocation
        ON allocations(ambulance_id)
        WHERE allocation_status = 'ACTIVE';
        """
    )

    # 5. Traffic Zones Table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS traffic_zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone_name TEXT UNIQUE NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            congestion_level TEXT NOT NULL,
            traffic_multiplier REAL NOT NULL DEFAULT 1.0
        );
        """
    )

    # 6. Event Logs Table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS event_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            description TEXT NOT NULL,
            related_incident_id INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (related_incident_id) REFERENCES incidents(id) ON DELETE SET NULL
        );
        """
    )


def is_database_empty(conn: sqlite3.Connection) -> bool:
    """Check if the core tables have no records."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM hospitals")
    hospitals_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ambulances")
    ambulances_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM incidents")
    incidents_count = cursor.fetchone()[0]
    return (hospitals_count + ambulances_count + incidents_count) == 0


def init_db(
    db_path: Optional[Union[str, Path]] = None,
    seed_if_empty: bool = True,
) -> bool:
    """Initialize database tables and optionally seed simulated data if empty.
    
    Returns True if seeding occurred, False if database was already populated.
    """
    seeded = False
    with get_db(db_path) as conn:
        create_tables(conn)
        if seed_if_empty and is_database_empty(conn):
            from backend.seed import seed_data
            seed_data(conn)
            seeded = True
    return seeded


if __name__ == "__main__":
    print(f"Initializing ResQGrid database at {DEFAULT_DB_PATH}...")
    did_seed = init_db()
    print(f"Initialization complete. Seeded: {did_seed}")

