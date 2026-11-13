"""ResQGrid Dynamic Reallocation REST API Routes

Provides event-driven dynamic resource reallocation for active dispatches:
1. Ambulance breakdown in transit (/api/reallocation/breakdown).
2. Receiving hospital capacity exhaustion / diversion (/api/reallocation/hospital).
3. Traffic corridor congestion spike adaptation (/api/reallocation/traffic).
"""

import math
from flask import Blueprint, abort, current_app, jsonify, request
from backend.database import DEFAULT_DB_PATH
from backend.services.reallocation import (
    handle_ambulance_breakdown,
    handle_hospital_capacity_exhausted,
    handle_traffic_congestion_spike,
)

reallocation_bp = Blueprint("reallocation", __name__, url_prefix="/api/reallocation")

# Supported hospital resource exhaustion types
SUPPORTED_EXHAUSTED_RESOURCES = {"BEDS", "ICU", "VENTILATOR", "VENTILATORS", "FULL"}

# Standardized traffic congestion levels
VALID_CONGESTION_LEVELS = {"LOW", "MODERATE", "HEAVY", "SEVERE", "GRIDLOCK"}


@reallocation_bp.route("/breakdown", methods=["POST"])
def ambulance_breakdown():
    """Handle vehicle breakdown by retiring failed unit and dispatching a replacement.

    Expected JSON:
    {
      "ambulance_id": 1,
      "reason": "Engine failure during transit"
    }
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Request body must be a valid JSON object.")

    # Validate ambulance_id
    if "ambulance_id" not in body or body["ambulance_id"] is None:
        abort(400, description="Field 'ambulance_id' is required.")
    ambulance_id = body["ambulance_id"]
    if isinstance(ambulance_id, bool) or not isinstance(ambulance_id, int) or ambulance_id <= 0:
        abort(400, description="Field 'ambulance_id' must be a positive integer.")

    # Validate reason
    if "reason" not in body or body["reason"] is None:
        abort(400, description="Field 'reason' is required.")
    reason = body["reason"]
    if not isinstance(reason, str) or not reason.strip():
        abort(400, description="Field 'reason' must be a non-empty string.")
    cleaned_reason = reason.strip()

    db_path = current_app.config.get("DATABASE", DEFAULT_DB_PATH)

    result = handle_ambulance_breakdown(
        ambulance_id=ambulance_id,
        reason=cleaned_reason,
        db_path=db_path,
    )

    if not result.get("success"):
        error_msg = result.get("error", "Ambulance breakdown handling failed.")
        err_lower = error_msg.lower()

        # 404 Not Found: Ambulance does not exist
        if "not found" in err_lower:
            abort(404, description=error_msg)

        # 409 Conflict: Ambulance has no active allocation (invalid operational state)
        if "no active allocation" in err_lower:
            abort(409, description=error_msg)

        # 422 Unprocessable Entity: No replacement ambulance available (incident returned to queue)
        if "no replacement ambulance available" in err_lower or "shortage" in err_lower:
            return jsonify({
                "success": False,
                "error": {
                    "code": 422,
                    "name": "Unprocessable Entity",
                    "message": error_msg,
                },
                "data": result,
                "incident_id": result.get("incident_id"),
                "broken_ambulance_id": result.get("broken_ambulance_id"),
                "broken_ambulance_number": result.get("broken_ambulance_number"),
                "replacement_ambulance": None,
                "old_allocation_id": result.get("old_allocation_id"),
                "new_allocation_id": None,
            }), 422

        # 500 Internal Server Error: Database or transaction abort
        abort(500, description=error_msg)

    # 200 OK: Replacement ambulance dispatched successfully
    return jsonify({
        "success": True,
        "message": (
            f"Ambulance {result.get('broken_ambulance_number')} marked OUT_OF_SERVICE. "
            f"Replacement {result.get('replacement_ambulance', {}).get('ambulance_number')} dispatched."
        ),
        "data": result,
        "incident_id": result.get("incident_id"),
        "broken_ambulance_id": result.get("broken_ambulance_id"),
        "broken_ambulance_number": result.get("broken_ambulance_number"),
        "replacement_ambulance": result.get("replacement_ambulance"),
        "hospital": result.get("hospital"),
        "old_allocation_id": result.get("old_allocation_id"),
        "new_allocation_id": result.get("new_allocation_id"),
        "estimated_arrival_minutes": result.get("estimated_arrival_minutes"),
        "decision_reason": result.get("decision_reason"),
    }), 200


@reallocation_bp.route("/hospital", methods=["POST"])
def hospital_capacity_exhausted():
    """Reroute incoming emergency transports away from a saturated receiving hospital.

    Expected JSON:
    {
      "hospital_id": 1,
      "reason": "ICU capacity exhausted",
      "exhausted_resource": "ICU"
    }
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Request body must be a valid JSON object.")

    # Validate hospital_id
    if "hospital_id" not in body or body["hospital_id"] is None:
        abort(400, description="Field 'hospital_id' is required.")
    hospital_id = body["hospital_id"]
    if isinstance(hospital_id, bool) or not isinstance(hospital_id, int) or hospital_id <= 0:
        abort(400, description="Field 'hospital_id' must be a positive integer.")

    # Validate reason
    if "reason" not in body or body["reason"] is None:
        abort(400, description="Field 'reason' is required.")
    reason = body["reason"]
    if not isinstance(reason, str) or not reason.strip():
        abort(400, description="Field 'reason' must be a non-empty string.")
    cleaned_reason = reason.strip()

    # Validate exhausted_resource
    raw_resource = body.get("exhausted_resource", "FULL")
    if raw_resource is None:
        raw_resource = "FULL"
    if not isinstance(raw_resource, str) or raw_resource.strip().upper() not in SUPPORTED_EXHAUSTED_RESOURCES:
        valid_options = ", ".join(sorted(SUPPORTED_EXHAUSTED_RESOURCES))
        abort(400, description=f"Field 'exhausted_resource' must be one of: {valid_options}.")
    cleaned_resource = raw_resource.strip().upper()

    db_path = current_app.config.get("DATABASE", DEFAULT_DB_PATH)

    result = handle_hospital_capacity_exhausted(
        hospital_id=hospital_id,
        reason=cleaned_reason,
        exhausted_resource=cleaned_resource,
        db_path=db_path,
    )

    if not result.get("success"):
        error_msg = result.get("error", "Hospital diversion failed.")
        err_lower = error_msg.lower()

        # 404 Not Found: Hospital does not exist
        if "not found" in err_lower:
            abort(404, description=error_msg)

        # 422 Unprocessable Entity: Transports could not be diverted due to alternative bed shortages
        if result.get("unresolved_count", 0) > 0 or "shortage" in err_lower:
            return jsonify({
                "success": False,
                "error": {
                    "code": 422,
                    "name": "Unprocessable Entity",
                    "message": error_msg,
                },
                "data": result,
                "hospital_id": result.get("hospital_id"),
                "hospital_name": result.get("hospital_name"),
                "affected_allocations": result.get("affected_allocations"),
                "reallocated_count": result.get("reallocated_count"),
                "unresolved_count": result.get("unresolved_count"),
                "reallocations": result.get("reallocations"),
                "unresolved": result.get("unresolved"),
            }), 422

        # 500 Internal Server Error: Database failure
        abort(500, description=error_msg)

    # 200 OK: Diversions successfully executed (or zero transports were affected)
    affected = result.get("affected_allocations", 0)
    reallocated = result.get("reallocated_count", 0)
    message = (
        f"Hospital {result.get('hospital_name')} capacity diversion complete: "
        f"{reallocated} of {affected} transport(s) rerouted."
        if affected > 0
        else result.get("message", f"Hospital {result.get('hospital_name')} has zero active transports to divert.")
    )

    return jsonify({
        "success": True,
        "message": message,
        "data": result,
        "hospital_id": result.get("hospital_id"),
        "hospital_name": result.get("hospital_name"),
        "affected_allocations": affected,
        "reallocated_count": reallocated,
        "unresolved_count": result.get("unresolved_count", 0),
        "reallocations": result.get("reallocations", []),
        "unresolved": result.get("unresolved", []),
    }), 200


