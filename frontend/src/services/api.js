/**
 * ResQGrid Centralized Frontend API Service
 *
 * Provides a unified HTTP client for communicating with the ResQGrid Flask REST API.
 * Uses relative `/api` paths in the browser to route through Vite's development proxy
 * (or a production reverse proxy) without hardcoding backend hostnames.
 */

// Determine base URL: browser uses relative '/api', Node test environments fall back to local Flask server
const BASE_URL = typeof window !== 'undefined'
  ? '/api'
  : (typeof process !== 'undefined' && process.env?.API_BASE_URL) || 'http://127.0.0.1:5000/api';

/**
 * Custom error class representing an API failure with HTTP status and structured payload.
 */
export class ApiError extends Error {
  constructor(message, status = 0, data = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

/**
 * Builds a valid URL query string from an object, omitting null, undefined, or empty values.
 *
 * @param {Record<string, any>} params
 * @returns {string} e.g. "?status=REPORTED&limit=25" or ""
 */
function buildQueryString(params = {}) {
  if (!params || typeof params !== 'object') return '';
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') {
      searchParams.append(key, String(value));
    }
  }

  const qs = searchParams.toString();
  return qs ? `?${qs}` : '';
}

/**
 * Core HTTP request handler with standardized JSON parsing, HTTP error mapping,
 * and network error handling.
 *
 * @param {string} endpoint - Relative path (e.g. "/incidents", "/health")
 * @param {RequestInit & { params?: Record<string, any> }} [options]
 * @returns {Promise<any>} Parsed JSON response payload
 */
async function request(endpoint, options = {}) {
  const { params, headers = {}, body, ...customConfig } = options;
  const queryString = buildQueryString(params);
  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const url = `${BASE_URL}${normalizedEndpoint}${queryString}`;

  const config = {
    headers: {
      'Accept': 'application/json',
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...headers,
    },
    ...(body ? { body: typeof body === 'string' ? body : JSON.stringify(body) } : {}),
    ...customConfig,
  };

  let response;
  try {
    response = await fetch(url, config);
  } catch (networkError) {
    throw new ApiError(
      `Network connection failed while requesting ${normalizedEndpoint}: ${networkError.message}`,
      0,
      null
    );
  }

  // Parse JSON or fallback to text if response body is empty or non-JSON
  let data = null;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    try {
      const text = await response.text();
      data = text ? { raw: text } : null;
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    // Extract error message from centralized backend error structure
    const serverMessage =
      data?.error?.message ||
      data?.error ||
      data?.message ||
      `Request failed with HTTP status ${response.status} (${response.statusText})`;

    throw new ApiError(serverMessage, response.status, data);
  }

  return data;
}

// ============================================================================
// 1. Health API
// ============================================================================

/**
 * Check backend API operational health and database connectivity.
 * @returns {Promise<{ success: boolean, status: string, timestamp: string, database: object }>}
 */
export async function getHealth() {
  return request('/health', { method: 'GET' });
}

// ============================================================================
// 2. Incidents API
// ============================================================================

/**
 * Retrieve emergency incidents with optional status and severity filtering.
 * @param {object} [params] - Optional query parameters
 * @param {string} [params.status] - Filter by lifecycle status (REPORTED, ASSIGNED, IN_TRANSIT, RESOLVED, CANCELLED)
 * @param {string} [params.severity] - Filter by severity level (CRITICAL, HIGH, MEDIUM, LOW)
 * @returns {Promise<{ success: boolean, count: number, data: Array<object> }>}
 */
export async function getIncidents(params = {}) {
  return request('/incidents', { method: 'GET', params });
}

/**
 * Retrieve single incident details by ID with active dispatch information.
 * @param {number|string} id - Incident ID
 * @returns {Promise<{ success: boolean, data: object }>}
 */
export async function getIncidentById(id) {
  if (id === undefined || id === null) {
    throw new ApiError('Incident ID is required', 400);
  }
  return request(`/incidents/${encodeURIComponent(id)}`, { method: 'GET' });
}

