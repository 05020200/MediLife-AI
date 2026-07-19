import unittest
from datetime import datetime, timedelta
from app import create_app
from database import db
from models import Patient, Doctor, Appointment, Admin, DoctorAvailability

class TestWeeklyAvailability(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_doctor_availability_logic(self):
        # 1. Create a doctor with custom availability
        # We want Wednesday Morning available, Wednesday Afternoon unavailable, and Thursday completely unavailable
        timestamp = int(datetime.now().timestamp())
        doc_email = f"sarah.connor.{timestamp}@example.com"
        doc = Doctor(
            first_name='Sarah',
            last_name='Connor',
            email=doc_email,
            specialization='General Medicine',
            license_number=f'LIC-SC-{timestamp}',
            experience_years=5
        )
        doc.set_password('password123')
        db.session.add(doc)
        db.session.flush()

        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for day in days:
            avail_day = False if day == 'Thursday' else True
            morn = True
            aft = False if day == 'Wednesday' else True
            
            avail = DoctorAvailability(
                doctor_id=doc.id,
                day=day,
                available=avail_day,
                morning=morn,
                morning_start='09:00 AM',
                morning_end='01:00 PM',
                afternoon=aft,
                afternoon_start='02:00 PM',
                afternoon_end='06:00 PM' if day == 'Monday' else '05:00 PM'
            )
            db.session.add(avail)
        db.session.commit()

        # Check model helper methods
        self.assertTrue(doc.is_available_day('Wednesday'))
        self.assertFalse(doc.is_available_day('Thursday'))
        self.assertTrue(doc.is_available('Wednesday', 'Morning'))
        self.assertFalse(doc.is_available('Wednesday', 'Afternoon'))
        self.assertTrue(doc.is_available('Monday', 'Afternoon'))
        
        # Check custom time retrieval
        self.assertEqual(doc.get_session_time('Monday', 'afternoon', 'end'), '06:00 PM')
        self.assertEqual(doc.get_session_time('Wednesday', 'afternoon', 'end'), '05:00 PM')

        # 2. Register a new test patient
        unique_email = f"patient.avail.{timestamp}@example.com"
        reg_data = {
            'first_name': 'Avail',
            'last_name': 'Patient',
            'date_of_birth': '1990-01-01',
            'gender': 'Female',
            'phone': '+15551212',
            'email': unique_email,
            'password': 'password123',
            'confirm_password': 'password123'
        }
        response = self.client.post('/register', data=reg_data, follow_redirects=True)
        self.assertIn(b'Your patient profile was created successfully', response.data)

        # Log in as patient
        login_data = {
            'role': 'patient',
            'identity': unique_email,
            'password': 'password123'
        }
        self.client.post('/login', data=login_data, follow_redirects=True)

        # 3. Determine next Wednesday and next Thursday
        today = datetime.now()
        
        # Next Wednesday
        days_ahead_wed = 2 - today.weekday()
        if days_ahead_wed <= 0:
            days_ahead_wed += 7
        next_wednesday = today + timedelta(days=days_ahead_wed)
        next_wednesday_str = next_wednesday.strftime('%Y-%m-%d')
        
        # Next Thursday
        days_ahead_thu = 3 - today.weekday()
        if days_ahead_thu <= 0:
            days_ahead_thu += 7
        next_thursday = today + timedelta(days=days_ahead_thu)
        next_thursday_str = next_thursday.strftime('%Y-%m-%d')

        # 4. Attempt to book Wednesday Afternoon (should fail session validation)
        book_data_fail_session = {
            'doctor_id': str(doc.id),
            'date': next_wednesday_str,
            'session': 'Afternoon',
            'reason': 'Consultation on Wednesday Afternoon.'
        }
        response = self.client.post('/patient/book-appointment', data=book_data_fail_session, follow_redirects=True)
        expected_err = f"Dr. Sarah Connor is not available on Wednesday Afternoon. Please choose another available day or session."
        self.assertIn(expected_err.encode('utf-8'), response.data)

        # 5. Attempt to book Thursday Morning (should fail day availability validation)
        book_data_fail_day = {
            'doctor_id': str(doc.id),
            'date': next_thursday_str,
            'session': 'Morning',
            'reason': 'Consultation on Thursday Morning.'
        }
        response = self.client.post('/patient/book-appointment', data=book_data_fail_day, follow_redirects=True)
        expected_err_day = f"Dr. Sarah Connor is not available on Thursday. Please choose another available day or session."
        self.assertIn(expected_err_day.encode('utf-8'), response.data)

        # Ensure no appointments were created for Wednesday Afternoon or Thursday Morning
        app_fail_session = Appointment.query.filter_by(doctor_id=doc.id, session='Afternoon').first()
        self.assertIsNone(app_fail_session)
        app_fail_day = Appointment.query.filter(Appointment.doctor_id == doc.id, Appointment.appointment_date == next_thursday).first()
        self.assertIsNone(app_fail_day)

        # 6. Book Wednesday Morning (should succeed)
        book_data_success = {
            'doctor_id': str(doc.id),
            'date': next_wednesday_str,
            'session': 'Morning',
            'reason': 'Consultation on Wednesday Morning.'
        }
        response = self.client.post('/patient/book-appointment', data=book_data_success, follow_redirects=True)
        self.assertIn(b'Your appointment request has been submitted successfully', response.data)

        # Ensure appointment was created
        app_success = Appointment.query.filter_by(doctor_id=doc.id, session='Morning').first()
        self.assertIsNotNone(app_success)

    def test_backward_compatibility(self):
        # Create doctor without custom availability records
        timestamp = int(datetime.now().timestamp())
        compat_email = f"compat.doc.{timestamp}@example.com"
        compat_doc = Doctor(
            first_name='Compat',
            last_name='Practitioner',
            email=compat_email,
            specialization='Pediatrics',
            license_number=f'LIC-CP-{timestamp}',
            experience_years=3
        )
        compat_doc.set_password('password123')
        db.session.add(compat_doc)
        db.session.commit()

        # Verify defaults to True/standard fallbacks
        self.assertTrue(compat_doc.is_available_day('Monday'))
        self.assertTrue(compat_doc.is_available('Monday', 'Morning'))
        self.assertTrue(compat_doc.is_available('Monday', 'Afternoon'))
        self.assertEqual(compat_doc.get_session_time('Monday', 'morning', 'start'), '09:00 AM')
        self.assertEqual(compat_doc.get_session_time('Sunday', 'afternoon', 'end'), '05:00 PM')
