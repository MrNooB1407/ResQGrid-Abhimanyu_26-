"""ResQGrid Dynamic Reallocation Engine

Provides safe, event-driven resource reallocation for active dispatches in response to:
1. Ambulance breakdown in transit.
2. Hospital emergency department / ICU capacity exhaustion.

Safety and Transaction Semantics:
- Never deletes allocation history; past allocations transition from 'ACTIVE' to 'REALLOCATED'.
- Releasing an ambulance strictly verifies both ambulance ID and assigned incident ID.
- Hospital capacity is conserved symmetrically (restored at departed facility, reserved at destination).
- Old allocation retirement and new allocation creation execute within a single atomic SQLite transaction.
- If a replacement resource cannot be secured, the active allocation is not retired prematurely,
  unless an irrecoverable event (e.g. vehicle breakdown) necessitates returning the incident to queue.
"""

import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.database import get_db, query_db
from backend.services.allocation import find_suitable_ambulances, find_suitable_hospitals
from backend.services.routing import calculate_route, haversine_distance
from backend.services.severity import estimate_severity


def is_route_affected_by_zone(
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    zone_coord: Tuple[float, float],
    zone_influence_km: float = 2.5,
) -> bool:
    """Check if any sampled point along the straight corridor intersects a traffic zone."""
    lat1, lon1 = origin[0], origin[1]
    lat2, lon2 = destination[0], destination[1]
    for r in (0.0, 0.25, 0.5, 0.75, 1.0):
        sample_pt = (lat1 + r * (lat2 - lat1), lon1 + r * (lon2 - lon1))
        if haversine_distance(sample_pt, zone_coord) <= zone_influence_km:
            return True
    return False


