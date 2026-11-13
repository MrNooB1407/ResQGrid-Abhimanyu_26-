/**
 * ResQGrid Ambulances Data Adapter
 *
 * Normalizes backend Ambulance records from `/api/ambulances` into the UI structures
 * expected by FleetOverview.jsx, EmergencyMap.jsx, and FleetView.jsx.
 */

import { projectCoordinates } from './geoAdapter.js';

/**
 * Ambulance operational status display mappings.
 */
export const AMBULANCE_STATUS_MAP = Object.freeze({
  AVAILABLE: {
    displayStatus: 'AVAILABLE',
    badgeClass: 'available',
    label: 'Available / Standby',
  },
  DISPATCHED: {
    displayStatus: 'EN_ROUTE',
    badgeClass: 'en_route',
    label: 'Dispatched to Scene',
  },
  BUSY: {
    displayStatus: 'ON_SCENE',
    badgeClass: 'on_scene',
    label: 'Active Incident',
  },
  OUT_OF_SERVICE: {
    displayStatus: 'OUT_OF_SERVICE',
    badgeClass: 'out_of_service',
    label: 'Out of Service',
  },
});

/**
 * Adapts a single raw ambulance record into a UI-compatible object.
 *
 * @param {object|null|undefined} raw
 * @returns {object|null}
 */
export function adaptAmbulance(raw) {
  if (!raw || typeof raw !== 'object') return null;

  const rawId = raw.id ?? null;
  const ambulanceNumber = raw.ambulance_number || (rawId !== null ? `AMB-${rawId}` : 'AMB-UNKNOWN');
  const backendStatus = String(raw.status || 'AVAILABLE').toUpperCase();
  const statusMeta = AMBULANCE_STATUS_MAP[backendStatus] || {
    displayStatus: backendStatus,
    badgeClass: 'unknown',
    label: backendStatus,
  };

  const validLat = typeof raw.latitude === 'number' && Number.isFinite(raw.latitude) ? raw.latitude : null;
  const validLon = typeof raw.longitude === 'number' && Number.isFinite(raw.longitude) ? raw.longitude : null;
  const coordinates = projectCoordinates(raw.latitude, raw.longitude);

  let location = null;
  if (typeof raw.location === 'string' && raw.location.trim()) {
    location = raw.location.trim();
  } else if (coordinates.isProjected && validLat !== null && validLon !== null) {
    location = `${validLat.toFixed(4)}°N, ${validLon.toFixed(4)}°E`;
  }

  const speedKmH =
    typeof raw.current_speed === 'number'
      ? Math.round(raw.current_speed * 10) / 10
      : 0;

  const alloc = (raw.current_allocation && typeof raw.current_allocation === 'object') ? raw.current_allocation : {};
  const hospName = alloc.hospital_name || raw.hospital_name || null;
  const rawEta = alloc.estimated_arrival_minutes ?? raw.estimated_arrival_minutes;
  const assignedIncId = raw.assigned_incident_id ?? alloc.incident_id ?? null;
  const incTitle = alloc.incident_title || raw.incident_title || null;
  const activeAllocId = alloc.allocation_id ?? raw.active_allocation_id ?? null;

  let targetDestination = null;
  if (hospName) {
    targetDestination = hospName.replace(/^\[SIMULATED\]\s*/i, '').trim();
  } else if (backendStatus === 'AVAILABLE') {
    targetDestination = 'Base Standby';
  }

  const etaMinutes =
    typeof rawEta === 'number'
      ? Math.round(rawEta * 10) / 10
      : null;

  return {
    // Identifiers
    id: ambulanceNumber,
    rawId: rawId,
    backendId: rawId,
    ambulanceNumber: ambulanceNumber,
    callsign: raw.callsign || ambulanceNumber,

    // Clinical Capabilities & Specifications
    capability: String(raw.capability || 'BLS').toUpperCase(),

    // Operational Status
    backendStatus: backendStatus,
    status: statusMeta.displayStatus,
    displayStatus: statusMeta.label,
    badgeClass: statusMeta.badgeClass,

    // Telemetry & Velocity (Uninvented: fuelPct is null if not provided)
    speedKmH: speedKmH,
    fuelPct: typeof raw.fuel_pct === 'number' ? raw.fuel_pct : null,
    fuelDisplay: typeof raw.fuel_pct === 'number' ? `${raw.fuel_pct}%` : 'N/A',

    // Geographic Position
    latitude: validLat,
    longitude: validLon,
    coordinates: coordinates,
    location: location,
    displayLocation: location || 'Location Unavailable',

    // Active Mission Linkages
    assignedIncidentId: assignedIncId,
    assignedIncident: assignedIncId ? `INC-${assignedIncId}` : null,
    incidentTitle: incTitle ? incTitle.replace(/^\[SIMULATED\]\s*/i, '').trim() : null,
    targetDestination: targetDestination,
    etaMinutes: etaMinutes,
    activeAllocationId: activeAllocId,
  };
}

/**
 * Adapts an array of raw ambulance records into normalized frontend records.
 *
 * @param {Array<object>|null|undefined} rawList
 * @returns {Array<object>}
 */
export function adaptAmbulances(rawList) {
  if (!Array.isArray(rawList)) return [];
  return rawList.map(adaptAmbulance).filter(Boolean);
}

