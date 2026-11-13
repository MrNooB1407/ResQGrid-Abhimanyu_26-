"""ResQGrid Ambulances REST API Route

Provides read access and status/capability filtering for emergency ambulance units.
"""

from flask import Blueprint, abort, current_app, jsonify, request
from backend.database import DEFAULT_DB_PATH, query_db

ambulances_bp = Blueprint("ambulances", __name__, url_prefix="/api/ambulances")


@ambulances_bp.route("", methods=["GET"])
def get_ambulances():
    """Retrieve all ambulance units with optional status and capability filtering."""
    db_path = current_app.config.get("DATABASE", DEFAULT_DB_PATH)

    status_filter = request.args.get("status")
    capability_filter = request.args.get("capability")

    conditions = []
    params = []

    if status_filter:
        conditions.append("UPPER(amb.status) = ?")
        params.append(status_filter.strip().upper())

    if capability_filter:
        conditions.append("UPPER(amb.capability) = ?")
        params.append(capability_filter.strip().upper())

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT amb.id, amb.ambulance_number, amb.latitude, amb.longitude,
               amb.status, amb.capability, amb.assigned_incident_id, amb.current_speed,
               a.id AS active_allocation_id,
               a.incident_id,
               i.title AS incident_title,
               a.hospital_id,
               h.name AS target_hospital_name,
               a.estimated_arrival_minutes
        FROM ambulances amb
        LEFT JOIN allocations a ON amb.id = a.ambulance_id AND a.allocation_status = 'ACTIVE'
        LEFT JOIN incidents i ON a.incident_id = i.id
        LEFT JOIN hospitals h ON a.hospital_id = h.id
        {where_clause}
        ORDER BY amb.id ASC;
    """

    rows = query_db(sql, tuple(params), db_path=db_path)
    if rows is None:
        rows = []

    ambulances = []
    for r in rows:
        amb_entry = {
            "id": r["id"],
            "ambulance_number": r["ambulance_number"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "status": r["status"],
            "capability": r["capability"],
            "assigned_incident_id": r["assigned_incident_id"],
            "current_speed": r["current_speed"],
        }
        if r["active_allocation_id"]:
            amb_entry["current_allocation"] = {
                "allocation_id": r["active_allocation_id"],
                "incident_id": r["incident_id"],
                "incident_title": r["incident_title"],
                "hospital_id": r["hospital_id"],
                "hospital_name": r["target_hospital_name"],
                "estimated_arrival_minutes": r["estimated_arrival_minutes"],
            }
        else:
            amb_entry["current_allocation"] = None
        ambulances.append(amb_entry)

    return jsonify({
        "success": True,
        "count": len(ambulances),
        "data": ambulances,
    }), 200


@ambulances_bp.route("/<int:ambulance_id>", methods=["GET"])
def get_ambulance(ambulance_id: int):
    """Retrieve detailed information for a single ambulance unit by ID."""
    db_path = current_app.config.get("DATABASE", DEFAULT_DB_PATH)

    sql = """
        SELECT amb.id, amb.ambulance_number, amb.latitude, amb.longitude,
               amb.status, amb.capability, amb.assigned_incident_id, amb.current_speed,
               a.id AS active_allocation_id,
               a.incident_id,
               i.title AS incident_title,
               a.hospital_id,
               h.name AS target_hospital_name,
               a.estimated_arrival_minutes,
               a.decision_reason
        FROM ambulances amb
        LEFT JOIN allocations a ON amb.id = a.ambulance_id AND a.allocation_status = 'ACTIVE'
        LEFT JOIN incidents i ON a.incident_id = i.id
        LEFT JOIN hospitals h ON a.hospital_id = h.id
        WHERE amb.id = ?;
    """

    row = query_db(sql, (ambulance_id,), one=True, db_path=db_path)
    if not row:
        abort(404, description=f"Ambulance with ID {ambulance_id} not found.")

    amb_entry = {
        "id": row["id"],
        "ambulance_number": row["ambulance_number"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "status": row["status"],
        "capability": row["capability"],
        "assigned_incident_id": row["assigned_incident_id"],
        "current_speed": row["current_speed"],
    }
    if row["active_allocation_id"]:
        amb_entry["current_allocation"] = {
            "allocation_id": row["active_allocation_id"],
            "incident_id": row["incident_id"],
            "incident_title": row["incident_title"],
            "hospital_id": row["hospital_id"],
            "hospital_name": row["target_hospital_name"],
            "estimated_arrival_minutes": row["estimated_arrival_minutes"],
            "decision_reason": row["decision_reason"],
        }
    else:
        amb_entry["current_allocation"] = None

    return jsonify({
        "success": True,
        "data": amb_entry,
    }), 200

