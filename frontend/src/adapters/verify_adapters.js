/**
 * ResQGrid Data Adapter Verification Suite
 *
 * Verifies all adapter modules in `frontend/src/adapters/` against both
 * live API server payloads and isolated edge-case fixtures:
 * 1. Incident field mapping & allocation linkage
 * 2. Ambulance field mapping & uninvented telemetry
 * 3. Hospital field mapping & name normalization
 * 4. Analytics mapping & null response time handling
 * 5. Event mapping & notification categorization
 * 6. Null and missing value resilience
 * 7. Invalid coordinate detection and fallback
 * 8. Coordinate clamping to visible canvas
 * 9. Backend status preservation
 */

import {
  projectCoordinates,
  HYDERABAD_BOUNDS,
  clamp,
} from './geoAdapter.js';

import {
  adaptIncident,
  adaptIncidents,
  formatRelativeTime,
  deriveIncidentLocation,
  INCIDENT_STATUS_MAP,
} from './incidentsAdapter.js';

import {
  adaptAmbulance,
  adaptAmbulances,
  AMBULANCE_STATUS_MAP,
} from './ambulancesAdapter.js';

import {
  adaptHospital,
  adaptHospitals,
} from './hospitalsAdapter.js';

import {
  adaptAnalytics,
} from './analyticsAdapter.js';

import {
  adaptEvent,
  adaptEvents,
  EVENT_TYPE_MAP,
} from './eventsAdapter.js';

import {
  getIncidents,
  getAmbulances,
  getHospitals,
  getEvents,
  getAnalyticsOverview,
} from '../services/api.js';

function assert(condition, message) {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
}

