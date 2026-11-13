import React, { useState, useEffect, useRef, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import CommandCenter from './pages/CommandCenter';
import IncidentsView from './pages/IncidentsView';
import FleetView from './pages/FleetView';
import HospitalsView from './pages/HospitalsView';
import AnalyticsView from './pages/AnalyticsView';
import SettingsView from './pages/SettingsView';

import ReportEmergencyModal from './components/ReportEmergencyModal';
import ActionFeedbackModal from './components/ActionFeedbackModal';

import {
  getAnalyticsOverview,
  getIncidents,
  getAmbulances,
  getHospitals,
  getEvents,
  allocateIncident,
  createIncident,
  reportAmbulanceBreakdown,
  reportHospitalSaturation,
} from './services/api';

import {
  adaptAnalytics,
  adaptIncidents,
  adaptAmbulances,
  adaptHospitals,
  adaptEvents,
} from './adapters';

export default function App() {
  const [currentView, setCurrentView] = useState('command-center');

  // Real Database State (initialized cleanly)
  const [kpis, setKpis] = useState({
    activeEmergencies: 0,
    criticalIncidents: 0,
    availableAmbulances: 0,
    totalAmbulances: 0,
    hospitalsOnline: 0,
    totalHospitals: 0,
    avgResponseTimeMin: null,
    avgResponseTimeDisplay: 'Pending telemetry',
    targetResponseTimeMin: 10.0,
  });

  const [analytics, setAnalytics] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [ambulances, setAmbulances] = useState([]);
  const [hospitals, setHospitals] = useState([]);
  const [notifications, setNotifications] = useState([]);

  const [selectedIncidentId, setSelectedIncidentId] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [apiError, setApiError] = useState(null);

  // Modals & Action Loaders
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [actionFeedbackData, setActionFeedbackData] = useState(null);
  const [isAllocatingId, setIsAllocatingId] = useState(null);
  const [isBreakdownLoadingId, setIsBreakdownLoadingId] = useState(null);
  const [isHospitalLoadingId, setIsHospitalLoadingId] = useState(null);

  // In-flight guard to prevent overlapping periodic requests
  const isFetchingRef = useRef(false);

  // Centralized Data Fetcher
  const fetchAllData = useCallback(async (isManual = false) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;

    if (isManual) {
      setIsRefreshing(true);
    }

    try {
      const [analyticsRes, incidentsRes, ambulancesRes, hospitalsRes, eventsRes] =
        await Promise.all([
          getAnalyticsOverview(),
          getIncidents(),
          getAmbulances(),
          getHospitals(),
          getEvents({ limit: 50 }),
        ]);

      // Normalize live database payloads through adapter layer
      const adaptedAnalytics = adaptAnalytics(analyticsRes.data);
      const adaptedIncidents = adaptIncidents(incidentsRes.data);
      const adaptedAmbulances = adaptAmbulances(ambulancesRes.data);
      const adaptedHospitals = adaptHospitals(hospitalsRes.data);
      const adaptedEventsList = adaptEvents(eventsRes.data);

      setAnalytics(adaptedAnalytics);
      setKpis(adaptedAnalytics.kpis);
      setIncidents(adaptedIncidents);
      setAmbulances(adaptedAmbulances);
      setHospitals(adaptedHospitals);
      setNotifications(adaptedEventsList);

      setLastUpdated(new Date().toLocaleTimeString('en-US', { hour12: false }));
      setApiError(null);
    } catch (err) {
      console.error('Failed to synchronize live dashboard data with Flask API:', err);
      setApiError(err.message || 'Unable to connect to Flask API server.');
    } finally {
      isFetchingRef.current = false;
      if (isManual) {
        setIsRefreshing(false);
      }
    }
  }, []);

  // Initial Load and Auto-Refresh (every 12 seconds with unmount cleanup)
  useEffect(() => {
    fetchAllData(false);

    const intervalTimer = setInterval(() => {
      fetchAllData(false);
    }, 12000);

    return () => clearInterval(intervalTimer);
  }, [fetchAllData]);

  // Manual Refresh Handler
  const handleRefresh = () => {
    fetchAllData(true);
  };

  const handleMarkAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  const handleSelectIncident = (id) => {
    setSelectedIncidentId((prev) => (prev === id ? null : id));
  };

  // --------------------------------------------------------------------------
  // ACTION: Allocate Resources to Incident
  // --------------------------------------------------------------------------
  const handleAllocateIncident = async (incidentId) => {
    if (!incidentId) return;

    try {
      setIsAllocatingId(incidentId);
      const res = await allocateIncident(incidentId);

      setActionFeedbackData({
        type: 'ALLOCATION',
        success: true,
        title: 'Emergency Unit Dispatched & Hospital Reserved',
        message:
          res.message ||
          `Assigned ${res.ambulance?.ambulance_number || 'Ambulance'} (${res.ambulance?.capability}) with estimated arrival in ${res.estimated_arrival_minutes}m.`,
        details: res,
      });

      // Refresh database state
      await fetchAllData(false);
    } catch (err) {
      const isShortage = err.status === 422;
      setActionFeedbackData({
        type: 'ALLOCATION',
        success: false,
        title: isShortage ? 'Resource Shortage Detected' : 'Allocation Request Rejected',
        message:
          err.message ||
          (isShortage
            ? 'No suitable ambulances with required clinical capability or hospital trauma beds available.'
            : 'Unable to commit resource allocation.'),
        details: err.data,
      });

      await fetchAllData(false);
    } finally {
      setIsAllocatingId(null);
    }
  };

  // --------------------------------------------------------------------------
  // ACTION: Report New Incident with Automated Triage
  // --------------------------------------------------------------------------
  const handleReportIncident = async (payload) => {
    const res = await createIncident(payload);
    await fetchAllData(false);
    return res;
  };

  // --------------------------------------------------------------------------
  // ACTION: Simulate Ambulance Breakdown in Transit
  // --------------------------------------------------------------------------
  const handleSimulateBreakdown = async (ambulanceId) => {
    if (!ambulanceId) return;

    try {
      setIsBreakdownLoadingId(ambulanceId);
      const res = await reportAmbulanceBreakdown({
        ambulance_id: ambulanceId,
        reason: 'Engine breakdown during emergency transit',
      });

      setActionFeedbackData({
        type: 'BREAKDOWN',
        success: true,
        title: 'Ambulance Breakdown Handled',
        message:
          res.message ||
          `Vehicle retired to OUT_OF_SERVICE. Replacement unit ${res.replacement_ambulance?.ambulance_number || 'dispatched'}.`,
        details: res,
      });

      await fetchAllData(false);
    } catch (err) {
      const isShortage = err.status === 422;
      const isNoActiveAlloc = err.status === 409;

      setActionFeedbackData({
        type: 'BREAKDOWN',
        success: false,
        title: isNoActiveAlloc
          ? 'Breakdown Simulation Notice'
          : isShortage
          ? 'Replacement Unit Shortage'
          : 'Breakdown Report Rejected',
        message:
          err.message ||
          (isNoActiveAlloc
            ? 'Vehicle has no active emergency dispatch to reroute.'
            : 'No replacement vehicle available in sector.'),
        details: err.data,
      });

      await fetchAllData(false);
    } finally {
      setIsBreakdownLoadingId(null);
    }
  };

  // --------------------------------------------------------------------------
  // ACTION: Simulate Hospital ER Saturation
  // --------------------------------------------------------------------------
  const handleSimulateHospitalSaturation = async (hospitalId) => {
    if (!hospitalId) return;

    try {
      setIsHospitalLoadingId(hospitalId);
      const res = await reportHospitalSaturation({
        hospital_id: hospitalId,
        reason: 'Emergency ICU capacity saturation',
        exhausted_resource: 'ICU',
      });

      setActionFeedbackData({
        type: 'HOSPITAL_SATURATION',
        success: true,
        title: 'Hospital Capacity Saturation Managed',
        message:
          res.message ||
          'Incoming emergency transports diverted to alternative medical facilities.',
        details: res.data || res,
      });

      await fetchAllData(false);
    } catch (err) {
      setActionFeedbackData({
        type: 'HOSPITAL_SATURATION',
        success: false,
        title: 'Hospital Diversion Notice',
        message: err.message || 'Unable to divert incoming transports.',
        details: err.data,
      });

      await fetchAllData(false);
    } finally {
      setIsHospitalLoadingId(null);
    }
  };

  const getHeaderTitle = () => {
    switch (currentView) {
      case 'incidents':
        return 'Emergency Incidents Queue';
      case 'fleet':
        return 'Ambulance Fleet Monitoring';
      case 'hospitals':
        return 'Hospital Network & ER Capacity';
      case 'analytics':
        return 'Operations Performance Analytics';
      case 'settings':
        return 'Dispatcher & System Settings';
      default:
        return 'Emergency Command Center';
    }
  };

  const getHeaderSubtitle = () => {
    switch (currentView) {
      case 'incidents':
        return 'Live incident tracking, severity triage, and dispatch logs across Hyderabad';
      case 'fleet':
        return 'Real-time telemetry, readiness status, and positioning of 8 seeded units';
      case 'hospitals':
        return 'Regional trauma centers, ICU occupancy, and ventilator capacity (5 seeded centers)';
      case 'analytics':
        return 'Database-derived triage aggregates, capacity load, and operational metrics';
      case 'settings':
        return 'Dispatch automation parameters, dynamic thresholds, and notifications';
      default:
        return 'Real-time emergency coordination across Hyderabad';
    }
  };

  const availableAmbulancesCount = ambulances.filter(
    (a) => a.backendStatus === 'AVAILABLE' || a.status === 'AVAILABLE'
  ).length;

  return (
    <div className="dashboard-root">
      {/* 1. Left Navigation Sidebar */}
      <Sidebar
        currentView={currentView}
        onViewChange={setCurrentView}
        incidentCount={incidents.length}
        availableAmbulanceCount={availableAmbulancesCount}
        totalAmbulanceCount={ambulances.length}
        hospitalCount={hospitals.length}
      />

      {/* Main Content Area */}
      <div className="main-wrapper">
        {/* Connection Failure Alert Banner */}
        {apiError && (
          <div className="connection-alert-banner">
            <span>
              ⚠️ <strong>Backend Offline / Network Error:</strong> {apiError} (Please verify Flask server is running at http://127.0.0.1:5000)
            </span>
            <button
              type="button"
              onClick={handleRefresh}
              style={{
                background: 'rgba(255, 255, 255, 0.2)',
                border: 'none',
                color: '#ffffff',
                padding: '0.2rem 0.6rem',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '0.72rem',
              }}
            >
              Retry Connection
            </button>
          </div>
        )}

        {/* 2. Top Header */}
        <Header
          title={getHeaderTitle()}
          subtitle={getHeaderSubtitle()}
          onRefresh={handleRefresh}
          isRefreshing={isRefreshing}
          notifications={notifications}
          onMarkAllRead={handleMarkAllRead}
          onOpenReportModal={() => setIsReportModalOpen(true)}
          lastUpdated={lastUpdated}
        />

        {/* View Switcher */}
        {currentView === 'command-center' && (
          <CommandCenter
            kpis={{
              ...kpis,
              availableAmbulances: availableAmbulancesCount,
              totalAmbulances: ambulances.length,
            }}
            incidents={incidents}
            ambulances={ambulances}
            hospitals={hospitals}
            selectedIncidentId={selectedIncidentId}
            onSelectIncident={handleSelectIncident}
            onAllocateIncident={handleAllocateIncident}
            onOpenReportModal={() => setIsReportModalOpen(true)}
            onSimulateBreakdown={handleSimulateBreakdown}
            onSimulateHospitalSaturation={handleSimulateHospitalSaturation}
            isAllocatingId={isAllocatingId}
            isBreakdownLoadingId={isBreakdownLoadingId}
            isHospitalLoadingId={isHospitalLoadingId}
          />
        )}

        {currentView === 'incidents' && (
          <IncidentsView
            incidents={incidents}
            onBackToCommand={() => setCurrentView('command-center')}
            onAllocateIncident={handleAllocateIncident}
            onOpenReportModal={() => setIsReportModalOpen(true)}
            isAllocatingId={isAllocatingId}
          />
        )}

        {currentView === 'fleet' && (
          <FleetView
            ambulances={ambulances}
            onBackToCommand={() => setCurrentView('command-center')}
            onSimulateBreakdown={handleSimulateBreakdown}
            isBreakdownLoadingId={isBreakdownLoadingId}
          />
        )}

        {currentView === 'hospitals' && (
          <HospitalsView
            hospitals={hospitals}
            onBackToCommand={() => setCurrentView('command-center')}
            onSimulateHospitalSaturation={handleSimulateHospitalSaturation}
            isHospitalLoadingId={isHospitalLoadingId}
          />
        )}

        {currentView === 'analytics' && (
          <AnalyticsView
            analytics={analytics}
            onBackToCommand={() => setCurrentView('command-center')}
          />
        )}

        {currentView === 'settings' && (
          <SettingsView
            onBackToCommand={() => setCurrentView('command-center')}
          />
        )}
      </div>

      {/* Emergency Report Modal */}
      <ReportEmergencyModal
        isOpen={isReportModalOpen}
        onClose={() => setIsReportModalOpen(false)}
        onSubmitIncident={handleReportIncident}
        onAllocateIncident={handleAllocateIncident}
      />

      {/* Action Outcome Feedback Modal */}
      <ActionFeedbackModal
        isOpen={Boolean(actionFeedbackData)}
        onClose={() => setActionFeedbackData(null)}
        data={actionFeedbackData}
      />
    </div>
  );
}
