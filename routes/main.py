# pyrefly: ignore [missing-import]
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, send_from_directory
from datetime import datetime, timedelta
from models import Admin, Patient, Doctor, Appointment, Consultation, SystemActivity, MedicalReport, Notification, DoctorLeave, DoctorAvailability
from database import db
# pyrefly: ignore [missing-import]
from werkzeug.utils import secure_filename
import os

main_bp = Blueprint('main', __name__)

def create_notification(patient_id, title, message):
    """
    Creates and saves a notification to the database for the given patient.
    """
    try:
        notification = Notification(
            patient_id=patient_id,
            title=title,
            message=message,
            is_read=False,
            created_at=datetime.utcnow()
        )
        db.session.add(notification)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating notification: {e}")

@main_bp.route('/')
def index():
    """
    Renders the landing/home page of the application.
    """
    return render_template('index.html')


@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles GET requests to render the login page, and POST requests
    to authenticate users based on selected role and credentials.
    """
    if 'user_id' in session:
        flash('You are already logged in.', 'info')
        if session.get('role') == 'patient':
            return redirect(url_for('main.patient_dashboard'))
        elif session.get('role') == 'doctor':
            return redirect(url_for('main.doctor_dashboard'))
        elif session.get('role') == 'admin':
            return redirect(url_for('main.admin_dashboard'))
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        role = request.form.get('role')
        identity = request.form.get('identity')
        password = request.form.get('password')
        
        user = None
        
        try:
            if role == 'patient':
                user = Patient.query.filter_by(email=identity).first()
            elif role == 'doctor':
                user = Doctor.query.filter_by(email=identity).first()
            elif role == 'admin':
                user = Admin.query.filter((Admin.username == identity) | (Admin.email == identity)).first()
            else:
                flash('Invalid access role selected.', 'warning')
                return render_template('login.html')
                
            if user and user.check_password(password):
                session['user_id'] = user.id
                session['role'] = role
                
                if role == 'admin':
                    session['user_name'] = user.username
                else:
                    session['user_name'] = user.full_name
                    
                flash(f"Welcome back, {session['user_name']}! Successfully signed in.", 'success')
                if role == 'patient':
                    return redirect(url_for('main.patient_dashboard'))
                elif role == 'doctor':
                    return redirect(url_for('main.doctor_dashboard'))
                elif role == 'admin':
                    return redirect(url_for('main.admin_dashboard'))
                return redirect(url_for('main.index'))
            else:
                flash('Invalid credentials. Please verify your identity and password.', 'error')
                
        except Exception as e:
            flash(f'System is currently unable to verify credentials. Please ensure database is configured. {e}', 'error')
            
    return render_template('login.html')


@main_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles GET requests to render the patient registration form,
    and POST requests to validate fields and store new patients.
    """
    if 'user_id' in session:
        flash('You are already logged in.', 'info')
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        dob_str = request.form.get('date_of_birth')
        gender = request.form.get('gender')
        phone = request.form.get('phone')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validations
        if not all([first_name, last_name, dob_str, gender, email, password, confirm_password]):
            flash('Please fill in all required fields.', 'error')
            return render_template('register.html')
            
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
            
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('register.html')
            
        # Parse date of birth and check sanity
        try:
            dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
            if dob > datetime.today().date():
                flash('Date of birth cannot be in the future.', 'error')
                return render_template('register.html')
        except ValueError:
            flash('Invalid date format for Date of Birth.', 'error')
            return render_template('register.html')
            
        try:
            # Check if email is already taken in the patients database
            existing_patient = Patient.query.filter_by(email=email).first()
            if existing_patient:
                flash('An account with this email address already exists.', 'error')
                return render_template('register.html')
                
            # Create and hash patient account
            new_patient = Patient(
                first_name=first_name,
                last_name=last_name,
                date_of_birth=dob,
                gender=gender,
                phone=phone,
                email=email
            )
            new_patient.set_password(password)
            
            # Commit record to DB
            db.session.add(new_patient)
            
            # Log System Activity
            activity = SystemActivity(
                activity_name="New Patient Registered",
                user=f"{new_patient.full_name} ({new_patient.email})"
            )
            db.session.add(activity)
            db.session.commit()
            
            flash('Your patient profile was created successfully. You can now log in.', 'success')
            return redirect(url_for('main.login'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Database error: Could not complete registration. Ensure database is running. Error: {e}', 'error')
            
    return render_template('register.html')


@main_bp.route('/logout')
def logout():
    """
    Destroys current session and redirects to the landing page.
    """
    session.clear()
    
    flash('Successfully signed out of your account.', 'success')
    return redirect(url_for('main.index'))


@main_bp.route('/patient/dashboard', methods=['GET', 'POST'])
def patient_dashboard():
    """
    Renders the patient dashboard, including tabs for upcoming appointments,
    past visits/medical history, booking new appointments, and managing profile details.
    """
    if 'user_id' not in session or session.get('role') != 'patient':
        flash('Please log in as a patient to access the dashboard.', 'warning')
        return redirect(url_for('main.login'))
        
    patient = Patient.query.get(session['user_id'])
    if not patient:
        session.clear()
        flash('Patient record not found.', 'error')
        return redirect(url_for('main.login'))
        
    doctors = Doctor.query.all()
    
    # Handle form submissions (POST)
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'book_appointment':
            doctor_id = request.form.get('doctor_id')
            app_date_str = request.form.get('appointment_date')
            session_val = request.form.get('session')
            reason = request.form.get('reason')
            
            if not doctor_id or not app_date_str or not session_val:
                flash('Please select a doctor, date, and session for the appointment.', 'error')
            else:
                try:
                    # Expecting 'YYYY-MM-DD' date string
                    app_date = datetime.strptime(app_date_str, '%Y-%m-%d')
                    today_ist = (datetime.utcnow() + timedelta(hours=5, minutes=30)).date()
                    if app_date.date() < today_ist:
                        flash('Appointment date cannot be in the past.', 'error')
                    else:
                        new_app = Appointment(
                            patient_id=patient.id,
                            doctor_id=int(doctor_id),
                            appointment_date=app_date,
                            session=session_val,
                            reason=reason,
                            status='Pending Approval'
                        )
                        db.session.add(new_app)
                        
                        # Log System Activity
                        activity = SystemActivity(
                            activity_name="Appointment Booked",
                            user=f"{patient.full_name} ({patient.email})"
                        )
                        db.session.add(activity)
                        db.session.commit()
                        flash('Your appointment request has been submitted successfully and is awaiting hospital confirmation.', 'success')
                        return redirect(url_for('main.patient_dashboard', tab='dashboard'))
                except ValueError:
                    flash('Invalid date or session format. Please try again.', 'error')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Failed to book appointment: {str(e)}', 'error')
                    
        elif action == 'update_profile':
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            phone = request.form.get('phone')
            dob_str = request.form.get('date_of_birth')
            gender = request.form.get('gender')
            blood_group = request.form.get('blood_group')
            address = request.form.get('address')
            
            if not first_name or not last_name or not dob_str or not gender:
                flash('First name, last name, date of birth, and gender are required.', 'error')
            else:
                try:
                    dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
                    if dob > datetime.today().date():
                        flash('Date of birth cannot be in the future.', 'error')
                    else:
                        patient.first_name = first_name
                        patient.last_name = last_name
                        patient.phone = phone
                        patient.date_of_birth = dob
                        patient.gender = gender
                        patient.blood_group = blood_group
                        patient.address = address
                        
                        db.session.commit()
                        session['user_name'] = patient.full_name
                        flash('Profile updated successfully!', 'success')
                        return redirect(url_for('main.patient_dashboard', tab='profile'))
                except ValueError:
                    flash('Invalid date format for Date of Birth.', 'error')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Failed to update profile: {str(e)}', 'error')
    
    # Query upcoming appointments: Approved or Pending Approval, sorted by date ascending
    today_ist = (datetime.utcnow() + timedelta(hours=5, minutes=30)).date()
    upcoming_appointments = Appointment.query.filter(
        Appointment.patient_id == patient.id,
        Appointment.status.in_(['Pending Approval', 'Approved']),
        db.func.date(Appointment.appointment_date) >= today_ist
    ).order_by(Appointment.appointment_date.asc()).all()
    
    # Query all appointments for history: sorted by date descending
    all_appointments = Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.appointment_date.desc()).all()
    
    # Query medical history (consultations)
    consultations = Consultation.query.filter_by(patient_id=patient.id).order_by(Consultation.consultation_date.desc()).all()
    
    # Query patient notifications: unread first, then by created_at desc
    notifications = Notification.query.filter_by(patient_id=patient.id).order_by(
        Notification.is_read.asc(),
        Notification.created_at.desc()
    ).all()
    unread_notifications_count = Notification.query.filter_by(patient_id=patient.id, is_read=False).count()
    
    # Determine default active tab from query parameter
    active_tab = request.args.get('tab', 'dashboard')
    
    return render_template(
        'dashboard.html',
        patient=patient,
        doctors=doctors,
        upcoming_appointments=upcoming_appointments,
        all_appointments=all_appointments,
        consultations=consultations,
        notifications=notifications,
        unread_notifications_count=unread_notifications_count,
        active_tab=active_tab,
        datetime=datetime
    )


@main_bp.route('/patient/book-appointment', methods=['GET', 'POST'])
def book_appointment():
    """
    Renders the appointment booking page.
    Filters doctors based on department, validates input (preventing past bookings),
    and saves appointments to the database.
    """
    if 'user_id' not in session or session.get('role') != 'patient':
        flash('Please log in as a patient to book an appointment.', 'warning')
        return redirect(url_for('main.login'))
        
    patient = Patient.query.get(session['user_id'])
    if not patient:
        session.clear()
        flash('Patient record not found.', 'error')
        return redirect(url_for('main.login'))
        
    doctors = Doctor.query.all()
    # Extract unique departments (specializations) of doctors
    departments = sorted(list(set(d.specialization for d in doctors if d.specialization)))
    
    if request.method == 'POST':
        doctor_id = request.form.get('doctor_id')
        app_date_str = request.form.get('date')
        session_val = request.form.get('session')
        reason = request.form.get('reason')
        
        if not doctor_id or not app_date_str or not session_val:
            flash('Please select a doctor, date, and session for the appointment.', 'error')
        else:
            try:
                # Form date input is typically YYYY-MM-DD
                app_date = datetime.strptime(app_date_str, '%Y-%m-%d')
                
                # Check if it's in the past
                today_ist = (datetime.utcnow() + timedelta(hours=5, minutes=30)).date()
                if app_date.date() < today_ist:
                    flash('You cannot book an appointment in the past.', 'error')
                else:
                    # Check doctor weekday session availability
                    doctor = Doctor.query.get(int(doctor_id))
                    weekday_name = app_date.strftime('%A')
                    if not doctor.is_available_day(weekday_name):
                        flash(f"Dr. {doctor.full_name} is not available on {weekday_name}. Please choose another available day or session.", "error")
                    elif not doctor.is_available(weekday_name, session_val):
                        flash(f"Dr. {doctor.full_name} is not available on {weekday_name} {session_val}. Please choose another available day or session.", "error")
                    else:
                        # Check for doctor leave conflicts
                        leave = DoctorLeave.query.filter(
                            DoctorLeave.doctor_id == int(doctor_id),
                            DoctorLeave.leave_date == app_date.date()
                        ).first()
                        if leave and (leave.session == 'Full Day' or leave.session == session_val):
                            flash("This doctor is unavailable during the selected session. Please choose another doctor or another date.", "error")
                        else:
                            new_app = Appointment(
                                patient_id=patient.id,
                                doctor_id=int(doctor_id),
                                appointment_date=app_date,
                                session=session_val,
                                reason=reason,
                                status='Pending Approval'
                            )
                            db.session.add(new_app)
                            
                            # Log System Activity
                            activity = SystemActivity(
                                activity_name="Appointment Booked",
                                user=f"{patient.full_name} ({patient.email})"
                            )
                            db.session.add(activity)
                            db.session.commit()
                            flash('Your appointment request has been submitted successfully and is awaiting hospital confirmation.', 'success')
                            return redirect(url_for('main.patient_dashboard', tab='dashboard'))
            except ValueError:
                flash('Invalid date or session format. Please try again.', 'error')
            except Exception as e:
                db.session.rollback()
                flash(f'Failed to book appointment: {str(e)}', 'error')
                
    return render_template(
        'book_appointment.html',
        patient=patient,
        doctors=doctors,
        departments=departments,
        datetime=datetime
    )


@main_bp.route('/patient/appointment-history', methods=['GET'])
def appointment_history():
    """
    Renders the patient's appointment history page.
    Queries all appointment records from MySQL and displays them in a Bootstrap table.
    """
    if 'user_id' not in session or session.get('role') != 'patient':
        flash('Please log in as a patient to view appointment history.', 'warning')
        return redirect(url_for('main.login'))
        
    patient = Patient.query.get(session['user_id'])
    if not patient:
        session.clear()
        flash('Patient record not found.', 'error')
        return redirect(url_for('main.login'))
        
    # Query all appointments for history: sorted by date descending
    all_appointments = Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.appointment_date.desc()).all()
    
    return render_template(
        'appointment_history.html',
        patient=patient,
        appointments=all_appointments,
        datetime=datetime
    )


