import React, { useState } from 'react';
import { Settings, Sliders, Cpu, Check, ArrowLeft } from 'lucide-react';

export default function SettingsView({ onBackToCommand }) {
  const [simulationSpeed, setSimulationSpeed] = useState('1x');
  const [autoReallocation, setAutoReallocation] = useState(true);
  const [trafficHysteresis, setTrafficHysteresis] = useState(5.0);
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="dashboard-content">
      <div className="panel-container" style={{ maxWidth: '850px', margin: '0 auto', width: '100%' }}>
        <div className="panel-header">
          <div className="panel-title-group">
            {onBackToCommand && (
              <button
                onClick={onBackToCommand}
                type="button"
                className="subview-back-btn"
                style={{ margin: 0, padding: '0.35rem 0.65rem' }}
                title="Return to Command Center"
              >
                <ArrowLeft size={14} />
                <span>Back</span>
              </button>
            )}
            <Settings size={18} color="#60a5fa" />
            <h3>Command Center System Configuration</h3>
          </div>
          <span className="panel-badge">Dispatcher Level 3</span>
        </div>

        <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Section 1: Algorithmic Reallocation Parameters */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <h4 style={{ fontSize: '0.88rem', color: '#60a5fa', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Sliders size={16} /> Dynamic Allocation &amp; Hysteresis
            </h4>
            <div style={{ background: '#090e1a', padding: '1rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <div>
                  <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#f8fafc' }}>
                    Automated Dynamic Reallocation
                  </div>
                  <div style={{ fontSize: '0.72rem', color: '#64748b' }}>
                    Automatically trigger reallocation on ambulance breakdown or hospital saturation
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={autoReallocation}
                  onChange={(e) => setAutoReallocation(e.target.checked)}
                  style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '0.75rem', borderTop: '1px solid #1e293b' }}>
                <div>
                  <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#f8fafc' }}>
                    Traffic Reallocation Threshold ({trafficHysteresis} min)
                  </div>
                  <div style={{ fontSize: '0.72rem', color: '#64748b' }}>
                    Minimum improvement in minutes required to switch assigned units
                  </div>
                </div>
                <input
                  type="range"
                  min="2"
                  max="10"
                  step="0.5"
                  value={trafficHysteresis}
                  onChange={(e) => setTrafficHysteresis(parseFloat(e.target.value))}
                  style={{ width: '140px', cursor: 'pointer' }}
                />
              </div>
            </div>
          </div>

          {/* Section 2: Simulation Mode Control */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <h4 style={{ fontSize: '0.88rem', color: '#f59e0b', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Cpu size={16} /> Telemetry Simulation Speed
            </h4>
            <div style={{ background: '#090e1a', padding: '1rem', borderRadius: '6px', border: '1px solid #1e293b', display: 'flex', gap: '0.75rem' }}>
              {['0.5x', '1x (Real-time)', '2x', '5x'].map((spd) => (
                <button
                  key={spd}
                  onClick={() => setSimulationSpeed(spd)}
                  type="button"
                  style={{
                    flex: 1,
                    padding: '0.5rem',
                    borderRadius: '6px',
                    border: '1px solid',
                    borderColor: simulationSpeed === spd ? '#f59e0b' : '#334155',
                    background: simulationSpeed === spd ? 'rgba(245, 158, 11, 0.15)' : 'transparent',
                    color: simulationSpeed === spd ? '#fbbf24' : '#94a3b8',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  {spd}
                </button>
              ))}
            </div>
          </div>

          {/* Save Button */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button
              onClick={handleSave}
              type="button"
              style={{
                background: '#2563eb',
                color: '#ffffff',
                border: 'none',
                padding: '0.5rem 1.25rem',
                borderRadius: '6px',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
              }}
            >
              {saved ? <Check size={16} /> : null}
              {saved ? 'Preferences Saved' : 'Save Parameters'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
