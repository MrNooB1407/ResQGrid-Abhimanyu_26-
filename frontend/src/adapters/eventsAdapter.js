/**
 * ResQGrid Events & Notifications Data Adapter
 *
 * Normalizes backend audit log entries from `/api/events` into the notification
 * objects consumed by NotificationDrawer.jsx and activity feeds.
 */

import { formatRelativeTime } from './incidentsAdapter.js';

/**
 * Maps SQLite event_type strings to frontend notification types and human titles.
 */
export const EVENT_TYPE_MAP = Object.freeze({
  AMBULANCE_BREAKDOWN: {
    type: 'ALERT',
    title: 'Ambulance Breakdown in Transit',
    badge: 'breakdown',
  },
  SHORTAGE_UNRESOLVED: {
    type: 'ALERT',
    title: 'Resource Shortage Unresolved',
    badge: 'shortage',
  },
  HOSPITAL_SATURATED: {
    type: 'WARNING',
    title: 'Hospital Capacity Saturated',
    badge: 'hospital',
  },
  TRAFFIC_SPIKE: {
    type: 'WARNING',
    title: 'Traffic Corridor Congestion Spike',
    badge: 'traffic',
  },
  RESOURCE_ALLOCATED: {
    type: 'SUCCESS',
    title: 'Resource Allocation Confirmed',
    badge: 'allocated',
  },
  RESOURCE_REALLOCATED: {
    type: 'SUCCESS',
    title: 'Dynamic Reallocation Executed',
    badge: 'reallocated',
  },
  INCIDENT_REPORTED: {
    type: 'INFO',
    title: 'New Emergency Incident Reported',
    badge: 'incident',
  },
  INCIDENT_STATUS_UPDATED: {
    type: 'INFO',
    title: 'Incident Lifecycle Status Updated',
    badge: 'status',
  },
  SYSTEM_INIT: {
    type: 'INFO',
    title: 'System Telemetry Initialized',
    badge: 'system',
  },
});

/**
 * Adapts a single raw event log item into a notification object.
 *
 * @param {object|null|undefined} raw
 * @returns {object|null}
 */
export function adaptEvent(raw) {
  if (!raw || typeof raw !== 'object') return null;

  const rawId = raw.id ?? null;
  const originalEventType = raw.event_type !== undefined && raw.event_type !== null ? String(raw.event_type) : null;
  const normalizedEventType = originalEventType ? originalEventType.trim().toUpperCase() : 'SYSTEM_LOG';
  const meta = EVENT_TYPE_MAP[normalizedEventType] || {
    type: 'INFO',
    title: normalizedEventType.replace(/_/g, ' '),
    badge: 'general',
  };

  const cleanDescription = (raw.description || '')
    .replace(/^\[SIMULATED\]\s*/i, '')
    .trim();

  return {
    // Identifiers
    id: rawId !== null ? `EVT-${rawId}` : 'EVT-0',
    rawId: rawId,
    backendId: rawId,

    // Notification Classification
    type: meta.type, // 'ALERT' | 'WARNING' | 'SUCCESS' | 'INFO'
    eventType: originalEventType || normalizedEventType,
    originalEventType: originalEventType,
    normalizedEventType: normalizedEventType,
    badge: meta.badge,
    title: meta.title,
    detail: cleanDescription,
    rawDescription: raw.description || '',

    // Related Incident Linkage
    relatedIncidentId: raw.related_incident_id ?? null,
    incidentTitle: raw.incident_title ? raw.incident_title.replace(/^\[SIMULATED\]\s*/i, '').trim() : null,

    // Timestamps
    time: formatRelativeTime(raw.created_at),
    createdAt: raw.created_at || null,
    timestamp: raw.created_at ? String(raw.created_at).slice(11, 16) : 'N/A',

    read: false,
  };
}

/**
 * Adapts an array of raw event items into normalized notification objects.
 *
 * @param {Array<object>|null|undefined} rawList
 * @returns {Array<object>}
 */
export function adaptEvents(rawList) {
  if (!Array.isArray(rawList)) return [];
  return rawList.map(adaptEvent).filter(Boolean);
}

