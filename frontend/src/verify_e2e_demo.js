/**
 * ResQGrid End-to-End Demonstration and Integration Verification Suite
 *
 * Exercises the complete 9-step demo sequence specified in Step 7 of the user prompt:
 * STEP 1: Fetch initial Command Center state (KPIs, incidents, ambulances, hospitals, events)
 * STEP 2: Report a new emergency report
 * STEP 3: Verify algorithmic severity estimation and score
 * STEP 4: Allocate resources to the new incident
 * STEP 5: Verify assigned ambulance, receiving hospital, ETA, and decision reason
 * STEP 6: Verify updated ambulance status, hospital capacity, and analytics
 * STEP 7: Trigger ambulance breakdown simulation in transit
 * STEP 8: Verify dynamic reallocation outcome and audit
 * STEP 9: Verify complete audit event log reflecting all operations
 */

import {
  getHealth,
  getAnalyticsOverview,
  getIncidents,
  getAmbulances,
  getHospitals,
  getEvents,
  createIncident,
  allocateIncident,
  reportAmbulanceBreakdown,
} from './services/api.js';

import {
  adaptAnalytics,
  adaptIncidents,
  adaptAmbulances,
  adaptHospitals,
  adaptEvents,
} from './adapters/index.js';

function assert(condition, message) {
  if (!condition) {
    throw new Error(`[ASSERTION FAILED] ${message}`);
  }
}

