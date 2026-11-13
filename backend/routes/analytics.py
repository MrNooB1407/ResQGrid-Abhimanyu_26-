"""ResQGrid Analytics REST API Route

Provides aggregated KPIs and real-time operational statistics calculated directly
from the SQLite database layer.
"""

from datetime import datetime
from flask import Blueprint, abort, current_app, jsonify, request
from backend.database import DEFAULT_DB_PATH, get_db

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


@analytics_bp.route("/overview", methods=["GET"])
def get_analytics_overview():
    """Retrieve aggregated emergency coordination metrics and system KPIs.

    All counts, capacities, and summaries are derived directly from the active
    database and not hardcoded.
    """
    if request.args:
        abort(400, description="The /api/analytics/overview endpoint does not accept query parameters.")

    db_path = current_app.config.get("DATABASE", DEFAULT_DB_PATH)

    with get_db(db_path) as conn:
        cur = conn.cursor()

        # 1. Incidents Analytics
        cur.execute("SELECT COUNT(*) AS total FROM incidents;")
        total_incidents = cur.fetchone()["total"]

        cur.execute(
            """
            SELECT COUNT(*) AS total
            FROM incidents
            WHERE status NOT IN ('RESOLVED', 'CANCELLED');
            """
        )
        active_incidents = cur.fetchone()["total"]

        cur.execute(
            """
            SELECT COUNT(*) AS total
            FROM incidents
            WHERE UPPER(severity_level) = 'CRITICAL'
              AND status NOT IN ('RESOLVED', 'CANCELLED');
            """
        )
        critical_active_incidents = cur.fetchone()["total"]

        cur.execute("SELECT COUNT(*) AS total FROM incidents WHERE UPPER(severity_level) = 'CRITICAL';")
        total_critical_incidents = cur.fetchone()["total"]

        # Incidents by severity
        cur.execute("SELECT severity_level, COUNT(*) AS count FROM incidents GROUP BY severity_level;")
        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for row in cur.fetchall():
            k = str(row["severity_level"]).upper()
            severity_counts[k] = row["count"]

        # Incidents by status
        cur.execute("SELECT status, COUNT(*) AS count FROM incidents GROUP BY status;")
        incident_status_counts = {"REPORTED": 0, "ASSIGNED": 0, "IN_TRANSIT": 0, "RESOLVED": 0, "CANCELLED": 0}
        for row in cur.fetchall():
            k = str(row["status"]).upper()
            incident_status_counts[k] = row["count"]

        # 2. Ambulances Analytics
        cur.execute("SELECT COUNT(*) AS total FROM ambulances;")
        total_ambulances = cur.fetchone()["total"]

        cur.execute("SELECT COUNT(*) AS total FROM ambulances WHERE status = 'AVAILABLE';")
        available_ambulances = cur.fetchone()["total"]

        # Ambulances by status
        cur.execute("SELECT status, COUNT(*) AS count FROM ambulances GROUP BY status;")
        ambulance_status_counts = {"AVAILABLE": 0, "DISPATCHED": 0, "BUSY": 0, "OUT_OF_SERVICE": 0}
        for row in cur.fetchall():
            k = str(row["status"]).upper()
            ambulance_status_counts[k] = row["count"]

        # Ambulances by capability
        cur.execute("SELECT capability, COUNT(*) AS count FROM ambulances GROUP BY capability;")
        ambulance_capability_counts = {"ALS": 0, "BLS": 0, "PATIENT_TRANSPORT": 0}
        for row in cur.fetchall():
            k = str(row["capability"]).upper()
            ambulance_capability_counts[k] = row["count"]

        # 3. Hospitals Analytics
        cur.execute("SELECT COUNT(*) AS total FROM hospitals;")
        total_hospitals = cur.fetchone()["total"]

        cur.execute(
            """
            SELECT
                COALESCE(SUM(total_beds), 0) AS total_beds,
                COALESCE(SUM(available_beds), 0) AS available_beds,
                COALESCE(SUM(total_icu_beds), 0) AS total_icu_beds,
                COALESCE(SUM(available_icu_beds), 0) AS available_icu_beds,
                COALESCE(SUM(available_ventilators), 0) AS available_ventilators,
                COALESCE(SUM(emergency_capacity), 0) AS emergency_capacity
            FROM hospitals;
            """
        )
        hosp_row = cur.fetchone()
        tot_beds = hosp_row["total_beds"]
        avail_beds = hosp_row["available_beds"]
        tot_icu = hosp_row["total_icu_beds"]
        avail_icu = hosp_row["available_icu_beds"]
        avail_vents = hosp_row["available_ventilators"]
        emer_cap = hosp_row["emergency_capacity"]

        occupied_beds = max(0, tot_beds - avail_beds)
        bed_occ_rate = round((occupied_beds / tot_beds) * 100, 1) if tot_beds > 0 else 0.0

        occupied_icu = max(0, tot_icu - avail_icu)
        icu_occ_rate = round((occupied_icu / tot_icu) * 100, 1) if tot_icu > 0 else 0.0

        # 4. Allocations Summary
        cur.execute(
            """
            SELECT
                COUNT(*) AS total_allocations,
                COALESCE(SUM(CASE WHEN allocation_status = 'ACTIVE' THEN 1 ELSE 0 END), 0) AS active_allocations,
                COALESCE(SUM(CASE WHEN allocation_status = 'REALLOCATED' THEN 1 ELSE 0 END), 0) AS reallocated_count,
                AVG(CASE WHEN allocation_status = 'ACTIVE' THEN estimated_arrival_minutes ELSE NULL END) AS avg_active_eta
            FROM allocations;
            """
        )
        alloc_row = cur.fetchone()
        tot_allocations = alloc_row["total_allocations"]
        active_allocations = alloc_row["active_allocations"]
        reallocated_count = alloc_row["reallocated_count"]
        avg_active_eta = round(alloc_row["avg_active_eta"], 1) if alloc_row["avg_active_eta"] is not None else None

    # Response time metric handling:
    # "Average response time, only if a valid stored source exists.
    # Do not invent response-time data. If unavailable, return null and explain that the metric is not yet recorded."
    response_time_info = {
        "average_minutes": None,
        "recorded": False,
        "explanation": "Actual on-scene response time is not yet recorded in the database schema.",
        "target_minutes": 10.0,
        "average_estimated_eta_minutes": avg_active_eta,
    }

    # Combined KPI object directly matching frontend KpiCards structure
    kpis = {
        "activeEmergencies": active_incidents,
        "criticalIncidents": critical_active_incidents,
        "availableAmbulances": available_ambulances,
        "totalAmbulances": total_ambulances,
        "hospitalsOnline": total_hospitals,
        "totalHospitals": total_hospitals,
        "avgResponseTimeMin": None,
        "targetResponseTimeMin": 10.0,
        "avgResponseTimeNote": "Metric not yet recorded",
    }

    return jsonify({
        "success": True,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": {
            "kpis": kpis,
            "incidents": {
                "total": total_incidents,
                "active": active_incidents,
                "critical": total_critical_incidents,
                "critical_active": critical_active_incidents,
                "by_severity": severity_counts,
                "by_status": incident_status_counts,
            },
            "ambulances": {
                "total": total_ambulances,
                "available": available_ambulances,
                "by_status": ambulance_status_counts,
                "by_capability": ambulance_capability_counts,
            },
            "hospitals": {
                "total": total_hospitals,
                "total_beds": tot_beds,
                "available_beds": avail_beds,
                "occupied_beds": occupied_beds,
                "bed_occupancy_rate_pct": bed_occ_rate,
                "total_icu_beds": tot_icu,
                "available_icu_beds": avail_icu,
                "occupied_icu_beds": occupied_icu,
                "icu_occupancy_rate_pct": icu_occ_rate,
                "available_ventilators": avail_vents,
                "total_emergency_capacity": emer_cap,
            },
            "allocations": {
                "total": tot_allocations,
                "active": active_allocations,
                "reallocated": reallocated_count,
                "avg_active_eta_minutes": avg_active_eta,
            },
            "response_time": response_time_info,
        },
    }), 200

