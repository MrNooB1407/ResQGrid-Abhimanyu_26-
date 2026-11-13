import React from 'react';
import { Bed, HeartPulse, Wind, ArrowLeft } from 'lucide-react';
import HospitalOverview from '../components/HospitalOverview';

export default function HospitalsView({ hospitals, onBackToCommand }) {
  const totalBeds = hospitals.reduce((acc, h) => acc + h.totalBeds, 0);
  const availBeds = hospitals.reduce((acc, h) => acc + h.availableBeds, 0);
  const totalIcu = hospitals.reduce((acc, h) => acc + h.totalIcu, 0);
  const availIcu = hospitals.reduce((acc, h) => acc + h.availableIcu, 0);
  const totalVents = hospitals.reduce((acc, h) => acc + h.totalVents, 0);
  const availVents = hospitals.reduce((acc, h) => acc + h.availableVents, 0);

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
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#ffffff' }}>Regional Hospital Trauma Network</h2>
            <p style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
              Capacity monitoring across all 5 seeded emergency and tertiary care medical centers.
            </p>
          </div>
        </div>
      </div>

      {/* Network Aggregate KPIs */}
      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
        <div className="kpi-card info">
          <div className="kpi-header">
            <span className="kpi-title">Network ER Beds</span>
            <Bed size={16} />
          </div>
          <div className="kpi-value">{`${availBeds} / ${totalBeds}`}</div>
          <span className="kpi-subtext">
            {Math.round(((totalBeds - availBeds) / totalBeds) * 100)}% Current Occupancy
          </span>
        </div>
        <div className="kpi-card critical">
          <div className="kpi-header">
            <span className="kpi-title">ICU Trauma Capacity</span>
            <HeartPulse size={16} />
          </div>
          <div className="kpi-value">{`${availIcu} / ${totalIcu}`}</div>
          <span className="kpi-subtext">
            {Math.round(((totalIcu - availIcu) / totalIcu) * 100)}% High Acuity Utilization
          </span>
        </div>
        <div className="kpi-card timer">
          <div className="kpi-header">
            <span className="kpi-title">Ventilators Online</span>
            <Wind size={16} />
          </div>
          <div className="kpi-value">{`${availVents} / ${totalVents}`}</div>
          <span className="kpi-subtext">Critical respiratory units ready</span>
        </div>
      </div>

      <HospitalOverview hospitals={hospitals} />
    </div>
  );
}
