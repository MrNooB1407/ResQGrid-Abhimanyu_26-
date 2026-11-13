import React from 'react';
import { AlertCircle, AlertTriangle, CheckCircle, Info, X } from 'lucide-react';

export default function NotificationDrawer({ notifications, onClose, onMarkAllRead }) {
  const getIcon = (type) => {
    switch (type) {
      case 'ALERT':
        return <AlertCircle size={16} color="#ef4444" />;
      case 'WARNING':
        return <AlertTriangle size={16} color="#f59e0b" />;
      case 'SUCCESS':
        return <CheckCircle size={16} color="#10b981" />;
      default:
        return <Info size={16} color="#3b82f6" />;
    }
  };

  return (
    <div className="notification-dropdown">
      <div className="notif-dropdown-header">
        <h4>Operational Alerts & Logs</h4>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            onClick={onMarkAllRead}
            type="button"
            style={{
              background: 'none',
              border: 'none',
              color: '#3b82f6',
              fontSize: '0.7rem',
              cursor: 'pointer',
              fontWeight: 600,
            }}
          >
            Mark all read
          </button>
          <button
            onClick={onClose}
            type="button"
            style={{
              background: 'none',
              border: 'none',
              color: '#64748b',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <X size={16} />
          </button>
        </div>
      </div>

      <div className="notif-list">
        {notifications.length === 0 ? (
          <div style={{ padding: '1.5rem', textAlign: 'center', color: '#64748b', fontSize: '0.8rem' }}>
            No new operational alerts.
          </div>
        ) : (
          notifications.map((item) => (
            <div key={item.id} className={`notif-item ${!item.read ? 'unread' : ''}`}>
              <div style={{ marginTop: '2px', flexShrink: 0 }}>{getIcon(item.type)}</div>
              <div className="notif-content">
                <div className="notif-title">{item.title}</div>
                <div className="notif-detail">{item.detail}</div>
                <div className="notif-time">{item.time}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