@reallocation_bp.route("/traffic", methods=["POST"])
def traffic_congestion_spike():
    """Handle sudden traffic corridor congestion spike and dynamically reallocate ambulances.

    Expected JSON:
    {
      "traffic_zone_id": 1,
      "new_multiplier": 2.5,
      "new_congestion_level": "SEVERE"
    }
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Request body must be a valid JSON object.")

    # Validate traffic_zone_id
    if "traffic_zone_id" not in body or body["traffic_zone_id"] is None:
        abort(400, description="Field 'traffic_zone_id' is required.")
    traffic_zone_id = body["traffic_zone_id"]
    if isinstance(traffic_zone_id, bool) or not isinstance(traffic_zone_id, int) or traffic_zone_id <= 0:
        abort(400, description="Field 'traffic_zone_id' must be a positive integer.")

    # Validate new_multiplier
    if "new_multiplier" not in body or body["new_multiplier"] is None:
        abort(400, description="Field 'new_multiplier' is required.")
    raw_multiplier = body["new_multiplier"]
    if isinstance(raw_multiplier, bool):
        abort(400, description="Field 'new_multiplier' must be numeric and cannot be a boolean.")
    try:
        mult_val = float(raw_multiplier)
    except (ValueError, TypeError):
        abort(400, description="Field 'new_multiplier' must be a valid numeric value.")

    if not math.isfinite(mult_val) or mult_val < 1.0 or mult_val > 20.0:
        abort(400, description="Field 'new_multiplier' must be a finite number between 1.0 and 20.0.")

    # Validate new_congestion_level
    raw_level = body.get("new_congestion_level", "SEVERE")
    if raw_level is None:
        raw_level = "SEVERE"
    if not isinstance(raw_level, str) or raw_level.strip().upper() not in VALID_CONGESTION_LEVELS:
        valid_levels = ", ".join(sorted(VALID_CONGESTION_LEVELS))
        abort(400, description=f"Field 'new_congestion_level' must be one of: {valid_levels}.")
    cleaned_level = raw_level.strip().upper()

    # Optional min_improvement_minutes
    raw_improvement = body.get("min_improvement_minutes", 5.0)
    try:
        min_improvement = float(raw_improvement) if raw_improvement is not None else 5.0
    except (ValueError, TypeError):
        min_improvement = 5.0

    db_path = current_app.config.get("DATABASE", DEFAULT_DB_PATH)

    result = handle_traffic_congestion_spike(
        traffic_zone_id=traffic_zone_id,
        new_multiplier=mult_val,
        new_congestion_level=cleaned_level,
        min_improvement_minutes=min_improvement,
        db_path=db_path,
    )

    if not result.get("success"):
        error_msg = result.get("error", "Traffic update failed.")
        err_lower = error_msg.lower()

        # 404 Not Found: Traffic zone does not exist
        if "not found" in err_lower:
            abort(404, description=error_msg)

        # 400 Bad Request: Invalid multiplier reported by service
        if "invalid traffic multiplier" in err_lower:
            abort(400, description=error_msg)

        # 500 Internal Server Error: Database failure
        abort(500, description=error_msg)

    # 200 OK: Zone updated and candidate routes evaluated
    realloc_count = result.get("reallocations_performed", 0)
    zone_name = result.get("traffic_zone", {}).get("name", f"Zone #{traffic_zone_id}")
    return jsonify({
        "success": True,
        "message": (
            f"Traffic zone '{zone_name}' congestion updated to {cleaned_level} ({mult_val:.2f}x). "
            f"{realloc_count} active dispatch(es) dynamically reallocated."
        ),
        "data": result,
        "traffic_zone": result.get("traffic_zone"),
        "previous_multiplier": result.get("previous_multiplier"),
        "new_multiplier": result.get("new_multiplier"),
        "affected_allocations_evaluated": result.get("affected_allocations_evaluated", 0),
        "reallocations_performed": realloc_count,
        "evaluations": result.get("evaluations", []),
    }), 200

