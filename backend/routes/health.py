"""ResQGrid Health Check Route

Provides system health and database connectivity diagnostics.
"""

from pathlib import Path
from flask import Blueprint, current_app, jsonify
from backend.database import DEFAULT_DB_PATH, get_db_connection

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/health", methods=["GET"])
def health_check():
    """Verify application health and SQLite database connectivity."""
    db_path = current_app.config.get("DATABASE", DEFAULT_DB_PATH)
    db_connected = False
    db_status = "UNAVAILABLE"
    details = {}

    try:
        resolved_path = Path(db_path)
        if not resolved_path.is_file():
            raise FileNotFoundError(f"Database file not found at {resolved_path}")

        conn = get_db_connection(resolved_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1;")
            row = cur.fetchone()
            if row and row[0] == 1:
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
                )
                tables = [r[0] for r in cur.fetchall()]
                db_connected = True
                db_status = "CONNECTED"
                details["tables_count"] = len(tables)
                details["tables"] = tables
        finally:
            conn.close()
    except Exception as exc:
        db_connected = False
        db_status = "UNAVAILABLE"
        details["error"] = "Database connection or verification failed"

    status_code = 200 if db_connected else 503
    return jsonify({
        "success": db_connected,
        "status": "HEALTHY" if db_connected else "UNHEALTHY",
        "application": "ResQGrid Emergency Coordination Engine",
        "database": {
            "connected": db_connected,
            "status": db_status,
            "details": details,
        },
    }), status_code

