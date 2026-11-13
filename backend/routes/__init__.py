"""ResQGrid Routes Package

Aggregates and registers API blueprints with the Flask application.
"""

import sys
from pathlib import Path

# Ensure project root is present in sys.path
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask
from backend.routes.allocations import allocations_bp
from backend.routes.ambulances import ambulances_bp
from backend.routes.health import health_bp
from backend.routes.hospitals import hospitals_bp
from backend.routes.incidents import incidents_bp
from backend.routes.reallocation import reallocation_bp


def register_blueprints(app: Flask) -> None:
    """Register all modular API blueprints on the Flask application instance."""
    app.register_blueprint(health_bp)
    app.register_blueprint(incidents_bp)
    app.register_blueprint(ambulances_bp)
    app.register_blueprint(hospitals_bp)
    app.register_blueprint(allocations_bp)
    app.register_blueprint(reallocation_bp)
