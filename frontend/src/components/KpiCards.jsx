import React from 'react';
import {
  AlertTriangle,
  Flame,
  Ambulance,
  Building2,
  Timer,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';

export default function KpiCards({ kpis }) {
  const dispatchedCount = Math.max(kpis.totalAmbulances - kpis.availableAmbulances, 0);

  return (
    <div className="kpi-grid">
      {/* 1. Active Emergencies */}
      <div className="kpi-card warning">
        <div className="kpi-header">
          <span className="kpi-title">Active Emergencies</span>
          <div className="kpi-icon-wrap">
            <Flame size={16} />
          </div>
        </div>
        <div className="kpi-value-row">
          <span className="kpi-value">{kpis.activeEmergencies}</span>
          <span className="kpi-subtext">in Hyderabad sector</span>
        </div>
        <div className="kpi-footer-metric" style={{ color: '#fb923c' }}>
          <TrendingUp size={13} />
          <span>+2 reported in last 30m</span>
        </div>
      </div>

      {/* 2. Critical Incidents */}
      <div className="kpi-card critical">
        <div className="kpi-header">
          <span className="kpi-title">Critical Incidents</span>
          <div className="kpi-icon-wrap">
            <AlertTriangle size={16} />
          </div>
        </div>
        <div className="kpi-value-row">
          <span className="kpi-value">{kpis.criticalIncidents}</span>
          <span className="kpi-subtext">Immediate ALS required</span>
        </div>
        <div className="kpi-footer-metric" style={{ color: '#f87171' }}>
          <span>Triage score &ge; 85 (High Priority)</span>
        </div>
      </div>

      {/* 3. Available Ambulances (Seeded 8 Fleet Units) */}
      <div className="kpi-card success">
        <div className="kpi-header">
          <span className="kpi-title">Available Ambulances</span>
          <div className="kpi-icon-wrap">
            <Ambulance size={16} />
          </div>
        </div>
        <div className="kpi-value-row">
          <span className="kpi-value">{`${kpis.availableAmbulances} / ${kpis.totalAmbulances}`}</span>
          <span className="kpi-subtext">seeded fleet units ready</span>
        </div>
        <div className="kpi-footer-metric" style={{ color: '#34d399' }}>
          <span>{dispatchedCount} Dispatched / Active (8 Seeded Units)</span>
        </div>
      </div>

      {/* 4. Hospitals Online */}
      <div className="kpi-card info">
        <div className="kpi-header">
          <span className="kpi-title">Hospitals Online</span>
          <div className="kpi-icon-wrap">
            <Building2 size={16} />
          </div>
        </div>
        <div className="kpi-value-row">
          <span className="kpi-value">{`${kpis.hospitalsOnline} / ${kpis.totalHospitals}`}</span>
          <span className="kpi-subtext">seeded trauma centers</span>
        </div>
        <div className="kpi-footer-metric" style={{ color: '#60a5fa' }}>
          <span>100% telemetry synced (5 Seeded Centers)</span>
        </div>
      </div>

      {/* 5. Average Response Time */}
      <div className="kpi-card timer">
        <div className="kpi-header">
          <span className="kpi-title">Avg Response Time</span>
          <div className="kpi-icon-wrap">
            <Timer size={16} />
          </div>
        </div>
        <div className="kpi-value-row">
          <span
            className="kpi-value"
            style={kpis.avgResponseTimeMin === null ? { fontSize: '1.05rem', color: '#94a3b8' } : {}}
          >
            {kpis.avgResponseTimeMin !== null ? `${kpis.avgResponseTimeMin}m` : 'Pending telemetry'}
          </span>
          <span className="kpi-subtext">
            {kpis.avgResponseTimeMin !== null ? 'minutes' : 'Awaiting hardware GPS logs'}
          </span>
        </div>
        <div className="kpi-footer-metric" style={{ color: '#a78bfa' }}>
          <TrendingDown size={13} />
          <span>Target: &lt; {kpis.targetResponseTimeMin || 10.0} min (Optimal)</span>
        </div>
      </div>
    </div>
  );
}
