import sys
from app import create_app
from database import db
from models import Admin

def reset_admin():
    """
    Checks if an admin with the email admin@medilife.ai exists in the database.
    If yes, updates the password. Otherwise, registers a new 'superadmin' account.
    """
    app = create_app()
    with app.app_context():
        admin = Admin.query.filter_by(email="admin@medilife.ai").first()
        if admin:
            admin.set_password("adminPass123!")
            db.session.commit()
            print("Admin password updated successfully!")
        else:
            new_admin = Admin(
                username="superadmin",
                email="admin@medilife.ai"
            )
            new_admin.set_password("adminPass123!")
            db.session.add(new_admin)
            db.session.commit()
            print("Admin created successfully!")

if __name__ == '__main__':
    reset_admin()