@main_bp.route('/patient/medical-history', methods=['GET'])
def medical_history():
    """
    Renders the patient's medical history page.
    Queries all consultation records from MySQL sorted in chronological order (ascending) and displays them.
    """
    if 'user_id' not in session or session.get('role') != 'patient':
        flash('Please log in as a patient to view medical history.', 'warning')
        return redirect(url_for('main.login'))
        
    patient = Patient.query.get(session['user_id'])
    if not patient:
        session.clear()
        flash('Patient record not found.', 'error')
        return redirect(url_for('main.login'))
        
    # Query medical history (consultations) in chronological order (ascending)
    consultations = Consultation.query.filter_by(patient_id=patient.id).order_by(Consultation.consultation_date.asc()).all()
    
    return render_template(
        'medical_history.html',
        patient=patient,
        consultations=consultations,
        datetime=datetime
    )


@main_bp.route('/doctor/dashboard', methods=['GET'])
def doctor_dashboard():
    """
    Renders the doctor dashboard, featuring stat cards for Today's Appointments,
    Total Patients, and Pending Consultations, along with a responsive table of today's appointments.
    """
    if 'user_id' not in session or session.get('role') != 'doctor':
        flash('Please log in as a doctor to access the clinical workspace.', 'warning')
        return redirect(url_for('main.login'))
        
    doctor = Doctor.query.get(session['user_id'])
    if not doctor:
        session.clear()
        flash('Doctor record not found.', 'error')
        return redirect(url_for('main.login'))
        
    # Get today's date in IST
    now_utc = datetime.utcnow()
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    today_ist = now_ist.date()
    
    # Query today's approved/completed appointments for this doctor
    today_appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.status.in_(['Approved', 'Completed']),
        db.func.date(Appointment.appointment_date) == today_ist
    ).order_by(Appointment.appointment_date.asc()).all()
    
    # Group by session
    morning_appointments = [app for app in today_appointments if app.session == 'Morning']
    afternoon_appointments = [app for app in today_appointments if app.session == 'Afternoon']
    
    # Calculate stat counters
    total_patients_count = db.session.query(Appointment.patient_id).filter(
        Appointment.doctor_id == doctor.id,
        Appointment.status.in_(['Approved', 'Completed'])
    ).distinct().count()
    
    pending_consultations_count = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.status == 'Approved'
    ).count()
    
    recent_activities = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.status.in_(['Approved', 'Completed', 'Cancelled'])
    ).order_by(Appointment.appointment_date.desc()).limit(5).all()
    
    return render_template(
        'doctor_dashboard.html',
        doctor=doctor,
        today_appointments=today_appointments,
        morning_appointments=morning_appointments,
        afternoon_appointments=afternoon_appointments,
        today_appointments_count=len(today_appointments),
        total_patients_count=total_patients_count,
        pending_consultations_count=pending_consultations_count,
        recent_activities=recent_activities,
        datetime=datetime
    )


