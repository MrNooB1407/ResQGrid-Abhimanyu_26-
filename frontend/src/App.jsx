import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import CommandCenter from './pages/CommandCenter';
import IncidentsView from './pages/IncidentsView';
import FleetView from './pages/FleetView';
import HospitalsView from './pages/HospitalsView';
import AnalyticsView from './pages/AnalyticsView';
import SettingsView from './pages/SettingsView';

import {
  INITIAL_KPIS,
  MOCK_INCIDENTS,
  MOCK_AMBULANCES,
  MOCK_HOSPITALS,
  MOCK_NOTIFICATIONS,
} from './data/mockData';

export default function App() {
  const [currentView, setCurrentView] = useState('command-center');
  const [kpis, setKpis] = useState(INITIAL_KPIS);
  const [incidents] = useState(MOCK_INCIDENTS);
  const [ambulances, setAmbulances] = useState(MOCK_AMBULANCES);
  const [hospitals] = useState(MOCK_HOSPITALS);
  const [notifications, setNotifications] = useState(MOCK_NOTIFICATIONS);
  const [selectedIncidentId, setSelectedIncidentId] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Functional refresh button handler
  const handleRefresh = () => {
    setIsRefreshing(true);

    // Simulate realistic dynamic telemetry updates on the 8 seeded ambulances
    setTimeout(() => {
      // Fluctuate response time slightly
      setKpis((prev) => ({
        ...prev,
        avgResponseTimeMin: Number((8.1 + Math.random() * 0.6).toFixed(1)),
      }));

      // Adjust ambulance speeds and slight ETA changes
      setAmbulances((prev) =>
        prev.map((amb) => {
          if (amb.status === 'EN_ROUTE' || amb.status === 'TRANSPORTING') {
            return {
              ...amb,
              speedKmH: Math.floor(42 + Math.random() * 18),
              etaMinutes: amb.etaMinutes ? Number(Math.max(amb.etaMinutes - 0.2, 0.5).toFixed(1)) : null,
            };
          }
          return amb;
        })
      );

      // Add a refresh notification if not already present
      const refreshNotice = {
        id: `NOTIF-${Date.now()}`,
        type: 'INFO',
        title: 'Telemetry Refreshed',
        detail: 'Dynamic routing and ETA calculations synchronized with 8 seeded ambulances and 5 hospitals.',
        time: 'Just now',
        read: false,
      };

      setNotifications((prev) => [refreshNotice, ...prev.slice(0, 5)]);
      setIsRefreshing(false);
    }, 600);
  };

  const handleMarkAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  const handleSelectIncident = (id) => {
    setSelectedIncidentId((prev) => (prev === id ? null : id));
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
        return 'Response time trends, route optimization efficiency, and triage accuracy';
      case 'settings':
        return 'Dispatch automation parameters, dynamic thresholds, and notifications';
      default:
        return 'Real-time emergency coordination across Hyderabad';
    }
  };

  const availableAmbulancesCount = ambulances.filter((a) => a.status === 'AVAILABLE').length;

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
        {/* 2. Top Header */}
        <Header
          title={getHeaderTitle()}
          subtitle={getHeaderSubtitle()}
          onRefresh={handleRefresh}
          isRefreshing={isRefreshing}
          notifications={notifications}
          onMarkAllRead={handleMarkAllRead}
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
          />
        )}

        {currentView === 'incidents' && (
          <IncidentsView
            incidents={incidents}
            onBackToCommand={() => setCurrentView('command-center')}
          />
        )}

        {currentView === 'fleet' && (
          <FleetView
            ambulances={ambulances}
            onBackToCommand={() => setCurrentView('command-center')}
          />
        )}

        {currentView === 'hospitals' && (
          <HospitalsView
            hospitals={hospitals}
            onBackToCommand={() => setCurrentView('command-center')}
          />
        )}

        {currentView === 'analytics' && (
          <AnalyticsView
            onBackToCommand={() => setCurrentView('command-center')}
          />
        )}

        {currentView === 'settings' && (
          <SettingsView
            onBackToCommand={() => setCurrentView('command-center')}
          />
        )}
      </div>
    </div>
  );
}