/**
 * Create a new emergency incident report with automated triage severity calculation.
 * @param {object} payload - Incident data
 * @param {string} payload.title - Short descriptive title (required)
 * @param {string} payload.incident_type - Category (e.g. ROAD_ACCIDENT, CARDIAC_EMERGENCY, FIRE)
 * @param {number} payload.latitude - WGS84 latitude (-90 to 90)
 * @param {number} payload.longitude - WGS84 longitude (-180 to 180)
 * @param {string} [payload.description] - Detailed incident narrative
 * @param {number} [payload.injured_people] - Count of injured casualties
 * @param {number} [payload.affected_people] - Estimated affected individuals
 * @param {Array<string>} [payload.critical_symptoms] - Observed clinical symptoms
 * @param {Array<string>} [payload.environmental_danger] - Scene hazards
 * @returns {Promise<{ success: boolean, data: object, severity_assessment: object }>}
 */
export async function createIncident(payload) {
  return request('/incidents', {
    method: 'POST',
    body: payload,
  });
}

/**
 * Transition an incident's lifecycle status through the validated state graph.
 * @param {number|string} id - Incident ID
 * @param {string} status - Target status (REPORTED, ASSIGNED, IN_TRANSIT, RESOLVED, CANCELLED)
 * @returns {Promise<{ success: boolean, message: string, data: object }>}
 */
export async function updateIncidentStatus(id, status) {
  if (id === undefined || id === null) {
    throw new ApiError('Incident ID is required', 400);
  }
  return request(`/incidents/${encodeURIComponent(id)}/status`, {
    method: 'PATCH',
    body: { status },
  });
}

// ============================================================================
// 3. Ambulances API
// ============================================================================

/**
 * Retrieve ambulance fleet with optional status and capability filters.
 * @param {object} [params] - Optional query parameters
 * @param {string} [params.status] - Filter by status (AVAILABLE, DISPATCHED, BUSY, OUT_OF_SERVICE)
 * @param {string} [params.capability] - Filter by capability (ALS, BLS, PATIENT_TRANSPORT)
 * @returns {Promise<{ success: boolean, count: number, data: Array<object> }>}
 */
export async function getAmbulances(params = {}) {
  return request('/ambulances', { method: 'GET', params });
}

/**
 * Retrieve single ambulance record by ID.
 * @param {number|string} id - Ambulance ID
 * @returns {Promise<{ success: boolean, data: object }>}
 */
export async function getAmbulanceById(id) {
  if (id === undefined || id === null) {
    throw new ApiError('Ambulance ID is required', 400);
  }
  return request(`/ambulances/${encodeURIComponent(id)}`, { method: 'GET' });
}

// ============================================================================
// 4. Hospitals API
// ============================================================================

/**
 * Retrieve hospital network facilities with optional filters.
 * @param {object} [params] - Optional query parameters
 * @param {string} [params.specialty] - Filter by clinical specialty substring
 * @param {number} [params.min_beds] - Minimum available general beds
 * @returns {Promise<{ success: boolean, count: number, data: Array<object> }>}
 */
export async function getHospitals(params = {}) {
  return request('/hospitals', { method: 'GET', params });
}

/**
 * Retrieve single hospital record by ID with incoming transport tracking.
 * @param {number|string} id - Hospital ID
 * @returns {Promise<{ success: boolean, data: object }>}
 */
export async function getHospitalById(id) {
  if (id === undefined || id === null) {
    throw new ApiError('Hospital ID is required', 400);
  }
  return request(`/hospitals/${encodeURIComponent(id)}`, { method: 'GET' });
}

// ============================================================================
// 5. Allocations API
// ============================================================================

/**
 * Execute atomic resource allocation for an incident: dispatches nearest suitable
 * ambulance and reserves receiving hospital capacity based on clinical severity and traffic.
 * @param {number|string} incidentId - Incident ID to allocate
 * @returns {Promise<{ success: boolean, allocation_id: number, ambulance: object, hospital: object, estimated_arrival_minutes: number, severity: object, fulfillment_status: string, decision_reason: string }>}
 */
export async function allocateIncident(incidentId) {
  if (incidentId === undefined || incidentId === null) {
    throw new ApiError('Incident ID is required', 400);
  }
  return request(`/allocations/${encodeURIComponent(incidentId)}`, {
    method: 'POST',
  });
}

