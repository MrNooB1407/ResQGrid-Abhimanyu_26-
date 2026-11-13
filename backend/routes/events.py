"""ResQGrid Events REST API Route

Provides access to the immutable audit event log stored in the SQLite database.
"""

from flask import Blueprint, abort, current_app, jsonify, request
from backend.database import DEFAULT_DB_PATH, get_db

events_bp = Blueprint("events", __name__, url_prefix="/api/events")

ALLOWED_EVENTS_PARAMS = {"limit", "event_type"}


@events_bp.route("", methods=["GET"])
def get_events():
    """Retrieve event log entries ordered newest first, with optional filtering.

    Query parameters:
    - limit: Maximum number of events to return (default 50, max 200).
    - event_type: Case-insensitive filter on event_type.
    """
    for param in request.args:
        if param not in ALLOWED_EVENTS_PARAMS:
            abort(400, description=f"Unsupported query parameter: '{param}'. Allowed parameters: limit, event_type.")

    # Validate limit
    limit_param = request.args.get("limit")
    limit = 50
    if limit_param is not None:
        try:
            limit = int(limit_param)
        except (ValueError, TypeError):
            abort(400, description="Query parameter 'limit' must be an integer.")
        if limit <= 0 or limit > 200:
            abort(400, description="Query parameter 'limit' must be between 1 and 200.")

    # Validate event_type
    event_type = request.args.get("event_type")
    conditions = []
    params = []
    if event_type is not None:
        cleaned_type = event_type.strip()
        if not cleaned_type:
            abort(400, description="Query parameter 'event_type' cannot be empty.")
        conditions.append("UPPER(e.event_type) = ?")
        params.append(cleaned_type.upper())

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT e.id, e.event_type, e.description, e.related_incident_id, e.created_at,
               i.title AS incident_title
        FROM event_logs e
        LEFT JOIN incidents i ON e.related_incident_id = i.id
        {where_clause}
        ORDER BY e.id DESC
        LIMIT ?;
    """
    params.append(limit)

    db_path = current_app.config.get("DATABASE", DEFAULT_DB_PATH)

    with get_db(db_path) as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()

    events = []
    for r in rows:
        item = dict(r)
        if item.get("created_at") is not None:
            item["created_at"] = str(item["created_at"])
        events.append(item)

    return jsonify({
        "success": True,
        "count": len(events),
        "data": events,
    }), 200

