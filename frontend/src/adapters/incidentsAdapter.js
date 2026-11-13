/**
 * ResQGrid Incidents Data Adapter
 *
 * Normalizes backend Incident records from `/api/incidents` into the UI structures
 * expected by IncidentFeed.jsx, EmergencyMap.jsx, and IncidentsView.jsx.
 */

import { projectCoordinates } from './geoAdapter.js';

/**
 * State machine display and badge mapping.
 * Preserves the original backend status in `backendStatus` while providing
 * UI-compatible status strings for components.
 */
export const INCIDENT_STATUS_MAP = Object.freeze({
  REPORTED: {
    displayStatus: 'REPORTED',
    badgeClass: 'reported',
    label: 'Reported / Queued',
  },
  ASSIGNED: {
    displayStatus: 'DISPATCHED',
    badgeClass: 'dispatched',
    label: 'Unit Dispatched',
  },
  IN_TRANSIT: {
    displayStatus: 'EN_ROUTE',
    badgeClass: 'en_route',
    label: 'En Route',
  },
  RESOLVED: {
    displayStatus: 'RESOLVED',
    badgeClass: 'resolved',
    label: 'Resolved',
  },
  CANCELLED: {
    displayStatus: 'CANCELLED',
    badgeClass: 'cancelled',
    label: 'Cancelled',
  },
});

/**
 * Formats an ISO/SQLite timestamp into a relative "X min ago" string.
 *
 * @param {string|Date|null} timestampStr
 * @returns {string}
 */
export function formatRelativeTime(timestampStr) {
  if (!timestampStr) return 'Just now';

  try {
    const eventTime = new Date(timestampStr.replace(' ', 'T') + (timestampStr.includes('Z') ? '' : 'Z'));
    if (isNaN(eventTime.getTime())) return 'Recently';

    const now = new Date();
    const diffMs = now.getTime() - eventTime.getTime();
    const diffMinutes = Math.floor(diffMs / 60000);

    if (diffMinutes <= 0) return 'Just now';
    if (diffMinutes === 1) return '1 min ago';
    if (diffMinutes < 60) return `${diffMinutes} min ago`;

    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours === 1) return '1 hour ago';
    if (diffHours < 24) return `${diffHours} hours ago`;

    return eventTime.toLocaleDateString();
  } catch {
    return 'Recently';
  }
}

/**
 * Derives a human-readable display location solely from provided incident fields
 * (such as explicit location fields, narrative description/title landmarks, or coordinates).
 * Strictly avoids substituting fabricated fallback strings like "Hyderabad Sector".
 *
 * @param {object} raw - Raw incident object
 * @param {string} cleanDesc - Sanitized narrative description
 * @param {string} cleanTitle - Sanitized incident title
 * @param {number|null} lat - Valid latitude if provided
 * @param {number|null} lon - Valid longitude if provided
 * @returns {string|null} - Real derived display location, or null if unprovided
 */
export function deriveIncidentLocation(raw, cleanDesc = '', cleanTitle = '', lat = null, lon = null) {
  if (!raw || typeof raw !== 'object') return null;

  // 1. Check if an explicit location name or field was directly provided
  if (typeof raw.location_name === 'string' && raw.location_name.trim()) {
    return raw.location_name.trim();
  }
  if (typeof raw.location === 'string' && raw.location.trim()) {
    return raw.location.trim();
  }
  if (typeof raw.landmark === 'string' && raw.landmark.trim()) {
    return raw.landmark.trim();
  }

  // 2. Extract landmark/corridor from narrative description or title using spatial prepositions
  // Matches "near <Location>", "on <Location>", "at <Location>", "in <Location>", "along <Location>"
  const textSources = [cleanDesc, cleanTitle].filter(Boolean);
  for (const text of textSources) {
    const match = text.match(/\b(?:near|on|at|in|along)\s+([^;,!?\n]+)/i);
    if (match && match[1]) {
      let candidate = match[1]
        .split(/(?<!\bNo)\.\s+|\.$|;\s*|\b(?:and|with|requir|trapped|involving)\b/i)[0]
        .trim();
      // Remove any trailing punctuation
      candidate = candidate.replace(/[.,;:]+$/, '').trim();

      if (candidate.length >= 3 && candidate.length <= 50) {
        return candidate;
      }
    }
  }

  // 3. Fallback to exact coordinates if latitude and longitude numbers are provided
  if (typeof lat === 'number' && typeof lon === 'number' && Number.isFinite(lat) && Number.isFinite(lon)) {
    return `${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E`;
  }

  // 4. Do NOT silently substitute a fabricated location name
  return null;
}

