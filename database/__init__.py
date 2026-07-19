# pyrefly: ignore [missing-import]
from flask_sqlalchemy import SQLAlchemy
# pyrefly: ignore [missing-import]
from sqlalchemy import text

# Initialize SQLAlchemy instance to be used across the application
db = SQLAlchemy()

def init_db(app):
    """
    Initializes the SQLAlchemy instance with the Flask app.
    Attempts to verify database connectivity.
    """
    db.init_app(app)
    
    with app.app_context():
        try:
            # Perform a basic query check
            db.session.execute(text("SELECT 1"))
            
            # Ensure all tables are created first before running dynamic column modifications
            db.create_all()
            
            # Dynamic migration check: profile_photo column in patients table
            try:
                db.session.execute(text("SELECT profile_photo FROM patients LIMIT 1"))
            except Exception:
                db.session.rollback()
                db.session.execute(text("ALTER TABLE patients ADD COLUMN profile_photo VARCHAR(255) DEFAULT NULL"))
                db.session.commit()
                
            # Dynamic migration check: previous_records_summary column in consultations table
            try:
                db.session.execute(text("SELECT previous_records_summary FROM consultations LIMIT 1"))
            except Exception:
                db.session.rollback()
                db.session.execute(text("ALTER TABLE consultations ADD COLUMN previous_records_summary TEXT DEFAULT NULL"))
                db.session.commit()

            # Dynamic migration check: title column in notifications table
            try:
                db.session.execute(text("SELECT title FROM notifications LIMIT 1"))
            except Exception:
                db.session.rollback()
                db.session.execute(text("ALTER TABLE notifications ADD COLUMN title VARCHAR(255) DEFAULT NULL"))
                db.session.commit()

            # Dynamic migration check: Doctors availability columns
            for col, col_type in [
                ('consultation_days', "VARCHAR(100) DEFAULT 'Monday-Friday'"),
                ('morning_start', "VARCHAR(20) DEFAULT '09:00 AM'"),
                ('morning_end', "VARCHAR(20) DEFAULT '01:00 PM'"),
                ('afternoon_start', "VARCHAR(20) DEFAULT '02:00 PM'"),
                ('afternoon_end', "VARCHAR(20) DEFAULT '05:00 PM'")
            ]:
                try:
                    db.session.execute(text(f"SELECT {col} FROM doctors LIMIT 1"))
                except Exception:
                    db.session.rollback()
                    db.session.execute(text(f"ALTER TABLE doctors ADD COLUMN {col} {col_type}"))
                    db.session.commit()

            # Dynamic migration check: Modify appointments status type and add new columns
            if db.engine.dialect.name == 'mysql':
                try:
                    db.session.execute(text("ALTER TABLE appointments MODIFY COLUMN status VARCHAR(50) DEFAULT 'Pending Approval'"))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                try:
                    db.session.execute(text("ALTER TABLE system_activities MODIFY COLUMN user VARCHAR(255) NOT NULL"))
                    db.session.commit()
                except Exception:
                    db.session.rollback()

            for col, col_type in [
                ('session', "VARCHAR(20) DEFAULT 'Morning'"),
                ('requested_at', "DATETIME DEFAULT CURRENT_TIMESTAMP"),
                ('approved_at', "DATETIME DEFAULT NULL"),
                ('approved_by', "INT DEFAULT NULL"),
                ('rejection_reason', "TEXT DEFAULT NULL"),
                ('cancelled_at', "DATETIME DEFAULT NULL"),
                ('cancellation_reason', "TEXT DEFAULT NULL")
            ]:
                try:
                    db.session.execute(text(f"SELECT {col} FROM appointments LIMIT 1"))
                except Exception:
                    db.session.rollback()
                    db.session.execute(text(f"ALTER TABLE appointments ADD COLUMN {col} {col_type}"))
                    db.session.commit()
                
            # Dynamic migration check: doctor_availabilities columns
            for col, col_type in [
                ('available', "BOOLEAN DEFAULT TRUE"),
                ('morning_start', "VARCHAR(20) DEFAULT '09:00 AM'"),
                ('morning_end', "VARCHAR(20) DEFAULT '01:00 PM'"),
                ('afternoon_start', "VARCHAR(20) DEFAULT '02:00 PM'"),
                ('afternoon_end', "VARCHAR(20) DEFAULT '05:00 PM'")
            ]:
                try:
                    db.session.execute(text(f"SELECT {col} FROM doctor_availabilities LIMIT 1"))
                except Exception:
                    db.session.rollback()
                    db.session.execute(text(f"ALTER TABLE doctor_availabilities ADD COLUMN {col} {col_type}"))
                    db.session.commit()
                
            app.logger.info("Database connection verified successfully and tables checked/created.")
            return True
        except Exception as e:
            app.logger.error(
                "\n" + "="*80 + "\n"
                "WARNING: DATABASE CONNECTION FAILED!\n"
                f"Details: {e}\n"
                "Please verify that:\n"
                "1. Your MySQL server is running.\n"
                f"2. A database named '{app.config.get('DB_NAME')}' exists.\n"
                "3. Your credentials in the .env file are correct.\n"
                + "="*80 + "\n"
            )
            return False
