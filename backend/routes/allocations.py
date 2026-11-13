"""ResQGrid Resource Allocation REST API Route

Provides emergency resource dispatch by matching active incidents with suitable
ambulances and hospitals using the allocation engine.
"""

from flask import Blueprint, abort, current_app, jsonify, request
from backend.database import DEFAULT_DB_PATH
from backend.services.allocation import allocate_incident

allocations_bp = Blueprint("allocations", __name__, url_prefix="/api/allocations")


@allocations_bp.route("/<int:incident_id>", methods=["POST"])
def create_allocation(incident_id: int):
    """Execute end-to-end atomic resource allocation for an incident.

    Delegates candidate selection, clinical capability matching, road ETA calculation,
    and capacity reservations entirely to the allocation engine service.
    """
    if incident_id <= 0:
        abort(400, description="Incident ID must be a positive integer.")

    db_path = current_app.config.get("DATABASE", DEFAULT_DB_PATH)

    result = allocate_incident(incident_id=incident_id, db_path=db_path)

    if not result.get("success"):
        error_msg = result.get("error", "Allocation failed.")
        err_lower = error_msg.lower()

        # 404 Not Found: Incident does not exist in database
        if "not found" in err_lower:
            abort(404, description=error_msg)

        # 409 Conflict: Incident already resolved/cancelled or holds active allocation
        if "already" in err_lower or "active allocation" in err_lower or "concurrent" in err_lower:
            abort(409, description=error_msg)

        # 422 Unprocessable Entity: Resource shortage (no suitable ambulance or hospital capacity)
        if "resource shortage" in err_lower or "shortage" in err_lower or "no available" in err_lower:
            abort(422, description=error_msg)

        # 500 Internal Server Error: Unexpected failure
        abort(500, description=error_msg)

    # 201 Created: New allocation successfully committed
    return jsonify({
        "success": True,
        "message": f"Resources successfully allocated for Incident #{incident_id}.",
        "data": result,
        "allocation_id": result.get("allocation_id"),
        "incident_id": result.get("incident_id"),
        "ambulance": result.get("ambulance"),
        "hospital": result.get("hospital"),
        "estimated_arrival_minutes": result.get("estimated_arrival_minutes"),
        "severity": result.get("severity"),
        "fulfillment_status": result.get("fulfillment_status"),
        "decision_reason": result.get("decision_reason"),
        "resources_reserved": result.get("resources_reserved"),
        "unfulfilled_requirements": result.get("unfulfilled_requirements"),
    }), 201

