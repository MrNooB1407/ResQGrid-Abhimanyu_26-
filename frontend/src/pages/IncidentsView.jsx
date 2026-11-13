import React, { useState } from 'react';
import {
  Search,
  MapPin,
  Ambulance,
  Building2,
  ArrowLeft,
  Zap,
  PlusCircle,
  Eye,
} from 'lucide-react';

export default function IncidentsView({
  incidents,
  onBackToCommand,
  onAllocateIncident,
  onOpenReportModal,
  isAllocatingId,
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [inspectedIncident, setInspectedIncident] = useState(null);

  const filtered = incidents.filter((inc) => {
    const titleMatch = (inc.title || '').toLowerCase().includes(searchTerm.toLowerCase());
    const locMatch = (inc.location || inc.displayLocation || '').toLowerCase().includes(searchTerm.toLowerCase());
    const idMatch = (inc.id || inc.code || '').toLowerCase().includes(searchTerm.toLowerCase());
    const typeMatch = (inc.type || '').toLowerCase().includes(searchTerm.toLowerCase());
    const matchesSearch = titleMatch || locMatch || idMatch || typeMatch;

    const matchesSev = severityFilter === 'ALL' || inc.severity === severityFilter;
    const matchesStatus =
      statusFilter === 'ALL' ||
      inc.backendStatus === statusFilter ||
      inc.status?.toUpperCase() === statusFilter;

    return matchesSearch && matchesSev && matchesStatus;
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

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
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
                  width: '210px',
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
                padding: '0.45rem 0.65rem',
                borderRadius: '6px',
                fontSize: '0.78rem',
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical (&ge;85)</option>
              <option value="HIGH">High Severity</option>
              <option value="MEDIUM">Medium Severity</option>
              <option value="LOW">Low Severity</option>
            </select>

            {/* Status Selector */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{
                background: '#090e1a',
                border: '1px solid #334155',
                color: '#f8fafc',
                padding: '0.45rem 0.65rem',
                borderRadius: '6px',
                fontSize: '0.78rem',
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              <option value="ALL">All Statuses</option>
              <option value="REPORTED">Reported (Unassigned)</option>
              <option value="ASSIGNED">Unit Assigned</option>
              <option value="IN_TRANSIT">En Route</option>
              <option value="RESOLVED">Resolved</option>
              <option value="CANCELLED">Cancelled</option>
            </select>

            {/* Report Button */}
            {onOpenReportModal && (
              <button
                type="button"
                className="btn-primary"
                onClick={onOpenReportModal}
                style={{
                  padding: '0.45rem 0.8rem',
                  fontSize: '0.78rem',
                  background: 'linear-gradient(135deg, #ef4444, #dc2626)',
                  borderColor: '#f87171',
                }}
              >
                <PlusCircle size={14} />
                <span>Report Emergency</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Inspected Incident Detail Card (If Clicked) */}
      {inspectedIncident && (
        <div
          className="panel-container"
          style={{
            padding: '1rem 1.25rem',
            background: '#0c152e',
            border: '1px solid #3b82f6',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.65rem',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Eye size={16} color="#60a5fa" />
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#ffffff' }}>
                Incident #{inspectedIncident.id}: {inspectedIncident.title}
              </h3>
            </div>
            <button
              type="button"
              className="subview-back-btn"
              onClick={() => setInspectedIncident(null)}
              style={{ margin: 0, padding: '0.2rem 0.5rem', fontSize: '0.7rem' }}
            >
              Close Details
            </button>
          </div>

          <p style={{ fontSize: '0.8rem', color: '#cbd5e1', lineHeight: 1.45 }}>
            {inspectedIncident.description || 'No extended description recorded.'}
          </p>

          <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.75rem', color: '#94a3b8', flexWrap: 'wrap' }}>
            <span>Coordinates: <strong style={{ color: '#f8fafc' }}>{inspectedIncident.latitude !== null ? `${inspectedIncident.latitude?.toFixed(4)}°N, ${inspectedIncident.longitude?.toFixed(4)}°E` : 'N/A'}</strong></span>
            <span>Casualties: <strong style={{ color: '#f8fafc' }}>{inspectedIncident.injuredCount} injured / {inspectedIncident.affectedCount} affected</strong></span>
            <span>Reported Time: <strong style={{ color: '#f8fafc' }}>{inspectedIncident.createdAt || inspectedIncident.reportedTime}</strong></span>
            <span>Lifecycle State: <strong style={{ color: '#38bdf8' }}>{inspectedIncident.backendStatus}</strong></span>
          </div>

          {/* Allocation Action in Detail Card */}
          {(!inspectedIncident.assignedAmbulance || inspectedIncident.backendStatus === 'REPORTED') && onAllocateIncident && (
            <div style={{ marginTop: '0.4rem' }}>
              <button
                type="button"
                className="btn-action-allocate"
                onClick={() => onAllocateIncident(inspectedIncident.backendId)}
                disabled={isAllocatingId === inspectedIncident.backendId}
              >
                <Zap size={13} />
                <span>{isAllocatingId === inspectedIncident.backendId ? 'Allocating...' : 'Allocate Resources Now'}</span>
              </button>
            </div>
          )}
        </div>
      )}

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
                {onAllocateIncident && <th>Action</th>}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={onAllocateIncident ? 8 : 7} style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>
                    No emergency incidents match &ldquo;{searchTerm}&rdquo; with severity &ldquo;{severityFilter}&rdquo;.
                  </td>
                </tr>
              ) : (
                filtered.map((inc) => (
                  <tr
                    key={inc.id}
                    onClick={() => setInspectedIncident(inc)}
                    style={{ cursor: 'pointer' }}
                    title="Click to inspect incident details"
                  >
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
                        <span style={{ color: '#cbd5e1' }}>{inc.location || inc.displayLocation || 'Sector Location'}</span>
                        {inc.latitude !== null && (
                          <span style={{ fontSize: '0.65rem', color: '#64748b' }}>
                            {inc.latitude.toFixed(4)}, {inc.longitude?.toFixed(4)}
                          </span>
                        )}
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
                    {onAllocateIncident && (
                      <td>
                        {(!inc.assignedAmbulance || inc.backendStatus === 'REPORTED') ? (
                          <button
                            type="button"
                            className="btn-action-allocate"
                            onClick={(e) => {
                              e.stopPropagation();
                              onAllocateIncident(inc.backendId);
                            }}
                            disabled={isAllocatingId === inc.backendId}
                            title="Dispatch nearest unit"
                          >
                            <Zap size={11} />
                            <span>{isAllocatingId === inc.backendId ? 'Allocating...' : 'Allocate'}</span>
                          </button>
                        ) : (
                          <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Fulfilled</span>
                        )}
                      </td>
                    )}
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