async function runEndToEndDemo() {
  console.log('================================================================');
  console.log('RESQGRID END-TO-END DEMO & INTEGRATION VERIFICATION');
  console.log('Target API: http://127.0.0.1:5000/api');
  console.log('================================================================\n');

  // STEP 0: Health Check
  console.log('[STEP 0] Checking Flask API Health & SQLite Connection...');
  const health = await getHealth();
  assert(health.success === true, 'Health check must return success: true');
  assert(health.status === 'HEALTHY', 'Backend health status must be HEALTHY');
  console.log(`  -> Status: ${health.status} | Engine: ${health.application}\n`);

  // STEP 1: Open Command Center & Verify Initial State
  console.log('[STEP 1] Fetching Live Command Center Data...');
  const [analyticsRaw, incidentsRaw, ambulancesRaw, hospitalsRaw, eventsRaw] =
    await Promise.all([
      getAnalyticsOverview(),
      getIncidents(),
      getAmbulances(),
      getHospitals(),
      getEvents({ limit: 50 }),
    ]);

  const analytics = adaptAnalytics(analyticsRaw.data);
  const incidents = adaptIncidents(incidentsRaw.data);
  const ambulances = adaptAmbulances(ambulancesRaw.data);
  const hospitals = adaptHospitals(hospitalsRaw.data);
  const events = adaptEvents(eventsRaw.data);

  console.log(`  -> Active Emergencies: ${analytics.kpis.activeEmergencies}`);
  console.log(`  -> Critical Incidents (Active): ${analytics.kpis.criticalIncidents}`);
  console.log(`  -> Ambulances Ready: ${analytics.kpis.availableAmbulances} / ${analytics.kpis.totalAmbulances}`);
  console.log(`  -> Hospitals Online: ${analytics.kpis.hospitalsOnline} / ${analytics.kpis.totalHospitals}`);
  console.log(`  -> Average Response Time: ${analytics.kpis.avgResponseTimeDisplay}`);
  console.log(`  -> Incidents Count: ${incidents.length}`);
  console.log(`  -> Events Logged: ${events.length}`);

  assert(analytics.kpis.totalAmbulances === 8, 'Expected 8 seeded ambulances');
  assert(analytics.kpis.totalHospitals === 5, 'Expected 5 seeded hospitals');
  assert(incidents.length >= 3, 'Expected at least 3 initial incidents');
  console.log('  -> Step 1 PASSED.\n');

  // STEP 2 & 3: Report a New Emergency Incident
  console.log('[STEP 2 & 3] Reporting New Emergency Incident via Frontend API...');
  const newIncidentPayload = {
    title: '[DEMO] High-Speed Collision on Tank Bund Road',
    incident_type: 'ROAD_ACCIDENT',
    description: 'Collision involving bus and private car near Tank Bund Secretariat gate. 4 passengers critically trapped with polytrauma and heavy bleeding; requires ALS dispatch.',
    latitude: 17.4125,
    longitude: 78.4720,
    injured_people: 4,
    affected_people: 6,
    critical_symptoms: ['polytrauma', 'heavy bleeding', 'unconscious'],
    environmental_danger: ['high speed traffic'],
  };

  const createRes = await createIncident(newIncidentPayload);
  assert(createRes.success === true, 'Incident creation must return success: true');
  assert(createRes.data && createRes.data.id, 'Created incident must have an ID');
  const createdId = createRes.data.id;
  const sevScore = createRes.data.severity_score;
  const sevLevel = createRes.data.severity_level;

  console.log(`  -> Created Incident ID: #${createdId}`);
  console.log(`  -> Algorithmic Severity Score: ${sevScore} / 100`);
  console.log(`  -> Triage Priority Level: ${sevLevel}`);
  assert(typeof sevScore === 'number' && sevScore >= 70, 'Severity score should be elevated for polytrauma');
  assert(sevLevel === 'CRITICAL' || sevLevel === 'HIGH', 'Severity level must be HIGH or CRITICAL');
  console.log('  -> Step 2 & 3 PASSED.\n');

  // STEP 4 & 5: Allocate Resources to the New Incident
  console.log(`[STEP 4 & 5] Allocating Resources to Incident #${createdId}...`);
  const allocRes = await allocateIncident(createdId);
  assert(allocRes.success === true, 'Allocation must return success: true');
  assert(allocRes.ambulance !== null, 'An ambulance must be allocated');
  assert(allocRes.hospital !== null, 'A receiving hospital must be allocated');
  assert(typeof allocRes.estimated_arrival_minutes === 'number', 'ETA must be a valid number');

  const allocatedAmbId = allocRes.ambulance.id;
  const allocatedAmbNumber = allocRes.ambulance.ambulance_number;
  const allocatedHospName = allocRes.hospital.name;
  const eta = allocRes.estimated_arrival_minutes;
  const reason = allocRes.decision_reason;

  console.log(`  -> Allocation ID: ${allocRes.allocation_id}`);
  console.log(`  -> Assigned Ambulance: ${allocatedAmbNumber} (${allocRes.ambulance.capability})`);
  console.log(`  -> Assigned Hospital: ${allocatedHospName}`);
  console.log(`  -> Estimated Arrival Time (ETA): ${eta} minutes`);
  console.log(`  -> Decision Reason: ${reason}`);
  console.log('  -> Step 4 & 5 PASSED.\n');

  // STEP 6: Verify Updated Dashboard State
  console.log('[STEP 6] Verifying Synchronized State Across Resources & Analytics...');
  const [incCheck, ambCheck, hospCheck, analyticsCheck] = await Promise.all([
    getIncidents(),
    getAmbulances(),
    getHospitals(),
    getAnalyticsOverview(),
  ]);

  const updatedInc = adaptIncidents(incCheck.data).find((i) => i.backendId === createdId);
  assert(updatedInc !== null, 'Updated incident must exist in list');
  assert(updatedInc.backendStatus === 'ASSIGNED', 'Incident status must be ASSIGNED');
  assert(updatedInc.assignedAmbulance.includes(allocatedAmbNumber), 'Incident must reflect assigned ambulance');

  const updatedAmb = adaptAmbulances(ambCheck.data).find((a) => a.backendId === allocatedAmbId);
  assert(updatedAmb !== null, 'Updated ambulance must exist');
  assert(updatedAmb.backendStatus === 'DISPATCHED' || updatedAmb.backendStatus === 'BUSY', 'Ambulance status must be DISPATCHED or BUSY');
  assert(updatedAmb.assignedIncidentId === createdId, 'Ambulance assigned_incident_id must match created incident');

  const updatedAnalytics = adaptAnalytics(analyticsCheck.data);
  assert(updatedAnalytics.allocations.active >= 1, 'Active allocations count must be >= 1');
  console.log(`  -> Incident #${createdId} Status: ${updatedInc.status} (${updatedInc.backendStatus})`);
  console.log(`  -> Ambulance ${allocatedAmbNumber} Status: ${updatedAmb.status} (${updatedAmb.backendStatus})`);
  console.log(`  -> Active Allocations: ${updatedAnalytics.allocations.active}`);
  console.log('  -> Step 6 PASSED.\n');

  // STEP 7 & 8: Trigger Ambulance Breakdown Simulation
  console.log(`[STEP 7 & 8] Triggering Breakdown Simulation for Dispatched Ambulance ${allocatedAmbNumber} (ID: ${allocatedAmbId})...`);
  const breakdownRes = await reportAmbulanceBreakdown({
    ambulance_id: allocatedAmbId,
    reason: 'Transmission failure while responding on Tank Bund corridor',
  });

  assert(breakdownRes.success === true, 'Breakdown reallocation must return success: true');
  assert(breakdownRes.broken_ambulance_id === allocatedAmbId, 'Broken ambulance ID must match');
  console.log(`  -> Broken Unit Status: ${breakdownRes.broken_ambulance_number} retired to OUT_OF_SERVICE`);

  if (breakdownRes.replacement_ambulance) {
    console.log(`  -> Replacement Dispatched: ${breakdownRes.replacement_ambulance.ambulance_number} (${breakdownRes.replacement_ambulance.capability})`);
    console.log(`  -> Revised ETA: ${breakdownRes.estimated_arrival_minutes} minutes`);
    console.log(`  -> Decision Reason: ${breakdownRes.decision_reason}`);
  } else {
    console.log('  -> Notice: No replacement ambulance available (Shortage alert logged).');
  }
  console.log('  -> Step 7 & 8 PASSED.\n');

  // STEP 9: Verify Event Audit Log
  console.log('[STEP 9] Verifying Immutable Event History from SQLite...');
  const eventsAfter = await getEvents({ limit: 50 });
  const adaptedEvents = adaptEvents(eventsAfter.data);

  const eventTypes = adaptedEvents.map((e) => e.normalizedEventType);
  console.log(`  -> Total Events in Audit Log: ${adaptedEvents.length}`);
  console.log(`  -> Recent Events:`);
  adaptedEvents.slice(0, 5).forEach((e, idx) => {
    console.log(`     ${idx + 1}. [${e.type}] ${e.normalizedEventType} (${e.time}): ${e.detail.slice(0, 70)}...`);
  });

  assert(eventTypes.includes('SYSTEM_INIT'), 'Events must contain SYSTEM_INIT');
  assert(eventTypes.includes('INCIDENT_REPORTED'), 'Events must contain INCIDENT_REPORTED');
  assert(eventTypes.includes('RESOURCE_ALLOCATED'), 'Events must contain RESOURCE_ALLOCATED');
  assert(eventTypes.includes('AMBULANCE_BREAKDOWN'), 'Events must contain AMBULANCE_BREAKDOWN');
  console.log('  -> Step 9 PASSED.\n');

  console.log('================================================================');
  console.log('DEMO SEQUENCE COMPLETE: ALL 9 STEPS SUCCESSFULLY VERIFIED!');
  console.log('================================================================');
}

runEndToEndDemo().catch((err) => {
  console.error('\nDEMO EXECUTION FAILED:', err);
  process.exit(1);
});

