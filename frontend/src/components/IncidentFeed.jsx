import React, { useState } from 'react';
import {
  Clock,
  MapPin,
  Ambulance,
  Building2,
  Flame,
  Zap,
  PlusCircle,
} from 'lucide-react';

export default function IncidentFeed({
  incidents,
  selectedIncidentId,
  onSelectIncident,
  onAllocateIncident,
  onOpenReportModal,
  isAllocatingId,
}) {
  const [severityFilter, setSeverityFilter] = useState('ALL');

  const filterTabs = [
    { id: 'ALL', label: 'All' },
    { id: 'CRITICAL', label: 'Critical' },
    { id: 'HIGH', label: 'High' },
    { id: 'MEDIUM', label: 'Medium' },
    { id: 'LOW', label: 'Low' },
  ];

  const getFilteredIncidents = () => {
    if (severityFilter === 'ALL') return incidents;
    return incidents.filter((inc) => inc.severity === severityFilter);
  };

  const getSeverityCount = (sev) => {
    if (sev === 'ALL') return incidents.length;
    return incidents.filter((i) => i.severity === sev).length;
  };

  const filteredList = getFilteredIncidents();

  return (
    <div className="panel-container incidents-panel">
      {/* Header */}
      <div className="panel-header">
        <div className="panel-title-group">
          <Flame size={17} color="#ef4444" />
          <h3>Recent Emergency Feed</h3>
          <span className="panel-badge">{`${incidents.length} Active Feeds`}</span>
        </div>
        {onOpenReportModal && (
          <button
            type="button"
            className="btn-danger-outline"
            onClick={onOpenReportModal}
            title="Report new emergency incident"
          >
            <PlusCircle size={13} />
            <span>Report</span>
          </button>
        )}
      </div>

      {/* Severity Filter Tabs */}
      <div className="severity-filter-bar">
        {filterTabs.map((tab) => {
          const count = getSeverityCount(tab.id);
          const isActive = severityFilter === tab.id;
          return (
            <button
              key={tab.id}
              className={`filter-tab ${isActive ? 'active' : ''}`}
              onClick={() => setSeverityFilter(tab.id)}
              type="button"
            >
              <span>{tab.label}</span>
              <span className="filter-count">{count}</span>
            </button>
          );
        })}
      </div>

      {/* Scrollable Incidents List */}
      <div className="incidents-list-scroll">
        {filteredList.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b', fontSize: '0.8rem' }}>
            No active incidents matching severity filter &ldquo;{severityFilter}&rdquo;.
          </div>
        ) : (
          filteredList.map((inc) => {
            const isSelected = selectedIncidentId === inc.id;
            const sevKey = inc.severity.toLowerCase();

            return (
              <div
                key={inc.id}
                className={`incident-card ${isSelected ? 'selected' : ''}`}
                onClick={() => onSelectIncident(inc.id)}
                style={{
                  borderLeft: `3px solid ${
                    inc.severity === 'CRITICAL'
                      ? '#ef4444'
                      : inc.severity === 'HIGH'
                      ? '#f97316'
                      : inc.severity === 'MEDIUM'
                      ? '#f59e0b'
                      : '#38bdf8'
                  }`,
                }}
              >
                {/* Top Row: Type & Severity */}
                <div className="incident-card-top">
                  <div className="incident-type-tag">
                    <span style={{ color: '#94a3b8', fontSize: '0.68rem', fontFamily: 'monospace' }}>
                      {inc.id}
                    </span>
                    <span>•</span>
                    <span>{inc.type.replace(/_/g, ' ')}</span>
                  </div>
                  <span className={`severity-pill ${sevKey}`}>
                    {inc.severity} ({inc.severityScore})
                  </span>
                </div>

                {/* Title */}
                <div className="incident-title-text">{inc.title}</div>

                {/* Location and Landmark */}
                <div className="incident-meta-row">
                  <div className="incident-loc">
                    <MapPin size={12} color="#64748b" />
                    <span>{inc.location || inc.displayLocation || 'Unspecified Location'}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    <Clock size={11} color="#64748b" />
                    <span>{inc.reportedTime}</span>
                  </div>
                </div>

                {/* Assigned Resources & Status */}
                <div className="incident-assignment-row">
                  <span className="incident-status-tag">{inc.status}</span>
                  {inc.assignedAmbulance ? (
                    <>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                        <Ambulance size={11} color="#10b981" />
                        {inc.assignedAmbulance}
                      </span>
                      {inc.assignedHospital && (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                          <Building2 size={11} color="#3b82f6" />
                          {inc.assignedHospital}
                        </span>
                      )}
                      {inc.etaMinutes > 0 && (
                        <span style={{ marginLeft: 'auto', color: '#fbbf24', fontWeight: 600 }}>
                          ETA {inc.etaMinutes}m
                        </span>
                      )}
                    </>
                  ) : (
                    onAllocateIncident && (
                      <button
                        type="button"
                        className="btn-action-allocate"
                        style={{ marginLeft: 'auto' }}
                        disabled={isAllocatingId === inc.backendId}
                        onClick={(e) => {
                          e.stopPropagation();
                          onAllocateIncident(inc.backendId);
                        }}
                        title="Dispatch nearest capable ambulance and reserve receiving hospital beds"
                      >
                        <Zap size={12} />
                        <span>{isAllocatingId === inc.backendId ? 'Allocating...' : 'Allocate Unit'}</span>
                      </button>
                    )
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
