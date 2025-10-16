"""
BMAD Backend Application Entrypoint

This module initializes the Flask app, configures CORS, registers API blueprints,
initializes the database, and serves the built frontend static assets.
"""
import os
from dotenv import load_dotenv
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory
from flask_cors import CORS
import logging
from src.models.user import db, init_db
from src.models.task import Task  # Import Task model
from src.models.workflow import Workflow  # Import Workflow model
from src.models.custom_agent import CustomAgent  # Import CustomAgent model
from src.routes.user import user_bp
from src.routes.bmad_api import bmad_bp
from src.utils.logger import setup_logging, LogDeduplicationFilter, HTTPRequestDeduplicationFilter

# Load environment variables from .env if present
load_dotenv()

# Initialize logging with environment variable support
log_level = os.environ.get('BMAD_LOG_LEVEL', 'INFO')
setup_logging(log_level=log_level)

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me-in-env')

# Enable CORS for all routes
CORS(app, origins="*")

# Register blueprints
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(bmad_bp)

# Initialize database with all models
init_db(app)

# Configure Flask/Werkzeug logging to reduce duplicate request logs
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.WARNING)  # Only show warnings and errors

# Add specialized HTTP request deduplication filter to werkzeug logger
http_dedup_filter = HTTPRequestDeduplicationFilter(time_window=30.0)
for handler in werkzeug_logger.handlers:
    handler.addFilter(http_dedup_filter)

# Also configure the root logger to prevent duplicate HTTP request logs
root_logger = logging.getLogger()
for handler in root_logger.handlers:
    if isinstance(handler, logging.StreamHandler) and handler.stream.name == '<stdout>':
        handler.addFilter(http_dedup_filter)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    """Serve static frontend files and fall back to index.html for SPA routes."""
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

@app.route('/api/status')
def api_status():
    """API status endpoint"""
    return {
        'status': 'running',
        'message': 'BMAD System API is operational',
        'version': '1.0.0'
    }

if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', os.environ.get('BACKEND_CONTAINER_PORT', 5000)))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host=host, port=port, debug=debug)
