def register_blueprints(app):
    """
    Import and register all application blueprints.
    """
    from .main import main_bp
    
    app.register_blueprint(main_bp)