// ============================================================================
// 6. Dynamic Reallocation API
// ============================================================================

/**
 * Handle ambulance breakdown in transit: retires failed unit to OUT_OF_SERVICE and
 * dynamically dispatches a replacement ambulance while preserving hospital reservation.
 * @param {object} payload
 * @param {number} payload.ambulance_id - ID of broken ambulance
 * @param {string} payload.reason - Failure diagnostic reason
 * @returns {Promise<object>}
 */
export async function reportAmbulanceBreakdown({ ambulance_id, reason }) {
  return request('/reallocation/breakdown', {
    method: 'POST',
    body: { ambulance_id, reason },
  });
}

export const reallocateAmbulanceBreakdown = reportAmbulanceBreakdown;

/**
 * Handle hospital capacity exhaustion: diverts active incoming transports away from
 * the saturated hospital to alternative facilities while preserving ambulances.
 * @param {object} payload
 * @param {number} payload.hospital_id - Saturated hospital ID
 * @param {string} payload.reason - Capacity exhaustion reason
 * @param {string} [payload.exhausted_resource='FULL'] - Resource type (BEDS, ICU, VENTILATORS, FULL)
 * @returns {Promise<object>}
 */
export async function reportHospitalSaturation({ hospital_id, reason, exhausted_resource = 'FULL' }) {
  return request('/reallocation/hospital', {
    method: 'POST',
    body: { hospital_id, reason, exhausted_resource },
  });
}

export const reallocateHospitalSaturation = reportHospitalSaturation;

/**
 * Handle traffic corridor congestion spike: updates zone multiplier and congestion level,
 * re-evaluating active dispatches and reallocating if hysteresis threshold is met.
 * @param {object} payload
 * @param {number} payload.traffic_zone_id - Traffic zone ID
 * @param {number} payload.new_multiplier - New delay multiplier (1.0 to 20.0)
 * @param {string} [payload.new_congestion_level='SEVERE'] - LOW, MODERATE, HEAVY, SEVERE, GRIDLOCK
 * @param {number} [payload.min_improvement_minutes=5.0] - Hysteresis threshold
 * @returns {Promise<object>}
 */
export async function reportTrafficSpike({
  traffic_zone_id,
  new_multiplier,
  new_congestion_level = 'SEVERE',
  min_improvement_minutes = 5.0,
}) {
  return request('/reallocation/traffic', {
    method: 'POST',
    body: {
      traffic_zone_id,
      new_multiplier,
      new_congestion_level,
      min_improvement_minutes,
    },
  });
}

export const reallocateTrafficSpike = reportTrafficSpike;

// ============================================================================
// 7. Events and Analytics API
// ============================================================================

/**
 * Retrieve immutable audit event logs ordered newest first.
 * @param {object} [params] - Optional query parameters
 * @param {number} [params.limit=50] - Maximum records to return (1 to 200)
 * @param {string} [params.event_type] - Case-insensitive filter on event type
 * @returns {Promise<{ success: boolean, count: number, data: Array<object> }>}
 */
export async function getEvents(params = {}) {
  return request('/events', { method: 'GET', params });
}

/**
 * Retrieve real-time aggregated operational statistics and system KPIs.
 * @returns {Promise<{ success: boolean, timestamp: string, data: object }>}
 */
export async function getAnalyticsOverview() {
  return request('/analytics/overview', { method: 'GET' });
}

// ============================================================================
// Default Export Object
// ============================================================================

const api = {
  // Health
  getHealth,

  // Incidents
  getIncidents,
  getIncidentById,
  createIncident,
  updateIncidentStatus,

  // Ambulances
  getAmbulances,
  getAmbulanceById,

  // Hospitals
  getHospitals,
  getHospitalById,

  // Allocations
  allocateIncident,

  // Reallocation
  reportAmbulanceBreakdown,
  reallocateAmbulanceBreakdown,
  reportHospitalSaturation,
  reallocateHospitalSaturation,
  reportTrafficSpike,
  reallocateTrafficSpike,

  // Events & Analytics
  getEvents,
  getAnalyticsOverview,
};

export default api;

