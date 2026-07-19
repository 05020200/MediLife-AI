import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()
class Config:
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-medilife-secret-key')
    FLASK_ENV = os.environ.get('FLASK_ENV', 'production')
    DEBUG = os.environ.get('FLASK_ENV') == 'development'

    # Database settings
    DB_USER = os.environ.get('MYSQL_USER', 'root')
    DB_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    DB_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    DB_PORT = os.environ.get('MYSQL_PORT', '3306')
    DB_NAME = os.environ.get('MYSQL_DB', 'medilife_ai')

    # Construct SQLAlchemy Database URI
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask-Session settings
    SESSION_TYPE = os.environ.get('SESSION_TYPE', 'filesystem')
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    
    # Path for filesystem session storage if used
    SESSION_FILE_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'flask_session')