@main_bp.route('/doctor/consultation/<int:appointment_id>', methods=['GET', 'POST'])
def consultation(appointment_id):
    """
    Renders the clinical consultation page (GET) and processes consultation submissions (POST).
    """
    if 'user_id' not in session or session.get('role') != 'doctor':
        flash('Please log in as a doctor to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    doctor = Doctor.query.get(session['user_id'])
    if not doctor:
        session.clear()
        flash('Doctor record not found.', 'error')
        return redirect(url_for('main.login'))
        
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.doctor_id != doctor.id:
        flash('You are not authorized to manage this appointment.', 'error')
        return redirect(url_for('main.doctor_dashboard'))
        
    patient = appointment.patient
    
    if request.method == 'POST':
        symptoms = request.form.get('symptoms')
        diagnosis = request.form.get('diagnosis')
        prescription = request.form.get('prescription')
        notes = request.form.get('notes')  # maps to Consultation Notes
        ai_summary_raw = request.form.get('ai_summary')
        ai_summary = None
        if ai_summary_raw:
            ai_summary_cleaned = ai_summary_raw.strip()
            if ai_summary_cleaned != '':
                ai_summary = ai_summary_cleaned
        
        if not diagnosis:
            flash('Diagnosis is a required field to submit a consultation.', 'error')
            return redirect(url_for('main.consultation', appointment_id=appointment.id))
            
        try:
            # Create new Consultation entry
            new_consultation = Consultation(
                appointment_id=appointment.id,
                patient_id=appointment.patient_id,
                doctor_id=doctor.id,
                consultation_date=datetime.utcnow(),
                symptoms=symptoms,
                diagnosis=diagnosis,
                prescription=prescription,
                notes=notes,
                ai_summary=ai_summary,
                previous_records_summary=ai_summary
            )
            
            # Update Appointment status to Completed
            appointment.status = 'Completed'
            
            # Create patient notification
            new_notif = Notification(
                patient_id=appointment.patient_id,
                message="Your consultation record is now available."
            )
            db.session.add(new_notif)
            
            db.session.add(new_consultation)
            
            # Log System Activity
            activity = SystemActivity(
                activity_name="Consultation Completed",
                user=f"Dr. {doctor.full_name}"
            )
            db.session.add(activity)
            db.session.commit()
            
            flash('Consultation saved successfully and appointment marked as completed.', 'success')
            return redirect(url_for('main.doctor_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to save consultation: {str(e)}', 'error')
            return redirect(url_for('main.consultation', appointment_id=appointment.id))
            
    # GET Request: Fetch past consultations for this patient to display as medical history
    past_consultations = Consultation.query.filter_by(patient_id=patient.id).order_by(Consultation.consultation_date.desc()).all()
    
    return render_template(
        'consultation.html',
        doctor=doctor,
        appointment=appointment,
        patient=patient,
        past_consultations=past_consultations,
        datetime=datetime
    )


@main_bp.route('/api/generate-summary', methods=['POST'])
def generate_summary():
    """
    Retrieves previous clinical records and calls Google Gemini API to generate a structured medical clinical summary.
    If Gemini API key is missing or calls fail, falls back on robust rules-based synthesis.
    """
    if 'user_id' not in session or session.get('role') != 'doctor':
        return {'error': 'Unauthorized access'}, 401
        
    data = request.get_json() or {}
    appointment_id = data.get('appointment_id')
    previous_only = data.get('previous_only', False)
    
    if not appointment_id:
        return {'error': 'Appointment ID is required.'}, 400
        
    if not previous_only:
        return {'error': 'Current session summary is disabled. previous_only must be set to True.'}, 400
        
    appointment = Appointment.query.get(appointment_id)
    if not appointment or appointment.doctor_id != session.get('user_id'):
        return {'error': 'Appointment not found or unauthorized.'}, 404
        
    # Retrieve previous consultation records for this patient
    patient = appointment.patient
    past_consultations = Consultation.query.filter(
        Consultation.patient_id == patient.id,
        Consultation.appointment_id != appointment.id
    ).order_by(Consultation.consultation_date.desc()).all()
    
    # Format past consultation history
    past_records_formatted = []
    for c in past_consultations:
        record = (
            f"Date: {c.consultation_date.strftime('%Y-%m-%d')}\n"
            f"- Diagnosis: {c.diagnosis}\n"
            f"- Symptoms: {c.symptoms or 'N/A'}\n"
            f"- Prescription: {c.prescription or 'N/A'}\n"
            f"- Clinical Notes: {c.notes or 'N/A'}\n"
        )
        past_records_formatted.append(record)
        
    past_records_text = "\n".join(past_records_formatted) if past_records_formatted else "No previous clinical consultation records."
    
    # Construct prompt for Gemini based ONLY on historical records
    prompt = (
        "You are an expert clinical assistant AI. Summarize the following patient's historical medical records into a structured clinical history summary.\n\n"
        "Generate a structured summary containing exactly the following sections in clean Markdown format:\n"
        "### Medical History\n"
        "### Previous Diagnoses\n"
        "### Historical Treatments\n"
        "### Patient Profile Summary\n\n"
        "--- PATIENT DETAILS ---\n"
        f"Name: {patient.full_name}\n"
        f"Gender: {patient.gender}\n"
        f"Age: {((datetime.now().date() - patient.date_of_birth).days // 365)} years\n\n"
        "--- PREVIOUS CONSULTATION HISTORY ---\n"
        f"{past_records_text}\n\n"
        "--- REQUIREMENTS ---\n"
        "Compile a professional, medical-grade summary incorporating only the historical data.\n"
        "At the very end of your response, you MUST append this disclaimer statement EXACTLY:\n"
        "\"Disclaimer: This summary is generated using only previous consultation records and is intended for clinical reference. It does not include the current consultation.\""
    )
    
    try:
        from services.ai_service import call_gemini_api
        summary = call_gemini_api(prompt)
        return {'summary': summary}
    except Exception as e:
        # Fallback to rules-based synthesis if key is missing or API errors
        past_diagnoses = [c.diagnosis for c in past_consultations if c.diagnosis]
        past_diagnoses_str = ", ".join(past_diagnoses) if past_diagnoses else "None recorded."
        
        fallback_summary = (
            f"### Medical History\n"
            f"- Patient Name: {patient.full_name}\n"
            f"- Demographics: {patient.gender}, {((datetime.now().date() - patient.date_of_birth).days // 365)} yrs\n"
            f"- Clinical Record: {len(past_consultations)} previous consultation(s).\n\n"
            f"### Previous Diagnoses\n"
            f"- {past_diagnoses_str}\n\n"
            f"### Historical Treatments\n"
            f"- Review of prior treatments in records.\n\n"
            f"Disclaimer: This summary is generated using only previous consultation records and is intended for clinical reference. It does not include the current consultation."
        )
        return {'summary': fallback_summary}


@main_bp.route('/doctor/patient/<int:patient_id>', methods=['GET'])
def patient_record(patient_id):
    """
    Renders the patient record page displaying personal info, past visits, clinical notes,
    and clinical AI summaries.
    """
    if 'user_id' not in session or session.get('role') != 'doctor':
        flash('Please log in as a doctor to view patient clinical records.', 'warning')
        return redirect(url_for('main.login'))
        
    doctor = Doctor.query.get(session['user_id'])
    if not doctor:
        session.clear()
        flash('Doctor record not found.', 'error')
        return redirect(url_for('main.login'))
        
    patient = Patient.query.get_or_404(patient_id)
    
    # Fetch all past consultations, sorted by date descending
    consultations = Consultation.query.filter_by(patient_id=patient.id).order_by(Consultation.consultation_date.desc()).all()
    
    # Find the latest consultation with an AI summary to show in the summary section
    latest_ai_summary = None
    for c in consultations:
        if c.ai_summary:
            latest_ai_summary = c.ai_summary
            break
            
    return render_template(
        'patient_record.html',
        doctor=doctor,
        patient=patient,
        consultations=consultations,
        latest_ai_summary=latest_ai_summary,
        datetime=datetime
    )


@main_bp.route('/doctor/patients', methods=['GET'])
def doctor_patient_directory():
    """
    Renders a searchable list of patients assigned to the doctor or patients with appointments.
    Doctors cannot add, edit, or delete patients from this directory.
    """
    if 'user_id' not in session or session.get('role') != 'doctor':
        flash('Please log in as a doctor to view the patient directory.', 'warning')
        return redirect(url_for('main.login'))
        
    doctor = Doctor.query.get(session['user_id'])
    if not doctor:
        session.clear()
        flash('Doctor record not found.', 'error')
        return redirect(url_for('main.login'))
        
    # Get unique patient IDs who have appointments or consultations with this doctor
    patient_ids_app = [a.patient_id for a in Appointment.query.filter(Appointment.doctor_id==doctor.id, Appointment.status.in_(['Approved', 'Completed'])).all()]
    patient_ids_cons = [c.patient_id for c in Consultation.query.filter_by(doctor_id=doctor.id).all()]
    all_patient_ids = list(set(patient_ids_app + patient_ids_cons))
    
    if all_patient_ids:
        patients = Patient.query.filter(Patient.id.in_(all_patient_ids)).all()
    else:
        patients = []
        
    # Calculate metadata attributes for templates
    now = datetime.utcnow()
    today_date = datetime.now().date()
    for patient in patients:
        # Age
        if patient.date_of_birth:
            patient.age = today_date.year - patient.date_of_birth.year - (
                (today_date.month, today_date.day) < (patient.date_of_birth.month, patient.date_of_birth.day)
            )
        else:
            patient.age = "N/A"
            
        # Last visit (most recent consultation with this doctor)
        last_consult = Consultation.query.filter_by(
            patient_id=patient.id, doctor_id=doctor.id
        ).order_by(Consultation.consultation_date.desc()).first()
        patient.last_visit = last_consult.consultation_date if last_consult else None
        
        # Next appointment (upcoming approved with this doctor)
        next_app = Appointment.query.filter(
            Appointment.patient_id == patient.id,
            Appointment.doctor_id == doctor.id,
            Appointment.status == 'Approved',
            db.func.date(Appointment.appointment_date) >= today_date
        ).order_by(Appointment.appointment_date.asc()).first()
        patient.next_appointment = next_app
        
        # Active appointment for start consultation action link
        active_app = Appointment.query.filter(
            Appointment.patient_id == patient.id,
            Appointment.doctor_id == doctor.id,
            Appointment.status == 'Approved'
        ).order_by(Appointment.appointment_date.asc()).first()
        patient.active_appointment_id = active_app.id if active_app else None

    return render_template(
        'doctor_patients.html',
        doctor=doctor,
        patients=patients,
        datetime=datetime
    )


@main_bp.route('/admin/dashboard', methods=['GET'])
def admin_dashboard():
    """
    Renders the Admin Dashboard, displaying system metrics, recent activities,
    and sections for managing patients, doctors, and admins.
    """
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an admin to access the dashboard.', 'warning')
        return redirect(url_for('main.login'))
        
    admin = Admin.query.get(session['user_id'])
    if not admin:
        session.clear()
        flash('Admin record not found.', 'error')
        return redirect(url_for('main.login'))
        
    # Stats counts
    total_patients = Patient.query.count()
    total_doctors = Doctor.query.count()
    total_admins = Admin.query.count()
    total_consultations = Consultation.query.count()
    
    # Today's Appointments range in IST, translated to UTC
    now_utc = datetime.utcnow()
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    today_ist = now_ist.date()
    
    start_of_today_ist = datetime.combine(today_ist, datetime.min.time())
    end_of_today_ist = datetime.combine(today_ist, datetime.max.time())
    
    start_of_today = start_of_today_ist - timedelta(hours=5, minutes=30)
    end_of_today = end_of_today_ist - timedelta(hours=5, minutes=30)
    
    today_appointments_count = Appointment.query.filter(
        Appointment.appointment_date >= start_of_today,
        Appointment.appointment_date <= end_of_today
    ).count()
    
    # Query lists for management
    patients = Patient.query.order_by(Patient.created_at.desc()).all()
    doctors = Doctor.query.order_by(Doctor.created_at.desc()).all()
    admins = Admin.query.order_by(Admin.created_at.desc()).all()
    
    # Query system activities (latest 10)
    recent_activities = SystemActivity.query.order_by(SystemActivity.timestamp.desc()).limit(10).all()
    
    # Query pending appointment requests
    pending_appointments = Appointment.query.filter_by(status='Pending Approval').order_by(Appointment.requested_at.asc()).all()
    
    return render_template(
        'admin_dashboard.html',
        admin=admin,
        total_patients=total_patients,
        total_doctors=total_doctors,
        total_admins=total_admins,
        today_appointments_count=today_appointments_count,
        total_consultations=total_consultations,
        patients=patients,
        doctors=doctors,
        admins=admins,
        recent_activities=recent_activities,
        pending_appointments=pending_appointments,
        datetime=datetime
    )


@main_bp.route('/admin/add-doctor', methods=['POST'])
def admin_add_doctor():
    """
    Processes creation of a new doctor from the Admin Dashboard and logs System Activity.
    """
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Unauthorized.', 'error')
        return redirect(url_for('main.login'))
        
    admin = Admin.query.get(session['user_id'])
    if not admin:
        session.clear()
        return redirect(url_for('main.login'))
        
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    specialization = request.form.get('specialization')
    license_number = request.form.get('license_number')
    experience_years_str = request.form.get('experience_years')
    password = request.form.get('password')
    
    consultation_days = request.form.get('consultation_days', 'Monday-Friday')
    morning_start = request.form.get('morning_start', '09:00 AM')
    morning_end = request.form.get('morning_end', '01:00 PM')
    afternoon_start = request.form.get('afternoon_start', '02:00 PM')
    afternoon_end = request.form.get('afternoon_end', '05:00 PM')
    
    if not all([first_name, last_name, email, specialization, license_number, password]):
        flash('Please fill in all required fields.', 'error')
        return redirect(url_for('main.admin_dashboard'))
        
    try:
        # Check uniqueness
        if Doctor.query.filter_by(email=email).first() or Patient.query.filter_by(email=email).first():
            flash('Email is already registered.', 'error')
            return redirect(url_for('main.admin_dashboard', tab='doctors'))
            
        if Doctor.query.filter_by(license_number=license_number).first():
            flash('License number is already registered.', 'error')
            return redirect(url_for('main.admin_dashboard', tab='doctors'))
            
        new_doc = Doctor(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            specialization=specialization,
            license_number=license_number,
            experience_years=int(experience_years_str or 0),
            consultation_days=consultation_days,
            morning_start=morning_start,
            morning_end=morning_end,
            afternoon_start=afternoon_start,
            afternoon_end=afternoon_end
        )
        new_doc.set_password(password)
        db.session.add(new_doc)
        db.session.flush()
        
        # Save weekly session availability
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for day in days:
            available = request.form.get(f'avail_{day}') == '1'
            morn = request.form.get(f'avail_{day}_morning') == '1'
            morn_start = request.form.get(f'avail_{day}_morning_start', '09:00 AM')
            morn_end = request.form.get(f'avail_{day}_morning_end', '01:00 PM')
            aft = request.form.get(f'avail_{day}_afternoon') == '1'
            aft_start = request.form.get(f'avail_{day}_afternoon_start', '02:00 PM')
            aft_end = request.form.get(f'avail_{day}_afternoon_end', '05:00 PM')
            
            avail = DoctorAvailability(
                doctor_id=new_doc.id,
                day=day,
                available=available,
                morning=morn,
                morning_start=morn_start,
                morning_end=morn_end,
                afternoon=aft,
                afternoon_start=aft_start,
                afternoon_end=aft_end
            )
            db.session.add(avail)
        
        # Log System Activity
        activity = SystemActivity(
            activity_name="Doctor Added",
            user=f"Admin {admin.username}"
        )
        db.session.add(activity)
        db.session.commit()
        
        flash(f"Successfully registered Dr. {new_doc.full_name}!", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to add doctor: {str(e)}", 'error')
        
    return redirect(url_for('main.admin_dashboard', tab='doctors'))


@main_bp.route('/admin/add-admin', methods=['POST'])
def admin_add_admin():
    """
    Processes creation of a new administrator from the Admin Dashboard and logs System Activity.
    """
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Unauthorized.', 'error')
        return redirect(url_for('main.login'))
        
    admin = Admin.query.get(session['user_id'])
    if not admin:
        session.clear()
        return redirect(url_for('main.login'))
        
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not all([username, email, password]):
        flash('Please fill in all required fields.', 'error')
        return redirect(url_for('main.admin_dashboard'))
        
    try:
        # Check uniqueness
        if Admin.query.filter_by(username=username).first():
            flash('Username is already taken.', 'error')
            return redirect(url_for('main.admin_dashboard', tab='admins'))
            
        if Admin.query.filter_by(email=email).first() or Patient.query.filter_by(email=email).first():
            flash('Email is already registered.', 'error')
            return redirect(url_for('main.admin_dashboard', tab='admins'))
            
        new_adm = Admin(
            username=username,
            email=email
        )
        new_adm.set_password(password)
        db.session.add(new_adm)
        
        # Log System Activity
        activity = SystemActivity(
            activity_name="Admin Added",
            user=f"Admin {admin.username}"
        )
        db.session.add(activity)
        db.session.commit()
        
        flash(f"Successfully added Admin {new_adm.username}!", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to add admin: {str(e)}", 'error')
        
    return redirect(url_for('main.admin_dashboard', tab='admins'))


@main_bp.route('/admin/users', methods=['GET'])
def admin_users():
    """
    Renders the Manage Users page containing complete directory tables for
    Patients, Doctors, and Admins. Supports tabs, search, and CRUD dialogs.
    """
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an admin to access user management.', 'warning')
        return redirect(url_for('main.login'))
        
    admin = Admin.query.get(session['user_id'])
    if not admin:
        session.clear()
        return redirect(url_for('main.login'))
        
    patients = Patient.query.order_by(Patient.created_at.desc()).all()
    doctors = Doctor.query.order_by(Doctor.created_at.desc()).all()
    admins = Admin.query.order_by(Admin.created_at.desc()).all()
    
    return render_template(
        'manage_users.html',
        admin=admin,
        patients=patients,
        doctors=doctors,
        admins=admins,
        datetime=datetime
    )


@main_bp.route('/admin/user/patient/edit/<int:patient_id>', methods=['POST'])
def edit_patient(patient_id):
    """
    Processes updates for a patient profile.
    """
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an administrator to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    patient = Patient.query.get_or_404(patient_id)
    
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    blood_group = request.form.get('blood_group')
    address = request.form.get('address')
    dob_str = request.form.get('date_of_birth')
    
    if not all([first_name, last_name, email, dob_str]):
        flash('Required fields are missing.', 'error')
        return redirect(url_for('main.admin_users', tab='patients'))
        
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
        if dob > datetime.now().date():
            flash('Date of birth cannot be in the future.', 'error')
            return redirect(url_for('main.admin_users', tab='patients'))
            
        # Check uniqueness of email (excluding self)
        existing = Patient.query.filter(Patient.email == email, Patient.id != patient.id).first() or \
                   Doctor.query.filter_by(email=email).first()
        if existing:
            flash('Email address is already in use.', 'error')
            return redirect(url_for('main.admin_users', tab='patients'))
            
        patient.first_name = first_name
        patient.last_name = last_name
        patient.email = email
        patient.phone = phone
        patient.blood_group = blood_group
        patient.address = address
        patient.date_of_birth = dob
        
        db.session.commit()
        flash(f"Successfully updated Patient {patient.full_name}.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to update patient: {str(e)}", 'error')
        
    return redirect(url_for('main.admin_users', tab='patients'))


@main_bp.route('/admin/user/patient/delete/<int:patient_id>', methods=['POST'])
def delete_patient(patient_id):
    """
    Deletes a patient record and cascaded dependencies (appointments, consultations).
    """
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an administrator to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    patient = Patient.query.get_or_404(patient_id)
    try:
        db.session.delete(patient)
        db.session.commit()
        flash(f"Successfully deleted Patient {patient.full_name} and all associated records.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete patient: {str(e)}", 'error')
        
    return redirect(url_for('main.admin_users', tab='patients'))


@main_bp.route('/admin/user/doctor/edit/<int:doctor_id>', methods=['POST'])
def edit_doctor(doctor_id):
    """
    Updates doctor clinical records. Logs System Activity.
    """
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an administrator to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    admin = Admin.query.get(session['user_id'])
    doctor = Doctor.query.get_or_404(doctor_id)
    
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    specialization = request.form.get('specialization')
    license_number = request.form.get('license_number')
    experience_years = request.form.get('experience_years')
    password = request.form.get('password')
    
    consultation_days = request.form.get('consultation_days', 'Monday-Friday')
    morning_start = request.form.get('morning_start', '09:00 AM')
    morning_end = request.form.get('morning_end', '01:00 PM')
    afternoon_start = request.form.get('afternoon_start', '02:00 PM')
    afternoon_end = request.form.get('afternoon_end', '05:00 PM')
    
    if not all([first_name, last_name, email, specialization, license_number]):
        flash('Required fields are missing.', 'error')
        return redirect(url_for('main.admin_users', tab='doctors'))
        
    try:
        # Check uniqueness of email and license
        existing_email = Doctor.query.filter(Doctor.email == email, Doctor.id != doctor.id).first() or \
                         Patient.query.filter_by(email=email).first()
        if existing_email:
            flash('Email address is already in use.', 'error')
            return redirect(url_for('main.admin_users', tab='doctors'))
            
        existing_license = Doctor.query.filter(Doctor.license_number == license_number, Doctor.id != doctor.id).first()
        if existing_license:
            flash('License number is already registered by another doctor.', 'error')
            return redirect(url_for('main.admin_users', tab='doctors'))
            
        doctor.first_name = first_name
        doctor.last_name = last_name
        doctor.email = email
        doctor.phone = phone
        doctor.specialization = specialization
        doctor.license_number = license_number
        doctor.experience_years = int(experience_years or 0)
        doctor.consultation_days = consultation_days
        doctor.morning_start = morning_start
        doctor.morning_end = morning_end
        doctor.afternoon_start = afternoon_start
        doctor.afternoon_end = afternoon_end
        
        if password and password.strip() != '':
            doctor.set_password(password)
            
        # Update weekly session availability
        DoctorAvailability.query.filter_by(doctor_id=doctor.id).delete()
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for day in days:
            available = request.form.get(f'avail_{day}') == '1'
            morn = request.form.get(f'avail_{day}_morning') == '1'
            morn_start = request.form.get(f'avail_{day}_morning_start', '09:00 AM')
            morn_end = request.form.get(f'avail_{day}_morning_end', '01:00 PM')
            aft = request.form.get(f'avail_{day}_afternoon') == '1'
            aft_start = request.form.get(f'avail_{day}_afternoon_start', '02:00 PM')
            aft_end = request.form.get(f'avail_{day}_afternoon_end', '05:00 PM')
            
            avail = DoctorAvailability(
                doctor_id=doctor.id,
                day=day,
                available=available,
                morning=morn,
                morning_start=morn_start,
                morning_end=morn_end,
                afternoon=aft,
                afternoon_start=aft_start,
                afternoon_end=aft_end
            )
            db.session.add(avail)
            
        # Log System Activity
        activity = SystemActivity(
            activity_name="Doctor Updated",
            user=f"Admin {admin.username}"
        )
        db.session.add(activity)
        db.session.commit()
        
        flash(f"Successfully updated Dr. {doctor.full_name}.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to update doctor: {str(e)}", 'error')
        
    return redirect(url_for('main.admin_users', tab='doctors'))


@main_bp.route('/admin/user/doctor/delete/<int:doctor_id>', methods=['POST'])
def delete_doctor(doctor_id):
    """
    Deletes a doctor account. Logs System Activity.
    """
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an administrator to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    admin = Admin.query.get(session['user_id'])
    doctor = Doctor.query.get_or_404(doctor_id)
    try:
        db.session.delete(doctor)
        
        # Log System Activity
        activity = SystemActivity(
            activity_name="Doctor Deleted",
            user=f"Admin {admin.username}"
        )
        db.session.add(activity)
        db.session.commit()
        flash(f"Successfully deleted Dr. {doctor.full_name} and all associated records.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete doctor: {str(e)}", 'error')
        
    return redirect(url_for('main.admin_users', tab='doctors'))


@main_bp.route('/admin/user/admin/edit/<int:admin_id>', methods=['POST'])
def edit_admin(admin_id):
    """
    Updates administrative profiles. Logs System Activity.
    """
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an administrator to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    logged_admin = Admin.query.get(session['user_id'])
    target_admin = Admin.query.get_or_404(admin_id)
    
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not all([username, email]):
        flash('Required fields are missing.', 'error')
        return redirect(url_for('main.admin_users', tab='admins'))
        
    try:
        # Check uniqueness of username and email
        existing_user = Admin.query.filter(Admin.username == username, Admin.id != target_admin.id).first()
        if existing_user:
            flash('Username is already taken.', 'error')
            return redirect(url_for('main.admin_users', tab='admins'))
            
        existing_email = Admin.query.filter(Admin.email == email, Admin.id != target_admin.id).first() or \
                         Patient.query.filter_by(email=email).first()
        if existing_email:
            flash('Email address is already in use.', 'error')
            return redirect(url_for('main.admin_users', tab='admins'))
            
        target_admin.username = username
        target_admin.email = email
        
        if password and password.strip() != '':
            target_admin.set_password(password)
            
        # Log System Activity
        activity = SystemActivity(
            activity_name="Admin Updated",
            user=f"Admin {logged_admin.username}"
        )
        db.session.add(activity)
        db.session.commit()
        
        # If editing oneself, update session username
        if logged_admin.id == target_admin.id:
            session['user_name'] = target_admin.username
            
        flash(f"Successfully updated Admin {target_admin.username}.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to update admin: {str(e)}", 'error')
        
    return redirect(url_for('main.admin_users', tab='admins'))


@main_bp.route('/admin/user/admin/delete/<int:admin_id>', methods=['POST'])
def delete_admin(admin_id):
    """
    Deletes an admin account. Prevents deleting active profile. Logs System Activity.
    """
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an administrator to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    logged_admin = Admin.query.get(session['user_id'])
    if logged_admin.id == admin_id:
        flash('Deletion blocked: You cannot delete your own administrative account.', 'error')
        return redirect(url_for('main.admin_users', tab='admins'))
        
    target_admin = Admin.query.get_or_404(admin_id)
    try:
        db.session.delete(target_admin)
        
        # Log System Activity
        activity = SystemActivity(
            activity_name="Admin Deleted",
            user=f"Admin {logged_admin.username}"
        )
        db.session.add(activity)
        db.session.commit()
        flash(f"Successfully deleted Admin {target_admin.username}.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete admin: {str(e)}", 'error')
        
    return redirect(url_for('main.admin_users', tab='admins'))


# =============================================================================
# Patient-Centered Digital Healthcare Management System Routes
# =============================================================================

ALLOWED_REPORT_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_REPORT_EXTENSIONS


@main_bp.route('/patient/appointment/cancel/<int:appointment_id>', methods=['POST'])
def cancel_appointment(appointment_id):
    if 'user_id' not in session or session.get('role') != 'patient':
        flash('Please log in as a patient to cancel appointments.', 'warning')
        return redirect(url_for('main.login'))
        
    patient = Patient.query.get(session['user_id'])
    if not patient:
        session.clear()
        return redirect(url_for('main.login'))
        
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.patient_id != patient.id:
        flash('Unauthorized action.', 'error')
        return redirect(url_for('main.patient_dashboard'))
        
    # Check if consultation or appointment status is already completed
    if appointment.status == 'Completed' or appointment.consultation is not None:
        flash('The appointment cannot be cancelled because the consultation has already been completed.', 'error')
        return redirect(url_for('main.patient_dashboard'))
        
    if appointment.status == 'Cancelled':
        flash('This appointment is already cancelled.', 'info')
        return redirect(url_for('main.patient_dashboard'))
        
    try:
        prev_status = appointment.status
        cancellation_reason = request.form.get('cancellation_reason')
        if cancellation_reason:
            cancellation_reason = cancellation_reason.strip()
            if not cancellation_reason:
                cancellation_reason = None
        else:
            cancellation_reason = None

        appointment.status = 'Cancelled'
        appointment.cancelled_at = datetime.utcnow()
        appointment.cancellation_reason = cancellation_reason
        
        # Create notification for patient
        notif = Notification(
            patient_id=appointment.patient_id,
            title="Appointment Cancelled",
            message="Your appointment has been cancelled successfully."
        )
        db.session.add(notif)
        
        # Log System Activity to notify the admin immediately
        app_date_str = appointment.appointment_date.strftime('%B %d, %Y')
        log_user = (
            f"Patient: {patient.full_name} | "
            f"Doctor: Dr. {appointment.doctor.full_name} | "
            f"Date: {app_date_str} | "
            f"Previous Status: {prev_status} | "
            f"Reason: {cancellation_reason if cancellation_reason else 'None'}"
        )
        
        activity = SystemActivity(
            activity_name="Patient Cancelled Appointment",
            user=log_user
        )
        db.session.add(activity)
        db.session.commit()
        flash('Your appointment has been cancelled successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to cancel appointment: {str(e)}', 'error')
        
    return redirect(url_for('main.patient_dashboard', tab='dashboard'))



@main_bp.route('/doctor/upload-report/<int:consultation_id>', methods=['POST'])
def upload_report(consultation_id):
    if 'user_id' not in session or session.get('role') != 'doctor':
        flash('Please log in as a doctor to upload reports.', 'warning')
        return redirect(url_for('main.login'))
        
    doctor = Doctor.query.get(session['user_id'])
    if not doctor:
        session.clear()
        return redirect(url_for('main.login'))
        
    consultation = Consultation.query.get_or_404(consultation_id)
    if consultation.doctor_id != doctor.id:
        flash('You are not authorized to upload reports for this consultation.', 'error')
        return redirect(url_for('main.doctor_dashboard'))
        
    report_type = request.form.get('report_type')
    valid_types = ['Blood Test Reports', 'MRI', 'CT Scan', 'X-Ray', 'ECG', 'Prescription PDFs', 'Medical Certificates', 'Lab Reports']
    if report_type not in valid_types:
        flash('Invalid report type selected.', 'error')
        return redirect(url_for('main.patient_record', patient_id=consultation.patient_id))
        
    if 'report_file' not in request.files:
        flash('No file part in the request.', 'error')
        return redirect(url_for('main.patient_record', patient_id=consultation.patient_id))
        
    file = request.files['report_file']
    if file.filename == '':
        flash('No file selected for upload.', 'error')
        return redirect(url_for('main.patient_record', patient_id=consultation.patient_id))
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'reports')
        os.makedirs(upload_folder, exist_ok=True)
        
        unique_filename = f"{consultation.patient_id}_{consultation.id}_{int(datetime.utcnow().timestamp())}_{filename}"
        file_path = os.path.join('static', 'uploads', 'reports', unique_filename)
        full_dest_path = os.path.join(current_app.root_path, file_path)
        
        try:
            file.save(full_dest_path)
            
            # Create MedicalReport record
            new_report = MedicalReport(
                patient_id=consultation.patient_id,
                doctor_id=doctor.id,
                consultation_id=consultation.id,
                file_name=filename,
                file_path=file_path,
                report_type=report_type
            )
            db.session.add(new_report)
            
            # Log System Activity
            activity = SystemActivity(
                activity_name="Report Uploaded",
                user=f"Dr. {doctor.full_name}"
            )
            db.session.add(activity)
            db.session.commit()
            
            flash(f'Report "{filename}" successfully uploaded and saved.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to upload report file: {str(e)}', 'error')
    else:
        flash('File type not allowed. Please upload a PDF, image, or document.', 'error')
        
    return redirect(url_for('main.patient_record', patient_id=consultation.patient_id))


@main_bp.route('/report/download/<int:report_id>')
def download_report(report_id):
    if 'user_id' not in session:
        flash('Please log in to access this report.', 'warning')
        return redirect(url_for('main.login'))
        
    report = MedicalReport.query.get_or_404(report_id)
    role = session.get('role')
    user_id = session.get('user_id')
    
    # Patients can only download their own reports, doctors and admins can download any patient's reports
    if role == 'patient' and report.patient_id != user_id:
        flash('You are not authorized to access this report.', 'error')
        return redirect(url_for('main.patient_dashboard'))
    elif role not in ['patient', 'doctor', 'admin']:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('main.login'))
        
    directory = os.path.join(current_app.root_path, 'static', 'uploads', 'reports')
    filename = os.path.basename(report.file_path)
    return send_from_directory(directory, filename, as_attachment=False)


@main_bp.route('/patient/profile-photo/upload', methods=['POST'])
def upload_profile_photo():
    if 'user_id' not in session or session.get('role') != 'patient':
        flash('Please log in as a patient to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    patient = Patient.query.get(session['user_id'])
    if not patient:
        session.clear()
        return redirect(url_for('main.login'))
        
    if 'profile_photo' not in request.files:
        flash('No file part in the request.', 'error')
        return redirect(url_for('main.patient_dashboard', tab='profile'))
        
    file = request.files['profile_photo']
    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('main.patient_dashboard', tab='profile'))
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
        os.makedirs(upload_folder, exist_ok=True)
        
        unique_filename = f"avatar_{patient.id}_{int(datetime.utcnow().timestamp())}_{filename}"
        file_path = os.path.join('static', 'uploads', 'profiles', unique_filename)
        full_dest_path = os.path.join(current_app.root_path, file_path)
        
        try:
            file.save(full_dest_path)
            patient.profile_photo = file_path
            db.session.commit()
            flash('Profile photo updated successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to save profile photo: {str(e)}', 'error')
    else:
        flash('File type not allowed. Please upload a PDF, image, or document.', 'error')
        
    return redirect(url_for('main.patient_dashboard', tab='profile'))


@main_bp.route('/admin/appointment/approve/<int:appointment_id>', methods=['POST'])
def admin_approve_appointment(appointment_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an admin to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    admin = Admin.query.get(session['user_id'])
    if not admin:
        session.clear()
        return redirect(url_for('main.login'))
        
    appointment = Appointment.query.get_or_404(appointment_id)
    
    # Check for leave conflict
    leave = DoctorLeave.query.filter(
        DoctorLeave.doctor_id == appointment.doctor_id,
        DoctorLeave.leave_date == db.func.date(appointment.appointment_date)
    ).first()
    if leave and (leave.session == 'Full Day' or leave.session == appointment.session):
        flash("This appointment conflicts with the doctor's leave schedule.", "error")
        return redirect(url_for('main.admin_appointment_conflict', appointment_id=appointment.id))
        
    appointment.status = 'Approved'
    appointment.approved_at = datetime.utcnow()
    appointment.approved_by = admin.id
    
    # Create notification for patient
    notif = Notification(
        patient_id=appointment.patient_id,
        title="Appointment Confirmed",
        message="Your appointment has been confirmed."
    )
    db.session.add(notif)
    
    # Log System Activity
    activity = SystemActivity(
        activity_name="Appointment Confirmed",
        user=f"Admin: {admin.username}"
    )
    db.session.add(activity)
    db.session.commit()
    
    flash('Appointment request has been approved successfully.', 'success')
    return redirect(url_for('main.admin_dashboard'))


@main_bp.route('/admin/appointment/reject/<int:appointment_id>', methods=['POST'])
def admin_reject_appointment(appointment_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an admin to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    admin = Admin.query.get(session['user_id'])
    if not admin:
        session.clear()
        return redirect(url_for('main.login'))
        
    appointment = Appointment.query.get_or_404(appointment_id)
    rejection_reason = request.form.get('rejection_reason', '').strip()
    
    appointment.status = 'Rejected'
    appointment.approved_at = datetime.utcnow()
    appointment.approved_by = admin.id
    appointment.rejection_reason = rejection_reason if rejection_reason else None
    
    # Create notification for patient
    message = "Your appointment request has been rejected."
    if rejection_reason:
        message += f" Reason: {rejection_reason}"
        
    notif = Notification(
        patient_id=appointment.patient_id,
        title="Appointment Cancelled",
        message=message
    )
    db.session.add(notif)
    
    # Log System Activity
    activity = SystemActivity(
        activity_name="Appointment Rejected",
        user=f"Admin: {admin.username}"
    )
    db.session.add(activity)
    db.session.commit()
    
    flash('Appointment request has been rejected.', 'info')
    return redirect(url_for('main.admin_dashboard'))


# =============================================================================
# Doctor Leave Management & Conflicts Routes
# =============================================================================

def get_affected_appointments(doctor_id, leave_date, session_type):
    query = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        db.func.date(Appointment.appointment_date) == leave_date,
        Appointment.status.in_(['Approved', 'Confirmed'])
    )
    if session_type == 'Morning':
        query = query.filter(Appointment.session == 'Morning')
    elif session_type == 'Afternoon':
        query = query.filter(Appointment.session == 'Afternoon')
    return query.all()

def is_doctor_available_day(doctor, target_date):
    """
    Checks if a doctor is scheduled to work on a target date based on consultation_days.
    """
    weekday_name = target_date.strftime('%A')
    days_str = doctor.consultation_days or 'Monday-Friday'
    
    # Standard mappings
    if 'Monday-Friday' in days_str:
        return weekday_name in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    if 'Saturday-Sunday' in days_str or 'Weekend' in days_str:
        return weekday_name in ['Saturday', 'Sunday']
    if 'Everyday' in days_str or 'Monday-Sunday' in days_str or 'All' in days_str:
        return True
        
    import re
    parts = re.split(r'[\s,\-]+', days_str.lower())
    return weekday_name.lower() in parts

def find_next_available_slot(doctor, orig_date, orig_session):
    """
    Finds the earliest available slot (date and session) for a doctor starting from orig_date
    within a 30-day scheduling window.
    """
    for i in range(0, 31):
        target_date = orig_date + timedelta(days=i)
        if is_doctor_available_day(doctor, target_date):
            # Check leaves on this date
            leaves = DoctorLeave.query.filter_by(doctor_id=doctor.id, leave_date=target_date).all()
            
            # Check what leaves exist
            has_morning = any(l.session in ['Morning', 'Full Day'] for l in leaves)
            has_afternoon = any(l.session in ['Afternoon', 'Full Day'] for l in leaves)
            
            if i == 0:
                # Same day: can only check/suggest the alternative session
                if orig_session == 'Morning' and not has_afternoon:
                    return target_date, 'Afternoon'
                elif orig_session == 'Afternoon' and not has_morning:
                    return target_date, 'Morning'
            else:
                # Future day: Morning is preferred, else Afternoon
                if not has_morning:
                    return target_date, 'Morning'
                elif not has_afternoon:
                    return target_date, 'Afternoon'
                    
    return None


@main_bp.route('/admin/leaves', methods=['GET', 'POST'])
def admin_leaves():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an administrator to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    admin = Admin.query.get(session['user_id'])
    if not admin:
        session.clear()
        return redirect(url_for('main.login'))
        
    if request.method == 'POST':
        doctor_id = request.form.get('doctor_id')
        leave_date_str = request.form.get('leave_date')
        session_val = request.form.get('session')
        reason = request.form.get('reason', '').strip()
        
        if not doctor_id or not leave_date_str or not session_val:
            flash('Please select a doctor, leave date, and session.', 'error')
            return redirect(url_for('main.admin_leaves'))
            
        try:
            leave_date = datetime.strptime(leave_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'error')
            return redirect(url_for('main.admin_leaves'))
            
        # Check if leave record already exists
        existing_leave = DoctorLeave.query.filter_by(
            doctor_id=int(doctor_id),
            leave_date=leave_date,
            session=session_val
        ).first()
        
        if existing_leave:
            flash('A leave record already exists for this doctor, date, and session.', 'error')
            return redirect(url_for('main.admin_leaves'))
            
        try:
            new_leave = DoctorLeave(
                doctor_id=int(doctor_id),
                leave_date=leave_date,
                session=session_val,
                reason=reason if reason else None
            )
            db.session.add(new_leave)
            
            # Log System Activity
            activity = SystemActivity(
                activity_name="Doctor Leave Added",
                user=f"Admin: {admin.username}"
            )
            db.session.add(activity)
            db.session.commit()
            
            # Check for affected appointments
            affected = get_affected_appointments(int(doctor_id), leave_date, session_val)
            if affected:
                flash(f'There are {len(affected)} confirmed appointments affected by this leave.', 'warning')
                return redirect(url_for('main.admin_leaves_conflict', leave_id=new_leave.id))
                
            flash('Doctor leave record added successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to add leave record: {str(e)}', 'error')
            
        return redirect(url_for('main.admin_leaves'))
        
    # GET request: Search and list leaves
    doctor_search = request.args.get('doctor', '').strip()
    date_search = request.args.get('date', '').strip()
    
    query = DoctorLeave.query.join(Doctor)
    if doctor_search:
        query = query.filter(
            (Doctor.first_name.like(f"%{doctor_search}%")) |
            (Doctor.last_name.like(f"%{doctor_search}%"))
        )
    if date_search:
        try:
            search_date = datetime.strptime(date_search, '%Y-%m-%d').date()
            query = query.filter(DoctorLeave.leave_date == search_date)
        except ValueError:
            pass
            
    leaves = query.order_by(DoctorLeave.leave_date.desc()).all()
    doctors = Doctor.query.order_by(Doctor.last_name.asc(), Doctor.first_name.asc()).all()
    
    return render_template(
        'admin_doctor_leaves.html',
        admin=admin,
        leaves=leaves,
        doctors=doctors,
        doctor_search=doctor_search,
        date_search=date_search
    )

@main_bp.route('/admin/leaves/edit/<int:leave_id>', methods=['POST'])
def admin_edit_leave(leave_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an administrator to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    admin = Admin.query.get(session['user_id'])
    leave = DoctorLeave.query.get_or_404(leave_id)
    
    doctor_id = request.form.get('doctor_id')
    leave_date_str = request.form.get('leave_date')
    session_val = request.form.get('session')
    reason = request.form.get('reason', '').strip()
    
    if not doctor_id or not leave_date_str or not session_val:
        flash('Please select a doctor, leave date, and session.', 'error')
        return redirect(url_for('main.admin_leaves'))
        
    try:
        leave_date = datetime.strptime(leave_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format. Please use YYYY-MM-DD.', 'error')
        return redirect(url_for('main.admin_leaves'))
        
    try:
        leave.doctor_id = int(doctor_id)
        leave.leave_date = leave_date
        leave.session = session_val
        leave.reason = reason if reason else None
        
        # Log System Activity
        activity = SystemActivity(
            activity_name="Doctor Leave Updated",
            user=f"Admin: {admin.username}"
        )
        db.session.add(activity)
        db.session.commit()
        
        # Check for affected appointments
        affected = get_affected_appointments(int(doctor_id), leave_date, session_val)
        if affected:
            flash(f'There are {len(affected)} confirmed appointments affected by this leave.', 'warning')
            return redirect(url_for('main.admin_leaves_conflict', leave_id=leave.id))
            
        flash('Doctor leave record updated successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to update leave record: {str(e)}', 'error')
        
    return redirect(url_for('main.admin_leaves'))

@main_bp.route('/admin/leaves/delete/<int:leave_id>', methods=['POST'])
def admin_delete_leave(leave_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an administrator to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    admin = Admin.query.get(session['user_id'])
    leave = DoctorLeave.query.get_or_404(leave_id)
    
    try:
        db.session.delete(leave)
        
        # Log System Activity
        activity = SystemActivity(
            activity_name="Doctor Leave Deleted",
            user=f"Admin: {admin.username}"
        )
        db.session.add(activity)
        db.session.commit()
        flash('Doctor leave record deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to delete leave record: {str(e)}', 'error')
        
    return redirect(url_for('main.admin_leaves'))

@main_bp.route('/admin/leaves/conflict/<int:leave_id>')
def admin_leaves_conflict(leave_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an administrator to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    admin = Admin.query.get(session['user_id'])
    leave = DoctorLeave.query.get_or_404(leave_id)
    
    affected = get_affected_appointments(leave.doctor_id, leave.leave_date, leave.session)
    
    # Calculate suggestion for each appointment
    appointments_with_suggestions = []
    for app in affected:
        slot = find_next_available_slot(app.doctor, app.appointment_date.date(), app.session)
        if slot:
            s_date, s_session = slot
            suggestion = {
                'date_str': s_date.strftime('%Y-%m-%d'),
                'display_date': s_date.strftime('%B %d, %Y'),
                'session': s_session
            }
        else:
            suggestion = None
        appointments_with_suggestions.append({
            'appointment': app,
            'suggestion': suggestion
        })
        
    return render_template(
        'admin_leaves_conflict.html',
        admin=admin,
        leave=leave,
        appointments=appointments_with_suggestions
    )

@main_bp.route('/admin/appointment/conflict/<int:appointment_id>')
def admin_appointment_conflict(appointment_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an administrator to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    admin = Admin.query.get(session['user_id'])
    appointment = Appointment.query.get_or_404(appointment_id)
    
    # Calculate suggestion
    slot = find_next_available_slot(appointment.doctor, appointment.appointment_date.date(), appointment.session)
    if slot:
        s_date, s_session = slot
        suggestion = {
            'date_str': s_date.strftime('%Y-%m-%d'),
            'display_date': s_date.strftime('%B %d, %Y'),
            'session': s_session
        }
    else:
        suggestion = None
        
    return render_template(
        'admin_appointment_conflict.html',
        admin=admin,
        appointment=appointment,
        suggestion=suggestion
    )

@main_bp.route('/admin/appointment/reschedule/<int:appointment_id>', methods=['POST'])
def admin_reschedule_appointment(appointment_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an administrator to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    admin = Admin.query.get(session['user_id'])
    appointment = Appointment.query.get_or_404(appointment_id)
    leave_id = request.form.get('leave_id')
    
    new_date_str = request.form.get('new_date')
    new_session = request.form.get('new_session')
    
    if not new_date_str or not new_session:
        flash('New Date and Session are required.', 'error')
        if leave_id:
            return redirect(url_for('main.admin_leaves_conflict', leave_id=leave_id))
        return redirect(url_for('main.admin_leaves'))
        
    try:
        new_date = datetime.strptime(new_date_str, '%Y-%m-%d')
        appointment.appointment_date = new_date
        appointment.session = new_session
        
        # Keep status as Confirmed/Approved
        if appointment.status == 'Pending Approval':
            appointment.status = 'Approved'
            
        # Create notification for patient
        notif = Notification(
            patient_id=appointment.patient_id,
            title="Appointment Rescheduled",
            message="Your appointment has been rescheduled to the next available date because your doctor is on leave."
        )
        db.session.add(notif)
        
        # Log System Activity
        activity = SystemActivity(
            activity_name="Appointment Rescheduled",
            user=f"Admin: {admin.username}"
        )
        db.session.add(activity)
        db.session.commit()
        
        flash('Appointment has been rescheduled successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to reschedule appointment: {str(e)}', 'error')
        
    if leave_id:
        leave = DoctorLeave.query.get(leave_id)
        if leave:
            remaining = get_affected_appointments(leave.doctor_id, leave.leave_date, leave.session)
            if remaining:
                return redirect(url_for('main.admin_leaves_conflict', leave_id=leave_id))
                
    return redirect(url_for('main.admin_leaves'))

@main_bp.route('/admin/appointment/accept-suggestion/<int:appointment_id>', methods=['POST'])
def admin_accept_suggestion(appointment_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an administrator to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    admin = Admin.query.get(session['user_id'])
    appointment = Appointment.query.get_or_404(appointment_id)
    leave_id = request.form.get('leave_id')
    
    suggested_date_str = request.form.get('suggested_date')
    suggested_session = request.form.get('suggested_session')
    
    if not suggested_date_str or not suggested_session:
        flash('Suggestion parameters are missing.', 'error')
        if leave_id:
            return redirect(url_for('main.admin_leaves_conflict', leave_id=leave_id))
        return redirect(url_for('main.admin_leaves'))
        
    try:
        new_date = datetime.strptime(suggested_date_str, '%Y-%m-%d')
        appointment.appointment_date = new_date
        appointment.session = suggested_session
        
        # Keep status as Confirmed/Approved
        if appointment.status == 'Pending Approval':
            appointment.status = 'Approved'
            
        # Create notification for patient
        notif = Notification(
            patient_id=appointment.patient_id,
            title="Appointment Rescheduled",
            message="Your appointment has been rescheduled to the next available date because your doctor is on leave."
        )
        db.session.add(notif)
        
        # Log System Activity
        activity = SystemActivity(
            activity_name="Appointment Rescheduled (Suggestion Accepted)",
            user=f"Admin: {admin.username}"
        )
        db.session.add(activity)
        db.session.commit()
        
        flash('Appointment rescheduled to the suggested slot successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to reschedule appointment: {str(e)}', 'error')
        
    if leave_id:
        leave = DoctorLeave.query.get(leave_id)
        if leave:
            remaining = get_affected_appointments(leave.doctor_id, leave.leave_date, leave.session)
            if remaining:
                return redirect(url_for('main.admin_leaves_conflict', leave_id=leave_id))
                
    return redirect(url_for('main.admin_leaves'))

@main_bp.route('/admin/appointment/cancel-by-leave/<int:appointment_id>', methods=['POST'])
def admin_cancel_appointment_by_leave(appointment_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as an administrator to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    admin = Admin.query.get(session['user_id'])
    appointment = Appointment.query.get_or_404(appointment_id)
    leave_id = request.form.get('leave_id')
    
    try:
        appointment.status = 'Cancelled'
        
        # Create notification for patient
        notif = Notification(
            patient_id=appointment.patient_id,
            title="Appointment Cancelled",
            message="Your appointment has been cancelled because your doctor is unavailable. Please book another appointment or contact the hospital."
        )
        db.session.add(notif)
        
        # Log System Activity
        activity = SystemActivity(
            activity_name="Appointment Cancelled by Admin",
            user=f"Admin: {admin.username}"
        )
        db.session.add(activity)
        db.session.commit()
        
        flash('Appointment cancelled successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to cancel appointment: {str(e)}', 'error')
        
    if leave_id:
        leave = DoctorLeave.query.get(leave_id)
        if leave:
            remaining = get_affected_appointments(leave.doctor_id, leave.leave_date, leave.session)
            if remaining:
                return redirect(url_for('main.admin_leaves_conflict', leave_id=leave_id))
                
    return redirect(url_for('main.admin_leaves'))

@main_bp.route('/patient/notification/read/<int:notification_id>', methods=['POST'])
def mark_notification_read(notification_id):
    if 'user_id' not in session or session.get('role') != 'patient':
        flash('Please log in as a patient to perform this action.', 'warning')
        return redirect(url_for('main.login'))
        
    patient = Patient.query.get(session['user_id'])
    if not patient:
        session.clear()
        return redirect(url_for('main.login'))
        
    notif = Notification.query.filter_by(id=notification_id, patient_id=patient.id).first_or_404()
    try:
        notif.is_read = True
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking notification as read: {e}")
        
    return redirect(url_for('main.patient_dashboard', tab='dashboard'))






