import React, { useState } from 'react';
import {
  MapPin,
  Ambulance as AmbIcon,
  Building2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Info,
} from 'lucide-react';

export default function EmergencyMap({
  incidents,
  ambulances,
  hospitals,
  onSelectIncident,
  selectedIncidentId,
}) {
  const [zoomLevel, setZoomLevel] = useState(1);
  const [showIncidents, setShowIncidents] = useState(true);
  const [showAmbulances, setShowAmbulances] = useState(true);
  const [showHospitals, setShowHospitals] = useState(true);
  const [activeTooltip, setActiveTooltip] = useState(null);

  const handleZoom = (delta) => {
    setZoomLevel((prev) => Math.min(Math.max(prev + delta, 0.8), 1.6));
  };

  const handleReset = () => {
    setZoomLevel(1);
  };

  return (
    <div className="panel-container">
      {/* Panel Header */}
      <div className="panel-header">
        <div className="panel-title-group">
          <MapPin size={17} color="#3b82f6" />
          <h3>Hyderabad Tactical Sector Grid</h3>
          <span className="panel-badge">Live Simulation View</span>
        </div>
        <div className="panel-actions">
          <button
            className={`map-ctrl-btn ${showIncidents ? 'active' : ''}`}
            onClick={() => setShowIncidents(!showIncidents)}
            title="Toggle Emergency Markers"
            type="button"
            style={{ width: 'auto', padding: '0 0.55rem', fontSize: '0.7rem' }}
          >
            Incidents ({incidents.length})
          </button>
          <button
            className={`map-ctrl-btn ${showAmbulances ? 'active' : ''}`}
            onClick={() => setShowAmbulances(!showAmbulances)}
            title="Toggle Ambulance Fleet"
            type="button"
            style={{ width: 'auto', padding: '0 0.55rem', fontSize: '0.7rem' }}
          >
            Fleet ({ambulances.length})
          </button>
          <button
            className={`map-ctrl-btn ${showHospitals ? 'active' : ''}`}
            onClick={() => setShowHospitals(!showHospitals)}
            title="Toggle Hospitals"
            type="button"
            style={{ width: 'auto', padding: '0 0.55rem', fontSize: '0.7rem' }}
          >
            Hospitals ({hospitals.length})
          </button>
        </div>
      </div>

      {/* Map Canvas */}
      <div className="map-canvas-wrapper">
        {/* Simulation Notice Watermark */}
        <div className="map-watermark">
          <Info size={12} />
          <span>SIMULATED HYDERABAD SECTOR GRID — NOT LIVE GPS TRACKING</span>
        </div>

        {/* Zoom & View Controls */}
        <div className="map-controls-overlay">
          <button
            className="map-ctrl-btn"
            onClick={() => handleZoom(0.2)}
            title="Zoom In"
            type="button"
          >
            <ZoomIn size={14} />
          </button>
          <button
            className="map-ctrl-btn"
            onClick={() => handleZoom(-0.2)}
            title="Zoom Out"
            type="button"
          >
            <ZoomOut size={14} />
          </button>
          <button
            className="map-ctrl-btn"
            onClick={handleReset}
            title="Reset View"
            type="button"
          >
            <RotateCcw size={14} />
          </button>
        </div>

        {/* Scalable Container */}
        <div
          style={{
            width: '100%',
            height: '100%',
            position: 'relative',
            transform: `scale(${zoomLevel})`,
            transformOrigin: 'center center',
            transition: 'transform 0.25s cubic-bezier(0.2, 0.8, 0.2, 1)',
          }}
        >
          {/* Tactical Vector Blueprint of Hyderabad */}
          <svg
            className="map-svg-background"
            viewBox="0 0 1000 650"
            preserveAspectRatio="xMidYMid meet"
          >
            <defs>
              {/* Grid pattern */}
              <pattern id="tacGrid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#162238" strokeWidth="0.75" />
              </pattern>
              {/* Radar rings */}
              <radialGradient id="centerGlow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#1e3a8a" stopOpacity="0.12" />
                <stop offset="100%" stopColor="#080c16" stopOpacity="0" />
              </radialGradient>
            </defs>

            {/* Background Base */}
            <rect width="1000" height="650" fill="#080d19" />
            <rect width="1000" height="650" fill="url(#tacGrid)" />
            <circle cx="500" cy="325" r="300" fill="url(#centerGlow)" />

            {/* Radar concentric rings */}
            <circle cx="500" cy="325" r="140" fill="none" stroke="#1e293b" strokeDasharray="4 6" strokeWidth="1" />
            <circle cx="500" cy="325" r="260" fill="none" stroke="#1e293b" strokeDasharray="4 6" strokeWidth="1" />

            {/* Hussain Sagar Lake representation */}
            <path
              d="M 520,240 C 550,225 575,250 565,280 C 555,305 530,310 515,290 C 500,270 500,250 520,240 Z"
              fill="#0e2a47"
              stroke="#1d4ed8"
              strokeWidth="1.5"
            />
            <text x="535" y="270" fill="#3b82f6" fontSize="10" fontWeight="600" textAnchor="middle" opacity="0.8">
              Hussain Sagar
            </text>

            {/* Mir Alam Tank representation (South-West) */}
            <path
              d="M 410,480 C 430,470 445,490 435,510 C 420,525 395,515 410,480 Z"
              fill="#0e2a47"
              stroke="#1d4ed8"
              strokeWidth="1"
            />

            {/* Major Arterial Roads & Expressways */}
            {/* Outer Ring Road (ORR) Loop */}
            <path
              d="M 120,600 C 100,320 180,100 480,80 C 760,70 880,240 880,500"
              fill="none"
              stroke="#1e293b"
              strokeWidth="3.5"
            />
            <path
              d="M 120,600 C 100,320 180,100 480,80 C 760,70 880,240 880,500"
              fill="none"
              stroke="#334155"
              strokeDasharray="6 4"
              strokeWidth="1.5"
            />

            {/* Inner Ring Road */}
            <ellipse cx="500" cy="330" rx="270" ry="190" fill="none" stroke="#1e293b" strokeWidth="2" />

            {/* Arterials */}
            {/* Gachibowli to Jubilee Hills (Congested corridor C-4) */}
            <line x1="210" y1="340" x2="380" y2="280" stroke="#f59e0b" strokeWidth="2.5" strokeDasharray="5 3" />
            <text x="285" y="300" fill="#f59e0b" fontSize="8" fontWeight="700">
              1.85x CONGESTION
            </text>

            {/* Jubilee Hills to Begumpet */}
            <line x1="380" y1="280" x2="570" y2="210" stroke="#334155" strokeWidth="2" />

            {/* Begumpet to Secunderabad */}
            <line x1="570" y1="210" x2="680" y2="165" stroke="#334155" strokeWidth="2" />

            {/* PVNR Expressway to Mehdipatnam & Old City */}
            <line x1="380" y1="280" x2="440" y2="390" stroke="#334155" strokeWidth="2" />
            <line x1="440" y1="390" x2="560" y2="430" stroke="#334155" strokeWidth="2" />
            <line x1="560" y1="430" x2="740" y2="420" stroke="#334155" strokeWidth="2" />

            {/* Hitec City corridor */}
            <line x1="210" y1="340" x2="280" y2="260" stroke="#334155" strokeWidth="2" />
            <line x1="280" y1="260" x2="380" y2="280" stroke="#334155" strokeWidth="2" />

            {/* Sector Boundary Labels matching Seeded Locations */}
            <g fill="#475569" fontSize="11" fontWeight="700" letterSpacing="1">
              <text x="210" y="375" textAnchor="middle">GACHIBOWLI</text>
              <text x="270" y="240" textAnchor="middle">HITEC CITY</text>
              <text x="380" y="315" textAnchor="middle">JUBILEE HILLS</text>
              <text x="450" y="340" textAnchor="middle">BANJARA HILLS</text>
              <text x="560" y="195" textAnchor="middle">BEGUMPET</text>
              <text x="700" y="145" textAnchor="middle">SECUNDERABAD</text>
              <text x="560" y="445" textAnchor="middle">AFZAL GUNJ / OLD CITY</text>
              <text x="740" y="435" textAnchor="middle">MALAKPET</text>
              <text x="440" y="410" textAnchor="middle">MEHDIPATNAM</text>
            </g>
          </svg>

          {/* 5 SEEDED HOSPITAL PINS */}
          {showHospitals &&
            hospitals.map((hosp) => (
              <div
                key={hosp.id}
                className="map-marker-pin"
                style={{ left: `${hosp.coordinates.x}%`, top: `${hosp.coordinates.y}%` }}
                onMouseEnter={() =>
                  setActiveTooltip({
                    title: hosp.name,
                    sub: `ER Beds: ${hosp.availableBeds}/${hosp.totalBeds} • ICU: ${hosp.availableIcu}/${hosp.totalIcu}`,
                    type: 'Hospital',
                  })
                }
                onMouseLeave={() => setActiveTooltip(null)}
              >
                <div className="marker-hosp-pin" title={hosp.name}>
                  <Building2 size={13} />
                </div>
              </div>
            ))}

          {/* 8 SEEDED AMBULANCE PINS */}
          {showAmbulances &&
            ambulances.map((amb) => {
              const isEnRoute = amb.status === 'EN_ROUTE' || amb.status === 'TRANSPORTING';
              return (
                <div
                  key={amb.id}
                  className="map-marker-pin"
                  style={{ left: `${amb.coordinates.x}%`, top: `${amb.coordinates.y}%` }}
                  onMouseEnter={() =>
                    setActiveTooltip({
                      title: `${amb.id} (${amb.capability}) — ${amb.status}`,
                      sub: amb.assignedIncident
                        ? `Assigned: ${amb.assignedIncident} | ETA: ${amb.etaMinutes} min`
                        : `Ready at ${amb.location}`,
                      type: 'Ambulance',
                    })
                  }
                  onMouseLeave={() => setActiveTooltip(null)}
                >
                  <div className={`marker-amb-pin ${isEnRoute ? 'en-route' : ''}`} title={amb.id}>
                    <AmbIcon size={12} />
                  </div>
                </div>
              );
            })}

          {/* EMERGENCY INCIDENT MARKERS */}
          {showIncidents &&
            incidents.map((inc) => {
              const isSelected = selectedIncidentId === inc.id;
              const sevClass = inc.severity.toLowerCase();
              return (
                <div
                  key={inc.id}
                  className="map-marker-pin"
                  style={{
                    left: `${inc.coordinates.x}%`,
                    top: `${inc.coordinates.y}%`,
                    transform: isSelected ? 'translate(-50%, -50%) scale(1.4)' : undefined,
                  }}
                  onClick={() => onSelectIncident(inc.id)}
                  onMouseEnter={() =>
                    setActiveTooltip({
                      title: `[${inc.severity}] ${inc.title}`,
                      sub: `${inc.location} • Status: ${inc.status} • ETA: ${inc.etaMinutes || 'N/A'}m`,
                      type: 'Incident',
                    })
                  }
                  onMouseLeave={() => setActiveTooltip(null)}
                >
                  <div className={`marker-incident-pulse ${sevClass}`}>
                    <span
                      style={{
                        width: '7px',
                        height: '7px',
                        borderRadius: '50%',
                        backgroundColor: '#ffffff',
                      }}
                    />
                  </div>
                </div>
              );
            })}

          {/* Active Tooltip Popover */}
          {activeTooltip && (
            <div
              className="map-tooltip"
              style={{
                top: '12px',
                right: '60px',
                bottom: 'auto',
                left: 'auto',
                transform: 'none',
              }}
            >
              <div className="map-tooltip-title">{activeTooltip.title}</div>
              <div className="map-tooltip-meta">{activeTooltip.sub}</div>
            </div>
          )}
        </div>
      </div>

      {/* Map Legend Bar */}
      <div className="map-legend-bar">
        <div className="legend-items-group">
          <div className="legend-entry">
            <span className="legend-dot red" />
            <span>Critical Emergency</span>
          </div>
          <div className="legend-entry">
            <span className="legend-dot orange" />
            <span>High Severity</span>
          </div>
          <div className="legend-entry">
            <span className="legend-dot amber" />
            <span>Medium</span>
          </div>
          <div className="legend-entry">
            <span className="legend-dot cyan" />
            <span>Low</span>
          </div>
        </div>

        <div className="legend-items-group">
          <div className="legend-entry">
            <span className="legend-dot green" />
            <span>Ambulance Available</span>
          </div>
          <div className="legend-entry">
            <span className="legend-dot amber" />
            <span>Ambulance En Route</span>
          </div>
          <div className="legend-entry">
            <span className="legend-dot blue" />
            <span>Seeded Trauma Center (5)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
