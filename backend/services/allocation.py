"""ResQGrid Allocation Engine

Coordinates emergency resource dispatch by matching active incidents with suitable
ambulances and hospitals based on clinical severity, capability requirements,
real-time traffic corridor delays, and hospital capacity constraints.

Capacity Reservation Assumption:
In this single-ambulance dispatch prototype, each committed allocation reserves
1 available bed (and 1 available ICU bed if icu_required is True) at the receiving
hospital. Capacities are decremented conditionally within an atomic transaction
to prevent negative inventory or partial allocations.
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from backend.database import get_db, query_db
from backend.services.routing import calculate_route
from backend.services.severity import estimate_severity


def find_suitable_ambulances(
    incident: Dict[str, Any],
    requirements: Dict[str, Any],
    traffic_zones: Optional[List[Dict[str, Any]]] = None,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Retrieve and rank available ambulances matching capability and proximity.

    Criteria:
    1. status = 'AVAILABLE' and assigned_incident_id IS NULL.
    2. Exclude ambulances with an existing ACTIVE allocation.
    3. Strict capability matching:
       - If ALS is required, BLS/PATIENT_TRANSPORT are strictly disqualified.
       - If BLS is required, ALS or BLS can be used.
       - If PATIENT_TRANSPORT is required, any capability can be used.
    4. Compute traffic-adjusted travel time from ambulance to incident scene.
    5. Sort ascending by traffic_adjusted_duration_minutes (ETA).

    Returns:
        List of candidate dictionaries sorted by lowest ETA.
    """
    incident_coord = (float(incident["latitude"]), float(incident["longitude"]))
    required_capability = str(requirements.get("ambulance_type", "BLS")).upper()

    # Retrieve traffic zones if not provided
    if traffic_zones is None:
        if conn is not None:
            cur = conn.cursor()
            cur.execute("SELECT * FROM traffic_zones;")
            traffic_zones = [dict(r) for r in cur.fetchall()]
        else:
            traffic_zones = query_db("SELECT * FROM traffic_zones;", db_path=db_path)

    # Query idle ambulances without active allocation records
    query = """
        SELECT id, ambulance_number, latitude, longitude, status, capability,
               assigned_incident_id, current_speed
        FROM ambulances
        WHERE status = 'AVAILABLE'
          AND assigned_incident_id IS NULL
          AND id NOT IN (
              SELECT ambulance_id FROM allocations WHERE allocation_status = 'ACTIVE'
          );
    """
    if conn is not None:
        cur = conn.cursor()
        cur.execute(query)
        ambulances = [dict(r) for r in cur.fetchall()]
    else:
        ambulances = query_db(query, db_path=db_path)

    candidates = []
    for amb in ambulances:
        amb_cap = str(amb.get("capability", "")).upper()

        # Enforce capability constraints
        if required_capability == "ALS":
            if amb_cap != "ALS":
                continue  # Never substitute BLS or transport when ALS is mandatory
        elif required_capability == "BLS":
            if amb_cap not in ("BLS", "ALS"):
                continue
        elif required_capability == "PATIENT_TRANSPORT":
            if amb_cap not in ("PATIENT_TRANSPORT", "BLS", "ALS"):
                continue

        amb_coord = (float(amb["latitude"]), float(amb["longitude"]))
        route = calculate_route(
            origin=amb_coord,
            destination=incident_coord,
            traffic_zones=traffic_zones,
        )
        eta_minutes = route["traffic_adjusted_duration_minutes"]
        road_km = route["estimated_road_distance_km"]
        traffic_mult = route["traffic_multiplier"]

        candidates.append({
            "ambulance_id": amb["id"],
            "ambulance_number": amb["ambulance_number"],
            "capability": amb["capability"],
            "estimated_arrival_minutes": eta_minutes,
            "road_distance_km": road_km,
            "traffic_multiplier": traffic_mult,
            "selection_explanation": (
                f"Ambulance {amb['ambulance_number']} ({amb['capability']}) ETA {eta_minutes:.1f}m, "
                f"road distance {road_km:.1f}km through traffic corridor multiplier {traffic_mult:.2f}x."
            ),
        })

    # Sort candidates by shortest traffic-adjusted ETA
    candidates.sort(key=lambda c: c["estimated_arrival_minutes"])
    return candidates


