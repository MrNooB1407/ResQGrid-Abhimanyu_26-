"""ResQGrid Flask Application Factory & Server Entrypoint

Provides the Flask application factory with CORS configuration, centralized JSON error handlers,
route blueprint registration, and local development server execution.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure project root is present in sys.path for direct script execution
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from backend.database import DEFAULT_DB_PATH
from backend.routes import register_blueprints


def create_app(test_config: Optional[Dict[str, Any]] = None) -> Flask:
    """Application factory for ResQGrid REST API.

    Args:
        test_config: Optional dictionary to override default configuration parameters (e.g. DATABASE).

    Returns:
        Flask application instance.
    """
    app = Flask(__name__)

    # Default configuration
    app.config.from_mapping(
        DATABASE=str(DEFAULT_DB_PATH),
        JSON_SORT_KEYS=False,
    )

    # Apply test or environment overrides
    if test_config:
        app.config.update(test_config)

    # Configure CORS for Vite frontend (http://localhost:5173 and http://127.0.0.1:5173)
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": [
                    "http://localhost:5173",
                    "http://127.0.0.1:5173",
                ]
            }
        },
        methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        supports_credentials=True,
    )

    # Register API route blueprints
    register_blueprints(app)

    # -----------------------------------------------------------------------
    # Centralized JSON Error Handlers
    # -----------------------------------------------------------------------
    @app.errorhandler(400)
    def bad_request(error):
        message = (
            error.description
            if hasattr(error, "description") and error.description
            else "The request payload was malformed or missing required parameters."
        )
        return jsonify({
            "success": False,
            "error": {
                "code": 400,
                "name": "Bad Request",
                "message": message,
            },
        }), 400

    @app.errorhandler(404)
    def not_found(error):
        message = (
            error.description
            if hasattr(error, "description") and error.description
            else "The requested endpoint or resource was not found."
        )
        return jsonify({
            "success": False,
            "error": {
                "code": 404,
                "name": "Not Found",
                "message": message,
            },
        }), 404

    @app.errorhandler(409)
    def conflict(error):
        message = (
            error.description
            if hasattr(error, "description") and error.description
            else "A state conflict occurred with the target resource."
        )
        return jsonify({
            "success": False,
            "error": {
                "code": 409,
                "name": "Conflict",
                "message": message,
            },
        }), 409

    @app.errorhandler(422)
    def unprocessable_entity(error):
        message = (
            error.description
            if hasattr(error, "description") and error.description
            else "The request syntax was valid but the instructions could not be fulfilled due to resource constraints."
        )
        return jsonify({
            "success": False,
            "error": {
                "code": 422,
                "name": "Unprocessable Entity",
                "message": message,
            },
        }), 422

    @app.errorhandler(500)
    def internal_server_error(error):
        return jsonify({
            "success": False,
            "error": {
                "code": 500,
                "name": "Internal Server Error",
                "message": "An internal server error occurred while processing the request.",
            },
        }), 500

    @app.errorhandler(Exception)
    def handle_unexpected_exception(error):
        # Propagate standard HTTPExceptions through their respective status codes
        if isinstance(error, HTTPException):
            return jsonify({
                "success": False,
                "error": {
                    "code": error.code or 500,
                    "name": error.name,
                    "message": error.description,
                },
            }), error.code or 500

        # Generic safe error response for unexpected server exceptions (no stack trace leak)
        return jsonify({
            "success": False,
            "error": {
                "code": 500,
                "name": "Internal Server Error",
                "message": "An unexpected error occurred. The incident has been safely logged.",
            },
        }), 500

    return app


if __name__ == "__main__":
    app = create_app()
    print("ResQGrid Emergency Coordination API starting on http://127.0.0.1:5000...")
    app.run(host="127.0.0.1", port=5000, debug=True)
