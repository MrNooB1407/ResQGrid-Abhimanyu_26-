import React from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Ambulance,
  Building2,
  Clock,
  Shield,
  X,
  Zap,
} from 'lucide-react';

export default function ActionFeedbackModal({
  isOpen,
  onClose,
  data,
}) {
  if (!isOpen || !data) return null;

  const {
    type = 'ALLOCATION', // 'ALLOCATION' | 'BREAKDOWN' | 'HOSPITAL_SATURATION' | 'ERROR'
    success = true,
    title = 'Operation Result',
    message = '',
    details = {},
  } = data;

  const isSuccess = Boolean(success);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-container" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '540px' }}>
        {/* Header */}
        <div className="modal-header">
          <h3>
            {isSuccess ? (
              <CheckCircle2 size={18} color="#10b981" />
            ) : (
              <AlertTriangle size={18} color="#ef4444" />
            )}
            <span>{title}</span>
          </h3>
          <button type="button" className="modal-close-btn" onClick={onClose} title="Close">
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body">
          {/* Main Status Banner */}
          <div
            style={{
              background: isSuccess ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
              border: `1px solid ${isSuccess ? '#10b981' : '#ef4444'}`,
              borderRadius: '8px',
              padding: '0.9rem 1.1rem',
              color: isSuccess ? '#6ee7b7' : '#fca5a5',
              fontSize: '0.82rem',
              fontWeight: 500,
              lineHeight: 1.45,
            }}
          >
            {message}
          </div>

          {/* Allocation Specific Details */}
          {type === 'ALLOCATION' && isSuccess && details && (
            <div
              style={{
                background: '#070b16',
                border: '1px solid #1e293b',
                borderRadius: '8px',
                padding: '1rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.65rem',
              }}
            >
              {/* Assigned Ambulance */}
              {details.ambulance && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.78rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                    <Ambulance size={14} color="#10b981" /> Dispatched Vehicle:
                  </span>
                  <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#ffffff' }}>
                    {details.ambulance.ambulance_number} ({details.ambulance.capability})
                  </span>
                </div>
              )}

              {/* Receiving Hospital */}
              {details.hospital && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.78rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                    <Building2 size={14} color="#3b82f6" /> Receiving Hospital:
                  </span>
                  <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#e2e8f0' }}>
                    {details.hospital.name?.replace(/^\[SIMULATED\]\s*/i, '')}
                  </span>
                </div>
              )}

              {/* Estimated ETA */}
              {details.estimated_arrival_minutes !== undefined && details.estimated_arrival_minutes !== null && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.78rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                    <Clock size={14} color="#fbbf24" /> Estimated Route ETA:
                  </span>
                  <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#fbbf24' }}>
                    {details.estimated_arrival_minutes} min
                  </span>
                </div>
              )}

              {/* Algorithmic Decision Reason */}
              {details.decision_reason && (
                <div
                  style={{
                    marginTop: '0.4rem',
                    paddingTop: '0.6rem',
                    borderTop: '1px solid #1e293b',
                    fontSize: '0.72rem',
                    color: '#94a3b8',
                    lineHeight: 1.4,
                  }}
                >
                  <strong style={{ color: '#cbd5e1' }}>Decision Logic:</strong> {details.decision_reason}
                </div>
              )}
            </div>
          )}

          {/* Breakdown Reallocation Details */}
          {type === 'BREAKDOWN' && details && (
            <div
              style={{
                background: '#070b16',
                border: '1px solid #1e293b',
                borderRadius: '8px',
                padding: '1rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.65rem',
              }}
            >
              {details.broken_ambulance_number && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>Failed Unit Retired:</span>
                  <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#ef4444' }}>
                    {details.broken_ambulance_number} (OUT_OF_SERVICE)
                  </span>
                </div>
              )}

              {details.replacement_ambulance ? (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>Replacement Unit:</span>
                    <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#10b981' }}>
                      {details.replacement_ambulance.ambulance_number} ({details.replacement_ambulance.capability})
                    </span>
                  </div>
                  {details.estimated_arrival_minutes && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>Revised Route ETA:</span>
                      <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#fbbf24' }}>
                        {details.estimated_arrival_minutes} min
                      </span>
                    </div>
                  )}
                </>
              ) : (
                <div style={{ fontSize: '0.75rem', color: '#fca5a5' }}>
                  No available replacement vehicle with required capability could be dispatched. Incident returned to priority queue.
                </div>
              )}

              {details.decision_reason && (
                <div
                  style={{
                    marginTop: '0.4rem',
                    paddingTop: '0.6rem',
                    borderTop: '1px solid #1e293b',
                    fontSize: '0.72rem',
                    color: '#94a3b8',
                  }}
                >
                  <strong style={{ color: '#cbd5e1' }}>Audit Trail:</strong> {details.decision_reason}
                </div>
              )}
            </div>
          )}

          {/* Hospital Saturation Details */}
          {type === 'HOSPITAL_SATURATION' && details && (
            <div
              style={{
                background: '#070b16',
                border: '1px solid #1e293b',
                borderRadius: '8px',
                padding: '1rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.5rem',
                fontSize: '0.78rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#cbd5e1' }}>
                <span>Incoming Transports Diverted:</span>
                <span style={{ fontWeight: 700, color: '#f59e0b' }}>
                  {details.diverted_count ?? (details.reallocations ? details.reallocations.length : 0)} unit(s)
                </span>
              </div>
              {details.decision_reason && (
                <div style={{ color: '#94a3b8', marginTop: '0.3rem' }}>
                  {details.decision_reason}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Acknowledge &amp; Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}

