import unittest
from datetime import datetime, timedelta
from app import create_app
from database import db
from models import Patient, Doctor, Appointment, Consultation, Admin, SystemActivity, MedicalReport, Notification, DoctorLeave

class TestPatientDashboard(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_dashboard_access_and_flow(self):
        # 1. Access dashboard without logging in (should redirect to login)
        response = self.client.get('/patient/dashboard')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)

        # 2. Register a new test patient
        unique_email = f"test.patient.{int(datetime.now().timestamp())}@example.com"
        reg_data = {
            'first_name': 'Test',
            'last_name': 'Patient',
            'date_of_birth': '1995-05-15',
            'gender': 'Male',
            'phone': '+15550199',
            'email': unique_email,
            'password': 'password123',
            'confirm_password': 'password123'
        }
        response = self.client.post('/register', data=reg_data, follow_redirects=True)
        self.assertIn(b'Your patient profile was created successfully', response.data)

        # 3. Log in as the new patient
        login_data = {
            'role': 'patient',
            'identity': unique_email,
            'password': 'password123'
        }
        response = self.client.post('/login', data=login_data, follow_redirects=True)
        self.assertIn(b'Patient Workspace', response.data)
        self.assertIn(b'Welcome back, Test Patient', response.data)

        # Retrieve the patient object to get ID
        patient = Patient.query.filter_by(email=unique_email).first()
        self.assertIsNotNone(patient)

        # 4. Create a fresh mock doctor for this test run to avoid database pollution issues
        timestamp = int(datetime.now().timestamp())
        doctor = Doctor(
            first_name='John',
            last_name='Smith',
            email=f'dr.john.smith.{timestamp}@example.com',
            specialization='Cardiology',
            license_number=f'LIC{timestamp}'
        )
        doctor.set_password('password123')
        db.session.add(doctor)
        db.session.commit()

        # 5. Book an appointment with a valid future date
        tomorrow = datetime.now() + timedelta(days=1)
        app_date_str = tomorrow.strftime('%Y-%m-%d')
        
        book_data = {
            'doctor_id': str(doctor.id),
            'date': app_date_str,
            'session': 'Morning',
            'reason': 'Routine checkup and blood pressure monitoring.'
        }
        response = self.client.post('/patient/book-appointment', data=book_data, follow_redirects=True)
        self.assertIn(b'Your appointment request has been submitted successfully and is awaiting hospital confirmation.', response.data)

        # Verify appointment exists in DB
        app = Appointment.query.filter_by(patient_id=patient.id, doctor_id=doctor.id).first()
        self.assertIsNotNone(app)
        self.assertEqual(app.reason, 'Routine checkup and blood pressure monitoring.')

        # 6. Attempt to book an appointment with a past date (should fail validation)
        yesterday = datetime.now() - timedelta(days=1)
        past_date_str = yesterday.strftime('%Y-%m-%d')
        
        past_book_data = {
            'doctor_id': str(doctor.id),
            'date': past_date_str,
            'session': 'Morning',
            'reason': 'This should fail validation.'
        }
        response = self.client.post('/patient/book-appointment', data=past_book_data, follow_redirects=True)
        self.assertIn(b'You cannot book an appointment in the past', response.data)

        # Verify that the past appointment WAS NOT saved to DB
        past_app = Appointment.query.filter_by(patient_id=patient.id, reason='This should fail validation.').first()
        self.assertIsNone(past_app)

        # 7. Update Profile via dashboard
        update_data = {
            'action': 'update_profile',
            'first_name': 'Testy',
            'last_name': 'Patient-Updated',
            'phone': '+19999999',
            'date_of_birth': '1995-05-15',
            'gender': 'Female',
            'blood_group': 'O+',
            'address': '123 Test St, Denver, CO'
        }
        response = self.client.post('/patient/dashboard', data=update_data, follow_redirects=True)
        self.assertIn(b'Profile updated successfully', response.data)

        # Verify profile updated in DB
        db.session.refresh(patient)
        self.assertEqual(patient.first_name, 'Testy')
        self.assertEqual(patient.last_name, 'Patient-Updated')
        self.assertEqual(patient.phone, '+19999999')
        self.assertEqual(patient.gender, 'Female')
        self.assertEqual(patient.blood_group, 'O+')
        self.assertEqual(patient.address, '123 Test St, Denver, CO')

        # 8. Access the standalone Appointment History page
        response = self.client.get('/patient/appointment-history')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Appointment History', response.data)
        self.assertIn(f"Dr. {doctor.first_name} {doctor.last_name}".encode('utf-8'), response.data)
        self.assertIn(doctor.specialization.encode('utf-8'), response.data)

        # 9. Access the standalone Medical History page
        # Create a mock consultation to show on the page
        consultation = Consultation(
            appointment_id=app.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            consultation_date=datetime.now(),
            symptoms='Headache and fatigue.',
            diagnosis='Mild dehydration.',
            prescription='Drink 3 liters of water daily.',
            notes='Follow up in one week.'
        )
        db.session.add(consultation)
        db.session.commit()

        response = self.client.get('/patient/medical-history')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Medical History', response.data)
        self.assertIn(f"Dr. {doctor.first_name} {doctor.last_name}".encode('utf-8'), response.data)
        self.assertIn(b'Mild dehydration.', response.data)
        self.assertIn(b'View Details', response.data)

        # 9b. Upload profile photo
        import io
        photo_data = {
            'profile_photo': (io.BytesIO(b"dummy image bytes"), 'test_avatar.jpg')
        }
        response = self.client.post('/patient/profile-photo/upload', data=photo_data, content_type='multipart/form-data', follow_redirects=True)
        self.assertIn(b'Profile photo updated successfully', response.data)
        
        # Verify in DB
        db.session.refresh(patient)
        self.assertIsNotNone(patient.profile_photo)
        self.assertIn('avatar_', patient.profile_photo)

        # 9c. Cancel pending appointment
        pending_app = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_date=datetime.utcnow() + timedelta(days=2),
            status='Pending Approval',
            reason='Pending cancellation test'
        )
        db.session.add(pending_app)
        db.session.commit()
        
        response = self.client.post(f'/patient/appointment/cancel/{pending_app.id}', follow_redirects=True)
        self.assertIn(b'Your appointment has been cancelled successfully.', response.data)
        
        # Verify in DB
        db.session.refresh(pending_app)
        self.assertEqual(pending_app.status, 'Cancelled')

        # 9d. Doctor uploads a report
        # Log out patient first
        self.client.get('/logout', follow_redirects=True)
        # Log in as doctor
        doctor.set_password('password123')
        db.session.commit()
        login_doc = {
            'role': 'doctor',
            'identity': doctor.email,
            'password': 'password123'
        }
        response = self.client.post('/login', data=login_doc, follow_redirects=True)
        self.assertIn(b'Doctor Workspace', response.data)
        
        # Upload report for the consultation
        report_file_data = {
            'report_type': 'Blood Test Reports',
            'report_file': (io.BytesIO(b"dummy report content"), 'blood_report.pdf')
        }
        response = self.client.post(f'/doctor/upload-report/{consultation.id}', data=report_file_data, content_type='multipart/form-data', follow_redirects=True)
        self.assertIn(b'successfully uploaded and saved', response.data)
        
        # Verify in DB
        report = MedicalReport.query.filter_by(consultation_id=consultation.id).first()
        self.assertIsNotNone(report)
        self.assertEqual(report.report_type, 'Blood Test Reports')
        self.assertEqual(report.file_name, 'blood_report.pdf')
        
        # 9e. Download report as doctor
        response = self.client.get(f'/report/download/{report.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"dummy report content")

        print("\nAll programmatic dashboard, appointment booking, and history tests completed successfully!")


class TestDoctorDashboard(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_doctor_dashboard_access_and_consultation(self):
        # 1. Access doctor dashboard without logging in (should redirect to login)
        response = self.client.get('/doctor/dashboard')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)

        # 2. Get or create a doctor for testing
        unique_email = f"test.doctor.{int(datetime.now().timestamp())}@medilife.ai"
        doctor = Doctor(
            first_name='Test',
            last_name='Doctor',
            email=unique_email,
            specialization='General Medicine',
            license_number=f"LIC-TEST-{int(datetime.now().timestamp())}"
        )
        doctor.set_password('password123')
        db.session.add(doctor)
        
        # 3. Create a patient
        patient = Patient(
            first_name='DoctorTest',
            last_name='Patient',
            email=f"dr.test.patient.{int(datetime.now().timestamp())}@example.com",
            date_of_birth=datetime.strptime('1990-01-01', '%Y-%m-%d').date(),
            gender='Female'
        )
        patient.set_password('password123')
        db.session.add(patient)
        db.session.commit()

        # 4. Create an appointment scheduled for TODAY
        today_app = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_date=datetime.utcnow() + timedelta(hours=5, minutes=30),
            status='Approved',
            reason='Today urgent consult',
            session='Morning'
        )
        db.session.add(today_app)
        db.session.commit()

        # 5. Log in as the test doctor
        login_data = {
            'role': 'doctor',
            'identity': unique_email,
            'password': 'password123'
        }
        response = self.client.post('/login', data=login_data, follow_redirects=True)
        self.assertIn(b'Doctor Workspace', response.data)
        self.assertIn(b'Welcome back, Dr. Test Doctor', response.data)
        self.assertIn(b'Today urgent consult', response.data)

        # 5b. Access the consultation page (GET request)
        response = self.client.get(f'/doctor/consultation/{today_app.id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'New Patient Consultation', response.data)
        self.assertIn(b'DoctorTest Patient', response.data)
        self.assertIn(b'Today urgent consult', response.data)

        # 5c. Test the AI Summary API without previous_only (should return error)
        ai_data = {
            'appointment_id': today_app.id,
            'symptoms': 'Fever and muscle pain.',
            'diagnosis': 'Influenza A.',
            'prescription': 'Oseltamivir 75mg bid for 5 days.',
            'notes': 'Advising home isolation.'
        }
        response = self.client.post('/api/generate-summary', json=ai_data)
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Current session summary is disabled. previous_only must be set to True.')

        # 5d. Test the previous records only AI Summary API
        ai_data_prev = {
            'appointment_id': today_app.id,
            'previous_only': True
        }
        response = self.client.post('/api/generate-summary', json=ai_data_prev)
        self.assertEqual(response.status_code, 200)
        data_prev = response.get_json()
        self.assertIn('Medical History', data_prev['summary'])
        self.assertIn('Previous Diagnoses', data_prev['summary'])
        self.assertIn('Disclaimer: This summary is generated using only previous consultation records and is intended for clinical reference. It does not include the current consultation.', data_prev['summary'])

        # 6. Submit a consultation for the appointment
        consult_data = {
            'symptoms': 'Persistent cough and sore throat.',
            'diagnosis': 'Acute Pharyngitis.',
            'prescription': 'Amoxicillin 500mg tid for 7 days.',
            'notes': 'Rest and stay hydrated.',
            'ai_summary': '### Medical History\nSome AI summary here.'
        }
        response = self.client.post(f'/doctor/consultation/{today_app.id}', data=consult_data, follow_redirects=True)
        self.assertIn(b'Consultation saved successfully and appointment marked as completed', response.data)

        # Verify database records
        db.session.refresh(today_app)
        self.assertEqual(today_app.status, 'Completed')
        
        consult = Consultation.query.filter_by(appointment_id=today_app.id).first()
        self.assertIsNotNone(consult)
        self.assertEqual(consult.diagnosis, 'Acute Pharyngitis.')
        self.assertEqual(consult.prescription, 'Amoxicillin 500mg tid for 7 days.')
        self.assertEqual(consult.ai_summary, '### Medical History\nSome AI summary here.')

        # 7. Check if dashboard displays the View Details button and Completed status
        response = self.client.get('/doctor/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'View Details', response.data)

        # 8. Access Patient Record page
        response = self.client.get(f'/doctor/patient/{patient.id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Patient Clinical Record', response.data)
        self.assertIn(b'DoctorTest Patient', response.data)
        self.assertIn(b'Some AI summary here.', response.data)
        self.assertIn(b'View Original Records', response.data)
        
        # 8a. Access Doctor Patient Directory page
        response = self.client.get('/doctor/patients')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'My Patient Directory', response.data)
        self.assertIn(b'DoctorTest Patient', response.data)
        self.assertIn(b'Profile', response.data)
        self.assertIn(b'History', response.data)
        
        # 9. Test Admin Dashboard Access and Flow
        # 9a. Create an admin user first
        admin_email = f"admin.{int(datetime.now().timestamp())}@medilife.ai"
        admin_username = f"admin_{int(datetime.now().timestamp())}"
        test_admin = Admin(
            username=admin_username,
            email=admin_email
        )
        test_admin.set_password('admin123')
        db.session.add(test_admin)
        db.session.commit()

        # 9b. Log out existing session and log in as admin
        self.client.get('/logout', follow_redirects=True)
        admin_login_data = {
            'role': 'admin',
            'identity': admin_username,
            'password': 'admin123'
        }
        response = self.client.post('/login', data=admin_login_data, follow_redirects=True)
        self.assertIn(b'System Control Center', response.data)
        self.assertIn(b'Live Audit Feed', response.data)

        # 9c. Test registering a doctor through the admin endpoint
        new_doc_email = f"new.doc.{int(datetime.now().timestamp())}@medilife.ai"
        new_doc_license = f"LIC{int(datetime.now().timestamp())}"
        doc_data = {
            'first_name': 'Added',
            'last_name': 'Doctor',
            'email': new_doc_email,
            'phone': '1234567890',
            'specialization': 'Pediatrics',
            'license_number': new_doc_license,
            'experience_years': '10',
            'password': 'password123'
        }
        response = self.client.post('/admin/add-doctor', data=doc_data, follow_redirects=True)
        self.assertIn(b'Successfully registered Dr. Added Doctor', response.data)

        # Verify doctor is in DB and activity is logged
        added_doctor = Doctor.query.filter_by(email=new_doc_email).first()
        self.assertIsNotNone(added_doctor)
        self.assertEqual(added_doctor.specialization, 'Pediatrics')

        doctor_activity = SystemActivity.query.filter_by(activity_name='Doctor Added').order_by(SystemActivity.timestamp.desc()).first()
        self.assertIsNotNone(doctor_activity)
        self.assertEqual(doctor_activity.user, f"Admin {admin_username}")

        # 9d. Test registering another admin
        new_admin_username = f"new_admin_{int(datetime.now().timestamp())}"
        new_admin_email = f"new.admin.{int(datetime.now().timestamp())}@medilife.ai"
        admin_data = {
            'username': new_admin_username,
            'email': new_admin_email,
            'password': 'password123'
        }
        response = self.client.post('/admin/add-admin', data=admin_data, follow_redirects=True)
        self.assertIn(f"Successfully added Admin {new_admin_username}".encode(), response.data)

        # Verify admin in DB and activity logged
        added_admin = Admin.query.filter_by(username=new_admin_username).first()
        self.assertIsNotNone(added_admin)

        admin_activity = SystemActivity.query.filter_by(activity_name='Admin Added').order_by(SystemActivity.timestamp.desc()).first()
        self.assertIsNotNone(admin_activity)

        # 9e. Load the admin dashboard page again to verify activities display
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Doctor Added', response.data)
        self.assertIn(b'Admin Added', response.data)
        
        # 10. Test Manage Users page and CRUD operations
        # 10a. Access GET /admin/users
        response = self.client.get('/admin/users')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'User Directory Management', response.data)
        self.assertIn(b'Dr. Added Doctor', response.data)
        self.assertIn(new_admin_username.encode(), response.data)

        # 10b. Test Editing a Doctor (POST) and verify audit log
        edit_doc_data = {
            'first_name': 'Updated',
            'last_name': 'DoctorName',
            'email': new_doc_email,
            'phone': '9876543210',
            'specialization': 'Cardiology',
            'license_number': new_doc_license,
            'experience_years': '15',
            'password': ''  # blank password should not reset
        }
        response = self.client.post(f'/admin/user/doctor/edit/{added_doctor.id}', data=edit_doc_data, follow_redirects=True)
        self.assertIn(b'Successfully updated Dr. Updated DoctorName', response.data)
        
        # Verify changes in DB
        db.session.refresh(added_doctor)
        self.assertEqual(added_doctor.first_name, 'Updated')
        self.assertEqual(added_doctor.specialization, 'Cardiology')
        
        # Verify "Doctor Updated" activity logged
        edit_activity = SystemActivity.query.filter_by(activity_name='Doctor Updated').order_by(SystemActivity.timestamp.desc()).first()
        self.assertIsNotNone(edit_activity)

        # 10c. Test Deleting a Doctor (POST) and verify audit log
        response = self.client.post(f'/admin/user/doctor/delete/{added_doctor.id}', follow_redirects=True)
        self.assertIn(b'Successfully deleted Dr. Updated DoctorName', response.data)
        
        # Verify deleted in DB
        deleted_doctor = Doctor.query.get(added_doctor.id)
        self.assertIsNone(deleted_doctor)
        
        # Verify "Doctor Deleted" activity logged
        delete_activity = SystemActivity.query.filter_by(activity_name='Doctor Deleted').order_by(SystemActivity.timestamp.desc()).first()
        self.assertIsNotNone(delete_activity)

        # 10d. Test Editing an Admin (POST) and verify audit log
        edit_adm_data = {
            'username': 'updated_admin_name',
            'email': new_admin_email,
            'password': 'newpassword123'
        }
        response = self.client.post(f'/admin/user/admin/edit/{added_admin.id}', data=edit_adm_data, follow_redirects=True)
        self.assertIn(b'Successfully updated Admin updated_admin_name', response.data)
        
        # Verify changes in DB
        db.session.refresh(added_admin)
        self.assertEqual(added_admin.username, 'updated_admin_name')
        self.assertTrue(added_admin.check_password('newpassword123'))
        
        # Verify "Admin Updated" activity logged
        adm_edit_activity = SystemActivity.query.filter_by(activity_name='Admin Updated').order_by(SystemActivity.timestamp.desc()).first()
        self.assertIsNotNone(adm_edit_activity)

        # 10e. Test Deleting an Admin (POST) and verify audit log
        response = self.client.post(f'/admin/user/admin/delete/{added_admin.id}', follow_redirects=True)
        self.assertIn(b'Successfully deleted Admin updated_admin_name', response.data)
        
        # Verify deleted in DB
        deleted_admin = Admin.query.get(added_admin.id)
        self.assertIsNone(deleted_admin)
        
        # Verify "Admin Deleted" activity logged
        adm_delete_activity = SystemActivity.query.filter_by(activity_name='Admin Deleted').order_by(SystemActivity.timestamp.desc()).first()
        self.assertIsNotNone(adm_delete_activity)

        # 10f. Test Deleting oneself as Admin (should be blocked)
        response = self.client.post(f'/admin/user/admin/delete/{test_admin.id}', follow_redirects=True)
        self.assertIn(b'Deletion blocked: You cannot delete your own administrative account', response.data)
        
        # Verify not deleted
        self.assertIsNotNone(Admin.query.get(test_admin.id))

        # 10g. Test Editing a Patient (POST)
        edit_pat_data = {
            'first_name': 'UpdatedPatient',
            'last_name': 'LastName',
            'email': patient.email,
            'phone': '1112223333',
            'date_of_birth': '1990-01-01',
            'blood_group': 'O+',
            'address': 'New Address'
        }
        response = self.client.post(f'/admin/user/patient/edit/{patient.id}', data=edit_pat_data, follow_redirects=True)
        self.assertIn(b'Successfully updated Patient UpdatedPatient LastName', response.data)
        
        # Verify in DB
        db.session.refresh(patient)
        self.assertEqual(patient.first_name, 'UpdatedPatient')
        self.assertEqual(patient.blood_group, 'O+')

        # 10h. Test Deleting a Patient (POST)
        response = self.client.post(f'/admin/user/patient/delete/{patient.id}', follow_redirects=True)
        self.assertIn(b'Successfully deleted Patient UpdatedPatient LastName', response.data)
        
        # Verify deleted in DB
        self.assertIsNone(Patient.query.get(patient.id))
        
        print("\nAll Doctor Dashboard, Consultation recording, Patient Record, Gemini fallback, Admin Dashboard, and User CRUD tests completed successfully!")