def reallocate_incident(
    incident_id: int,
    reason: str,
    replace_ambulance: bool = True,
    replace_hospital: bool = False,
    excluded_ambulance_ids: Optional[List[int]] = None,
    excluded_hospital_ids: Optional[List[int]] = None,
    old_ambulance_new_status: str = "AVAILABLE",
    db_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Atomically reallocate an active incident to a replacement ambulance and/or hospital.

    Args:
        incident_id: ID of the incident to reallocate.
        reason: Diagnostic justification for the reallocation.
        replace_ambulance: If True, search and dispatch a replacement ambulance.
        replace_hospital: If True, search and reserve an alternative receiving hospital.
        excluded_ambulance_ids: IDs of ambulances disqualified from candidate search.
        excluded_hospital_ids: IDs of hospitals disqualified from candidate search.
        old_ambulance_new_status: Status to assign the departing ambulance ('AVAILABLE' or 'OUT_OF_SERVICE').
        db_path: Target SQLite database file.

    Returns:
        Structured response detailing the reallocation outcome.
    """
    def _fail(msg: str, shortage_type: Optional[str] = None) -> Dict[str, Any]:
        return {
            "success": False,
            "incident_id": incident_id,
            "old_allocation_id": old_alloc["id"] if old_alloc else None,
            "new_allocation_id": None,
            "reallocation_type": None,
            "ambulance": None,
            "hospital": None,
            "estimated_arrival_minutes": None,
            "shortage_type": shortage_type,
            "decision_reason": None,
            "error": msg,
        }

    excluded_amb_set = set(excluded_ambulance_ids or [])
    excluded_hosp_set = set(excluded_hospital_ids or [])

    # 1. Retrieve the active allocation for the incident
    old_alloc = query_db(
        "SELECT * FROM allocations WHERE incident_id = ? AND allocation_status = 'ACTIVE';",
        (incident_id,),
        one=True,
        db_path=db_path,
    )
    if not old_alloc:
        return _fail(f"No active allocation found for incident #{incident_id} to reallocate.")

    # 2. Retrieve incident and evaluate triage requirements
    incident = query_db("SELECT * FROM incidents WHERE id = ?;", (incident_id,), one=True, db_path=db_path)
    if not incident:
        return _fail(f"Incident #{incident_id} not found in database.")

    severity_info = estimate_severity(incident)
    requirements = severity_info["resource_requirements"]
    incident_coord = (float(incident["latitude"]), float(incident["longitude"]))
    traffic_zones = query_db("SELECT * FROM traffic_zones;", db_path=db_path)

    # 3. Handle Ambulance Candidate Selection
    target_ambulance = None
    if replace_ambulance:
        # Exclude the currently assigned ambulance plus any caller-specified exclusions
        excluded_amb_set.add(old_alloc["ambulance_id"])
        candidates = find_suitable_ambulances(
            incident=incident,
            requirements=requirements,
            traffic_zones=traffic_zones,
            db_path=db_path,
        )
        filtered_ambs = [c for c in candidates if c["ambulance_id"] not in excluded_amb_set]
        if not filtered_ambs:
            req_type = requirements.get("ambulance_type", "BLS")
            return _fail(
                f"Resource shortage: No suitable {req_type} replacement ambulance available.",
                shortage_type="AMBULANCE",
            )
        best_amb_candidate = filtered_ambs[0]
        target_ambulance = {
            "id": best_amb_candidate["ambulance_id"],
            "ambulance_number": best_amb_candidate["ambulance_number"],
            "capability": best_amb_candidate["capability"],
            "estimated_arrival_minutes": best_amb_candidate["estimated_arrival_minutes"],
            "road_distance_km": best_amb_candidate["road_distance_km"],
            "traffic_multiplier": best_amb_candidate["traffic_multiplier"],
        }
    else:
        # Retain existing ambulance
        current_amb = query_db("SELECT * FROM ambulances WHERE id = ?;", (old_alloc["ambulance_id"],), one=True, db_path=db_path)
        if not current_amb:
            return _fail(f"Currently assigned ambulance #{old_alloc['ambulance_id']} not found.")
        amb_coord = (float(current_amb["latitude"]), float(current_amb["longitude"]))
        route = calculate_route(amb_coord, incident_coord, traffic_zones=traffic_zones)
        target_ambulance = {
            "id": current_amb["id"],
            "ambulance_number": current_amb["ambulance_number"],
            "capability": current_amb["capability"],
            "estimated_arrival_minutes": route["traffic_adjusted_duration_minutes"],
            "road_distance_km": route["estimated_road_distance_km"],
            "traffic_multiplier": route["traffic_multiplier"],
        }

    # 4. Handle Hospital Candidate Selection
    target_hospital = None
    if replace_hospital:
        # Exclude the current hospital plus caller-specified exclusions
        excluded_hosp_set.add(old_alloc["hospital_id"])
        hosp_candidates = find_suitable_hospitals(
            incident=incident,
            requirements=requirements,
            traffic_zones=traffic_zones,
            db_path=db_path,
        )
        filtered_hosps = [h for h in hosp_candidates if h["hospital_id"] not in excluded_hosp_set]
        if not filtered_hosps:
            return _fail(
                "Resource shortage: No alternative hospitals with sufficient capacity meet clinical criteria.",
                shortage_type="HOSPITAL",
            )
        best_hosp_candidate = filtered_hosps[0]
        target_hospital = {
            "id": best_hosp_candidate["hospital_id"],
            "name": best_hosp_candidate["name"],
            "estimated_arrival_minutes": best_hosp_candidate["estimated_arrival_minutes"],
            "road_distance_km": best_hosp_candidate["road_distance_km"],
            "traffic_multiplier": best_hosp_candidate["traffic_multiplier"],
            "specialties": best_hosp_candidate["specialties"],
            "available_beds": best_hosp_candidate["available_beds"],
            "available_icu_beds": best_hosp_candidate["available_icu_beds"],
        }
    else:
        # Retain existing hospital
        current_hosp = query_db("SELECT * FROM hospitals WHERE id = ?;", (old_alloc["hospital_id"],), one=True, db_path=db_path)
        if not current_hosp:
            return _fail(f"Currently assigned hospital #{old_alloc['hospital_id']} not found.")
        hosp_coord = (float(current_hosp["latitude"]), float(current_hosp["longitude"]))
        h_route = calculate_route(incident_coord, hosp_coord, traffic_zones=traffic_zones)
        target_hospital = {
            "id": current_hosp["id"],
            "name": current_hosp["name"],
            "estimated_arrival_minutes": h_route["traffic_adjusted_duration_minutes"],
            "road_distance_km": h_route["estimated_road_distance_km"],
            "traffic_multiplier": h_route["traffic_multiplier"],
            "specialties": current_hosp["specialties"],
            "available_beds": current_hosp["available_beds"],
            "available_icu_beds": current_hosp["available_icu_beds"],
        }

    # Capacity quantities
    reserved_beds = 1
    reserved_icu = 1 if requirements.get("icu_required") else 0

    reallocation_type = (
        "BOTH" if (replace_ambulance and replace_hospital)
        else ("AMBULANCE" if replace_ambulance else "HOSPITAL")
    )

    # 5. Execute Atomic Transactional Transition
    try:
        with get_db(db_path) as conn:
            cur = conn.cursor()

            # A. Verify old allocation remains ACTIVE under lock
            cur.execute("SELECT id FROM allocations WHERE id = ? AND allocation_status = 'ACTIVE';", (old_alloc["id"],))
            if not cur.fetchone():
                raise RuntimeError(f"Allocation #{old_alloc['id']} status changed concurrently.")

            # B. Retire old allocation record
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            superseded_text = (
                f"{old_alloc.get('decision_reason', '')} | "
                f"[SUPERSEDED at {timestamp_str}: {reason}]"
            )
            cur.execute(
                """
                UPDATE allocations
                SET allocation_status = 'REALLOCATED',
                    decision_reason = ?
                WHERE id = ? AND allocation_status = 'ACTIVE';
                """,
                (superseded_text, old_alloc["id"]),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"Failed to transition allocation #{old_alloc['id']} to REALLOCATED.")

            # C. Release old ambulance (only if replaced)
            if replace_ambulance:
                cur.execute(
                    """
                    UPDATE ambulances
                    SET status = ?, assigned_incident_id = NULL
                    WHERE id = ? AND assigned_incident_id = ?;
                    """,
                    (old_ambulance_new_status, old_alloc["ambulance_id"], incident_id),
                )
                if cur.rowcount != 1:
                    raise RuntimeError(
                        f"Old ambulance #{old_alloc['ambulance_id']} was not assigned to incident #{incident_id}."
                    )

                # Reserve new ambulance
                cur.execute(
                    """
                    UPDATE ambulances
                    SET status = 'DISPATCHED', assigned_incident_id = ?
                    WHERE id = ? AND status = 'AVAILABLE' AND assigned_incident_id IS NULL;
                    """,
                    (incident_id, target_ambulance["id"]),
                )
                if cur.rowcount != 1:
                    raise RuntimeError(
                        f"Replacement ambulance {target_ambulance['ambulance_number']} was acquired concurrently."
                    )

            # D. Hospital capacity transition (only if replaced)
            if replace_hospital:
                # Restore old hospital capacity
                cur.execute(
                    """
                    UPDATE hospitals
                    SET available_beds = available_beds + ?,
                        available_icu_beds = available_icu_beds + ?
                    WHERE id = ?;
                    """,
                    (reserved_beds, reserved_icu, old_alloc["hospital_id"]),
                )
                if cur.rowcount != 1:
                    raise RuntimeError(f"Failed to restore capacity at old hospital #{old_alloc['hospital_id']}.")

                # Reserve new hospital capacity
                cur.execute(
                    """
                    UPDATE hospitals
                    SET available_beds = available_beds - ?,
                        available_icu_beds = available_icu_beds - ?
                    WHERE id = ? AND available_beds >= ? AND available_icu_beds >= ?;
                    """,
                    (
                        reserved_beds,
                        reserved_icu,
                        target_hospital["id"],
                        reserved_beds,
                        reserved_icu,
                    ),
                )
                if cur.rowcount != 1:
                    raise RuntimeError(
                        f"New hospital {target_hospital['name']} capacity was exhausted concurrently."
                    )

            # E. Format decision justification for the new allocation
            new_decision_reason = (
                f"[DYNAMIC REALLOCATION] Replaced {reallocation_type.lower()} for Incident #{incident_id}. "
                f"Trigger: {reason}. "
                f"Ambulance: {target_ambulance['ambulance_number']} ({target_ambulance['capability']}, ETA {target_ambulance['estimated_arrival_minutes']:.1f}m). "
                f"Facility: {target_hospital['name']} (Transit ETA {target_hospital['estimated_arrival_minutes']:.1f}m). "
                f"Supersedes Allocation #{old_alloc['id']}."
            )

            # F. Insert new ACTIVE allocation
            cur.execute(
                """
                INSERT INTO allocations (
                    incident_id, ambulance_id, hospital_id, estimated_arrival_minutes,
                    allocation_status, decision_reason
                ) VALUES (?, ?, ?, ?, 'ACTIVE', ?);
                """,
                (
                    incident_id,
                    target_ambulance["id"],
                    target_hospital["id"],
                    target_ambulance["estimated_arrival_minutes"],
                    new_decision_reason,
                ),
            )
            new_allocation_id = cur.lastrowid

            # G. Insert immutable event log entry
            log_desc = (
                f"[SIMULATED] Reallocation #{new_allocation_id} committed (superseding #{old_alloc['id']}): "
                f"Replaced {reallocation_type.lower()} for Incident #{incident_id}. Reason: {reason}."
            )
            cur.execute(
                """
                INSERT INTO event_logs (event_type, description, related_incident_id)
                VALUES ('RESOURCE_REALLOCATED', ?, ?);
                """,
                (log_desc, incident_id),
            )

        return {
            "success": True,
            "incident_id": incident_id,
            "old_allocation_id": old_alloc["id"],
            "new_allocation_id": new_allocation_id,
            "reallocation_type": reallocation_type,
            "ambulance": target_ambulance,
            "hospital": target_hospital,
            "estimated_arrival_minutes": target_ambulance["estimated_arrival_minutes"],
            "decision_reason": new_decision_reason,
            "error": None,
        }

    except Exception as exc:
        return _fail(f"Reallocation transaction aborted: {str(exc)}")


def handle_ambulance_breakdown(
    ambulance_id: int,
    reason: str = "Mechanical failure in transit",
    db_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Handle vehicle breakdown by marking unit OUT_OF_SERVICE and securing a replacement.

    Workflow:
    1. Verify ambulance exists and holds an active allocation.
    2. Attempt to reallocate the incident to a replacement ambulance, keeping hospital intact.
    3. If a replacement is secured, old ambulance is retired to OUT_OF_SERVICE.
    4. If no replacement ambulance exists:
       - Retire failed ambulance to OUT_OF_SERVICE and clear assigned_incident_id.
       - Safely close the old allocation.
       - Restore reserved hospital capacity so it is not leaked.
       - Re-queue the incident back to 'REPORTED'.
       - Log AMBULANCE_BREAKDOWN and SHORTAGE_UNRESOLVED events.
       - Return clear failure without corrupting state.
    """
    # 1. Verify ambulance and active assignment
    amb = query_db("SELECT * FROM ambulances WHERE id = ?;", (ambulance_id,), one=True, db_path=db_path)
    if not amb:
        return {"success": False, "error": f"Ambulance with ID {ambulance_id} not found."}

    alloc = query_db(
        "SELECT * FROM allocations WHERE ambulance_id = ? AND allocation_status = 'ACTIVE';",
        (ambulance_id,),
        one=True,
        db_path=db_path,
    )
    if not alloc:
        return {
            "success": False,
            "error": f"Ambulance {amb['ambulance_number']} (ID #{ambulance_id}) has no active allocation to reallocate.",
        }

    incident_id = alloc["incident_id"]

    # 2. Attempt reallocation to an alternative ambulance
    realloc_result = reallocate_incident(
        incident_id=incident_id,
        reason=f"Ambulance breakdown ({amb['ambulance_number']}): {reason}",
        replace_ambulance=True,
        replace_hospital=False,
        excluded_ambulance_ids=[ambulance_id],
        old_ambulance_new_status="OUT_OF_SERVICE",
        db_path=db_path,
    )

    if realloc_result["success"]:
        # Log breakdown event specifically
        breakdown_log = (
            f"[SIMULATED] AMBULANCE_BREAKDOWN: Unit {amb['ambulance_number']} failed ({reason}) "
            f"on Incident #{incident_id}. Replaced by {realloc_result['ambulance']['ambulance_number']}."
        )
        try:
            with get_db(db_path) as conn:
                conn.execute(
                    "INSERT INTO event_logs (event_type, description, related_incident_id) VALUES ('AMBULANCE_BREAKDOWN', ?, ?);",
                    (breakdown_log, incident_id),
                )
        except Exception:
            pass

        return {
            "success": True,
            "incident_id": incident_id,
            "broken_ambulance_id": ambulance_id,
            "broken_ambulance_number": amb["ambulance_number"],
            "old_allocation_id": realloc_result["old_allocation_id"],
            "new_allocation_id": realloc_result["new_allocation_id"],
            "replacement_ambulance": realloc_result["ambulance"],
            "hospital": realloc_result["hospital"],
            "estimated_arrival_minutes": realloc_result["estimated_arrival_minutes"],
            "decision_reason": realloc_result["decision_reason"],
            "error": None,
        }

    # 3. Shortage handling: no replacement ambulance is currently available
    try:
        with get_db(db_path) as conn:
            cur = conn.cursor()

            # Mark broken ambulance OUT_OF_SERVICE and clear assigned incident
            cur.execute(
                "UPDATE ambulances SET status = 'OUT_OF_SERVICE', assigned_incident_id = NULL WHERE id = ?;",
                (ambulance_id,),
            )

            # Safely close old allocation
            close_reason = (
                f"{alloc.get('decision_reason', '')} | "
                f"[TERMINATED: Ambulance {amb['ambulance_number']} breakdown ({reason}) with no replacement available]"
            )
            cur.execute(
                "UPDATE allocations SET allocation_status = 'REALLOCATED', decision_reason = ? WHERE id = ?;",
                (close_reason, alloc["id"]),
            )

            # Restore reserved hospital capacity so it is not tied up
            cur.execute(
                """
                UPDATE hospitals
                SET available_beds = available_beds + 1,
                    available_icu_beds = available_icu_beds + ?
                WHERE id = ?;
                """,
                (1 if "ICU" in str(alloc.get("decision_reason", "")) else 0, alloc["hospital_id"]),
            )

            # Return incident to REPORTED queue
            cur.execute("UPDATE incidents SET status = 'REPORTED' WHERE id = ?;", (incident_id,))

            # Log AMBULANCE_BREAKDOWN
            breakdown_desc = (
                f"[SIMULATED] AMBULANCE_BREAKDOWN: Unit {amb['ambulance_number']} broke down on Incident #{incident_id}: {reason}. "
                "Vehicle transitioned to OUT_OF_SERVICE."
            )
            cur.execute(
                "INSERT INTO event_logs (event_type, description, related_incident_id) VALUES ('AMBULANCE_BREAKDOWN', ?, ?);",
                (breakdown_desc, incident_id),
            )

            # Log SHORTAGE_UNRESOLVED
            shortage_desc = (
                f"[SIMULATED] SHORTAGE_UNRESOLVED: No replacement ambulance available for Incident #{incident_id}. "
                "Incident reset to REPORTED status; hospital bed reservation released."
            )
            cur.execute(
                "INSERT INTO event_logs (event_type, description, related_incident_id) VALUES ('SHORTAGE_UNRESOLVED', ?, ?);",
                (shortage_desc, incident_id),
            )

        return {
            "success": False,
            "incident_id": incident_id,
            "broken_ambulance_id": ambulance_id,
            "broken_ambulance_number": amb["ambulance_number"],
            "replacement_ambulance": None,
            "old_allocation_id": alloc["id"],
            "new_allocation_id": None,
            "error": (
                f"Ambulance {amb['ambulance_number']} marked OUT_OF_SERVICE. "
                f"No replacement ambulance available: incident #{incident_id} returned to REPORTED queue."
            ),
        }

    except Exception as exc:
        return {
            "success": False,
            "incident_id": incident_id,
            "broken_ambulance_id": ambulance_id,
            "replacement_ambulance": None,
            "error": f"Failed to handle ambulance breakdown safely: {str(exc)}",
        }


def handle_hospital_capacity_exhausted(
    hospital_id: int,
    reason: str = "Emergency department capacity exhausted",
    exhausted_resource: str = "FULL",
    db_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Reroute active incoming transports away from a saturated receiving hospital.

    Workflow:
    1. Validate hospital exists.
    2. Identify all active allocations heading to this facility.
    3. For each active incident, find a suitable alternative hospital while preserving
       the assigned ambulance.
    4. Restore bed capacity at the saturated facility and reserve capacity at the destination.
    5. If any incident has no alternative hospital, preserve its current allocation and report
       an unresolved destination shortage.
    """
    hosp = query_db("SELECT * FROM hospitals WHERE id = ?;", (hospital_id,), one=True, db_path=db_path)
    if not hosp:
        return {"success": False, "error": f"Hospital with ID {hospital_id} not found."}

    active_allocs = query_db(
        "SELECT * FROM allocations WHERE hospital_id = ? AND allocation_status = 'ACTIVE';",
        (hospital_id,),
        db_path=db_path,
    )
    if not active_allocs:
        return {
            "success": True,
            "hospital_id": hospital_id,
            "hospital_name": hosp["name"],
            "affected_allocations": 0,
            "reallocated_count": 0,
            "unresolved_count": 0,
            "reallocations": [],
            "unresolved": [],
            "message": f"Hospital {hosp['name']} has zero active incoming transports to divert.",
        }

    reallocations = []
    unresolved = []

    for alloc in active_allocs:
        inc_id = alloc["incident_id"]
        res = reallocate_incident(
            incident_id=inc_id,
            reason=f"Hospital diversion from {hosp['name']}: {reason} ({exhausted_resource})",
            replace_ambulance=False,
            replace_hospital=True,
            excluded_hospital_ids=[hospital_id],
            db_path=db_path,
        )

        if res["success"]:
            reallocations.append({
                "incident_id": inc_id,
                "old_allocation_id": res["old_allocation_id"],
                "new_allocation_id": res["new_allocation_id"],
                "diverted_to": res["hospital"],
                "ambulance": res["ambulance"],
            })
            # Log individual diversion event
            div_desc = (
                f"[SIMULATED] HOSPITAL_SATURATED: Incident #{inc_id} diverted from "
                f"{hosp['name']} to {res['hospital']['name']} ({reason})."
            )
            try:
                with get_db(db_path) as conn:
                    conn.execute(
                        "INSERT INTO event_logs (event_type, description, related_incident_id) VALUES ('HOSPITAL_SATURATED', ?, ?);",
                        (div_desc, inc_id),
                    )
            except Exception:
                pass
        else:
            unresolved.append({
                "incident_id": inc_id,
                "allocation_id": alloc["id"],
                "error": res["error"],
            })
            # Log unresolved shortage
            short_desc = (
                f"[SIMULATED] SHORTAGE_UNRESOLVED: Failed to divert Incident #{inc_id} away from "
                f"{hosp['name']}: no alternative hospitals with sufficient capacity found."
            )
            try:
                with get_db(db_path) as conn:
                    conn.execute(
                        "INSERT INTO event_logs (event_type, description, related_incident_id) VALUES ('SHORTAGE_UNRESOLVED', ?, ?);",
                        (short_desc, inc_id),
                    )
            except Exception:
                pass

    all_diverted = (len(unresolved) == 0)
    return {
        "success": all_diverted,
        "hospital_id": hospital_id,
        "hospital_name": hosp["name"],
        "affected_allocations": len(active_allocs),
        "reallocated_count": len(reallocations),
        "unresolved_count": len(unresolved),
        "reallocations": reallocations,
        "unresolved": unresolved,
        "error": None if all_diverted else f"Failed to divert {len(unresolved)} of {len(active_allocs)} incoming transports due to alternative hospital bed shortages.",
    }



def handle_traffic_congestion_spike(
    traffic_zone_id: int,
    new_multiplier: float,
    new_congestion_level: str = "SEVERE",
    min_improvement_minutes: float = 5.0,
    db_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Handle sudden traffic congestion increase in a traffic corridor.

    Workflow:
    1. Validate zone ID and multiplier value (>= 1.0 and finite).
    2. Retrieve old multiplier and update traffic_zones table.
    3. Identify active allocations whose ambulance-to-incident corridor traverses the zone.
    4. Recalculate current ambulance ETA under updated congestion.
    5. Query candidate available alternative ambulances.
    6. Evaluate alternatives: reallocate only if ETA improvement is >= min_improvement_minutes
       (default 5.0 min) AND >= 25% faster.
    7. Preserve hospital reservations and unaffected allocations.
    8. Log traffic change in event_logs and return audit summary.
    """
    # 1. Validate multiplier value
    try:
        mult_float = float(new_multiplier)
    except (ValueError, TypeError):
        return {
            "success": False,
            "error": f"Invalid traffic multiplier '{new_multiplier}': must be a finite number >= 1.0.",
        }

    if not math.isfinite(mult_float) or mult_float < 1.0 or mult_float > 20.0:
        return {
            "success": False,
            "error": f"Invalid traffic multiplier {mult_float}: must be a finite number between 1.0 and 20.0.",
        }

    # 2. Validate traffic zone exists
    zone = query_db(
        "SELECT * FROM traffic_zones WHERE id = ?;",
        (traffic_zone_id,),
        one=True,
        db_path=db_path,
    )
    if not zone:
        return {"success": False, "error": f"Traffic zone with ID {traffic_zone_id} not found."}

    old_multiplier = float(zone["traffic_multiplier"])
    zone_coord = (float(zone["latitude"]), float(zone["longitude"]))

    # 3. Atomically update traffic zone and log event
    try:
        with get_db(db_path) as conn:
            conn.execute(
                "UPDATE traffic_zones SET traffic_multiplier = ?, congestion_level = ? WHERE id = ?;",
                (mult_float, str(new_congestion_level), traffic_zone_id),
            )
            spike_log = (
                f"[SIMULATED] TRAFFIC_SPIKE: Zone '{zone['zone_name']}' congestion increased to "
                f"{new_congestion_level} (multiplier: {old_multiplier:.2f}x -> {mult_float:.2f}x)."
            )
            conn.execute(
                "INSERT INTO event_logs (event_type, description, related_incident_id) VALUES ('TRAFFIC_SPIKE', ?, NULL);",
                (spike_log,),
            )
    except Exception as exc:
        return {"success": False, "error": f"Failed to update traffic zone in database: {str(exc)}"}

    # 4. Identify active allocations
    active_allocs = query_db(
        "SELECT * FROM allocations WHERE allocation_status = 'ACTIVE';",
        db_path=db_path,
    )
    updated_traffic_zones = query_db("SELECT * FROM traffic_zones;", db_path=db_path)

    affected_count = 0
    reallocations_performed = 0
    evaluations = []

    # 5. Evaluate each active dispatch
    for alloc in active_allocs:
        inc_id = alloc["incident_id"]
        amb_id = alloc["ambulance_id"]

        inc = query_db("SELECT * FROM incidents WHERE id = ?;", (inc_id,), one=True, db_path=db_path)
        amb = query_db("SELECT * FROM ambulances WHERE id = ?;", (amb_id,), one=True, db_path=db_path)
        if not inc or not amb:
            continue

        inc_coord = (float(inc["latitude"]), float(inc["longitude"]))
        amb_coord = (float(amb["latitude"]), float(amb["longitude"]))

        # Check if ambulance route traverses the congested zone
        is_affected = is_route_affected_by_zone(
            origin=amb_coord,
            destination=inc_coord,
            zone_coord=zone_coord,
            zone_influence_km=2.5,
        )

        if not is_affected:
            evaluations.append({
                "incident_id": inc_id,
                "allocation_id": alloc["id"],
                "status": "SKIPPED_NOT_AFFECTED",
                "reason": f"Corridor for {amb['ambulance_number']} does not intersect {zone['zone_name']}.",
            })
            continue

        affected_count += 1

        # Recalculate current ambulance ETA under new traffic conditions
        current_route = calculate_route(
            origin=amb_coord,
            destination=inc_coord,
            traffic_zones=updated_traffic_zones,
        )
        current_eta = current_route["traffic_adjusted_duration_minutes"]

        # Determine clinical requirements
        sev = estimate_severity(inc)
        reqs = sev["resource_requirements"]

        # Search for available alternative ambulances
        candidates = find_suitable_ambulances(
            incident=inc,
            requirements=reqs,
            traffic_zones=updated_traffic_zones,
            db_path=db_path,
        )
        # Exclude currently assigned ambulance
        alternative_ambs = [c for c in candidates if c["ambulance_id"] != amb_id]

        if not alternative_ambs:
            evaluations.append({
                "incident_id": inc_id,
                "allocation_id": alloc["id"],
                "status": "RETAINED_NO_ALTERNATIVES",
                "current_eta": current_eta,
                "reason": "No alternative idle ambulances currently available matching requirement.",
            })
            continue

        best_alt = alternative_ambs[0]
        alt_eta = best_alt["estimated_arrival_minutes"]
        eta_improvement = current_eta - alt_eta
        eta_improvement_pct = (eta_improvement / current_eta * 100.0) if current_eta > 0 else 0.0

        # Enforce threshold hysteresis: at least min_improvement_minutes (5m) AND at least 25% faster
        if eta_improvement >= min_improvement_minutes and eta_improvement_pct >= 25.0:
            realloc_res = reallocate_incident(
                incident_id=inc_id,
                reason=(
                    f"Traffic spike in {zone['zone_name']} ({old_multiplier:.2f}x -> {mult_float:.2f}x). "
                    f"Alternative unit {best_alt['ambulance_number']} arrives {eta_improvement:.1f}m faster "
                    f"({current_eta:.1f}m -> {alt_eta:.1f}m, {eta_improvement_pct:.1f}% reduction)."
                ),
                replace_ambulance=True,
                replace_hospital=False,
                excluded_ambulance_ids=[amb_id],
                old_ambulance_new_status="AVAILABLE",
                db_path=db_path,
            )

            if realloc_res["success"]:
                reallocations_performed += 1
                evaluations.append({
                    "incident_id": inc_id,
                    "old_allocation_id": alloc["id"],
                    "new_allocation_id": realloc_res["new_allocation_id"],
                    "status": "REALLOCATED",
                    "old_ambulance": amb["ambulance_number"],
                    "new_ambulance": best_alt["ambulance_number"],
                    "current_eta": current_eta,
                    "new_eta": alt_eta,
                    "saved_minutes": eta_improvement,
                    "saved_percentage": eta_improvement_pct,
                })
            else:
                evaluations.append({
                    "incident_id": inc_id,
                    "allocation_id": alloc["id"],
                    "status": "FAILED",
                    "error": realloc_res["error"],
                })
        else:
            evaluations.append({
                "incident_id": inc_id,
                "allocation_id": alloc["id"],
                "status": "RETAINED_INSUFFICIENT_IMPROVEMENT",
                "current_eta": current_eta,
                "alt_eta": alt_eta,
                "improvement_minutes": eta_improvement,
                "improvement_percentage": eta_improvement_pct,
                "reason": (
                    f"Alternative {best_alt['ambulance_number']} (ETA {alt_eta:.1f}m) does not meet hysteresis threshold "
                    f"(saves {eta_improvement:.1f}m < {min_improvement_minutes:.1f}m or {eta_improvement_pct:.1f}% < 25%)."
                ),
            })

    return {
        "success": True,
        "traffic_zone": {
            "id": traffic_zone_id,
            "name": zone["zone_name"],
            "congestion_level": str(new_congestion_level),
        },
        "previous_multiplier": old_multiplier,
        "new_multiplier": mult_float,
        "affected_allocations_evaluated": affected_count,
        "reallocations_performed": reallocations_performed,
        "evaluations": evaluations,
    }