/**
 * Adapts a single raw incident record from SQLite into the frontend data shape.
 *
 * @param {object|null|undefined} raw - Raw API response item
 * @returns {object|null}
 */
export function adaptIncident(raw) {
  if (!raw || typeof raw !== 'object') return null;

  const rawId = raw.id ?? null;
  const backendStatus = String(raw.status || 'REPORTED').toUpperCase();
  const statusMeta = INCIDENT_STATUS_MAP[backendStatus] || {
    displayStatus: backendStatus,
    badgeClass: 'unknown',
    label: backendStatus,
  };

  // Strip simulated tag if present for clean UI display
  const rawTitle = raw.title || 'Untitled Emergency';
  const cleanTitle = rawTitle.replace(/^\[SIMULATED\]\s*/i, '').trim();

  const rawDesc = raw.description || '';
  const cleanDesc = rawDesc.replace(/^\[SIMULATED\]\s*/i, '').trim();

  // Validate coordinates and project to SVG percentage coordinates
  const validLat = typeof raw.latitude === 'number' && Number.isFinite(raw.latitude) ? raw.latitude : null;
  const validLon = typeof raw.longitude === 'number' && Number.isFinite(raw.longitude) ? raw.longitude : null;
  const coordinates = projectCoordinates(raw.latitude, raw.longitude);

  // Derive location truthfully from provided fields or coordinates (no fabrication)
  const location = deriveIncidentLocation(raw, cleanDesc, cleanTitle, validLat, validLon);

  // Active allocation information (support nested current_allocation or flat fields)
  const alloc = (raw.current_allocation && typeof raw.current_allocation === 'object') ? raw.current_allocation : {};
  const ambNum = alloc.ambulance_number || raw.ambulance_number || null;
  const ambCap = alloc.ambulance_capability || raw.ambulance_capability || null;
  const hospName = alloc.hospital_name || raw.hospital_name || null;
  const rawEta = alloc.estimated_arrival_minutes ?? raw.estimated_arrival_minutes;
  const activeAllocId = alloc.allocation_id ?? raw.active_allocation_id ?? null;

  let assignedAmbulance = null;
  if (ambNum) {
    assignedAmbulance = ambCap
      ? `${ambNum} (${ambCap})`
      : String(ambNum);
  }

  let assignedHospital = null;
  if (hospName) {
    assignedHospital = hospName.replace(/^\[SIMULATED\]\s*/i, '').trim();
  }

  const etaMinutes =
    typeof rawEta === 'number'
      ? Math.round(rawEta * 10) / 10
      : null;

  const severityScore =
    typeof raw.severity_score === 'number'
      ? Math.round(raw.severity_score * 10) / 10
      : 0;

  const severity = String(raw.severity_level || 'LOW').toUpperCase();

  return {
    // Identifiers
    id: rawId !== null ? String(rawId) : '',
    rawId: rawId,
    backendId: rawId,
    code: rawId !== null ? `INC-${String(rawId).padStart(3, '0')}` : '',

    // Clinical & Type Metadata
    type: String(raw.incident_type || 'GENERAL_EMERGENCY').toUpperCase(),
    incidentType: String(raw.incident_type || 'GENERAL_EMERGENCY').toUpperCase(),
    title: cleanTitle,
    rawTitle: rawTitle,
    description: cleanDesc,
    rawDescription: rawDesc,
    severity: severity,
    severityLevel: severity,
    severityScore: severityScore,

    // Casualties & Impact
    injuredCount: typeof raw.injured_people === 'number' ? raw.injured_people : 0,
    affectedCount: typeof raw.affected_people === 'number' ? raw.affected_people : 0,

    // Lifecycle Status
    backendStatus: backendStatus,
    status: statusMeta.displayStatus,
    displayStatus: statusMeta.label,
    badgeClass: statusMeta.badgeClass,

    // Timestamps
    createdAt: raw.created_at || null,
    reportedTime: formatRelativeTime(raw.created_at),
    timestamp: raw.created_at ? String(raw.created_at).slice(11, 16) : 'N/A',

    // Geographic / Map Position
    latitude: validLat,
    longitude: validLon,
    coordinates: coordinates,
    location: location,
    displayLocation: location || 'Location Unspecified',

    // Dispatch & Allocation Linkages
    assignedAmbulance: assignedAmbulance,
    assignedHospital: assignedHospital,
    etaMinutes: etaMinutes,
    activeAllocationId: activeAllocId,
  };
}

/**
 * Adapts an array of raw incidents into normalized frontend records.
 *
 * @param {Array<object>|null|undefined} rawList
 * @returns {Array<object>}
 */
export function adaptIncidents(rawList) {
  if (!Array.isArray(rawList)) return [];
  return rawList.map(adaptIncident).filter(Boolean);
}

