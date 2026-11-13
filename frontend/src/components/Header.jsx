import React, { useState, useEffect } from 'react';
import { RefreshCw, Bell, Clock } from 'lucide-react';
import NotificationDrawer from './NotificationDrawer';

export default function Header({
  title = 'Emergency Command Center',
  subtitle = 'Real-time emergency coordination across Hyderabad',
  onRefresh,
  isRefreshing,
  notifications,
  onMarkAllRead,
}) {
  const [currentTime, setCurrentTime] = useState(new Date());
  const [showNotifications, setShowNotifications] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const formatClock = (date) => {
    const dateStr = date.toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
    const timeStr = date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
    return `${dateStr} • ${timeStr} IST`;
  };

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <header className="top-header">
      {/* Title & Subtitle */}
      <div className="header-left">
        <div className="header-title-row">
          <h2>{title}</h2>
          <div className="sim-pill" title="Running on verified algorithmic simulation data">
            <span className="sim-dot" />
            <span>SIMULATION MODE</span>
          </div>
        </div>
        <p className="header-subtitle">{subtitle}</p>
      </div>

      {/* Header Right Utilities */}
      <div className="header-right">
        {/* Real-time Clock */}
        <div className="clock-display" title="System Operational Time">
          <Clock size={14} className="clock-icon" />
          <span>{formatClock(currentTime)}</span>
        </div>

        {/* Refresh Action Button */}
        <button
          className={`header-btn ${isRefreshing ? 'spinning' : ''}`}
          onClick={onRefresh}
          title="Refresh Telemetry & Recalculate ETAs"
          type="button"
        >
          <RefreshCw size={16} />
        </button>

        {/* Notification Bell */}
        <div style={{ position: 'relative' }}>
          <button
            className="header-btn"
            onClick={() => setShowNotifications(!showNotifications)}
            title="Operational Alerts"
            type="button"
          >
            <Bell size={16} />
            {unreadCount > 0 && <span className="notif-badge-pill">{unreadCount}</span>}
          </button>

          {showNotifications && (
            <NotificationDrawer
              notifications={notifications}
              onClose={() => setShowNotifications(false)}
              onMarkAllRead={onMarkAllRead}
            />
          )}
        </div>

        {/* Profile Badge */}
        <div className="user-profile-badge">
          <div className="avatar-initials">DC</div>
          <div className="profile-info">
            <span className="profile-name">Dispatcher 04</span>
            <span className="profile-role">Lead Operations</span>
          </div>
        </div>
      </div>
    </header>
  );
}
