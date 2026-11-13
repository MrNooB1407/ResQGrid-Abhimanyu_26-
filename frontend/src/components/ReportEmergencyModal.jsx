import React, { useState } from 'react';
import {
  AlertCircle,
  Flame,
  X,
  MapPin,
  Users,
  Activity,
  ShieldAlert,
  Zap,
  CheckCircle2,
} from 'lucide-react';

const HYDERABAD_PRESETS = [
  { name: 'Gachibowli ORR', lat: 17.4422, lon: 78.3512 },
  { name: 'Banjara Hills Rd 10', lat: 17.4172, lon: 78.4415 },
  { name: 'Begumpet Nala', lat: 17.4468, lon: 78.4639 },
  { name: 'Secunderabad Junction', lat: 17.4399, lon: 78.4983 },
  { name: 'Charminar / Old City', lat: 17.3616, lon: 78.4747 },
];

const INCIDENT_TYPES = [
  { id: 'ROAD_ACCIDENT', label: 'Road Traffic Accident (MVA)' },
  { id: 'CARDIAC_EMERGENCY', label: 'Cardiac Emergency / Acute STEMI' },
  { id: 'URBAN_FLOODING', label: 'Urban Flooding / Structural Inundation' },
  { id: 'FIRE_HAZARD', label: 'Commercial / Residential Fire' },
  { id: 'INDUSTRIAL_TRAUMA', label: 'Industrial / Machinery Trauma' },
  { id: 'RESPIRATORY_DISTRESS', label: 'Acute Respiratory Distress' },
  { id: 'MASS_CASUALTY', label: 'Mass Casualty Incident (MCI)' },
  { id: 'HEAT_EXHAUSTION', label: 'Severe Heat Exhaustion / Collapse' },
];

const SYMPTOM_OPTIONS = [
  'unconscious',
  'cardiac arrest',
  'chest pain',
  'heavy bleeding',
  'asphyxiation',
  'polytrauma',
  'severe burns',
];

const HAZARD_OPTIONS = [
  'high speed traffic',
  'active fire',
  'stormwater flood',
  'structural collapse',
  'chemical hazard',
];

