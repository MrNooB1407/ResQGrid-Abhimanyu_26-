"""ResQGrid Hospitals REST API Route

Provides read access, name search, and capacity monitoring for regional hospital centers.
"""

from flask import Blueprint, abort, current_app, jsonify, request
from backend.database import DEFAULT_DB_PATH, query_db

hospitals_bp = Blueprint("hospitals", __name__, url_prefix="/api/hospitals")


@hospitals_bp.route("", methods=["GET"])
def get_hospitals():
    """Retrieve all regional hospital centers with optional name substring filtering."""
    db_path = current_app.config.get("DATABASE", DEFAULT_DB_PATH)

    name_query = request.args.get("name") or request.args.get("search")

    conditions = []
    params = []

    if name_query:
        conditions.append("LOWER(h.name) LIKE ?")
        params.append(f"%{name_query.strip().lower()}%")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT h.id, h.name, h.latitude, h.longitude,
               h.total_beds, h.available_beds,
               h.total_icu_beds, h.available_icu_beds,
               h.available_ventilators, h.emergency_capacity,
               h.specialties,
               (
                   SELECT COUNT(*)
                   FROM allocations a
                   WHERE a.hospital_id = h.id AND a.allocation_status = 'ACTIVE'
               ) AS active_incoming_transports
        FROM hospitals h
        {where_clause}
        ORDER BY h.id ASC;
    """

    rows = query_db(sql, tuple(params), db_path=db_path)
    if rows is None:
        rows = []

    hospitals = []
    for r in rows:
        occupancy_pct = (
            round(((r["total_beds"] - r["available_beds"]) / r["total_beds"]) * 100, 1)
            if r["total_beds"] > 0
            else 0.0
        )
        hospitals.append({
            "id": r["id"],
            "name": r["name"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "total_beds": r["total_beds"],
            "available_beds": r["available_beds"],
            "total_icu_beds": r["total_icu_beds"],
            "available_icu_beds": r["available_icu_beds"],
            "available_ventilators": r["available_ventilators"],
            "emergency_capacity": r["emergency_capacity"],
            "specialties": r["specialties"],
            "active_incoming_transports": r["active_incoming_transports"],
            "occupancy_percentage": occupancy_pct,
        })

    return jsonify({
        "success": True,
        "count": len(hospitals),
        "data": hospitals,
    }), 200


@hospitals_bp.route("/<int:hospital_id>", methods=["GET"])
def get_hospital(hospital_id: int):
    """Retrieve detailed information and active incoming transports for a single hospital."""
    db_path = current_app.config.get("DATABASE", DEFAULT_DB_PATH)

    sql = """
        SELECT h.id, h.name, h.latitude, h.longitude,
               h.total_beds, h.available_beds,
               h.total_icu_beds, h.available_icu_beds,
               h.available_ventilators, h.emergency_capacity,
               h.specialties
        FROM hospitals h
        WHERE h.id = ?;
    """

    row = query_db(sql, (hospital_id,), one=True, db_path=db_path)
    if not row:
        abort(404, description=f"Hospital with ID {hospital_id} not found.")

    # Retrieve active incoming dispatches for this facility
    transports_sql = """
        SELECT a.id AS allocation_id,
               a.incident_id,
               i.title AS incident_title,
               i.severity_level,
               a.ambulance_id,
               amb.ambulance_number,
               amb.capability AS ambulance_capability,
               a.estimated_arrival_minutes,
               a.created_at
        FROM allocations a
        JOIN incidents i ON a.incident_id = i.id
        JOIN ambulances amb ON a.ambulance_id = amb.id
        WHERE a.hospital_id = ? AND a.allocation_status = 'ACTIVE'
        ORDER BY a.estimated_arrival_minutes ASC;
    """
    transport_rows = query_db(transports_sql, (hospital_id,), db_path=db_path) or []
    incoming_transports = [
        {
            "allocation_id": t["allocation_id"],
            "incident_id": t["incident_id"],
            "incident_title": t["incident_title"],
            "severity_level": t["severity_level"],
            "ambulance_id": t["ambulance_id"],
            "ambulance_number": t["ambulance_number"],
            "ambulance_capability": t["ambulance_capability"],
            "estimated_arrival_minutes": t["estimated_arrival_minutes"],
            "created_at": str(t["created_at"]) if t["created_at"] else None,
        }
        for t in transport_rows
    ]

    occupancy_pct = (
        round(((row["total_beds"] - row["available_beds"]) / row["total_beds"]) * 100, 1)
        if row["total_beds"] > 0
        else 0.0
    )

    hospital_entry = {
        "id": row["id"],
        "name": row["name"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "total_beds": row["total_beds"],
        "available_beds": row["available_beds"],
        "total_icu_beds": row["total_icu_beds"],
        "available_icu_beds": row["available_icu_beds"],
        "available_ventilators": row["available_ventilators"],
        "emergency_capacity": row["emergency_capacity"],
        "specialties": row["specialties"],
        "occupancy_percentage": occupancy_pct,
        "active_incoming_transports_count": len(incoming_transports),
        "incoming_transports": incoming_transports,
    }

    return jsonify({
        "success": True,
        "data": hospital_entry,
    }), 200

