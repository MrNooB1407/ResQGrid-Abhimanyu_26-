import React, { useState } from 'react';
import { Search, MapPin, Ambulance, Building2, ArrowLeft } from 'lucide-react';

export default function IncidentsView({ incidents, onBackToCommand }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [severityFilter, setSeverityFilter] = useState('ALL');

  const filtered = incidents.filter((inc) => {
    const matchesSearch =
      inc.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      inc.location.toLowerCase().includes(searchTerm.toLowerCase()) ||
      inc.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      inc.type.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesSev = severityFilter === 'ALL' || inc.severity === severityFilter;
    return matchesSearch && matchesSev;
  });

  return (
    <div className="dashboard-content">
      {/* Search & Filter Header Bar */}
      <div className="panel-container" style={{ padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
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
            <div>
              <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#ffffff' }}>Emergency Dispatch Queue</h2>
              <p style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                Operational triage roster across Hyderabad metropolitan emergency corridors.
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {/* Search Input */}
            <div style={{ position: 'relative' }}>
              <Search size={14} style={{ position: 'absolute', left: '10px', top: '10px', color: '#64748b' }} />
              <input
                type="text"
                placeholder="Search incident, location, ID..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{
                  background: '#090e1a',
                  border: '1px solid #334155',
                  color: '#f8fafc',
                  padding: '0.45rem 0.75rem 0.45rem 2rem',
                  borderRadius: '6px',
                  fontSize: '0.8rem',
                  outline: 'none',
                  width: '240px',
                }}
              />
            </div>

            {/* Severity Selector */}
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              style={{
                background: '#090e1a',
                border: '1px solid #334155',
                color: '#f8fafc',
                padding: '0.45rem 0.75rem',
                borderRadius: '6px',
                fontSize: '0.8rem',
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical Only (&ge;85)</option>
              <option value="HIGH">High Severity</option>
              <option value="MEDIUM">Medium Severity</option>
              <option value="LOW">Low Severity</option>
            </select>
          </div>
        </div>
      </div>

      {/* Incidents Table */}
      <div className="panel-container">
        <div className="fleet-table-wrapper">
          <table className="fleet-table">
            <thead>
              <tr>
                <th>ID / Reported</th>
                <th>Incident Type &amp; Summary</th>
                <th>Severity</th>
                <th>Location / Landmark</th>
                <th>Assigned Unit</th>
                <th>Receiving ER</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>
                    No emergency incidents match &ldquo;{searchTerm}&rdquo; with severity &ldquo;{severityFilter}&rdquo;.
                  </td>
                </tr>
              ) : (
                filtered.map((inc) => (
                  <tr key={inc.id}>
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontWeight: 700, color: '#ffffff' }}>{inc.id}</span>
                        <span style={{ fontSize: '0.68rem', color: '#64748b' }}>{inc.reportedTime}</span>
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontWeight: 600, color: '#e2e8f0' }}>{inc.title}</span>
                        <span style={{ fontSize: '0.68rem', color: '#94a3b8' }}>
                          {inc.type.replace(/_/g, ' ')} • {inc.injuredCount} patient(s)
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className={`severity-pill ${inc.severity.toLowerCase()}`}>
                        {inc.severity} ({inc.severityScore})
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ color: '#cbd5e1' }}>{inc.location}</span>
                        <span style={{ fontSize: '0.68rem', color: '#64748b' }}>{inc.landmark}</span>
                      </div>
                    </td>
                    <td>
                      {inc.assignedAmbulance ? (
                        <span style={{ color: '#10b981', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                          <Ambulance size={12} />
                          {inc.assignedAmbulance}
                        </span>
                      ) : (
                        <span style={{ color: '#ef4444', fontStyle: 'italic' }}>Pending Allocation</span>
                      )}
                    </td>
                    <td>
                      {inc.assignedHospital ? (
                        <span style={{ color: '#60a5fa', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                          <Building2 size={12} />
                          {inc.assignedHospital}
                        </span>
                      ) : (
                        <span style={{ color: '#64748b' }}>TBD</span>
                      )}
                    </td>
                    <td>
                      <span className="incident-status-tag">{inc.status}</span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