class TestDoctorLeaveManagement(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_leave_management_flow(self):
        # 1. Create a Doctor
        doc_email = f"leave.doc.{int(datetime.now().timestamp())}@medilife.ai"
        doctor = Doctor(
            first_name='Leave',
            last_name='Doctor',
            email=doc_email,
            specialization='Pediatrics',
            license_number=f"LIC-L-{int(datetime.now().timestamp())}"
        )
        doctor.set_password('password123')
        db.session.add(doctor)
        
        # 2. Create a Patient
        pat_email = f"leave.patient.{int(datetime.now().timestamp())}@example.com"
        patient = Patient(
            first_name='Leave',
            last_name='Patient',
            email=pat_email,
            date_of_birth=datetime.strptime('1990-01-01', '%Y-%m-%d').date(),
            gender='Male'
        )
        patient.set_password('password123')
        db.session.add(patient)
        db.session.commit()

        # 3. Create Admin
        admin_username = f"leave_admin_{int(datetime.now().timestamp())}"
        admin = Admin(
            username=admin_username,
            email=f"{admin_username}@medilife.ai"
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

        # Log in as Admin to add leave
        self.client.post('/login', data={'role': 'admin', 'identity': admin_username, 'password': 'admin123'}, follow_redirects=True)

        # Add leave for doctor tomorrow morning
        tomorrow = datetime.now() + timedelta(days=2)
        leave_date_str = tomorrow.strftime('%Y-%m-%d')
        leave_data = {
            'doctor_id': str(doctor.id),
            'leave_date': leave_date_str,
            'session': 'Morning',
            'reason': 'Medical conference'
        }
        response = self.client.post('/admin/leaves', data=leave_data, follow_redirects=True)
        self.assertIn(b'Doctor leave record added successfully.', response.data)

        # Log out Admin, Log in as Patient
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'role': 'patient', 'identity': pat_email, 'password': 'password123'}, follow_redirects=True)

        # Try to book appointment for tomorrow morning (should fail)
        book_fail_data = {
            'doctor_id': str(doctor.id),
            'date': leave_date_str,
            'session': 'Morning',
            'reason': 'Checkup'
        }
        response = self.client.post('/patient/book-appointment', data=book_fail_data, follow_redirects=True)
        self.assertIn(b'This doctor is unavailable during the selected session. Please choose another doctor or another date.', response.data)

        # Book for tomorrow afternoon (should succeed)
        book_success_data = {
            'doctor_id': str(doctor.id),
            'date': leave_date_str,
            'session': 'Afternoon',
            'reason': 'Checkup'
        }
        response = self.client.post('/patient/book-appointment', data=book_success_data, follow_redirects=True)
        self.assertIn(b'Your appointment request has been submitted successfully and is awaiting hospital confirmation.', response.data)

        # Log out Patient, Log in as Admin
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'role': 'admin', 'identity': admin_username, 'password': 'admin123'}, follow_redirects=True)

        # Approve the afternoon appointment
        app = Appointment.query.filter_by(patient_id=patient.id, doctor_id=doctor.id, session='Afternoon').first()
        self.assertIsNotNone(app)
        self.client.post(f'/admin/appointment/approve/{app.id}', follow_redirects=True)
        
        # Add another leave for Afternoon on same day (will conflict)
        conflict_leave_data = {
            'doctor_id': str(doctor.id),
            'leave_date': leave_date_str,
            'session': 'Afternoon',
            'reason': 'Personal errand'
        }
        response = self.client.post('/admin/leaves', data=conflict_leave_data, follow_redirects=True)
        self.assertIn(b'confirmed appointments are affected by this leave.', response.data)

        # Retrieve the new conflict leave
        conflict_leave = DoctorLeave.query.filter_by(doctor_id=doctor.id, leave_date=tomorrow.date(), session='Afternoon').first()
        self.assertIsNotNone(conflict_leave)

        # 4. View conflicts page to check suggestion calculation
        response = self.client.get(f'/admin/leaves/conflict/{conflict_leave.id}')
        self.assertIn(b'Earliest Available Slot:', response.data)

        # 5. Accept Suggestion
        next_day = tomorrow + timedelta(days=1)
        
        # We POST to accept suggestion
        accept_data = {
            'leave_id': str(conflict_leave.id),
            'suggested_date': next_day.strftime('%Y-%m-%d'),
            'suggested_session': 'Morning'
        }
        response = self.client.post(f'/admin/appointment/accept-suggestion/{app.id}', data=accept_data, follow_redirects=True)
        self.assertIn(b'rescheduled to the suggested slot successfully', response.data)

        # Verify rescheduled appointment in DB
        db.session.refresh(app)
        self.assertEqual(app.session, 'Morning')
        self.assertEqual(app.appointment_date.date(), next_day.date())

        # Log out Admin, Log in as Patient
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'role': 'patient', 'identity': pat_email, 'password': 'password123'}, follow_redirects=True)

        # Check notification received has correct message
        response = self.client.get('/patient/dashboard')
        self.assertIn(b'Appointment Rescheduled', response.data)
        self.assertIn(b'Your appointment has been rescheduled to the next available date because your doctor is on leave.', response.data)
        
        # Mark notification as read
        notif = Notification.query.filter_by(patient_id=patient.id, title="Appointment Rescheduled").first()
        self.assertIsNotNone(notif)
        self.client.post(f'/patient/notification/read/{notif.id}', follow_redirects=True)
        
        # Verify read in DB
        db.session.refresh(notif)
        self.assertTrue(notif.is_read)

        # 6. Verify manual cancellation notification message
        # Let's log in as Admin
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'role': 'admin', 'identity': admin_username, 'password': 'admin123'}, follow_redirects=True)

        # Cancel the appointment
        self.client.post(f'/admin/appointment/cancel-by-leave/{app.id}', data={'leave_id': str(conflict_leave.id)}, follow_redirects=True)
        db.session.refresh(app)
        self.assertEqual(app.status, 'Cancelled')

        # Log in as patient to verify cancel notification
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'role': 'patient', 'identity': pat_email, 'password': 'password123'}, follow_redirects=True)

        response = self.client.get('/patient/dashboard')
        self.assertIn(b'Appointment Cancelled', response.data)
        self.assertIn(b'Your appointment has been cancelled because your doctor is unavailable. Please book another appointment or contact the hospital.', response.data)

        # 7. Test Leave Validation Rule 2 (Leave added after request submitted but before approval)
        # Log in as Patient to book a new appointment
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'role': 'patient', 'identity': pat_email, 'password': 'password123'}, follow_redirects=True)
        
        future_date = datetime.now() + timedelta(days=5)
        future_date_str = future_date.strftime('%Y-%m-%d')
        new_book_data = {
            'doctor_id': str(doctor.id),
            'date': future_date_str,
            'session': 'Morning',
            'reason': 'Routine checkup'
        }
        self.client.post('/patient/book-appointment', data=new_book_data, follow_redirects=True)
        
        # Verify pending appointment exists
        pending_app = Appointment.query.filter_by(patient_id=patient.id, doctor_id=doctor.id, session='Morning', status='Pending Approval').first()
        self.assertIsNotNone(pending_app)
        
        # Log in as Admin to add conflicting leave
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'role': 'admin', 'identity': admin_username, 'password': 'admin123'}, follow_redirects=True)
        
        new_leave_data = {
            'doctor_id': str(doctor.id),
            'leave_date': future_date_str,
            'session': 'Morning',
            'reason': 'Unexpected holiday'
        }
        # Note: Since the appointment is currently 'Pending Approval', it won't trigger a warning alert on creation (which only flags Approved/Confirmed appointments)
        self.client.post('/admin/leaves', data=new_leave_data, follow_redirects=True)
        
        # Now try to approve the pending appointment (should fail due to conflict validation)
        response = self.client.post(f'/admin/appointment/approve/{pending_app.id}', follow_redirects=True)
        self.assertIn(b"This appointment conflicts with the doctor&#39;s leave schedule.", response.data)
        self.assertIn(b'Appointment Leave Conflict', response.data) # single conflict template title
        
        # Resolve the conflict by accepting the next available slot suggestion
        # Since leave is on future_date, search will suggest future_date + 1 day
        resolved_date = future_date + timedelta(days=1)
        accept_resolution_data = {
            'suggested_date': resolved_date.strftime('%Y-%m-%d'),
            'suggested_session': 'Morning'
        }
        response = self.client.post(f'/admin/appointment/accept-suggestion/{pending_app.id}', data=accept_resolution_data, follow_redirects=True)
        self.assertIn(b'Appointment rescheduled to the suggested slot successfully.', response.data)
        
        # Verify it has been approved/confirmed on the new date
        db.session.refresh(pending_app)
        self.assertEqual(pending_app.status, 'Approved')
        self.assertEqual(pending_app.session, 'Morning')
        self.assertEqual(pending_app.appointment_date.date(), resolved_date.date())
        
        # 8. Same-day alternative session suggestion test
        # Let's book a new pending appointment on future_date + 10 days, session = Morning
        booking_date = future_date + timedelta(days=10)
        booking_date_str = booking_date.strftime('%Y-%m-%d')
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'role': 'patient', 'identity': pat_email, 'password': 'password123'}, follow_redirects=True)
        
        self.client.post('/patient/book-appointment', data={
            'doctor_id': str(doctor.id),
            'date': booking_date_str,
            'session': 'Morning',
            'reason': 'Same day check'
        }, follow_redirects=True)
        
        pending_app2 = Appointment.query.filter_by(patient_id=patient.id, doctor_id=doctor.id, session='Morning', status='Pending Approval').filter(db.func.date(Appointment.appointment_date) == booking_date.date()).first()
        self.assertIsNotNone(pending_app2)
        
        # Log in as Admin to add Morning leave on that date
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'role': 'admin', 'identity': admin_username, 'password': 'admin123'}, follow_redirects=True)
        
        self.client.post('/admin/leaves', data={
            'doctor_id': str(doctor.id),
            'leave_date': booking_date_str,
            'session': 'Morning',
            'reason': 'Morning off'
        }, follow_redirects=True)
        
        # Try to approve, should conflict
        response = self.client.post(f'/admin/appointment/approve/{pending_app2.id}', follow_redirects=True)
        self.assertIn(b"This appointment conflicts with the doctor&#39;s leave schedule.", response.data)
        
        # Access conflict page, should suggest Afternoon on the SAME date!
        response = self.client.get(f'/admin/appointment/conflict/{pending_app2.id}')
        self.assertIn(booking_date.strftime('%B %d, %Y').encode(), response.data)
        self.assertIn(b'Afternoon Session', response.data)
        
        # Accept same-day suggestion
        accept_same_day = {
            'suggested_date': booking_date_str,
            'suggested_session': 'Afternoon'
        }
        response = self.client.post(f'/admin/appointment/accept-suggestion/{pending_app2.id}', data=accept_same_day, follow_redirects=True)
        db.session.refresh(pending_app2)
        self.assertEqual(pending_app2.session, 'Afternoon')
        self.assertEqual(pending_app2.appointment_date.date(), booking_date.date())

        # 9. Manual scheduling warning message test (if no slots available within next 30 days)
        # Create a new pending appointment
        no_slot_date = future_date + timedelta(days=20)
        no_slot_date_str = no_slot_date.strftime('%Y-%m-%d')
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'role': 'patient', 'identity': pat_email, 'password': 'password123'}, follow_redirects=True)
        
        self.client.post('/patient/book-appointment', data={
            'doctor_id': str(doctor.id),
            'date': no_slot_date_str,
            'session': 'Morning',
            'reason': 'No slots check'
        }, follow_redirects=True)
        
        pending_app3 = Appointment.query.filter_by(patient_id=patient.id, doctor_id=doctor.id, session='Morning', status='Pending Approval').filter(db.func.date(Appointment.appointment_date) == no_slot_date.date()).first()
        self.assertIsNotNone(pending_app3)
        
        # Log in as Admin and add leaves for the doctor for next 35 days starting from no_slot_date
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'role': 'admin', 'identity': admin_username, 'password': 'admin123'}, follow_redirects=True)
        
        for offset in range(0, 32):
            leave_d = no_slot_date + timedelta(days=offset)
            db.session.add(DoctorLeave(doctor_id=doctor.id, leave_date=leave_d.date(), session='Full Day'))
        db.session.commit()
        
        # Try to approve, should conflict
        response = self.client.post(f'/admin/appointment/approve/{pending_app3.id}', follow_redirects=True)
        self.assertIn(b"This appointment conflicts with the doctor&#39;s leave schedule.", response.data)
        
        # Access conflict page, should say manual scheduling is required
        response = self.client.get(f'/admin/appointment/conflict/{pending_app3.id}')
        self.assertIn(b'No available slots found within the next 30 days. Manual scheduling is required.', response.data)
        
        print("\nAll Doctor Leave Management tests completed successfully!")


if __name__ == '__main__':
    unittest.main()
