import React from 'react';
import { BarChart3, TrendingDown, Clock, ShieldCheck, Zap, Activity, ArrowLeft } from 'lucide-react';

export default function AnalyticsView({ onBackToCommand }) {
  return (
    <div className="dashboard-content">
      {/* Top Header with Back button */}
      <div className="panel-container" style={{ padding: '0.85rem 1.25rem' }}>
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
              Historical triage efficiency, route optimization savings, and sector performance.
            </p>
          </div>
        </div>
      </div>

      {/* Analytics KPI Row */}
      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <div className="kpi-card timer">
          <div className="kpi-header">
            <span className="kpi-title">Avg Triage-to-Dispatch</span>
            <Clock size={16} />
          </div>
          <div className="kpi-value">1.8 min</div>
          <span className="kpi-subtext">32% faster than municipal benchmark</span>
        </div>
        <div className="kpi-card success">
          <div className="kpi-header">
            <span className="kpi-title">Allocation Success</span>
            <ShieldCheck size={16} />
          </div>
          <div className="kpi-value">98.6%</div>
          <span className="kpi-subtext">Zero failed hospital bed allocations</span>
        </div>
        <div className="kpi-card info">
          <div className="kpi-header">
            <span className="kpi-title">Dynamic Reallocations</span>
            <Zap size={16} />
          </div>
          <div className="kpi-value">7</div>
          <span className="kpi-subtext">Automated traffic and breakdown reroutes</span>
        </div>
        <div className="kpi-card warning">
          <div className="kpi-header">
            <span className="kpi-title">Time Saved by AI</span>
            <TrendingDown size={16} />
          </div>
          <div className="kpi-value">14.2 min</div>
          <span className="kpi-subtext">Per critical cardiac/trauma incident</span>
        </div>
      </div>

      {/* Visual Analysis Panels */}
      <div className="middle-grid">
        {/* Hourly Response Performance (Visual SVG Chart) */}
        <div className="panel-container">
          <div className="panel-header">
            <div className="panel-title-group">
              <BarChart3 size={17} color="#3b82f6" />
              <h3>Dispatch Response Time Curve (Last 6 Hours)</h3>
            </div>
            <span className="panel-badge">Target &le; 10 min</span>
          </div>

          <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <svg viewBox="0 0 500 180" style={{ width: '100%', height: '180px' }}>
              <defs>
                <linearGradient id="curveGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
                </linearGradient>
              </defs>
              {/* Horizontal guide lines */}
              <line x1="30" y1="30" x2="480" y2="30" stroke="#1e293b" strokeDasharray="3 3" />
              <line x1="30" y1="80" x2="480" y2="80" stroke="#1e293b" strokeDasharray="3 3" />
              <line x1="30" y1="130" x2="480" y2="130" stroke="#1e293b" strokeDasharray="3 3" />

              {/* Target Line (10 min) */}
              <line x1="30" y1="65" x2="480" y2="65" stroke="#ef4444" strokeWidth="1" strokeDasharray="4 4" />
              <text x="440" y="60" fill="#ef4444" fontSize="9" fontWeight="600">
                Target 10m
              </text>

              {/* Response curve fill & line */}
              <polygon
                points="50,140 50,110 120,95 190,120 260,85 330,70 400,90 470,75 470,140"
                fill="url(#curveGradient)"
              />
              <polyline
                fill="none"
                stroke="#60a5fa"
                strokeWidth="2.5"
                points="50,110 120,95 190,120 260,85 330,70 400,90 470,75"
              />

              {/* Data point dots */}
              {[
                { x: 50, y: 110, val: '9.2m' },
                { x: 120, y: 95, val: '8.8m' },
                { x: 190, y: 120, val: '9.6m' },
                { x: 260, y: 85, val: '8.4m' },
                { x: 330, y: 70, val: '7.9m' },
                { x: 400, y: 90, val: '8.5m' },
                { x: 470, y: 75, val: '8.4m' },
              ].map((pt, i) => (
                <g key={i}>
                  <circle cx={pt.x} cy={pt.y} r="4" fill="#3b82f6" stroke="#ffffff" strokeWidth="1.5" />
                  <text x={pt.x} y={pt.y - 8} fill="#cbd5e1" fontSize="9" textAnchor="middle" fontWeight="600">
                    {pt.val}
                  </text>
                </g>
              ))}

              {/* X Axis Time Labels */}
              <text x="50" y="160" fill="#64748b" fontSize="9" textAnchor="middle">06:00</text>
              <text x="120" y="160" fill="#64748b" fontSize="9" textAnchor="middle">07:00</text>
              <text x="190" y="160" fill="#64748b" fontSize="9" textAnchor="middle">08:00</text>
              <text x="260" y="160" fill="#64748b" fontSize="9" textAnchor="middle">09:00</text>
              <text x="330" y="160" fill="#64748b" fontSize="9" textAnchor="middle">10:00</text>
              <text x="400" y="160" fill="#64748b" fontSize="9" textAnchor="middle">10:30</text>
              <text x="470" y="160" fill="#64748b" fontSize="9" textAnchor="middle">Current</text>
            </svg>

            <div style={{ fontSize: '0.75rem', color: '#94a3b8', lineHeight: 1.4 }}>
              Mean transit time has improved from 9.2m to 8.4m following dynamic rerouting around the Gachibowli Outer Ring Road corridor congestion.
            </div>
          </div>
        </div>

        {/* Severity & Incident Type Distribution */}
        <div className="panel-container">
          <div className="panel-header">
            <div className="panel-title-group">
              <Activity size={17} color="#f59e0b" />
              <h3>Incident Distribution by Category</h3>
            </div>
          </div>

          <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {[
              { label: 'Cardiac Emergency / Refractory STEMI', pct: 35, count: 14, color: '#ef4444' },
              { label: 'Road Traffic Accident (MVA)', pct: 28, count: 11, color: '#f97316' },
              { label: 'Urban Flooding / Submersion', pct: 18, count: 7, color: '#f59e0b' },
              { label: 'Industrial / Structural Trauma', pct: 12, count: 5, color: '#8b5cf6' },
              { label: 'Heat Exhaustion / Non-Trauma', pct: 7, count: 3, color: '#38bdf8' },
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
          </div>
        </div>
      </div>
    </div>
  );
}
