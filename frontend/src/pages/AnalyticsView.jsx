import React from 'react';
import {
  BarChart3,
  TrendingDown,
  Clock,
  ShieldCheck,
  Zap,
  Activity,
  ArrowLeft,
  Ambulance,
  Building2,
  AlertTriangle,
  Info,
} from 'lucide-react';

export default function AnalyticsView({ analytics, onBackToCommand }) {
  const data = analytics || {
    incidents: { total: 0, active: 0, critical: 0, bySeverity: {}, byStatus: {} },
    ambulances: { total: 0, available: 0, byStatus: {}, byCapability: {} },
    hospitals: { total: 0, totalBeds: 0, availableBeds: 0, occupiedBeds: 0, occupancyPct: 0, totalIcu: 0, availableIcu: 0, occupiedIcu: 0, icuOccupancyPct: 0, availableVents: 0 },
    allocations: { total: 0, active: 0, reallocated: 0, avgEtaMinutes: null },
    kpis: { avgResponseTimeDisplay: 'Pending telemetry', targetResponseTimeMin: 10.0 },
    responseTime: { isRecorded: false, explanation: 'Actual on-scene response time is not yet recorded in the database schema.' },
  };

  const incTotal = data.incidents.total || 1;
  const sevCritical = data.incidents.bySeverity?.CRITICAL || 0;
  const sevHigh = data.incidents.bySeverity?.HIGH || 0;
  const sevMed = data.incidents.bySeverity?.MEDIUM || 0;
  const sevLow = data.incidents.bySeverity?.LOW || 0;

  const statReported = data.incidents.byStatus?.REPORTED || 0;
  const statAssigned = data.incidents.byStatus?.ASSIGNED || 0;
  const statTransit = data.incidents.byStatus?.IN_TRANSIT || 0;
  const statResolved = data.incidents.byStatus?.RESOLVED || 0;
  const statCancelled = data.incidents.byStatus?.CANCELLED || 0;

  const ambAls = data.ambulances.byCapability?.ALS || 0;
  const ambBls = data.ambulances.byCapability?.BLS || 0;
  const ambPt = data.ambulances.byCapability?.PATIENT_TRANSPORT || 0;

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
              <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#ffffff' }}>Operations Performance Analytics</h2>
              <p style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                Live operational aggregates calculated directly from SQLite database records.
              </p>
            </div>
          </div>
          <div className="sim-pill" title="Live database metrics">
            <span className="sim-dot" />
            <span>REAL-TIME SQLITE AGGREGATES</span>
          </div>
        </div>
      </div>

      {/* Analytics KPI Row */}
      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <div className="kpi-card timer">
          <div className="kpi-header">
            <span className="kpi-title">Avg Response Time</span>
            <Clock size={16} />
          </div>
          <div className="kpi-value" style={{ fontSize: '1.05rem', color: '#94a3b8' }}>
            {data.kpis?.avgResponseTimeDisplay || 'Pending telemetry'}
          </div>
          <span className="kpi-subtext">Target: &le; 10 min (Hardware telemetry pending)</span>
        </div>

        <div className="kpi-card success">
          <div className="kpi-header">
            <span className="kpi-title">Active Allocations</span>
            <ShieldCheck size={16} />
          </div>
          <div className="kpi-value">{data.allocations.active}</div>
          <span className="kpi-subtext">
            {data.allocations.total} total historical dispatch commitments
          </span>
        </div>

        <div className="kpi-card info">
          <div className="kpi-header">
            <span className="kpi-title">Dynamic Reallocations</span>
            <Zap size={16} />
          </div>
          <div className="kpi-value">{data.allocations.reallocated}</div>
          <span className="kpi-subtext">Automated breakdown &amp; saturation reroutes</span>
        </div>

        <div className="kpi-card warning">
          <div className="kpi-header">
            <span className="kpi-title">Average Active ETA</span>
            <TrendingDown size={16} />
          </div>
          <div className="kpi-value">
            {data.allocations.avgEtaMinutes !== null ? `${data.allocations.avgEtaMinutes}m` : 'N/A'}
          </div>
          <span className="kpi-subtext">Estimated arrival for active dispatches</span>
        </div>
      </div>

      {/* Visual Analysis Panels */}
      <div className="middle-grid">
        {/* Left Panel: Real Resource Capacity & Fleet */}
        <div className="panel-container">
          <div className="panel-header">
            <div className="panel-title-group">
              <Building2 size={17} color="#3b82f6" />
              <h3>Hospital &amp; Fleet Real-Time Capacity</h3>
            </div>
            <span className="panel-badge">{data.hospitals.total} Seeded Hospitals</span>
          </div>

          <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
            {/* Hospital Beds Occupancy Meter */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem' }}>
                <span style={{ color: '#e2e8f0', fontWeight: 600 }}>General ER Inpatient Occupancy</span>
                <span style={{ color: '#93c5fd' }}>
                  {data.hospitals.occupiedBeds} / {data.hospitals.totalBeds} beds ({data.hospitals.occupancyPct}%)
                </span>
              </div>
              <div style={{ height: '8px', background: '#1e293b', borderRadius: '4px', overflow: 'hidden' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${Math.min(100, data.hospitals.occupancyPct)}%`,
                    background: data.hospitals.occupancyPct > 90 ? '#ef4444' : '#3b82f6',
                    borderRadius: '4px',
                    transition: 'width 0.4s ease',
                  }}
                />
              </div>
            </div>

            {/* ICU Beds Occupancy Meter */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem' }}>
                <span style={{ color: '#e2e8f0', fontWeight: 600 }}>Critical Care / ICU Trauma Capacity</span>
                <span style={{ color: '#fca5a5' }}>
                  {data.hospitals.occupiedIcu} / {data.hospitals.totalIcu} ICU beds ({data.hospitals.icuOccupancyPct}%)
                </span>
              </div>
              <div style={{ height: '8px', background: '#1e293b', borderRadius: '4px', overflow: 'hidden' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${Math.min(100, data.hospitals.icuOccupancyPct)}%`,
                    background: data.hospitals.icuOccupancyPct > 85 ? '#ef4444' : '#f59e0b',
                    borderRadius: '4px',
                    transition: 'width 0.4s ease',
                  }}
                />
              </div>
            </div>

            {/* Ventilators & Ambulances Stat Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', marginTop: '0.5rem' }}>
              <div style={{ background: '#070b16', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#64748b' }}>Ventilators Online</div>
                <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#38bdf8' }}>{data.hospitals.availableVents}</div>
                <div style={{ fontSize: '0.65rem', color: '#94a3b8' }}>Available for intake</div>
              </div>

              <div style={{ background: '#070b16', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#64748b' }}>Fleet Ready</div>
                <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#10b981' }}>
                  {data.ambulances.available} / {data.ambulances.total}
                </div>
                <div style={{ fontSize: '0.65rem', color: '#94a3b8' }}>Immediate ALS/BLS</div>
              </div>

              <div style={{ background: '#070b16', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#64748b' }}>Dispatched Fleet</div>
                <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#fbbf24' }}>
                  {Math.max(0, data.ambulances.total - data.ambulances.available)}
                </div>
                <div style={{ fontSize: '0.65rem', color: '#94a3b8' }}>Active in transit</div>
              </div>
            </div>

            {/* Ambulance Capabilities Roster */}
            <div style={{ borderTop: '1px solid #1e293b', paddingTop: '0.75rem', display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#94a3b8' }}>
              <span>ALS Units: <strong style={{ color: '#ffffff' }}>{ambAls}</strong></span>
              <span>BLS Units: <strong style={{ color: '#ffffff' }}>{ambBls}</strong></span>
              <span>Patient Transport: <strong style={{ color: '#ffffff' }}>{ambPt}</strong></span>
            </div>
          </div>
        </div>

        {/* Right Panel: Incident Distributions by Severity & Status */}
        <div className="panel-container">
          <div className="panel-header">
            <div className="panel-title-group">
              <Activity size={17} color="#f59e0b" />
              <h3>Database Incident Distributions</h3>
            </div>
            <span className="panel-badge">{data.incidents.total} Total Incidents</span>
          </div>

          <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <h4 style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Incidents By Severity
            </h4>
            {[
              { label: 'CRITICAL (Priority 1)', count: sevCritical, pct: Math.round((sevCritical / incTotal) * 100), color: '#ef4444' },
              { label: 'HIGH (Priority 2)', count: sevHigh, pct: Math.round((sevHigh / incTotal) * 100), color: '#f97316' },
              { label: 'MEDIUM (Priority 3)', count: sevMed, pct: Math.round((sevMed / incTotal) * 100), color: '#f59e0b' },
              { label: 'LOW (Priority 4)', count: sevLow, pct: Math.round((sevLow / incTotal) * 100), color: '#38bdf8' },
            ].map((cat, idx) => (
              <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                  <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{cat.label}</span>
                  <span style={{ color: '#94a3b8' }}>{cat.count} cases ({cat.pct}%)</span>
                </div>
                <div style={{ height: '6px', background: '#1e293b', borderRadius: '4px', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${cat.pct}%`, background: cat.color, borderRadius: '4px' }} />
                </div>
              </div>
            ))}

            <h4 style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: '0.4rem', borderTop: '1px solid #1e293b', paddingTop: '0.75rem' }}>
              Incidents By Lifecycle Status
            </h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '0.4rem', textAlign: 'center' }}>
              <div style={{ background: '#070b16', padding: '0.5rem', borderRadius: '5px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.65rem', color: '#64748b' }}>REPORTED</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f59e0b' }}>{statReported}</div>
              </div>
              <div style={{ background: '#070b16', padding: '0.5rem', borderRadius: '5px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.65rem', color: '#64748b' }}>ASSIGNED</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#38bdf8' }}>{statAssigned}</div>
              </div>
              <div style={{ background: '#070b16', padding: '0.5rem', borderRadius: '5px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.65rem', color: '#64748b' }}>EN ROUTE</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#a78bfa' }}>{statTransit}</div>
              </div>
              <div style={{ background: '#070b16', padding: '0.5rem', borderRadius: '5px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.65rem', color: '#64748b' }}>RESOLVED</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#10b981' }}>{statResolved}</div>
              </div>
              <div style={{ background: '#070b16', padding: '0.5rem', borderRadius: '5px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.65rem', color: '#64748b' }}>CANCELLED</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#64748b' }}>{statCancelled}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Audit Footnote */}
      <div
        style={{
          background: '#070b16',
          border: '1px solid #1e293b',
          borderRadius: '8px',
          padding: '0.75rem 1rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.6rem',
          fontSize: '0.75rem',
          color: '#64748b',
        }}
      >
        <Info size={14} color="#3b82f6" />
        <span>
          All metrics above are calculated directly from live SQLite tables (<code>incidents</code>, <code>ambulances</code>, <code>hospitals</code>, <code>allocations</code>). Operational telemetry does not invent simulated trend curves or fictitious response times.
        </span>
      </div>
    </div>
  );
}