async function runAdapterVerification() {
  console.log('====================================================');
  console.log('ResQGrid Frontend Data Adapter Layer Verification');
  console.log('====================================================\n');

  let passed = 0;
  let failed = 0;

  function test(name, fn) {
    try {
      fn();
      console.log(`✓ ${name}`);
      passed++;
    } catch (err) {
      console.error(`✗ ${name}: ${err.message}`);
      failed++;
    }
  }

  async function testAsync(name, fn) {
    try {
      await fn();
      console.log(`✓ ${name}`);
      passed++;
    } catch (err) {
      console.error(`✗ ${name}: ${err.message}`);
      failed++;
    }
  }

  // -------------------------------------------------------------------------
  // 1. Incident Field Mapping
  // -------------------------------------------------------------------------
  await testAsync('1. Incident field mapping (Live API + Fixtures)', async () => {
    let rawItem;
    try {
      const res = await getIncidents();
      rawItem = res.data[0];
    } catch {
      rawItem = {
        id: 1,
        title: '[SIMULATED] Highway Collision at ORR',
        incident_type: 'ROAD_ACCIDENT',
        description: '[SIMULATED] Multiple casualties near exit 19.',
        latitude: 17.4401,
        longitude: 78.3489,
        injured_people: 3,
        affected_people: 5,
        severity_score: 88.0,
        severity_level: 'CRITICAL',
        status: 'ASSIGNED',
        created_at: '2026-11-13 10:00:00',
        active_allocation_id: 10,
        ambulance_number: 'AMB-HYD-01',
        ambulance_capability: 'ALS',
        hospital_name: '[SIMULATED] Apollo Hospitals, Jubilee Hills',
        estimated_arrival_minutes: 6.4,
      };
    }

    const adapted = adaptIncident(rawItem);
    assert(adapted !== null, 'Adapted incident must not be null');
    assert(adapted.backendId === rawItem.id, 'backendId must preserve integer ID');
    assert(adapted.rawId === rawItem.id, 'rawId must preserve integer ID');
    assert(adapted.id === String(rawItem.id), 'id must be stringified ID for React keys');
    assert(adapted.type === rawItem.incident_type, 'type must match incident_type');
    assert(adapted.severity === rawItem.severity_level, 'severity must match severity_level');
    assert(typeof adapted.severityScore === 'number', 'severityScore must be numeric');
    assert(adapted.injuredCount === rawItem.injured_people, 'injuredCount must match injured_people');
    assert(adapted.backendStatus === rawItem.status, 'backendStatus must equal raw status');
    assert(typeof adapted.coordinates.x === 'number', 'coordinates.x must be numeric');
    assert(typeof adapted.coordinates.y === 'number', 'coordinates.y must be numeric');
    assert(!adapted.title.startsWith('[SIMULATED]'), 'Title must strip [SIMULATED] prefix');

    if (rawItem.ambulance_number) {
      assert(adapted.assignedAmbulance.includes(rawItem.ambulance_number), 'assignedAmbulance must contain ambulance plate');
    }
    if (rawItem.hospital_name) {
      assert(!adapted.assignedHospital.startsWith('[SIMULATED]'), 'assignedHospital must strip [SIMULATED]');
    }
  });

  // -------------------------------------------------------------------------
  // 2. Ambulance Field Mapping
  // -------------------------------------------------------------------------
  await testAsync('2. Ambulance field mapping & uninvented telemetry', async () => {
    let rawAmb;
    try {
      const res = await getAmbulances();
      rawAmb = res.data[0];
    } catch {
      rawAmb = {
        id: 1,
        ambulance_number: 'AMB-HYD-01',
        latitude: 17.4401,
        longitude: 78.3489,
        status: 'AVAILABLE',
        capability: 'ALS',
        assigned_incident_id: null,
        current_speed: 48.5,
      };
    }

    const adapted = adaptAmbulance(rawAmb);
    assert(adapted !== null, 'Adapted ambulance must not be null');
    assert(adapted.backendId === rawAmb.id, 'backendId must preserve integer ID');
    assert(adapted.ambulanceNumber === rawAmb.ambulance_number, 'ambulanceNumber must match');
    assert(adapted.id === rawAmb.ambulance_number, 'id must match ambulance plate');
    assert(adapted.capability === rawAmb.capability, 'capability must match');
    assert(adapted.backendStatus === rawAmb.status, 'backendStatus must preserve raw status');
    assert(adapted.speedKmH === Math.round(rawAmb.current_speed * 10) / 10, 'speedKmH must be rounded');
    assert(adapted.fuelPct === null, 'fuelPct must be strictly null (not fabricated)');
    assert(adapted.fuelDisplay === 'N/A', 'fuelDisplay must be N/A');
    assert(adapted.coordinates.isValid === true, 'Coordinates must be valid');
  });

  // -------------------------------------------------------------------------
  // 3. Hospital Field Mapping
  // -------------------------------------------------------------------------
  await testAsync('3. Hospital field mapping & name normalization', async () => {
    let rawHosp;
    try {
      const res = await getHospitals();
      rawHosp = res.data[0];
    } catch {
      rawHosp = {
        id: 1,
        name: '[SIMULATED] Apollo Hospitals, Jubilee Hills',
        latitude: 17.4325,
        longitude: 78.4071,
        total_beds: 350,
        available_beds: 42,
        total_icu_beds: 60,
        available_icu_beds: 5,
        available_ventilators: 3,
        emergency_capacity: 50,
        specialties: 'Level-1 Trauma, Cardiology',
        occupancy_rate: 88.0,
      };
    }

    const adapted = adaptHospital(rawHosp);
    assert(adapted !== null, 'Adapted hospital must not be null');
    assert(adapted.backendId === rawHosp.id, 'backendId must match integer ID');
    assert(!adapted.name.startsWith('[SIMULATED]'), 'Display name must strip [SIMULATED]');
    assert(adapted.fullName === rawHosp.name, 'fullName must preserve original raw name');
    assert(adapted.totalBeds === rawHosp.total_beds, 'totalBeds must match');
    assert(adapted.availableBeds === rawHosp.available_beds, 'availableBeds must match');
    assert(adapted.occupiedBeds === rawHosp.total_beds - rawHosp.available_beds, 'occupiedBeds must be total - available');
    assert(adapted.totalIcu === rawHosp.total_icu_beds, 'totalIcu must match');
    assert(adapted.availableIcu === rawHosp.available_icu_beds, 'availableIcu must match');
    assert(adapted.availableVents === rawHosp.available_ventilators, 'availableVents must match');
    assert(adapted.totalVents === null, 'totalVents must be strictly null (not fabricated)');
    assert(adapted.totalVentsDisplay === 'N/A', 'totalVentsDisplay must be N/A');
    assert(typeof adapted.occupancyPct === 'number', 'occupancyPct must be numeric');
    assert(adapted.coordinates.isValid === true, 'Coordinates must be valid');
  });

  // -------------------------------------------------------------------------
  // 4. Analytics Mapping
  // -------------------------------------------------------------------------
  await testAsync('4. Analytics mapping & active critical KPI handling', async () => {
    let rawAnalytics;
    try {
      const res = await getAnalyticsOverview();
      rawAnalytics = res.data;
    } catch {
      rawAnalytics = {
        kpis: {
          activeEmergencies: 3,
          criticalIncidents: 2,
          availableAmbulances: 8,
          totalAmbulances: 8,
          hospitalsOnline: 5,
          totalHospitals: 5,
        },
        incidents: { total: 3, active: 3, critical: 2, critical_active: 2 },
        ambulances: { total: 8, available: 8 },
        hospitals: { total: 5, total_beds: 1980, available_beds: 277 },
        allocations: { total: 0, active: 0, reallocated: 0 },
        response_time: { average_minutes: null, recorded: false },
      };
    }

    const adapted = adaptAnalytics(rawAnalytics);
    assert(adapted.kpis.activeEmergencies === (rawAnalytics.incidents?.active ?? 3), 'kpis.activeEmergencies must match');
    assert(adapted.kpis.criticalIncidents === (rawAnalytics.incidents?.critical_active ?? 2), 'kpis.criticalIncidents must match');
    assert(adapted.kpis.totalAmbulances === (rawAnalytics.ambulances?.total ?? 8), 'kpis.totalAmbulances must match');
    assert(adapted.kpis.availableAmbulances === (rawAnalytics.ambulances?.available ?? 8), 'kpis.availableAmbulances must match');
    assert(adapted.kpis.totalHospitals === (rawAnalytics.hospitals?.total ?? 5), 'kpis.totalHospitals must match');
    assert(adapted.kpis.avgResponseTimeMin === null, 'kpis.avgResponseTimeMin must be strictly null');
    assert(adapted.kpis.avgResponseTimeDisplay === 'Pending telemetry', 'Display must show "Pending telemetry"');
    assert(adapted.responseTime.isRecorded === false, 'responseTime.isRecorded must be false');
    assert(adapted.hospitals.totalBeds === (rawAnalytics.hospitals?.total_beds ?? 1980), 'Total hospital beds must match');

    // Regression: verify when historical total critical > active critical
    const splitCritical = adaptAnalytics({
      incidents: { total: 10, active: 4, critical: 7, critical_active: 2 },
      kpis: { criticalIncidents: 2 },
    });
    assert(splitCritical.kpis.criticalIncidents === 2, 'KPI criticalIncidents must use active critical count (2)');
    assert(splitCritical.kpis.criticalTotal === 7, 'criticalTotal must preserve historical total critical count (7)');
    assert(splitCritical.incidents.critical === 2, 'incidents.critical must be active count for UI badges');
    assert(splitCritical.incidents.criticalActive === 2, 'incidents.criticalActive must be 2');
    assert(splitCritical.incidents.criticalTotal === 7, 'incidents.criticalTotal must be 7');
  });

  // -------------------------------------------------------------------------
  // 5. Event Mapping
  // -------------------------------------------------------------------------
  await testAsync('5. Event mapping & notification classification', async () => {
    let rawEvents;
    try {
      const res = await getEvents();
      rawEvents = res.data;
    } catch {
      rawEvents = [
        {
          id: 1,
          event_type: 'SYSTEM_INIT',
          description: '[SIMULATED] ResQGrid database initialized with benchmark dataset.',
          related_incident_id: null,
          created_at: '2026-11-13 05:24:10',
        },
      ];
    }

    const adaptedList = adaptEvents(rawEvents);
    assert(adaptedList.length >= 1, 'Should adapt at least 1 event');
    const first = adaptedList[0];
    assert(first.backendId !== null, 'backendId must be present');
    assert(!first.detail.startsWith('[SIMULATED]'), 'detail must strip [SIMULATED]');
    assert(typeof first.time === 'string', 'time must be formatted relative string');

    const sysInitEvent = adaptedList.find((e) => e.normalizedEventType === 'SYSTEM_INIT') || adaptEvent(rawEvents.find((e) => e.event_type === 'SYSTEM_INIT') || { id: 1, event_type: 'SYSTEM_INIT' });
    assert(sysInitEvent.type === 'INFO', 'SYSTEM_INIT should map to INFO');

    // Test all backend-generated event types and their exact required classifications:
    // ALERT types
    const bdEvent = adaptEvent({ id: 2, event_type: 'AMBULANCE_BREAKDOWN', description: 'Engine dead' });
    assert(bdEvent.type === 'ALERT', 'AMBULANCE_BREAKDOWN must map to ALERT');
    assert(bdEvent.originalEventType === 'AMBULANCE_BREAKDOWN', 'originalEventType must be preserved');

    const shortEvent = adaptEvent({ id: 3, event_type: 'SHORTAGE_UNRESOLVED', description: 'No units available' });
    assert(shortEvent.type === 'ALERT', 'SHORTAGE_UNRESOLVED must map to ALERT');
    assert(shortEvent.originalEventType === 'SHORTAGE_UNRESOLVED', 'originalEventType must be preserved');

    // WARNING types
    const satEvent = adaptEvent({ id: 4, event_type: 'HOSPITAL_SATURATED', description: 'ER full' });
    assert(satEvent.type === 'WARNING', 'HOSPITAL_SATURATED must map to WARNING');
    assert(satEvent.originalEventType === 'HOSPITAL_SATURATED', 'originalEventType must be preserved');

    const trafEvent = adaptEvent({ id: 5, event_type: 'TRAFFIC_SPIKE', description: 'Gachibowli corridor gridlock' });
    assert(trafEvent.type === 'WARNING', 'TRAFFIC_SPIKE must map to WARNING');
    assert(trafEvent.originalEventType === 'TRAFFIC_SPIKE', 'originalEventType must be preserved');

    // SUCCESS types
    const allocEvent = adaptEvent({ id: 6, event_type: 'RESOURCE_ALLOCATED', description: 'Dispatched unit' });
    assert(allocEvent.type === 'SUCCESS', 'RESOURCE_ALLOCATED must map to SUCCESS');
    assert(allocEvent.originalEventType === 'RESOURCE_ALLOCATED', 'originalEventType must be preserved');

    const reallocEvent = adaptEvent({ id: 7, event_type: 'RESOURCE_REALLOCATED', description: 'Unit re-routed' });
    assert(reallocEvent.type === 'SUCCESS', 'RESOURCE_REALLOCATED must map to SUCCESS');
    assert(reallocEvent.originalEventType === 'RESOURCE_REALLOCATED', 'originalEventType must be preserved');

    // INFO types
    const repEvent = adaptEvent({ id: 8, event_type: 'INCIDENT_REPORTED', description: 'Call received' });
    assert(repEvent.type === 'INFO', 'INCIDENT_REPORTED must map to INFO');
    assert(repEvent.originalEventType === 'INCIDENT_REPORTED', 'originalEventType must be preserved');

    const statusEvent = adaptEvent({ id: 9, event_type: 'INCIDENT_STATUS_UPDATED', description: 'Status changed to RESOLVED' });
    assert(statusEvent.type === 'INFO', 'INCIDENT_STATUS_UPDATED must map to INFO');
    assert(statusEvent.originalEventType === 'INCIDENT_STATUS_UPDATED', 'originalEventType must be preserved');

    const initEvent = adaptEvent({ id: 10, event_type: 'SYSTEM_INIT', description: 'System initialized' });
    assert(initEvent.type === 'INFO', 'SYSTEM_INIT must map to INFO');
    assert(initEvent.originalEventType === 'SYSTEM_INIT', 'originalEventType must be preserved');

    // Preserves original casing if custom string provided
    const lowerEvent = adaptEvent({ id: 11, event_type: 'incident_reported', description: 'lowercase test' });
    assert(lowerEvent.originalEventType === 'incident_reported', 'Original lowercase event type must be preserved in originalEventType');
    assert(lowerEvent.type === 'INFO', 'Lowercase event type should still be correctly classified');
  });

  // -------------------------------------------------------------------------
  // 6. Null & Missing Value Resilience
  // -------------------------------------------------------------------------
  test('6. Null & missing value resilience', () => {
    assert(adaptIncident(null) === null, 'adaptIncident(null) should return null');
    assert(adaptIncident(undefined) === null, 'adaptIncident(undefined) should return null');
    assert(adaptIncidents(null).length === 0, 'adaptIncidents(null) should return empty array');

    const emptyInc = adaptIncident({});
    assert(emptyInc.id === '', 'Empty incident id should be empty string');
    assert(emptyInc.severity === 'LOW', 'Default severity should be LOW');
    assert(emptyInc.injuredCount === 0, 'Default injuredCount should be 0');
    assert(emptyInc.coordinates.isValid === false, 'Empty coords should have isValid=false');

    assert(adaptAmbulance(null) === null, 'adaptAmbulance(null) should return null');
    assert(adaptHospital(null) === null, 'adaptHospital(null) should return null');
    assert(adaptEvent(null) === null, 'adaptEvent(null) should return null');

    const emptyAnalytics = adaptAnalytics(null);
    assert(emptyAnalytics.kpis.activeEmergencies === 0, 'Empty analytics should default to 0');
    assert(emptyAnalytics.kpis.avgResponseTimeMin === null, 'Empty response time should be null');
  });

  // -------------------------------------------------------------------------
  // 7. Invalid Coordinate Handling
  // -------------------------------------------------------------------------
  test('7. Invalid coordinate handling and fallback', () => {
    const invalidCoords = [
      [null, null],
      [undefined, undefined],
      ['invalid', 'coordinates'],
      [NaN, NaN],
      [Infinity, 78.4],
      [17.4, -999], // Out of range longitude
      [105, 78.4],  // Out of range latitude
    ];

    for (const [lat, lon] of invalidCoords) {
      const proj = projectCoordinates(lat, lon);
      assert(proj.x === null, `Invalid coords [${lat}, ${lon}] must have x=null`);
      assert(proj.y === null, `Invalid coords [${lat}, ${lon}] must have y=null`);
      assert(proj.isValid === false, `Invalid coords [${lat}, ${lon}] must have isValid=false`);
      assert(proj.isProjected === false, `Invalid coords [${lat}, ${lon}] must have isProjected=false`);
      assert(proj.x !== 50.0 && proj.y !== 50.0, 'Invalid coords must NEVER default to map center (50, 50)');
    }
  });

  // -------------------------------------------------------------------------
  // 8. Coordinate Clamping
  // -------------------------------------------------------------------------
  test('8. Coordinate clamping to visible canvas [5, 95]%', () => {
    // Extreme point far to North-East (e.g. Himalayas)
    const farNorthEast = projectCoordinates(35.0, 85.0);
    assert(farNorthEast.x === 95, `Out-of-bounds East lon should clamp to 95%, got ${farNorthEast.x}`);
    assert(farNorthEast.y === 5, `Out-of-bounds North lat should clamp to 5%, got ${farNorthEast.y}`);

    // Extreme point far to South-West (e.g. Indian Ocean)
    const farSouthWest = projectCoordinates(5.0, 70.0);
    assert(farSouthWest.x === 5, `Out-of-bounds West lon should clamp to 5%, got ${farSouthWest.x}`);
    assert(farSouthWest.y === 95, `Out-of-bounds South lat should clamp to 95%, got ${farSouthWest.y}`);

    // Normal Hyderabad coordinate should be within [15, 85]%
    const hydCenter = projectCoordinates(17.405, 78.435);
    assert(hydCenter.x > 15 && hydCenter.x < 85, `Hyderabad center X must be within comfortable margin, got ${hydCenter.x}`);
    assert(hydCenter.y > 15 && hydCenter.y < 85, `Hyderabad center Y must be within comfortable margin, got ${hydCenter.y}`);
  });

  // -------------------------------------------------------------------------
  // 9. Backend Status Preservation
  // -------------------------------------------------------------------------
  test('9. Backend status preservation for future mutations', () => {
    const statuses = ['REPORTED', 'ASSIGNED', 'IN_TRANSIT', 'RESOLVED', 'CANCELLED'];

    for (const st of statuses) {
      const inc = adaptIncident({ id: 10, status: st });
      assert(inc.backendStatus === st, `backendStatus must exactly equal '${st}'`);
      assert(typeof inc.status === 'string' && inc.status.length > 0, `UI status must exist for '${st}'`);
    }

    const ambStatuses = ['AVAILABLE', 'DISPATCHED', 'BUSY', 'OUT_OF_SERVICE'];
    for (const st of ambStatuses) {
      const amb = adaptAmbulance({ id: 5, status: st });
      assert(amb.backendStatus === st, `Ambulance backendStatus must exactly equal '${st}'`);
    }
  });

  // -------------------------------------------------------------------------
  // 10. Incident Location Derivation Without Fabrication
  // -------------------------------------------------------------------------
  test('10. Incident location derivation without fabrication', () => {
    // A. Explicit location_name provided
    const locNameInc = adaptIncident({ id: 1, location_name: 'HITEC City Cyber Towers', description: 'Fire alarm' });
    assert(locNameInc.location === 'HITEC City Cyber Towers', 'Should use provided location_name');

    // B. Explicit location provided
    const locInc = adaptIncident({ id: 2, location: 'Jubilee Hills Check Post', description: 'Minor scrape' });
    assert(locInc.location === 'Jubilee Hills Check Post', 'Should use provided location');

    // C. Extracted from narrative description with prepositions (near, on, at, in, along)
    const nearInc = adaptIncident({ id: 3, description: 'Severe accident near Gachibowli ORR exit. 3 hurt.' });
    assert(nearInc.location === 'Gachibowli ORR exit', 'Should extract landmark following "near"');

    const onInc = adaptIncident({ id: 4, description: 'Patient collapsed on Banjara Hills Road No. 10.' });
    assert(onInc.location === 'Banjara Hills Road No. 10', 'Should extract landmark following "on"');

    const inInc = adaptIncident({ id: 5, description: 'Urban flooding in Begumpet Nala basin. Evacuation underway.' });
    assert(inInc.location === 'Begumpet Nala basin', 'Should extract landmark following "in"');

    // D. Fallback to coordinates when no textual landmark exists
    const coordInc = adaptIncident({
      id: 6,
      title: 'Cardiac Emergency',
      description: 'Patient unresponsive.',
      latitude: 17.4422,
      longitude: 78.3512,
    });
    assert(coordInc.location === '17.4422°N, 78.3512°E', 'Should format coordinates when text landmark is absent');

    // E. Missing both text landmark and coordinates: must NEVER return "Hyderabad Sector"
    const emptyLocInc = adaptIncident({
      id: 7,
      title: 'General Distress',
      description: 'Alarm tripped.',
      latitude: null,
      longitude: null,
    });
    assert(emptyLocInc.location === null, 'Should return null when location is missing (never fabricated)');
    assert(emptyLocInc.displayLocation === 'Location Unspecified', 'Display fallback should be truthful');
    assert(emptyLocInc.location !== 'Hyderabad Sector', 'Must NEVER fabricate "Hyderabad Sector"');
  });

  // -------------------------------------------------------------------------
  // 11. Invalid Map Coordinates Consumer Safety
  // -------------------------------------------------------------------------
  test('11. Invalid map coordinates consumer safety', () => {
    const validInc = adaptIncident({ id: 1, latitude: 17.4422, longitude: 78.3512 });
    const invalidInc = adaptIncident({ id: 2, latitude: null, longitude: null });

    assert(validInc.coordinates.isProjected === true, 'Valid incident must have isProjected=true');
    assert(typeof validInc.coordinates.x === 'number', 'Valid incident must have numeric x');
    assert(typeof validInc.coordinates.y === 'number', 'Valid incident must have numeric y');

    assert(invalidInc.coordinates.isProjected === false, 'Invalid incident must have isProjected=false');
    assert(invalidInc.coordinates.isValid === false, 'Invalid incident must have isValid=false');
    assert(invalidInc.coordinates.x === null, 'Invalid incident must have x=null');
    assert(invalidInc.coordinates.y === null, 'Invalid incident must have y=null');

    // Consumer filtering simulation: verifies map consumers can cleanly filter unprojectable items
    const rawFeed = [validInc, invalidInc];
    const mapMarkers = rawFeed.filter((item) => item.coordinates && item.coordinates.isProjected);
    assert(mapMarkers.length === 1, 'Map markers filter must exclude invalid coordinates');
    assert(mapMarkers[0].id === '1', 'Only valid projected incident should be mapped');

    // Ambulance consumer safety
    const invalidAmb = adaptAmbulance({ id: 9, latitude: 'invalid', longitude: undefined });
    assert(invalidAmb.coordinates.isProjected === false, 'Invalid ambulance must have isProjected=false');
    assert(invalidAmb.coordinates.x === null, 'Invalid ambulance must have x=null');
    assert(invalidAmb.location === null, 'Invalid ambulance without coords or location must not have fabricated location');
  });

  console.log('\n====================================================');
  console.log(`VERIFICATION SUMMARY: ${passed}/11 passed, ${failed} failed`);
  console.log('====================================================');

  if (failed > 0) {
    process.exit(1);
  }
}

runAdapterVerification();