export default function ReportEmergencyModal({
  isOpen,
  onClose,
  onSubmitIncident,
  onAllocateIncident,
}) {
  const [title, setTitle] = useState('');
  const [incidentType, setIncidentType] = useState('ROAD_ACCIDENT');
  const [description, setDescription] = useState('');
  const [latitude, setLatitude] = useState(17.4422);
  const [longitude, setLongitude] = useState(78.3512);
  const [injuredPeople, setInjuredPeople] = useState(2);
  const [affectedPeople, setAffectedPeople] = useState(2);
  const [selectedSymptoms, setSelectedSymptoms] = useState(['polytrauma']);
  const [selectedHazards, setSelectedHazards] = useState(['high speed traffic']);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [createdResult, setCreatedResult] = useState(null);
  const [isAllocating, setIsAllocating] = useState(false);

  if (!isOpen) return null;

  const toggleSymptom = (s) => {
    setSelectedSymptoms((prev) =>
      prev.includes(s) ? prev.filter((item) => item !== s) : [...prev, s]
    );
  };

  const toggleHazard = (h) => {
    setSelectedHazards((prev) =>
      prev.includes(h) ? prev.filter((item) => item !== h) : [...prev, h]
    );
  };

  const handleApplyPreset = (p) => {
    setLatitude(p.lat);
    setLongitude(p.lon);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!title.trim()) {
      setErrorMessage('Please enter an incident title.');
      return;
    }

    const latNum = parseFloat(latitude);
    const lonNum = parseFloat(longitude);
    if (!Number.isFinite(latNum) || latNum < -90 || latNum > 90) {
      setErrorMessage('Latitude must be a valid number between -90 and 90.');
      return;
    }
    if (!Number.isFinite(lonNum) || lonNum < -180 || lonNum > 180) {
      setErrorMessage('Longitude must be a valid number between -180 and 180.');
      return;
    }

    const payload = {
      title: title.trim(),
      incident_type: incidentType,
      description: description.trim(),
      latitude: latNum,
      longitude: lonNum,
      injured_people: Math.max(0, parseInt(injuredPeople, 10) || 0),
      affected_people: Math.max(0, parseInt(affectedPeople, 10) || 0),
      critical_symptoms: selectedSymptoms,
      environmental_danger: selectedHazards,
    };

    try {
      setIsSubmitting(true);
      const res = await onSubmitIncident(payload);
      setCreatedResult(res);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to submit emergency report.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDirectAllocate = async () => {
    if (!createdResult?.data?.id) return;
    try {
      setIsAllocating(true);
      await onAllocateIncident(createdResult.data.id);
      onClose();
    } catch (err) {
      setErrorMessage(err.message || 'Allocation failed.');
    } finally {
      setIsAllocating(false);
    }
  };

  const handleResetAndClose = () => {
    setTitle('');
    setDescription('');
    setCreatedResult(null);
    setErrorMessage(null);
    onClose();
  };

  return (
    <div className="modal-backdrop" onClick={handleResetAndClose}>
      <div className="modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <h3>
            <Flame size={18} color="#ef4444" />
            <span>Report Emergency Incident</span>
          </h3>
          <button
            type="button"
            className="modal-close-btn"
            onClick={handleResetAndClose}
            title="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body">
          {errorMessage && (
            <div
              style={{
                background: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid #ef4444',
                color: '#fca5a5',
                padding: '0.65rem 0.85rem',
                borderRadius: '6px',
                fontSize: '0.78rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <AlertCircle size={16} />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Success Result View */}
          {createdResult ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div
                style={{
                  background: 'rgba(16, 185, 129, 0.12)',
                  border: '1px solid #10b981',
                  borderRadius: '8px',
                  padding: '1rem',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.75rem',
                }}
              >
                <CheckCircle2 size={22} color="#10b981" style={{ flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <div style={{ color: '#ffffff', fontWeight: 700, fontSize: '0.95rem' }}>
                    Incident #{createdResult.data.id} Created &amp; Triaged
                  </div>
                  <div style={{ color: '#94a3b8', fontSize: '0.75rem', marginTop: '0.2rem' }}>
                    Stored in SQLite and processed by algorithmic severity triage engine.
                  </div>
                </div>
              </div>

              {/* Triage Score Details */}
              <div
                style={{
                  background: '#070b16',
                  border: '1px solid #1e293b',
                  borderRadius: '8px',
                  padding: '1rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.5rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>Algorithmic Severity Score:</span>
                  <span
                    style={{
                      fontSize: '1.1rem',
                      fontWeight: 800,
                      color:
                        createdResult.data.severity_level === 'CRITICAL'
                          ? '#ef4444'
                          : createdResult.data.severity_level === 'HIGH'
                          ? '#f97316'
                          : '#f59e0b',
                    }}
                  >
                    {createdResult.data.severity_score} / 100
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>Triage Priority Level:</span>
                  <span
                    className={`severity-pill ${createdResult.data.severity_level.toLowerCase()}`}
                    style={{ fontSize: '0.75rem' }}
                  >
                    {createdResult.data.severity_level}
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>Incident Type:</span>
                  <span style={{ fontSize: '0.78rem', color: '#f8fafc', fontWeight: 600 }}>
                    {createdResult.data.incident_type}
                  </span>
                </div>
              </div>

              {/* Direct Next Action: Allocate Resources */}
              <div
                style={{
                  background: 'rgba(59, 130, 246, 0.08)',
                  border: '1px solid rgba(59, 130, 246, 0.25)',
                  borderRadius: '8px',
                  padding: '0.85rem 1rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '0.75rem',
                }}
              >
                <div>
                  <div style={{ color: '#93c5fd', fontSize: '0.82rem', fontWeight: 600 }}>
                    Immediate Response Recommendation
                  </div>
                  <div style={{ color: '#64748b', fontSize: '0.72rem' }}>
                    Match nearest capable ambulance and reserve receiving ER trauma beds.
                  </div>
                </div>
                <button
                  type="button"
                  className="btn-action-allocate"
                  onClick={handleDirectAllocate}
                  disabled={isAllocating}
                  style={{ padding: '0.5rem 0.9rem', fontSize: '0.8rem' }}
                >
                  <Zap size={14} />
                  <span>{isAllocating ? 'Allocating...' : 'Allocate Resources Now'}</span>
                </button>
              </div>
            </div>
          ) : (
            /* Input Form */
            <form id="emergency-report-form" onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
              {/* Title */}
              <div className="form-group">
                <label>Incident Title *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Multi-Vehicle Collision on Gachibowli ORR"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                />
              </div>

              {/* Incident Type & Casualties */}
              <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr', gap: '0.75rem' }}>
                <div className="form-group">
                  <label>Incident Category *</label>
                  <select
                    className="form-select"
                    value={incidentType}
                    onChange={(e) => setIncidentType(e.target.value)}
                  >
                    {INCIDENT_TYPES.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label>Injured Count</label>
                  <input
                    type="number"
                    min="0"
                    className="form-input"
                    value={injuredPeople}
                    onChange={(e) => setInjuredPeople(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label>Total Affected</label>
                  <input
                    type="number"
                    min="0"
                    className="form-input"
                    value={affectedPeople}
                    onChange={(e) => setAffectedPeople(e.target.value)}
                  />
                </div>
              </div>

              {/* Description */}
              <div className="form-group">
                <label>Narrative Description</label>
                <textarea
                  className="form-textarea"
                  placeholder="Describe location landmarks, casualty conditions, trapped victims, or structural hazards..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>

              {/* Coordinates & Presets */}
              <div className="form-group">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                    <MapPin size={13} color="#3b82f6" />
                    <span>Coordinates (WGS84 Latitude / Longitude) *</span>
                  </label>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <input
                    type="number"
                    step="0.0001"
                    className="form-input"
                    placeholder="Latitude (e.g. 17.4422)"
                    value={latitude}
                    onChange={(e) => setLatitude(e.target.value)}
                    required
                  />
                  <input
                    type="number"
                    step="0.0001"
                    className="form-input"
                    placeholder="Longitude (e.g. 78.3512)"
                    value={longitude}
                    onChange={(e) => setLongitude(e.target.value)}
                    required
                  />
                </div>

                {/* Quick Sector Presets */}
                <div className="preset-chips-row">
                  <span style={{ fontSize: '0.68rem', color: '#64748b' }}>Quick Presets:</span>
                  {HYDERABAD_PRESETS.map((p) => (
                    <button
                      key={p.name}
                      type="button"
                      className="preset-chip"
                      onClick={() => handleApplyPreset(p)}
                    >
                      {p.name}
                    </button>
                  ))}
                </div>
              </div>

              {/* Clinical Symptoms */}
              <div className="form-group">
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                  <Activity size={13} color="#ef4444" />
                  <span>Clinical Symptoms (Triage Weight Multipliers)</span>
                </label>
                <div className="tag-pills-row">
                  {SYMPTOM_OPTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      className={`tag-pill-btn ${selectedSymptoms.includes(s) ? 'active' : ''}`}
                      onClick={() => toggleSymptom(s)}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              {/* Environmental Hazards */}
              <div className="form-group">
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                  <ShieldAlert size={13} color="#f59e0b" />
                  <span>Scene Environmental Hazards</span>
                </label>
                <div className="tag-pills-row">
                  {HAZARD_OPTIONS.map((h) => (
                    <button
                      key={h}
                      type="button"
                      className={`tag-pill-btn ${selectedHazards.includes(h) ? 'active' : ''}`}
                      onClick={() => toggleHazard(h)}
                    >
                      {h}
                    </button>
                  ))}
                </div>
              </div>
            </form>
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer">
          {createdResult ? (
            <button
              type="button"
              className="btn-secondary"
              onClick={handleResetAndClose}
            >
              Done &amp; Return to Dashboard
            </button>
          ) : (
            <>
              <button
                type="button"
                className="btn-secondary"
                onClick={handleResetAndClose}
                disabled={isSubmitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                form="emergency-report-form"
                className="btn-primary"
                disabled={isSubmitting}
              >
                <Flame size={14} />
                <span>{isSubmitting ? 'Submitting & Triaging...' : 'Submit Emergency Report'}</span>
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

