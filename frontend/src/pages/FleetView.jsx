import React, { useState } from 'react';
import { Ambulance, Shield, Radio, CheckCircle2, ArrowLeft } from 'lucide-react';
import FleetOverview from '../components/FleetOverview';

export default function FleetView({
  ambulances,
  onBackToCommand,
  onSimulateBreakdown,
  isBreakdownLoadingId,
}) {
  const [statusFilter, setStatusFilter] = useState('ALL');

  const filteredAmbulances = ambulances.filter((a) => {
    if (statusFilter === 'ALL') return true;
    return a.status === statusFilter;
  });

  const availableCount = ambulances.filter((a) => a.status === 'AVAILABLE').length;
  const enRouteCount = ambulances.filter((a) => a.status === 'EN_ROUTE' || a.status === 'TRANSPORTING').length;
  const onSceneCount = ambulances.filter((a) => a.status === 'ON_SCENE').length;

  return (
    <div className="dashboard-content">
      {/* Top Header with Back button */}
      <div className="panel-container" style={{ padding: '0.85rem 1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {onBackToCommand && (
              <button
                onClick={onBackToCommand}
                type="button"
                className="subview-back-btn"
                style={{ margin: 0, padding: '0.4rem 0.75rem' }}
                title="Return to Command Center"
              >
                <ArrowLeft size={14} />
                <span>Back</span>
              </button>
            )}
            <div>
              <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#ffffff' }}>Ambulance Fleet Telemetry</h2>
              <p style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                All 8 seeded vehicles registered with Hyderabad emergency dispatch node.
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Filter Status:</span>
            {['ALL', 'AVAILABLE', 'EN_ROUTE', 'TRANSPORTING'].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                type="button"
                className={`filter-tab ${statusFilter === st ? 'active' : ''}`}
                style={{ fontSize: '0.72rem' }}
              >
                {st.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Fleet Stats Overview */}
      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <div className="kpi-card info">
          <div className="kpi-header">
            <span className="kpi-title">Total Seeded Fleet</span>
            <Ambulance size={16} />
          </div>
          <div className="kpi-value">{ambulances.length}</div>
          <span className="kpi-subtext">Registered response vehicles</span>
        </div>
        <div className="kpi-card success">
          <div className="kpi-header">
            <span className="kpi-title">Standby Ready</span>
            <CheckCircle2 size={16} />
          </div>
          <div className="kpi-value">{availableCount}</div>
          <span className="kpi-subtext">Immediate ALS/BLS dispatch</span>
        </div>
        <div className="kpi-card warning">
          <div className="kpi-header">
            <span className="kpi-title">Dispatched / Transit</span>
            <Radio size={16} />
          </div>
          <div className="kpi-value">{enRouteCount}</div>
          <span className="kpi-subtext">En route to scene or trauma facility</span>
        </div>
        <div className="kpi-card critical">
          <div className="kpi-header">
            <span className="kpi-title">On-Scene Triage</span>
            <Shield size={16} />
          </div>
          <div className="kpi-value">{onSceneCount}</div>
          <span className="kpi-subtext">Paramedics administering care</span>
        </div>
      </div>

      {/* Fleet Table with Controls */}
      <FleetOverview
        ambulances={filteredAmbulances}
        onSimulateBreakdown={onSimulateBreakdown}
        isBreakdownLoadingId={isBreakdownLoadingId}
      />
    </div>
  );
}
