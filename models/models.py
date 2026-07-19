from datetime import datetime
# pyrefly: ignore [missing-import]
from werkzeug.security import generate_password_hash, check_password_hash
from database import db

class Admin(db.Model):
    __tablename__ = 'admins'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Patient(db.Model):
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.Enum('Male', 'Female', 'Other'), nullable=False)
    blood_group = db.Column(db.String(5), nullable=True)
    address = db.Column(db.Text, nullable=True)
    profile_photo = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    appointments = db.relationship('Appointment', back_populates='patient', cascade='all, delete-orphan', lazy=True)
    consultations = db.relationship('Consultation', back_populates='patient', cascade='all, delete-orphan', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def to_dict(self):
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'gender': self.gender,
            'blood_group': self.blood_group,
            'address': self.address,
            'profile_photo': self.profile_photo,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Doctor(db.Model):
    __tablename__ = 'doctors'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    specialization = db.Column(db.String(100), nullable=False)
    license_number = db.Column(db.String(50), nullable=False, unique=True)
    experience_years = db.Column(db.Integer, default=0)
    bio = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Consultation availability
    consultation_days = db.Column(db.String(100), default='Monday-Friday')
    morning_start = db.Column(db.String(20), default='09:00 AM')
    morning_end = db.Column(db.String(20), default='01:00 PM')
    afternoon_start = db.Column(db.String(20), default='02:00 PM')
    afternoon_end = db.Column(db.String(20), default='05:00 PM')

    # Relationships
    appointments = db.relationship('Appointment', back_populates='doctor', cascade='all, delete-orphan', lazy=True)
    consultations = db.relationship('Consultation', back_populates='doctor', cascade='all, delete-orphan', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def has_configured_availability(self):
        return DoctorAvailability.query.filter_by(doctor_id=self.id).first() is not None

    def is_available(self, day, session_type):
        """
        Checks if the doctor is available for a given weekday and session (morning/afternoon).
        Defaults to True for backward compatibility.
        """
        avail = DoctorAvailability.query.filter_by(doctor_id=self.id, day=day).first()
        if avail:
            if not avail.available:
                return False
            if session_type.lower() == 'morning':
                return avail.morning
            elif session_type.lower() == 'afternoon':
                return avail.afternoon
        return True

    def is_available_day(self, day):
        """
        Checks if the doctor is marked as available on a given weekday.
        Defaults to True for backward compatibility.
        """
        avail = DoctorAvailability.query.filter_by(doctor_id=self.id, day=day).first()
        if avail:
            return avail.available
        return True

    def get_session_time(self, day, session_type, time_type):
        """
        Retrieves the start/end time for a given day and session.
        Defaults to standard fallbacks for backward compatibility.
        """
        avail = DoctorAvailability.query.filter_by(doctor_id=self.id, day=day).first()
        if avail:
            if session_type.lower() == 'morning':
                return avail.morning_start if time_type == 'start' else avail.morning_end
            elif session_type.lower() == 'afternoon':
                return avail.afternoon_start if time_type == 'start' else avail.afternoon_end
        
        # Standard Fallbacks
        if session_type.lower() == 'morning':
            return '09:00 AM' if time_type == 'start' else '01:00 PM'
        else:
            return '02:00 PM' if time_type == 'start' else '05:00 PM'

    def to_dict(self):
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'specialization': self.specialization,
            'license_number': self.license_number,
            'experience_years': self.experience_years,
            'bio': self.bio,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class DoctorAvailability(db.Model):
    __tablename__ = 'doctor_availabilities'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False)
    day = db.Column(db.String(20), nullable=False) # 'Monday', 'Tuesday', ...
    available = db.Column(db.Boolean, default=True, nullable=False)
    morning = db.Column(db.Boolean, default=True, nullable=False)
    morning_start = db.Column(db.String(20), default='09:00 AM', nullable=True)
    morning_end = db.Column(db.String(20), default='01:00 PM', nullable=True)
    afternoon = db.Column(db.Boolean, default=True, nullable=False)
    afternoon_start = db.Column(db.String(20), default='02:00 PM', nullable=True)
    afternoon_end = db.Column(db.String(20), default='05:00 PM', nullable=True)

    doctor = db.relationship('Doctor', backref=db.backref('availabilities', cascade='all, delete-orphan', lazy=True))


class Appointment(db.Model):
    __tablename__ = 'appointments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), default='Pending Approval')
    reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Approval and session workflow columns
    session = db.Column(db.String(20), default='Morning')
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by = db.Column(db.Integer, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    cancellation_reason = db.Column(db.Text, nullable=True)

    # Back Reference relationships mapped to primary tables
    patient = db.relationship('Patient', back_populates='appointments')
    doctor = db.relationship('Doctor', back_populates='appointments')
    consultation = db.relationship('Consultation', back_populates='appointment', uselist=False, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'doctor_id': self.doctor_id,
            'appointment_date': self.appointment_date.isoformat() if self.appointment_date else None,
            'status': self.status,
            'reason': self.reason,
            'session': self.session,
            'requested_at': self.requested_at.isoformat() if self.requested_at else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'approved_by': self.approved_by,
            'rejection_reason': self.rejection_reason,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'cancellation_reason': self.cancellation_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Consultation(db.Model):
    __tablename__ = 'consultations'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id', ondelete='CASCADE'), unique=True, nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False)
    consultation_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    symptoms = db.Column(db.Text, nullable=True)
    diagnosis = db.Column(db.Text, nullable=False)
    prescription = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    ai_summary = db.Column(db.Text, nullable=True)
    previous_records_summary = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Back Reference relationships
    appointment = db.relationship('Appointment', back_populates='consultation')
    patient = db.relationship('Patient', back_populates='consultations')
    doctor = db.relationship('Doctor', back_populates='consultations')

    def to_dict(self):
        return {
            'id': self.id,
            'appointment_id': self.appointment_id,
            'patient_id': self.patient_id,
            'doctor_id': self.doctor_id,
            'consultation_date': self.consultation_date.isoformat() if self.consultation_date else None,
            'symptoms': self.symptoms,
            'diagnosis': self.diagnosis,
            'prescription': self.prescription,
            'notes': self.notes,
            'ai_summary': self.ai_summary,
            'previous_records_summary': self.previous_records_summary,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class SystemActivity(db.Model):
    __tablename__ = 'system_activities'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    activity_name = db.Column(db.String(100), nullable=False)
    user = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'activity_name': self.activity_name,
            'user': self.user,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


class MedicalReport(db.Model):
    __tablename__ = 'medical_reports'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=True)
    consultation_id = db.Column(db.Integer, db.ForeignKey('consultations.id', ondelete='SET NULL'), nullable=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    report_type = db.Column(db.Enum('Blood Test Reports', 'MRI', 'CT Scan', 'X-Ray', 'ECG', 'Prescription PDFs', 'Medical Certificates', 'Lab Reports'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    patient = db.relationship('Patient', backref=db.backref('reports', cascade='all, delete-orphan', lazy=True))
    doctor = db.relationship('Doctor', backref=db.backref('reports', lazy=True))
    consultation = db.relationship('Consultation', backref=db.backref('reports', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'doctor_id': self.doctor_id,
            'consultation_id': self.consultation_id,
            'file_name': self.file_name,
            'file_path': self.file_path,
            'report_type': self.report_type,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=True)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship('Patient', backref=db.backref('notifications', cascade='all, delete-orphan', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'title': self.title,
            'message': self.message,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class DoctorLeave(db.Model):
    __tablename__ = 'doctor_leaves'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False)
    leave_date = db.Column(db.Date, nullable=False)
    session = db.Column(db.Enum('Morning', 'Afternoon', 'Full Day'), nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    doctor = db.relationship('Doctor', backref=db.backref('leaves', cascade='all, delete-orphan', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'doctor_id': self.doctor_id,
            'leave_date': self.leave_date.isoformat() if self.leave_date else None,
            'session': self.session,
            'reason': self.reason,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
