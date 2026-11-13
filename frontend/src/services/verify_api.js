/**
 * ResQGrid API Service Verification Script
 *
 * Exercises all core functions in `api.js` against the live backend:
 * 1. Health endpoint connectivity
 * 2. Incident list retrieval
 * 3. Ambulance list retrieval
 * 4. Hospital list retrieval
 * 5. Events retrieval
 * 6. Analytics retrieval
 * 7. Proper handling of a failed request (ApiError propagation)
 */

import {
  ApiError,
  getHealth,
  getIncidents,
  getIncidentById,
  getAmbulances,
  getHospitals,
  getEvents,
  getAnalyticsOverview,
} from './api.js';

async function runVerification() {
  console.log('====================================================');
  console.log('ResQGrid Frontend API Service Verification');
  console.log('Target API: http://127.0.0.1:5000/api');
  console.log('====================================================\n');

  let passed = 0;
  let failed = 0;

  // 1. Health Check
  try {
    const health = await getHealth();
    if (health.success && health.status === 'HEALTHY' && health.database?.connected) {
      console.log('✓ [1/7] Health endpoint: SUCCESS (Status: HEALTHY, DB: Connected)');
      passed++;
    } else {
      console.error('✗ [1/7] Health endpoint: UNEXPECTED PAYLOAD', health);
      failed++;
    }
  } catch (err) {
    console.error('✗ [1/7] Health endpoint: FAILED ->', err.message);
    failed++;
  }

  // 2. Incident List Retrieval
  try {
    const incidentsRes = await getIncidents({ limit: 10 });
    if (incidentsRes.success && Array.isArray(incidentsRes.data)) {
      console.log(`✓ [2/7] Incident list: SUCCESS (${incidentsRes.count} incident(s) retrieved)`);
      passed++;
    } else {
      console.error('✗ [2/7] Incident list: UNEXPECTED PAYLOAD', incidentsRes);
      failed++;
    }
  } catch (err) {
    console.error('✗ [2/7] Incident list: FAILED ->', err.message);
    failed++;
  }

  // 3. Ambulance List Retrieval
  try {
    const ambulancesRes = await getAmbulances();
    if (ambulancesRes.success && Array.isArray(ambulancesRes.data) && ambulancesRes.count >= 8) {
      console.log(`✓ [3/7] Ambulance list: SUCCESS (${ambulancesRes.count} ambulance(s) retrieved)`);
      passed++;
    } else {
      console.error('✗ [3/7] Ambulance list: UNEXPECTED PAYLOAD', ambulancesRes);
      failed++;
    }
  } catch (err) {
    console.error('✗ [3/7] Ambulance list: FAILED ->', err.message);
    failed++;
  }

  // 4. Hospital List Retrieval
  try {
    const hospitalsRes = await getHospitals();
    if (hospitalsRes.success && Array.isArray(hospitalsRes.data) && hospitalsRes.count >= 5) {
      console.log(`✓ [4/7] Hospital list: SUCCESS (${hospitalsRes.count} hospital(s) retrieved)`);
      passed++;
    } else {
      console.error('✗ [4/7] Hospital list: UNEXPECTED PAYLOAD', hospitalsRes);
      failed++;
    }
  } catch (err) {
    console.error('✗ [4/7] Hospital list: FAILED ->', err.message);
    failed++;
  }

  // 5. Events Retrieval
  try {
    const eventsRes = await getEvents({ limit: 5 });
    if (eventsRes.success && Array.isArray(eventsRes.data)) {
      console.log(`✓ [5/7] Events list: SUCCESS (${eventsRes.count} event(s) retrieved)`);
      passed++;
    } else {
      console.error('✗ [5/7] Events list: UNEXPECTED PAYLOAD', eventsRes);
      failed++;
    }
  } catch (err) {
    console.error('✗ [5/7] Events list: FAILED ->', err.message);
    failed++;
  }

  // 6. Analytics Overview Retrieval
  try {
    const analyticsRes = await getAnalyticsOverview();
    if (
      analyticsRes.success &&
      analyticsRes.data?.incidents &&
      analyticsRes.data?.ambulances &&
      analyticsRes.data?.hospitals &&
      analyticsRes.data?.kpis
    ) {
      console.log('✓ [6/7] Analytics overview: SUCCESS (All metric groups present)');
      passed++;
    } else {
      console.error('✗ [6/7] Analytics overview: UNEXPECTED PAYLOAD', analyticsRes);
      failed++;
    }
  } catch (err) {
    console.error('✗ [6/7] Analytics overview: FAILED ->', err.message);
    failed++;
  }

  // 7. Error Handling (404 on nonexistent incident)
  try {
    await getIncidentById(999999);
    console.error('✗ [7/7] Failed request handling: Request should have thrown ApiError but succeeded');
    failed++;
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      console.log(`✓ [7/7] Failed request handling: SUCCESS (Correctly caught ApiError HTTP 404: "${err.message}")`);
      passed++;
    } else {
      console.error('✗ [7/7] Failed request handling: Caught wrong error type/status ->', err);
      failed++;
    }
  }

  console.log('\n====================================================');
  console.log(`VERIFICATION SUMMARY: ${passed}/7 passed, ${failed} failed`);
  console.log('====================================================');

  if (failed > 0) {
    process.exit(1);
  }
}

runVerification();

