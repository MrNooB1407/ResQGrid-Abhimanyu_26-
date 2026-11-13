import React from 'react';
import { Building2, Bed, HeartPulse, Wind, AlertTriangle } from 'lucide-react';

export default function HospitalOverview({
  hospitals,
  onSimulateHospitalSaturation,
  isHospitalLoadingId,
}) {
  const getCapacityClass = (occupancyPct) => {
    if (occupancyPct > 90) return 'critical';
    if (occupancyPct > 80) return 'moderate';
    return 'low';
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'NORMAL':
        return (
          <span style={{ fontSize: '0.65rem', color: '#10b981', fontWeight: 600 }}>
            ● NORMAL CAPACITY
          </span>
        );
      case 'ELEVATED':
        return (
          <span style={{ fontSize: '0.65rem', color: '#f59e0b', fontWeight: 600 }}>
            ● ELEVATED SURGE
          </span>
        );
      case 'CRITICAL_CAPACITY':
        return (
          <span style={{ fontSize: '0.65rem', color: '#ef4444', fontWeight: 700 }}>
            ▲ CRITICAL SATURATION
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="panel-container">
      <div className="panel-header">
        <div className="panel-title-group">
          <Building2 size={17} color="#3b82f6" />
          <h3>Hospital Network Capacity</h3>
          <span className="panel-badge">{`${hospitals.length} Seeded Trauma Centers`}</span>
        </div>
      </div>

      <div className="hospitals-list">
        {hospitals.map((hosp) => {
          const capClass = getCapacityClass(hosp.occupancyPct);

          return (
            <div key={hosp.id} className="hospital-card-item">
              {/* Top Row: Name & Status */}
              <div className="hosp-top-row">
                <div>
                  <div className="hosp-name-title">
                    <span>{hosp.name}</span>
                  </div>
                  <div className="hosp-type-sub">{hosp.type} • {hosp.address}</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  {getStatusBadge(hosp.status)}
                  {onSimulateHospitalSaturation && (
                    <button
                      type="button"
                      className="btn-warning-outline"
                      onClick={() => onSimulateHospitalSaturation(hosp.backendId)}
                      disabled={isHospitalLoadingId === hosp.backendId}
                      title="Simulate ICU capacity exhaustion and divert incoming units"
                    >
                      <AlertTriangle size={11} />
                      <span>{isHospitalLoadingId === hosp.backendId ? 'Simulating...' : 'Saturate'}</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Metrics Grid */}
              <div className="hosp-metrics-grid">
                {/* ER Beds */}
                <div className="hosp-stat-cell">
                  <span className="stat-cell-label" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
                    <Bed size={11} /> ER Beds
                  </span>
                  <span className="stat-cell-value">
                    {hosp.availableBeds}{' '}
                    <span style={{ fontSize: '0.68rem', color: '#64748b' }}>
                      / {hosp.totalBeds} avail
                    </span>
                  </span>
                </div>

                {/* ICU Beds */}
                <div className="hosp-stat-cell">
                  <span className="stat-cell-label" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
                    <HeartPulse size={11} /> ICU Beds
                  </span>
                  <span className={`stat-cell-value ${hosp.availableIcu <= 3 ? 'critical' : ''}`}>
                    {hosp.availableIcu}{' '}
                    <span style={{ fontSize: '0.68rem', color: '#64748b' }}>
                      / {hosp.totalIcu} avail
                    </span>
                  </span>
                </div>

                {/* Ventilators */}
                <div className="hosp-stat-cell">
                  <span className="stat-cell-label" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
                    <Wind size={11} /> Ventilators
                  </span>
                  <span className="stat-cell-value">
                    {hosp.availableVents}{' '}
                    <span style={{ fontSize: '0.68rem', color: '#64748b' }}>
                      online
                    </span>
                  </span>
                </div>
              </div>

              {/* Capacity Progress Bar */}
              <div className="capacity-meter-wrapper">
                <div className="meter-labels">
                  <span>ER Ward Load</span>
                  <span>{hosp.occupancyPct}% Occupied</span>
                </div>
                <div className="meter-track">
                  <div
                    className={`meter-fill ${capClass}`}
                    style={{ width: `${hosp.occupancyPct}%` }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
