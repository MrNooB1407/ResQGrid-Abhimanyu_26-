"""ResQGrid Severity Estimation Engine

Transparent rule-based scoring module for emergency triage and severity assessment.
Calculates a severity score (0–100), categorization, resource requirement estimates,
and detailed human-readable audit explanations.

Disclaimer: These calculations are automated triage prototypes for emergency logistics
and resource dispatch coordination, not clinical diagnostic advice.
"""

from typing import Any, Dict, List, Optional, Union

# Severity category thresholds
SEVERITY_THRESHOLDS = {
    "CRITICAL": 85.0,
    "HIGH": 65.0,
    "MEDIUM": 35.0,
    "LOW": 0.0,
}

# Base weights for recognized emergency incident types
INCIDENT_TYPE_BASE_SCORES = {
    "CARDIAC_EMERGENCY": 50.0,
    "STROKE": 46.0,
    "RESPIRATORY_ARREST": 48.0,
    "ROAD_ACCIDENT": 38.0,
    "MASS_CASUALTY": 48.0,
    "EXPLOSION": 45.0,
    "STRUCTURAL_COLLAPSE": 42.0,
    "URBAN_FLOODING": 32.0,
    "FIRE": 36.0,
    "INDUSTRIAL_HAZARD": 34.0,
    "SEVERE_TRAUMA": 40.0,
    "FALL_FROM_HEIGHT": 28.0,
    "ASSAULT": 26.0,
    "MINOR_ACCIDENT": 12.0,
    "MINOR_INJURY": 10.0,
    "NON_CRITICAL": 8.0,
}

# Symptom keywords and their severity contribution
CRITICAL_SYMPTOMS = {
    "cardiac arrest": 25.0,
    "unresponsive": 22.0,
    "unconscious": 20.0,
    "severe chest pain": 18.0,
    "respiratory distress": 18.0,
    "massive hemorrhage": 20.0,
    "heavy bleeding": 16.0,
    "polytrauma": 18.0,
    "airway compromise": 22.0,
    "severe burn": 16.0,
    "third degree burn": 18.0,
    "drowning": 18.0,
    "hypothermia": 12.0,
    "head trauma": 16.0,
    "altered mental status": 14.0,
    "fracture": 8.0,
    "smoke inhalation": 12.0,
    "mild pain": 2.0,
    "abrasion": 1.0,
    "sprain": 2.0,
}

# Environmental hazard keywords and their contribution
ENVIRONMENTAL_HAZARDS = {
    "structural collapse": 16.0,
    "building collapse": 16.0,
    "wall collapse": 14.0,
    "rising floodwater": 15.0,
    "flash flood": 15.0,
    "trapped": 14.0,
    "active fire": 16.0,
    "toxic chemical": 18.0,
    "gas leak": 16.0,
    "hazardous materials": 16.0,
    "live electrical wire": 14.0,
    "explosion risk": 16.0,
    "highway traffic": 6.0,
    "waterlogged": 8.0,
    "heavy rain": 5.0,
}


def _normalize_string_list(raw_input: Union[List[str], str, None]) -> List[str]:
    """Helper to safely convert strings or lists into lowercase stripped string items."""
    if not raw_input:
        return []
    if isinstance(raw_input, list):
        items = []
        for item in raw_input:
            if isinstance(item, str):
                items.extend([sub.strip().lower() for sub in item.split(",") if sub.strip()])
        return items
    if isinstance(raw_input, str):
        return [sub.strip().lower() for sub in raw_input.split(",") if sub.strip()]
    return []


