import os
# pyrefly: ignore [missing-import]
from flask import Flask, render_template
# pyrefly: ignore [missing-import]
from flask_session import Session
from config import Config
from database import init_db
from routes import register_blueprints

def create_app():
    """
    Application factory pattern to configure and initialize the Flask application.
    """
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(Config)
    
    # Ensure instance folder and session directories exist
    os.makedirs(app.instance_path, exist_ok=True)
    if app.config.get('SESSION_TYPE') == 'filesystem':
        os.makedirs(app.config.get('SESSION_FILE_DIR'), exist_ok=True)
        
    # Configure Server-side Sessions
    Session(app)
    
    # Initialize Database Connection
    init_db(app)
    
    # Template Filters for Timezone Conversion (UTC -> IST)
    from datetime import timezone, timedelta
    
    # IST is fixed at UTC+5:30 (Asia/Kolkata timezone offset)
    ist_tz = timezone(timedelta(hours=5, minutes=30), name="IST")
    
    @app.template_filter('to_ist')
    def to_ist(dt):
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ist_tz)
        
    @app.template_filter('format_ist')
    def format_ist(dt):
        if not dt:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        ist_dt = dt.astimezone(ist_tz)
        month = ist_dt.strftime("%B")
        day = ist_dt.strftime("%d").lstrip("0")
        year = ist_dt.strftime("%Y")
        hour = ist_dt.strftime("%I").lstrip("0")
        minute_ampm = ist_dt.strftime("%M %p")
        return f"{month} {day}, {year} at {hour}:{minute_ampm}"
    
    # Register blueprints (routing)
    register_blueprints(app)
    
    # Register Global Error Handlers for reliability
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('index.html'), 404
        
    @app.errorhandler(500)
    def internal_server_error(e):
        app.logger.error(f"Internal server error encountered: {e}")
        return render_template('index.html'), 500

    return app

# Entrypoint for running the application directly
if __name__ == '__main__':
    app = create_app()
    
    # Run the development server
    # Bind to localhost on port 5000 (default)
    app.run(
        host='127.0.0.1',
        port=int(os.environ.get('PORT', 5000)),
        debug=app.config.get('DEBUG', True)
    )