def find_suitable_hospitals(
    incident: Dict[str, Any],
    requirements: Dict[str, Any],
    traffic_zones: Optional[List[Dict[str, Any]]] = None,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Retrieve and rank candidate hospitals based on capacity, specialty, and ETA.

    Criteria:
    1. Mandatory capacity:
       - Available general beds >= 1.
       - If icu_required is True: available ICU beds >= 1.
       - If ventilator is required: available ventilators >= 1.
    2. Requirement compatibility:
       - Match clinical specialties (Cardiology for cardiac emergencies, Level-1 Trauma for accidents).
    3. Traffic-adjusted ETA from incident scene to hospital emergency entrance.
    4. Rank candidates:
       1st: Requirement compatibility score (higher is better)
       2nd: Traffic-adjusted ETA (lower is better)
       3rd: Available emergency capacity (higher is better)

    Returns:
        List of candidate dictionaries sorted by suitability ranking.
    """
    incident_coord = (float(incident["latitude"]), float(incident["longitude"]))
    icu_needed = bool(requirements.get("icu_required", False))

    # Detect mandatory ventilator requirement from incident symptoms/narrative
    incident_narrative = (
        str(incident.get("description", "")) + " " +
        str(incident.get("critical_symptoms", "")) + " " +
        str(incident.get("title", ""))
    ).lower()
    ventilator_needed = any(
        kw in incident_narrative
        for kw in ("cardiac arrest", "respiratory distress", "airway compromise", "unresponsive", "stemi")
    )

    # Retrieve traffic zones if not provided
    if traffic_zones is None:
        if conn is not None:
            cur = conn.cursor()
            cur.execute("SELECT * FROM traffic_zones;")
            traffic_zones = [dict(r) for r in cur.fetchall()]
        else:
            traffic_zones = query_db("SELECT * FROM traffic_zones;", db_path=db_path)

    query = """
        SELECT id, name, latitude, longitude, total_beds, available_beds,
               total_icu_beds, available_icu_beds, available_ventilators,
               emergency_capacity, specialties
        FROM hospitals;
    """
    if conn is not None:
        cur = conn.cursor()
        cur.execute(query)
        hospitals = [dict(r) for r in cur.fetchall()]
    else:
        hospitals = query_db(query, db_path=db_path)

    candidates = []
    incident_type = str(incident.get("incident_type", "")).upper()

    for hosp in hospitals:
        # Mandatory capacity rules: never select a facility that fails capacity
        if hosp["available_beds"] < 1:
            continue
        if icu_needed and hosp["available_icu_beds"] < 1:
            continue
        if ventilator_needed and hosp["available_ventilators"] < 1:
            continue

        # Evaluate clinical specialty compatibility
        specialties_text = str(hosp.get("specialties", "")).lower()
        compatibility_score = 0
        if "CARDIAC" in incident_type and ("cardio" in specialties_text or "cath lab" in specialties_text):
            compatibility_score += 15
        if ("ACCIDENT" in incident_type or "TRAUMA" in incident_type) and "trauma" in specialties_text:
            compatibility_score += 15
        if "FLOOD" in incident_type and ("mass casualty" in specialties_text or "emergency" in specialties_text):
            compatibility_score += 10
        if "burn" in incident_narrative and "burn" in specialties_text:
            compatibility_score += 15

        hosp_coord = (float(hosp["latitude"]), float(hosp["longitude"]))
        route = calculate_route(
            origin=incident_coord,
            destination=hosp_coord,
            traffic_zones=traffic_zones,
        )
        eta_minutes = route["traffic_adjusted_duration_minutes"]
        road_km = route["estimated_road_distance_km"]
        traffic_mult = route["traffic_multiplier"]

        explanation_parts = [
            f"{hosp['name']} ETA {eta_minutes:.1f}m ({road_km:.1f}km, corridor {traffic_mult:.2f}x).",
            f"Available capacity: {hosp['available_beds']} beds, {hosp['available_icu_beds']} ICU, {hosp['available_ventilators']} vents.",
        ]
        if compatibility_score > 0:
            explanation_parts.append(f"Specialty match confirmed ({specialties_text}).")

        candidates.append({
            "hospital_id": hosp["id"],
            "name": hosp["name"],
            "estimated_arrival_minutes": eta_minutes,
            "road_distance_km": road_km,
            "traffic_multiplier": traffic_mult,
            "available_beds": hosp["available_beds"],
            "available_icu_beds": hosp["available_icu_beds"],
            "available_ventilators": hosp["available_ventilators"],
            "emergency_capacity": hosp["emergency_capacity"],
            "specialties": hosp["specialties"],
            "compatibility_score": compatibility_score,
            "selection_explanation": " ".join(explanation_parts),
        })

    # Ranking:
    # 1. Compatibility score (descending)
    # 2. Traffic-adjusted ETA (ascending)
    # 3. Emergency capacity as tie-breaker (descending)
    candidates.sort(
        key=lambda h: (
            -h["compatibility_score"],
            h["estimated_arrival_minutes"],
            -h["emergency_capacity"],
        )
    )
    return candidates


def allocate_incident(
    incident_id: int,
    db_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Execute end-to-end atomic resource allocation for an incident.

    Workflow:
    1. Retrieve and validate incident status.
    2. Calculate triage severity requirements.
    3. Query suitable ambulances and hospitals.
    4. Handle resource shortages gracefully without partial allocation.
    5. Within an atomic transaction, conditionally update resources, commit
       the active allocation, and record an immutable event log.

    Returns:
        Structured response dictionary detailing the allocation outcome.
    """
    def _error_response(msg: str, sev: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "success": False,
            "incident_id": incident_id,
            "allocation_id": None,
            "ambulance": None,
            "hospital": None,
            "estimated_arrival_minutes": None,
            "severity": sev,
            "decision_reason": None,
            "error": msg,
        }

    # 1. Retrieve incident
    incident = query_db(
        "SELECT * FROM incidents WHERE id = ?;",
        (incident_id,),
        one=True,
        db_path=db_path,
    )
    if not incident:
        return _error_response(f"Incident with ID {incident_id} not found.")

    # 2. Reject non-allocatable statuses
    current_status = str(incident.get("status", "")).upper()
    if current_status in ("RESOLVED", "CANCELLED"):
        return _error_response(
            f"Cannot allocate resources: incident #{incident_id} is already marked {current_status}."
        )

    # 3. Reject incidents with existing ACTIVE allocations
    existing_allocation = query_db(
        "SELECT id FROM allocations WHERE incident_id = ? AND allocation_status = 'ACTIVE';",
        (incident_id,),
        one=True,
        db_path=db_path,
    )
    if existing_allocation:
        return _error_response(
            f"Incident #{incident_id} already has an active allocation (Allocation #{existing_allocation['id']})."
        )

    # 4. Assess severity requirements
    severity_info = estimate_severity(incident)
    requirements = severity_info["resource_requirements"]

    # 5. Retrieve traffic zones
    traffic_zones = query_db("SELECT * FROM traffic_zones;", db_path=db_path)

    # 6. Find suitable ambulances
    suitable_ambulances = find_suitable_ambulances(
        incident=incident,
        requirements=requirements,
        traffic_zones=traffic_zones,
        db_path=db_path,
    )
    if not suitable_ambulances:
        req_type = requirements.get("ambulance_type", "BLS")
        return _error_response(
            f"Resource shortage: No available ambulances match requirement '{req_type}'. "
            "Dispatch postponed pending unit availability.",
            sev=severity_info,
        )

    # 7. Find suitable hospitals
    suitable_hospitals = find_suitable_hospitals(
        incident=incident,
        requirements=requirements,
        traffic_zones=traffic_zones,
        db_path=db_path,
    )
    if not suitable_hospitals:
        return _error_response(
            "Resource shortage: No hospitals with sufficient bed/ICU capacity currently meet "
            "the incident's clinical requirements.",
            sev=severity_info,
        )

    # 8. Select optimal candidates
    best_amb = suitable_ambulances[0]
    best_hosp = suitable_hospitals[0]

    # Conservative reservation assumptions: 1 general bed, and 1 ICU bed if required
    reserved_beds = 1
    reserved_icu = 1 if requirements.get("icu_required") else 0

    # 9. Perform atomic transactional allocation
    try:
        with get_db(db_path) as conn:
            cursor = conn.cursor()

            # A. Recheck incident status under transaction
            cursor.execute("SELECT status FROM incidents WHERE id = ?;", (incident_id,))
            row = cursor.fetchone()
            if not row:
                raise RuntimeError(f"Incident #{incident_id} vanished during transaction.")
            if row["status"] in ("RESOLVED", "CANCELLED", "ASSIGNED"):
                raise RuntimeError(
                    f"Incident #{incident_id} status transitioned to {row['status']} concurrently."
                )

            # B. Recheck for concurrent active allocation on this incident
            cursor.execute(
                "SELECT id FROM allocations WHERE incident_id = ? AND allocation_status = 'ACTIVE';",
                (incident_id,),
            )
            if cursor.fetchone():
                raise RuntimeError(f"Concurrent active allocation detected on incident #{incident_id}.")

            # C. Atomically reserve the ambulance (conditional update)
            cursor.execute(
                """
                UPDATE ambulances
                SET status = 'DISPATCHED', assigned_incident_id = ?
                WHERE id = ? AND status = 'AVAILABLE' AND assigned_incident_id IS NULL;
                """,
                (incident_id, best_amb["ambulance_id"]),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"Ambulance {best_amb['ambulance_number']} was acquired by another dispatch concurrently."
                )

            # D. Atomically reserve hospital capacity (conditional update prevents negative inventory)
            cursor.execute(
                """
                UPDATE hospitals
                SET available_beds = available_beds - ?,
                    available_icu_beds = available_icu_beds - ?
                WHERE id = ? AND available_beds >= ? AND available_icu_beds >= ?;
                """,
                (
                    reserved_beds,
                    reserved_icu,
                    best_hosp["hospital_id"],
                    reserved_beds,
                    reserved_icu,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"Hospital {best_hosp['name']} capacity was exhausted concurrently."
                )

            # E. Update incident status
            cursor.execute(
                """
                UPDATE incidents
                SET status = 'ASSIGNED',
                    severity_score = ?,
                    severity_level = ?
                WHERE id = ? AND status NOT IN ('RESOLVED', 'CANCELLED');
                """,
                (
                    severity_info["severity_score"],
                    severity_info["severity_level"],
                    incident_id,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(f"Failed to update incident #{incident_id} status.")

            # F. Construct transparent decision justification and fulfillment tracking
            unfulfilled = {
                "ambulances": max(0, int(requirements.get("estimated_ambulances", 1)) - 1),
                "general_beds": max(0, int(requirements.get("general_beds_required", 1)) - reserved_beds),
                "icu_beds": max(0, int(requirements.get("estimated_icu_beds", 1)) - reserved_icu) if requirements.get("icu_required") else 0,
                "rescue_units": int(requirements.get("rescue_units_required", 0)),
            }
            is_partial = (
                unfulfilled["ambulances"] > 0
                or unfulfilled["general_beds"] > 0
                or unfulfilled["rescue_units"] > 0
                or unfulfilled["icu_beds"] > 0
            )
            fulfillment_status = "PARTIAL" if is_partial else "FULFILLED"

            fulfillment_note = (
                f"Fulfillment: PARTIAL (Dispatched primary unit 1/{requirements.get('estimated_ambulances', 1)} ambulances; "
                f"Pending: {unfulfilled['ambulances']} ambulance(s), {unfulfilled['general_beds']} general bed(s), "
                f"{unfulfilled['rescue_units']} rescue unit(s))."
                if is_partial else
                "Fulfillment: FULFILLED (All estimated triage resource requirements met by primary dispatch)."
            )

            decision_reason = (
                f"Dispatched {best_amb['capability']} unit {best_amb['ambulance_number']} "
                f"(ETA: {best_amb['estimated_arrival_minutes']:.1f}m, dist: {best_amb['road_distance_km']:.1f}km). "
                f"Assigned receiving facility {best_hosp['name']} "
                f"(Transit ETA: {best_hosp['estimated_arrival_minutes']:.1f}m, dist: {best_hosp['road_distance_km']:.1f}km). "
                f"Severity category: {severity_info['severity_level']} ({severity_info['severity_score']:.1f}/100 pts). "
                f"Reserved: {reserved_beds} general bed(s), {reserved_icu} ICU bed(s). {fulfillment_note}"
            )

            # G. Insert active allocation record
            cursor.execute(
                """
                INSERT INTO allocations (
                    incident_id, ambulance_id, hospital_id, estimated_arrival_minutes,
                    allocation_status, decision_reason
                ) VALUES (?, ?, ?, ?, 'ACTIVE', ?);
                """,
                (
                    incident_id,
                    best_amb["ambulance_id"],
                    best_hosp["hospital_id"],
                    best_amb["estimated_arrival_minutes"],
                    decision_reason,
                ),
            )
            allocation_id = cursor.lastrowid

            # H. Insert immutable event log entry
            log_desc = (
                f"[SIMULATED] Allocation #{allocation_id} committed: Dispatched "
                f"{best_amb['ambulance_number']} ({best_amb['capability']}) and designated "
                f"{best_hosp['name']} for Incident #{incident_id}. [{fulfillment_status}]"
            )
            cursor.execute(
                """
                INSERT INTO event_logs (event_type, description, related_incident_id)
                VALUES ('RESOURCE_ALLOCATED', ?, ?);
                """,
                (log_desc, incident_id),
            )

        # Successful commit
        return {
            "success": True,
            "incident_id": incident_id,
            "allocation_id": allocation_id,
            "fulfillment_status": fulfillment_status,
            "resources_reserved": {
                "ambulances": 1,
                "general_beds": reserved_beds,
                "icu_beds": reserved_icu,
                "rescue_units": 0,
            },
            "unfulfilled_requirements": unfulfilled,
            "ambulance": {
                "id": best_amb["ambulance_id"],
                "ambulance_number": best_amb["ambulance_number"],
                "capability": best_amb["capability"],
                "estimated_arrival_minutes": best_amb["estimated_arrival_minutes"],
                "road_distance_km": best_amb["road_distance_km"],
                "traffic_multiplier": best_amb["traffic_multiplier"],
            },
            "hospital": {
                "id": best_hosp["hospital_id"],
                "name": best_hosp["name"],
                "estimated_arrival_minutes": best_hosp["estimated_arrival_minutes"],
                "road_distance_km": best_hosp["road_distance_km"],
                "traffic_multiplier": best_hosp["traffic_multiplier"],
                "specialties": best_hosp["specialties"],
            },
            "estimated_arrival_minutes": best_amb["estimated_arrival_minutes"],
            "severity": {
                "severity_score": severity_info["severity_score"],
                "severity_level": severity_info["severity_level"],
                "resource_requirements": severity_info["resource_requirements"],
            },
            "decision_reason": decision_reason,
            "error": None,
        }

    except Exception as exc:
        # Transaction automatically rolled back by get_db() context manager
        return _error_response(f"Allocation transaction aborted: {str(exc)}", sev=severity_info)

