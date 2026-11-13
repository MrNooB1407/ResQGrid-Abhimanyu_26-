/**
 * ResQGrid Hospitals Data Adapter
 *
 * Normalizes backend Hospital records from `/api/hospitals` into the UI structures
 * expected by HospitalOverview.jsx, EmergencyMap.jsx, and HospitalsView.jsx.
 */

import { projectCoordinates } from './geoAdapter.js';

/**
 * Adapts a single raw hospital record from SQLite into a normalized UI structure.
 *
 * @param {object|null|undefined} raw
 * @returns {object|null}
 */
export function adaptHospital(raw) {
  if (!raw || typeof raw !== 'object') return null;

  const rawId = raw.id ?? null;
  const rawName = raw.name || 'Unnamed Hospital Facility';
  const cleanName = rawName.replace(/^\[SIMULATED\]\s*/i, '').trim();

  const totalBeds = typeof raw.total_beds === 'number' ? raw.total_beds : 0;
  const availableBeds = typeof raw.available_beds === 'number' ? raw.available_beds : 0;
  const occupiedBeds = Math.max(0, totalBeds - availableBeds);

  const totalIcu = typeof raw.total_icu_beds === 'number' ? raw.total_icu_beds : 0;
  const availableIcu = typeof raw.available_icu_beds === 'number' ? raw.available_icu_beds : 0;
  const occupiedIcu = Math.max(0, totalIcu - availableIcu);

  const availableVents = typeof raw.available_ventilators === 'number' ? raw.available_ventilators : 0;
  const emergencyCapacity = typeof raw.emergency_capacity === 'number' ? raw.emergency_capacity : 0;

  // Calculate or preserve occupancy percentage
  let occupancyPct = 0;
  if (typeof raw.occupancy_percentage === 'number') {
    occupancyPct = raw.occupancy_percentage;
  } else if (typeof raw.occupancy_rate === 'number') {
    occupancyPct = raw.occupancy_rate;
  } else if (totalBeds > 0) {
    occupancyPct = Math.round(((totalBeds - availableBeds) / totalBeds) * 1000) / 10;
  }

  // Derive hospital operational capacity status
  let status = 'NORMAL';
  if (occupancyPct >= 95 || availableIcu <= 2) {
    status = 'CRITICAL_CAPACITY';
  } else if (occupancyPct >= 90 || availableIcu <= 5) {
    status = 'ELEVATED';
  }

  const coordinates = projectCoordinates(raw.latitude, raw.longitude);

  return {
    // Identifiers
    id: rawId !== null ? String(rawId) : '',
    rawId: rawId,
    backendId: rawId,
    code: rawId !== null ? `HOSP-${String(rawId).padStart(3, '0')}` : '',

    // Facility Names & Descriptions
    name: cleanName,
    fullName: rawName,
    rawName: rawName,
    type: cleanName.includes('General') ? 'Public Level-1 Trauma Center' : 'Tertiary Emergency Care Facility',
    specialties: raw.specialties || '',
    address: `${cleanName}, Hyderabad`,

    // General Inpatient Beds
    totalBeds: totalBeds,
    availableBeds: availableBeds,
    occupiedBeds: occupiedBeds,
    occupancyPct: occupancyPct,

    // Critical Care / ICU Beds
    totalIcu: totalIcu,
    availableIcu: availableIcu,
    occupiedIcu: occupiedIcu,

    // Mechanical Ventilators (Backend stores available count; total count is not stored)
    availableVents: availableVents,
    totalVents: null,
    totalVentsDisplay: 'N/A',

    // Emergency Department Capacity
    emergencyCapacity: emergencyCapacity,
    status: status,

    // Geographic Position
    latitude: typeof raw.latitude === 'number' ? raw.latitude : null,
    longitude: typeof raw.longitude === 'number' ? raw.longitude : null,
    coordinates: coordinates,

    // Active Inbound Transports
    activeIncomingTransportsCount: raw.active_incoming_transports || raw.active_incoming_transports_count || 0,
    incomingTransports: Array.isArray(raw.incoming_transports) ? raw.incoming_transports : [],
  };
}

/**
 * Adapts an array of raw hospital records into normalized frontend records.
 *
 * @param {Array<object>|null|undefined} rawList
 * @returns {Array<object>}
 */
export function adaptHospitals(rawList) {
  if (!Array.isArray(rawList)) return [];
  return rawList.map(adaptHospital).filter(Boolean);
}

