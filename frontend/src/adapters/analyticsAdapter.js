/**
 * ResQGrid Analytics Data Adapter
 *
 * Normalizes live aggregated database statistics from `/api/analytics/overview`
 * into the structures required by KpiCards.jsx and AnalyticsView.jsx.
 */

/**
 * Adapts raw analytics overview API response into frontend dashboard models.
 *
 * @param {object|null|undefined} rawResponse
 * @returns {object}
 */
export function adaptAnalytics(rawResponse) {
  // Support either raw response or nested response.data
  const raw = rawResponse?.data || rawResponse || {};

  const inc = raw.incidents || {};
  const amb = raw.ambulances || {};
  const hosp = raw.hospitals || {};
  const alloc = raw.allocations || {};
  const resp = raw.response_time || {};
  const kpisRaw = raw.kpis || {};

  const activeEmergencies = inc.active ?? kpisRaw.activeEmergencies ?? 0;
  // Use the active critical count for active-emergency KPI
  const criticalActive = inc.critical_active ?? kpisRaw.criticalIncidents ?? inc.critical ?? 0;
  // Preserve the total historical critical count separately
  const criticalTotal = inc.critical ?? criticalActive;

  const availableAmbulances = amb.available ?? kpisRaw.availableAmbulances ?? 0;
  const totalAmbulances = amb.total ?? kpisRaw.totalAmbulances ?? 0;
  const totalHospitals = hosp.total ?? kpisRaw.totalHospitals ?? 0;

  // Response time: preserved strictly as null when not recorded in backend
  const avgResponseTimeMin =
    typeof resp.average_minutes === 'number'
      ? resp.average_minutes
      : null;

  const avgResponseTimeDisplay =
    avgResponseTimeMin !== null
      ? `${avgResponseTimeMin.toFixed(1)}m`
      : 'Pending telemetry';

  return {
    timestamp: raw.timestamp || new Date().toISOString(),

    // Flat KPIs object directly consumed by KpiCards.jsx
    kpis: {
      activeEmergencies: activeEmergencies,
      criticalIncidents: criticalActive,
      criticalTotal: criticalTotal,
      availableAmbulances: availableAmbulances,
      totalAmbulances: totalAmbulances,
      hospitalsOnline: totalHospitals,
      totalHospitals: totalHospitals,
      avgResponseTimeMin: avgResponseTimeMin,
      avgResponseTimeDisplay: avgResponseTimeDisplay,
      targetResponseTimeMin: typeof resp.target_minutes === 'number' ? resp.target_minutes : 10.0,
      dispatchedAmbulances: Math.max(0, totalAmbulances - availableAmbulances),
    },

    // Categorized aggregations
    incidents: {
      total: inc.total ?? 0,
      active: activeEmergencies,
      critical: criticalActive,
      criticalActive: criticalActive,
      criticalTotal: criticalTotal,
      bySeverity: inc.by_severity || { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 },
      byStatus: inc.by_status || { REPORTED: 0, ASSIGNED: 0, IN_TRANSIT: 0, RESOLVED: 0, CANCELLED: 0 },
    },

    ambulances: {
      total: totalAmbulances,
      available: availableAmbulances,
      byStatus: amb.by_status || { AVAILABLE: 0, DISPATCHED: 0, BUSY: 0, OUT_OF_SERVICE: 0 },
      byCapability: amb.by_capability || { ALS: 0, BLS: 0, PATIENT_TRANSPORT: 0 },
    },

    hospitals: {
      total: totalHospitals,
      totalBeds: hosp.total_beds ?? 0,
      availableBeds: hosp.available_beds ?? 0,
      occupiedBeds: hosp.occupied_beds ?? 0,
      occupancyPct: hosp.bed_occupancy_rate_pct ?? 0,
      totalIcu: hosp.total_icu_beds ?? 0,
      availableIcu: hosp.available_icu_beds ?? 0,
      occupiedIcu: hosp.occupied_icu_beds ?? 0,
      icuOccupancyPct: hosp.icu_occupancy_rate_pct ?? 0,
      availableVents: hosp.available_ventilators ?? 0,
      emergencyCapacity: hosp.total_emergency_capacity ?? 0,
    },

    allocations: {
      total: alloc.total ?? 0,
      active: alloc.active ?? 0,
      reallocated: alloc.reallocated ?? 0,
      avgEtaMinutes: typeof alloc.avg_active_eta_minutes === 'number' ? alloc.avg_active_eta_minutes : null,
    },

    responseTime: {
      averageMinutes: avgResponseTimeMin,
      display: avgResponseTimeDisplay,
      isRecorded: Boolean(resp.recorded),
      explanation: resp.explanation || 'Actual response times are not yet recorded in the database schema.',
      targetMinutes: 10.0,
      estimatedEtaMinutes: typeof resp.average_estimated_eta_minutes === 'number' ? resp.average_estimated_eta_minutes : null,
    },
  };
}