def estimate_severity(incident_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate transparent rule-based emergency severity score (0-100).

    Inputs within incident_data:
    - incident_type (str)
    - injured_people (int)
    - affected_people (int)
    - critical_symptoms (list of str or comma-separated str)
    - environmental_danger (list of str or comma-separated str)
    - description (str, optional contextual keywords)

    Returns:
    Dict containing:
    - severity_score (float, 0-100)
    - severity_level ("CRITICAL" | "HIGH" | "MEDIUM" | "LOW")
    - resource_requirements (Dict)
    - explanation (List[str])
    """
    if not isinstance(incident_data, dict):
        incident_data = {}

    explanation: List[str] = []
    total_score: float = 0.0

    # 1. Base Score from Incident Type
    raw_type = str(incident_data.get("incident_type", "")).strip().upper()
    matched_type = None
    if raw_type:
        for known_type, base_val in INCIDENT_TYPE_BASE_SCORES.items():
            if known_type in raw_type or raw_type in known_type:
                matched_type = known_type
                total_score += base_val
                explanation.append(f"Base incident type '{matched_type}': +{base_val:.1f} pts")
                break

    if not matched_type:
        if raw_type:
            default_base = 20.0
            total_score += default_base
            explanation.append(f"Unclassified incident type '{raw_type}': +{default_base:.1f} pts")
        else:
            default_base = 10.0
            total_score += default_base
            explanation.append("Unspecified incident type (default baseline): +10.0 pts")

    # 2. Impact of Injured Casualties
    raw_injured = incident_data.get("injured_people", 0)
    try:
        injured_count = max(0, int(raw_injured))
    except (ValueError, TypeError):
        injured_count = 0

    if injured_count > 0:
        if injured_count == 1:
            injury_pts = 8.0
        elif 2 <= injured_count <= 3:
            injury_pts = 16.0
        elif 4 <= injured_count <= 5:
            injury_pts = 24.0
        else:
            injury_pts = min(30.0, 24.0 + (injured_count - 5) * 1.5)
        total_score += injury_pts
        explanation.append(f"Casualty scale ({injured_count} injured): +{injury_pts:.1f} pts")
    else:
        explanation.append("Zero reported injuries: +0.0 pts")

    # 3. Impact of Affected / Trapped Population
    raw_affected = incident_data.get("affected_people", 0)
    try:
        affected_count = max(0, int(raw_affected))
    except (ValueError, TypeError):
        affected_count = 0

    uninjured_affected = max(0, affected_count - injured_count)
    if uninjured_affected > 0:
        affected_pts = min(15.0, uninjured_affected * 1.2)
        total_score += affected_pts
        explanation.append(
            f"Vulnerable population exposure ({uninjured_affected} uninjured at-risk): +{affected_pts:.1f} pts"
        )

    # 4. Critical Symptoms Analysis
    symptoms_list = _normalize_string_list(incident_data.get("critical_symptoms"))
    description_text = str(incident_data.get("description", "")).lower()

    detected_symptom_scores = []
    for symptom_key, weight in CRITICAL_SYMPTOMS.items():
        # Check explicit list or in description text
        if any(symptom_key in s for s in symptoms_list) or (symptom_key in description_text):
            detected_symptom_scores.append((symptom_key, weight))

    if detected_symptom_scores:
        # Avoid duplicate counting of similar terms; pick max items with diminishing returns
        detected_symptom_scores.sort(key=lambda x: x[1], reverse=True)
        primary_symptom_pts = detected_symptom_scores[0][1]
        secondary_symptom_pts = sum(s[1] * 0.4 for s in detected_symptom_scores[1:])
        symptom_total = min(30.0, primary_symptom_pts + secondary_symptom_pts)
        total_score += symptom_total
        symptom_names = ", ".join(f"'{s[0]}'" for s in detected_symptom_scores[:3])
        explanation.append(f"Critical symptoms detected ({symptom_names}): +{symptom_total:.1f} pts")

    # 5. Environmental Hazards Analysis
    hazard_list = _normalize_string_list(incident_data.get("environmental_danger"))
    detected_hazards = []
    for hazard_key, weight in ENVIRONMENTAL_HAZARDS.items():
        if any(hazard_key in h for h in hazard_list) or (hazard_key in description_text):
            detected_hazards.append((hazard_key, weight))

    if detected_hazards:
        detected_hazards.sort(key=lambda x: x[1], reverse=True)
        primary_hazard_pts = detected_hazards[0][1]
        secondary_hazard_pts = sum(h[1] * 0.35 for h in detected_hazards[1:])
        hazard_total = min(20.0, primary_hazard_pts + secondary_hazard_pts)
        total_score += hazard_total
        hazard_names = ", ".join(f"'{h[0]}'" for h in detected_hazards[:2])
        explanation.append(f"Environmental hazards detected ({hazard_names}): +{hazard_total:.1f} pts")

    # Final Score Normalization (Clamp to 0-100)
    final_score = round(min(100.0, max(0.0, total_score)), 1)

    # Determine Severity Category
    if final_score >= SEVERITY_THRESHOLDS["CRITICAL"]:
        severity_level = "CRITICAL"
    elif final_score >= SEVERITY_THRESHOLDS["HIGH"]:
        severity_level = "HIGH"
    elif final_score >= SEVERITY_THRESHOLDS["MEDIUM"]:
        severity_level = "MEDIUM"
    else:
        severity_level = "LOW"

    # 6. Estimate Resource Requirements
    # Ambulance Type
    has_cardiac = (
        "CARDIAC" in raw_type
        or any("cardiac" in s[0] for s in detected_symptom_scores)
        or any(k in description_text for k in ("cardiac", "myocardial infarction", "stemi", "cpr"))
    )
    has_airway = (
        any(s[0] in ("airway compromise", "respiratory distress", "unresponsive") for s in detected_symptom_scores)
        or any(k in description_text for k in ("airway compromise", "respiratory distress", "unresponsive", "unconscious"))
    )
    has_trauma = (
        any(s[0] in ("polytrauma", "massive hemorrhage", "severe burn") for s in detected_symptom_scores)
        or any(k in description_text for k in ("polytrauma", "massive hemorrhage", "severe bleeding"))
    )

    if severity_level == "CRITICAL" or has_cardiac or has_airway or has_trauma:
        recommended_ambulance_type = "ALS"
    elif severity_level == "HIGH":
        recommended_ambulance_type = "ALS" if injured_count >= 2 else "BLS"
    elif severity_level == "MEDIUM":
        recommended_ambulance_type = "BLS"
    else:
        recommended_ambulance_type = "PATIENT_TRANSPORT" if injured_count > 0 else "NONE"

    # Ambulance Count
    if injured_count == 0:
        estimated_ambulances = 1 if severity_level in ("CRITICAL", "HIGH") else 0
    elif injured_count == 1:
        estimated_ambulances = 1
    elif 2 <= injured_count <= 3:
        estimated_ambulances = 2
    elif 4 <= injured_count <= 5:
        estimated_ambulances = 3
    else:
        estimated_ambulances = max(1, (injured_count + 1) // 2)

    # ICU Bed Need
    icu_required = (severity_level == "CRITICAL") or has_cardiac or (has_trauma and injured_count > 0)
    if icu_required:
        estimated_icu_beds = max(1, 1 if injured_count <= 1 else (injured_count + 1) // 2)
    else:
        estimated_icu_beds = 0

    # General Beds
    general_beds_required = max(injured_count, 1 if severity_level in ("HIGH", "CRITICAL") else 0)

    # Rescue Units Requirement
    has_flood_or_collapse = any(h[0] in ("structural collapse", "building collapse", "wall collapse", "flash flood", "rising floodwater", "trapped") for h in detected_hazards)
    if has_flood_or_collapse:
        rescue_units_required = max(1, (affected_count + 4) // 5)
    else:
        rescue_units_required = 0

    resource_requirements = {
        "ambulance_type": recommended_ambulance_type,
        "estimated_ambulances": estimated_ambulances,
        "icu_required": icu_required,
        "estimated_icu_beds": estimated_icu_beds,
        "general_beds_required": general_beds_required,
        "rescue_units_required": rescue_units_required,
    }

    explanation.append(f"Calculated composite score: {final_score}/100 -> Category: {severity_level}")
    explanation.append(
        "Disclaimer: These are prototype triage estimates for emergency coordination, not clinical medical diagnoses."
    )

    return {
        "severity_score": final_score,
        "severity_level": severity_level,
        "resource_requirements": resource_requirements,
        "explanation": explanation,
    }
