import React from 'react';
import { Ambulance, Gauge, Fuel } from 'lucide-react';

export default function FleetOverview({ ambulances }) {
  const getStatusBadge = (status) => {
    switch (status) {
      case 'AVAILABLE':
        return (
          <span className="status-badge available">
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981' }} />
            AVAILABLE
          </span>
        );
      case 'EN_ROUTE':
        return (
          <span className="status-badge en_route">
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#f59e0b' }} />
            EN ROUTE
          </span>
        );
      case 'ON_SCENE':
        return (
          <span className="status-badge on_scene">
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#3b82f6' }} />
            ON SCENE
          </span>
        );
      case 'TRANSPORTING':
        return (
          <span className="status-badge transporting">
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#8b5cf6' }} />
            TRANSPORTING
          </span>
        );
      default:
        return <span className="status-badge">{status}</span>;
    }
  };

  const getTypePill = (type) => {
    if (type === 'ALS') return <span className="type-pill">ALS</span>;
    if (type === 'BLS') return <span className="type-pill bls">BLS</span>;
    return <span className="type-pill pt">PT</span>;
  };

  return (
    <div className="panel-container">
      <div className="panel-header">
        <div className="panel-title-group">
          <Ambulance size={17} color="#10b981" />
          <h3>Ambulance Fleet Status</h3>
          <span className="panel-badge">{`${ambulances.length} Seeded Units`}</span>
        </div>
      </div>

      <div className="fleet-table-wrapper">
        <table className="fleet-table">
          <thead>
            <tr>
              <th>Vehicle ID</th>
              <th>Type</th>
              <th>Status</th>
              <th>Station / Base</th>
              <th>Assignment &amp; Destination</th>
              <th>Speed / Fuel</th>
            </tr>
          </thead>
          <tbody>
            {ambulances.map((amb) => (
              <tr key={amb.id}>
                {/* ID & Callsign */}
                <td>
                  <div className="amb-id-badge">
                    <span>{amb.id}</span>
                    <span style={{ fontSize: '0.65rem', color: '#64748b', fontWeight: 500 }}>
                      ({amb.callsign})
                    </span>
                  </div>
                </td>

                {/* Capability Type */}
                <td>{getTypePill(amb.capability)}</td>

                {/* Status */}
                <td>{getStatusBadge(amb.status)}</td>

                {/* Location */}
                <td>
                  <span style={{ color: '#cbd5e1' }}>{amb.location}</span>
                </td>

                {/* Assignment & Destination */}
                <td>
                  {amb.assignedIncident ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
                      <span style={{ color: '#fbbf24', fontWeight: 600 }}>
                        {amb.assignedIncident} &rarr; {amb.targetDestination}
                      </span>
                      {amb.etaMinutes !== null && amb.etaMinutes > 0 && (
                        <span style={{ fontSize: '0.68rem', color: '#94a3b8' }}>
                          ETA: {amb.etaMinutes} mins
                        </span>
                      )}
                    </div>
                  ) : (
                    <span style={{ color: '#64748b', fontStyle: 'italic' }}>
                      Ready on Standby
                    </span>
                  )}
                </td>

                {/* Telemetry */}
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', fontSize: '0.72rem' }}>
                    <span title="GPS Speed" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
                      <Gauge size={12} color="#64748b" />
                      {amb.speedKmH} km/h
                    </span>
                    <span title="Fuel Level" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
                      <Fuel size={12} color={amb.fuelPct < 40 ? '#ef4444' : '#10b981'} />
                      {amb.fuelPct}%
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
