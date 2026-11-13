"""ResQGrid Incidents REST API Route

Provides read access, filtering, incident creation with automated severity triage,
and safe lifecycle status transitions.
"""

from flask import Blueprint, abort, current_app, jsonify, request
from backend.database import DEFAULT_DB_PATH, get_db, query_db
from backend.services.severity import estimate_severity

incidents_bp = Blueprint("incidents", __name__, url_prefix="/api/incidents")

# Recognized emergency incident lifecycle statuses
VALID_LIFECYCLE_STATUSES = {"REPORTED", "ASSIGNED", "IN_TRANSIT", "RESOLVED", "CANCELLED"}

# Explicit state transition graph
VALID_TRANSITIONS = {
    "REPORTED": {"ASSIGNED", "CANCELLED", "RESOLVED"},
    "ASSIGNED": {"IN_TRANSIT", "REPORTED", "CANCELLED", "RESOLVED"},
    "IN_TRANSIT": {"RESOLVED", "ASSIGNED", "CANCELLED", "REPORTED"},
    "RESOLVED": set(),   # Terminal state
    "CANCELLED": set(),  # Terminal state
}


@incidents_bp.route("", methods=["GET"])
def get_incidents():
    """Retrieve all emergency incidents with optional status and severity filtering."""
    db_path = current_app.config.get("DATABASE", DEFAULT_DB_PATH)

    status_filter = request.args.get("status")
    severity_filter = request.args.get("severity") or request.args.get("severity_level")

    conditions = []
    params = []

    if status_filter:
        conditions.append("UPPER(i.status) = ?")
        params.append(status_filter.strip().upper())

    if severity_filter:
        conditions.append("UPPER(i.severity_level) = ?")
        params.append(severity_filter.strip().upper())

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT i.id, i.title, i.incident_type, i.description,
               i.latitude, i.longitude, i.affected_people, i.injured_people,
               i.severity_score, i.severity_level, i.status, i.created_at,
               a.id AS active_allocation_id,
               a.ambulance_id,
               amb.ambulance_number,
               amb.capability AS ambulance_capability,
               a.hospital_id,
               h.name AS hospital_name,
               a.estimated_arrival_minutes
        FROM incidents i
        LEFT JOIN allocations a ON i.id = a.incident_id AND a.allocation_status = 'ACTIVE'
        LEFT JOIN ambulances amb ON a.ambulance_id = amb.id
        LEFT JOIN hospitals h ON a.hospital_id = h.id
        {where_clause}
        ORDER BY i.created_at DESC, i.id DESC;
    """

    rows = query_db(sql, tuple(params), db_path=db_path)
    if rows is None:
        rows = []

    incidents = []
    for r in rows:
        incident_entry = {
            "id": r["id"],
            "title": r["title"],
            "incident_type": r["incident_type"],
            "description": r["description"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "affected_people": r["affected_people"],
            "injured_people": r["injured_people"],
            "severity_score": r["severity_score"],
            "severity_level": r["severity_level"],
            "status": r["status"],
            "created_at": str(r["created_at"]) if r["created_at"] else None,
        }
        if r["active_allocation_id"]:
            incident_entry["current_allocation"] = {
                "allocation_id": r["active_allocation_id"],
                "ambulance_id": r["ambulance_id"],
                "ambulance_number": r["ambulance_number"],
                "ambulance_capability": r["ambulance_capability"],
                "hospital_id": r["hospital_id"],
                "hospital_name": r["hospital_name"],
                "estimated_arrival_minutes": r["estimated_arrival_minutes"],
            }
        else:
            incident_entry["current_allocation"] = None
        incidents.append(incident_entry)

    return jsonify({
        "success": True,
        "count": len(incidents),
        "data": incidents,
    }), 200


@incidents_bp.route("/<int:incident_id>", methods=["GET"])
def get_incident(incident_id: int):
    """Retrieve detailed information for a single incident by ID."""
    db_path = current_app.config.get("DATABASE", DEFAULT_DB_PATH)

    sql = """
        SELECT i.id, i.title, i.incident_type, i.description,
               i.latitude, i.longitude, i.affected_people, i.injured_people,
               i.severity_score, i.severity_level, i.status, i.created_at,
               a.id AS active_allocation_id,
               a.ambulance_id,
               amb.ambulance_number,
               amb.capability AS ambulance_capability,
               a.hospital_id,
               h.name AS hospital_name,
               a.estimated_arrival_minutes,
               a.decision_reason
        FROM incidents i
        LEFT JOIN allocations a ON i.id = a.incident_id AND a.allocation_status = 'ACTIVE'
        LEFT JOIN ambulances amb ON a.ambulance_id = amb.id
        LEFT JOIN hospitals h ON a.hospital_id = h.id
        WHERE i.id = ?;
    """

    row = query_db(sql, (incident_id,), one=True, db_path=db_path)
    if not row:
        abort(404, description=f"Incident with ID {incident_id} not found.")

    incident_entry = {
        "id": row["id"],
        "title": row["title"],
        "incident_type": row["incident_type"],
        "description": row["description"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "affected_people": row["affected_people"],
        "injured_people": row["injured_people"],
        "severity_score": row["severity_score"],
        "severity_level": row["severity_level"],
        "status": row["status"],
        "created_at": str(row["created_at"]) if row["created_at"] else None,
    }
    if row["active_allocation_id"]:
        incident_entry["current_allocation"] = {
            "allocation_id": row["active_allocation_id"],
            "ambulance_id": row["ambulance_id"],
            "ambulance_number": row["ambulance_number"],
            "ambulance_capability": row["ambulance_capability"],
            "hospital_id": row["hospital_id"],
            "hospital_name": row["hospital_name"],
            "estimated_arrival_minutes": row["estimated_arrival_minutes"],
            "decision_reason": row["decision_reason"],
        }
    else:
        incident_entry["current_allocation"] = None

    return jsonify({
        "success": True,
        "data": incident_entry,
    }), 200


@incidents_bp.route("", methods=["POST"])
def create_incident():
    """Create a new emergency incident report and automatically estimate severity triage."""
    db_path = current_app.config.get("DATABASE", DEFAULT_DB_PATH)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Request body must be a valid JSON object.")

    # 1. Required string fields
    title = data.get("title")
    incident_type = data.get("incident_type")

    if not title or not isinstance(title, str) or not title.strip():
        abort(400, description="Field 'title' is required and must be a non-empty string.")

    if not incident_type or not isinstance(incident_type, str) or not incident_type.strip():
        abort(400, description="Field 'incident_type' is required and must be a non-empty string.")

    # 2. Coordinates validation
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if latitude is None or longitude is None:
        abort(400, description="Fields 'latitude' and 'longitude' are required coordinates.")

    if isinstance(latitude, bool) or isinstance(longitude, bool):
        abort(400, description="Coordinates must be numbers, not booleans.")

    try:
        lat_f = float(latitude)
        lon_f = float(longitude)
    except (ValueError, TypeError):
        abort(400, description="Fields 'latitude' and 'longitude' must be valid floating-point numbers.")

    if not (-90.0 <= lat_f <= 90.0):
        abort(400, description=f"Latitude {lat_f} is out of bounds. Must be between -90.0 and 90.0.")

    if not (-180.0 <= lon_f <= 180.0):
        abort(400, description=f"Longitude {lon_f} is out of bounds. Must be between -180.0 and 180.0.")

    # 3. Numeric casualty counts validation
    injured_raw = data.get("injured_people", 0)
    affected_raw = data.get("affected_people", 0)

    if isinstance(injured_raw, bool) or isinstance(affected_raw, bool):
        abort(400, description="Fields 'injured_people' and 'affected_people' must be integers, not booleans.")

    try:
        injured = int(injured_raw)
        affected = int(affected_raw)
    except (ValueError, TypeError):
        abort(400, description="Fields 'injured_people' and 'affected_people' must be valid non-negative integers.")

    if injured < 0 or affected < 0:
        abort(400, description="Fields 'injured_people' and 'affected_people' cannot be negative.")

    # If injured casualties exceed affected population, normalize affected count
    if affected < injured:
        affected = injured

    # 4. Optional narrative and clinical symptom/hazard metadata
    description = data.get("description", "")
    if description is not None and not isinstance(description, str):
        abort(400, description="Field 'description' must be a string if provided.")
    description = (description or "").strip()

    critical_symptoms = data.get("critical_symptoms", [])
    if not isinstance(critical_symptoms, (list, str)):
        abort(400, description="Field 'critical_symptoms' must be a list of strings or comma-separated string.")

    environmental_danger = data.get("environmental_danger", [])
    if not isinstance(environmental_danger, (list, str)):
        abort(400, description="Field 'environmental_danger' must be a list of strings or comma-separated string.")

    # 5. Automated AI Severity Triage Estimation
    severity_input = {
        "incident_type": incident_type.strip(),
        "injured_people": injured,
        "affected_people": affected,
        "critical_symptoms": critical_symptoms,
        "environmental_danger": environmental_danger,
        "description": description,
    }
    severity_result = estimate_severity(severity_input)
    severity_score = severity_result["severity_score"]
    severity_level = severity_result["severity_level"]

    # 6. Atomic Database Transaction: Insert incident & event log
    try:
        with get_db(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO incidents (
                    title, incident_type, description, latitude, longitude,
                    affected_people, injured_people, severity_score, severity_level, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'REPORTED');
                """,
                (
                    title.strip(),
                    incident_type.strip().upper(),
                    description,
                    lat_f,
                    lon_f,
                    affected,
                    injured,
                    severity_score,
                    severity_level,
                ),
            )
            new_id = cur.lastrowid

            log_desc = (
                f"[SIMULATED] Incident #{new_id} '{title.strip()}' reported ({incident_type.strip().upper()}). "
                f"Triage: {severity_level} ({severity_score:.1f}/100 pts)."
            )
            cur.execute(
                """
                INSERT INTO event_logs (event_type, description, related_incident_id)
                VALUES ('INCIDENT_REPORTED', ?, ?);
                """,
                (log_desc, new_id),
            )

            cur.execute("SELECT * FROM incidents WHERE id = ?;", (new_id,))
            created_row = dict(cur.fetchone())

    except Exception as exc:
        abort(500, description=f"Database transaction failed while creating incident: {str(exc)}")

    return jsonify({
        "success": True,
        "message": "Emergency incident created and triaged successfully.",
        "data": {
            "id": created_row["id"],
            "title": created_row["title"],
            "incident_type": created_row["incident_type"],
            "description": created_row["description"],
            "latitude": created_row["latitude"],
            "longitude": created_row["longitude"],
            "affected_people": created_row["affected_people"],
            "injured_people": created_row["injured_people"],
            "severity_score": created_row["severity_score"],
            "severity_level": created_row["severity_level"],
            "status": created_row["status"],
            "created_at": str(created_row["created_at"]) if created_row["created_at"] else None,
            "severity_assessment": {
                "severity_score": severity_score,
                "severity_level": severity_level,
                "resource_requirements": severity_result["resource_requirements"],
                "explanation": severity_result["explanation"],
            },
        },
    }), 201


