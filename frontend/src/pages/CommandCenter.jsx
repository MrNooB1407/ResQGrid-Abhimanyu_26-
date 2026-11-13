import React from 'react';
import KpiCards from '../components/KpiCards';
import EmergencyMap from '../components/EmergencyMap';
import IncidentFeed from '../components/IncidentFeed';
import FleetOverview from '../components/FleetOverview';
import HospitalOverview from '../components/HospitalOverview';

export default function CommandCenter({
  kpis,
  incidents,
  ambulances,
  hospitals,
  selectedIncidentId,
  onSelectIncident,
  onAllocateIncident,
  onOpenReportModal,
  onSimulateBreakdown,
  onSimulateHospitalSaturation,
  isAllocatingId,
  isBreakdownLoadingId,
  isHospitalLoadingId,
}) {
  return (
    <div className="dashboard-content">
      {/* Top Simulated KPI Metrics */}
      <KpiCards kpis={kpis} />

      {/* Main Content Area: Tactical Map (Left) & Emergency Feed (Right) */}
      <div className="middle-grid">
        <EmergencyMap
          incidents={incidents}
          ambulances={ambulances}
          hospitals={hospitals}
          selectedIncidentId={selectedIncidentId}
          onSelectIncident={onSelectIncident}
        />
        <IncidentFeed
          incidents={incidents}
          selectedIncidentId={selectedIncidentId}
          onSelectIncident={onSelectIncident}
          onAllocateIncident={onAllocateIncident}
          onOpenReportModal={onOpenReportModal}
          isAllocatingId={isAllocatingId}
        />
      </div>

      {/* Bottom Section: Ambulance Fleet & Hospital Capacity Overviews */}
      <div className="bottom-grid">
        <FleetOverview
          ambulances={ambulances}
          onSimulateBreakdown={onSimulateBreakdown}
          isBreakdownLoadingId={isBreakdownLoadingId}
        />
        <HospitalOverview
          hospitals={hospitals}
          onSimulateHospitalSaturation={onSimulateHospitalSaturation}
          isHospitalLoadingId={isHospitalLoadingId}
        />
      </div>
    </div>
  );
}

