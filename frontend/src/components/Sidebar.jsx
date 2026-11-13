import React from 'react';
import {
  ShieldAlert,
  LayoutDashboard,
  AlertTriangle,
  Ambulance,
  Building2,
  BarChart3,
  Settings,
} from 'lucide-react';

export default function Sidebar({ currentView, onViewChange, incidentCount = 12, availableAmbulanceCount = 5, totalAmbulanceCount = 8, hospitalCount = 5 }) {
  const navItems = [
    { id: 'command-center', label: 'Command Center', icon: LayoutDashboard },
    { id: 'incidents', label: 'Incidents', icon: AlertTriangle, count: incidentCount },
    { id: 'fleet', label: 'Ambulance Fleet', icon: Ambulance, count: `${availableAmbulanceCount}/${totalAmbulanceCount}` },
    { id: 'hospitals', label: 'Hospitals', icon: Building2, count: hospitalCount },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <div className="sidebar-header">
        <div className="brand-wrapper">
          <div className="brand-icon-shield">
            <ShieldAlert size={22} strokeWidth={2.2} />
          </div>
          <div className="brand-text">
            <h1>ResQGrid</h1>
            <span className="brand-version">Command Core v1.0</span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentView === item.id;
          return (
            <button
              key={item.id}
              className={`nav-item ${isActive ? 'active' : ''}`}
              onClick={() => onViewChange(item.id)}
              type="button"
            >
              <Icon size={18} strokeWidth={isActive ? 2.2 : 1.8} />
              <span style={{ flex: 1 }}>{item.label}</span>
              {item.count !== undefined && item.count !== null && (
                <span
                  style={{
                    fontSize: '0.68rem',
                    padding: '0.1rem 0.4rem',
                    borderRadius: '4px',
                    backgroundColor: isActive ? 'rgba(59, 130, 246, 0.25)' : 'rgba(255, 255, 255, 0.08)',
                    color: isActive ? '#93c5fd' : '#94a3b8',
                    fontWeight: 600,
                  }}
                >
                  {item.count}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* System Status in Sidebar Footer */}
      <div className="sidebar-footer">
        <div className="system-status-box">
          <div className="status-dot-pulse" />
          <div className="status-box-text">
            <div className="status-label">Sector Node Active</div>
            <div className="status-sub">Hyderabad Central Grid (8 AMB / 5 HOSP)</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