@incidents_bp.route("/<int:incident_id>/status", methods=["PATCH"])
def update_incident_status(incident_id: int):
    """Update an existing incident's lifecycle status adhering to transition rules and allocation protection."""
    db_path = current_app.config.get("DATABASE", DEFAULT_DB_PATH)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Request body must be a valid JSON object.")

    new_status_raw = data.get("status")
    if not new_status_raw or not isinstance(new_status_raw, str) or not new_status_raw.strip():
        abort(400, description="Field 'status' is required and must be a non-empty string.")

    new_status = new_status_raw.strip().upper()

    # 1. Allowlist validation
    if new_status not in VALID_LIFECYCLE_STATUSES:
        abort(
            400,
            description=f"Invalid status '{new_status_raw}'. Allowed statuses: {sorted(list(VALID_LIFECYCLE_STATUSES))}.",
        )

    # 2. Retrieve existing incident
    incident = query_db(
        "SELECT * FROM incidents WHERE id = ?;",
        (incident_id,),
        one=True,
        db_path=db_path,
    )
    if not incident:
        abort(404, description=f"Incident with ID {incident_id} not found.")

    current_status = incident["status"].upper()

    # 3. Idempotent no-op check
    if current_status == new_status:
        return jsonify({
            "success": True,
            "message": f"Incident #{incident_id} is already in '{new_status}' status.",
            "data": {
                "id": incident["id"],
                "title": incident["title"],
                "incident_type": incident["incident_type"],
                "description": incident["description"],
                "latitude": incident["latitude"],
                "longitude": incident["longitude"],
                "affected_people": incident["affected_people"],
                "injured_people": incident["injured_people"],
                "severity_score": incident["severity_score"],
                "severity_level": incident["severity_level"],
                "status": incident["status"],
                "created_at": str(incident["created_at"]) if incident["created_at"] else None,
            },
        }), 200

    # 4. Terminal state check
    if current_status in ("RESOLVED", "CANCELLED"):
        abort(
            409,
            description=f"Cannot transition incident #{incident_id}: incident is already '{current_status}' (terminal state).",
        )

    # 5. Lifecycle transition rule check
    allowed_next_states = VALID_TRANSITIONS.get(current_status, set())
    if new_status not in allowed_next_states:
        abort(
            409,
            description=(
                f"Invalid lifecycle transition from '{current_status}' to '{new_status}'. "
                f"Allowed transitions from '{current_status}': {sorted(list(allowed_next_states))}."
            ),
        )

    # 6. Active Allocation Protection
    active_alloc = query_db(
        "SELECT id, ambulance_id, hospital_id FROM allocations WHERE incident_id = ? AND allocation_status = 'ACTIVE';",
        (incident_id,),
        one=True,
        db_path=db_path,
    )
    if new_status in ("RESOLVED", "CANCELLED") and active_alloc:
        abort(
            409,
            description=(
                f"Cannot transition incident #{incident_id} to '{new_status}': "
                f"incident has an active resource allocation (Allocation #{active_alloc['id']}). "
                "Active dispatch must be closed, completed, or reallocated before resolving or cancelling."
            ),
        )

    # 7. Atomic Database Transaction: Update status & log event
    try:
        with get_db(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE incidents SET status = ? WHERE id = ?;",
                (new_status, incident_id),
            )
            log_desc = (
                f"[SIMULATED] Incident #{incident_id} lifecycle status transitioned "
                f"from '{current_status}' to '{new_status}'."
            )
            cur.execute(
                """
                INSERT INTO event_logs (event_type, description, related_incident_id)
                VALUES ('INCIDENT_STATUS_UPDATED', ?, ?);
                """,
                (log_desc, incident_id),
            )
            cur.execute("SELECT * FROM incidents WHERE id = ?;", (incident_id,))
            updated_row = dict(cur.fetchone())

    except Exception as exc:
        abort(500, description=f"Database transaction failed while updating incident status: {str(exc)}")

    return jsonify({
        "success": True,
        "message": f"Incident #{incident_id} status updated to '{new_status}'.",
        "data": {
            "id": updated_row["id"],
            "title": updated_row["title"],
            "incident_type": updated_row["incident_type"],
            "description": updated_row["description"],
            "latitude": updated_row["latitude"],
            "longitude": updated_row["longitude"],
            "affected_people": updated_row["affected_people"],
            "injured_people": updated_row["injured_people"],
            "severity_score": updated_row["severity_score"],
            "severity_level": updated_row["severity_level"],
            "status": updated_row["status"],
            "created_at": str(updated_row["created_at"]) if updated_row["created_at"] else None,
        },
    }), 200
