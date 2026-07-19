-- =============================================================================
-- MediLife AI Database Schema
-- Target Database: MySQL 8.x
-- =============================================================================

-- Create Database if not exists (uncomment if running as root DBA)
-- CREATE DATABASE IF NOT EXISTS medilife_ai;
-- USE medilife_ai;

-- -----------------------------------------------------------------------------
-- Table: admins
-- Description: Stores system administrator credentials and access profiles.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `admins` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(50) NOT NULL UNIQUE,
    `email` VARCHAR(100) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_admin_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- Table: patients
-- Description: Stores personal, contact, and medical indicators for patients.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `patients` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `first_name` VARCHAR(50) NOT NULL,
    `last_name` VARCHAR(50) NOT NULL,
    `email` VARCHAR(100) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `phone` VARCHAR(20) DEFAULT NULL,
    `date_of_birth` DATE NOT NULL,
    `gender` ENUM('Male', 'Female', 'Other') NOT NULL,
    `blood_group` VARCHAR(5) DEFAULT NULL,
    `address` TEXT DEFAULT NULL,
    `profile_photo` VARCHAR(255) DEFAULT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_patient_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- Table: doctors
-- Description: Stores professional credentials, specialization, and ratings.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `doctors` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `first_name` VARCHAR(50) NOT NULL,
    `last_name` VARCHAR(50) NOT NULL,
    `email` VARCHAR(100) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `phone` VARCHAR(20) DEFAULT NULL,
    `specialization` VARCHAR(100) NOT NULL,
    `license_number` VARCHAR(50) NOT NULL UNIQUE,
    `experience_years` INT UNSIGNED DEFAULT 0,
    `bio` TEXT DEFAULT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `consultation_days` VARCHAR(100) DEFAULT 'Monday-Friday',
    `morning_start` VARCHAR(20) DEFAULT '09:00 AM',
    `morning_end` VARCHAR(20) DEFAULT '01:00 PM',
    `afternoon_start` VARCHAR(20) DEFAULT '02:00 PM',
    `afternoon_end` VARCHAR(20) DEFAULT '05:00 PM',
    INDEX `idx_doctor_specialization` (`specialization`),
    INDEX `idx_doctor_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- Table: appointments
-- Description: Tracks bookings between patients and doctors.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `appointments` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `patient_id` INT NOT NULL,
    `doctor_id` INT NOT NULL,
    `appointment_date` DATETIME NOT NULL,
    `status` VARCHAR(50) DEFAULT 'Pending Approval',
    `reason` TEXT DEFAULT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `session` VARCHAR(20) DEFAULT 'Morning',
    `requested_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `approved_at` DATETIME DEFAULT NULL,
    `approved_by` INT DEFAULT NULL,
    `rejection_reason` TEXT DEFAULT NULL,
    CONSTRAINT `fk_appointments_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_appointments_doctor` FOREIGN KEY (`doctor_id`) REFERENCES `doctors` (`id`) ON DELETE CASCADE,
    INDEX `idx_appointment_date` (`appointment_date`),
    INDEX `idx_appointment_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- Table: consultations
-- Description: Detailed diagnosis, symptoms, and prescriptions for completed appointments.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `consultations` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `appointment_id` INT NOT NULL UNIQUE,
    `patient_id` INT NOT NULL,
    `doctor_id` INT NOT NULL,
    `consultation_date` DATETIME NOT NULL,
    `symptoms` TEXT DEFAULT NULL,
    `diagnosis` TEXT NOT NULL,
    `prescription` TEXT DEFAULT NULL,
    `notes` TEXT DEFAULT NULL,
    `ai_summary` TEXT DEFAULT NULL,
    `previous_records_summary` TEXT DEFAULT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_consultations_appointment` FOREIGN KEY (`appointment_id`) REFERENCES `appointments` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_consultations_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_consultations_doctor` FOREIGN KEY (`doctor_id`) REFERENCES `doctors` (`id`) ON DELETE CASCADE,
    INDEX `idx_consultation_date` (`consultation_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- Table: medical_reports
-- Description: Stores medical reports uploaded by doctors for patients.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `medical_reports` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `patient_id` INT NOT NULL,
    `doctor_id` INT DEFAULT NULL,
    `consultation_id` INT DEFAULT NULL,
    `file_name` VARCHAR(255) NOT NULL,
    `file_path` VARCHAR(255) NOT NULL,
    `report_type` ENUM('Blood Test Reports', 'MRI', 'CT Scan', 'X-Ray', 'ECG', 'Prescription PDFs', 'Medical Certificates', 'Lab Reports') NOT NULL,
    `uploaded_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_medical_reports_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_medical_reports_doctor` FOREIGN KEY (`doctor_id`) REFERENCES `doctors` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_medical_reports_consultation` FOREIGN KEY (`consultation_id`) REFERENCES `consultations` (`id`) ON DELETE SET NULL,
    INDEX `idx_report_patient` (`patient_id`),
    INDEX `idx_report_type` (`report_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- Table: notifications
-- Description: Tracks notifications sent to patients about status changes.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `notifications` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `patient_id` INT NOT NULL,
    `message` VARCHAR(255) NOT NULL,
    `is_read` BOOLEAN DEFAULT FALSE,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_notifications_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`id`) ON DELETE CASCADE,
    INDEX `idx_notification_patient` (`patient_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



-- =============================================================================
-- Mock Seed Data
-- =============================================================================

-- Seed System Admins (Password hash corresponds to 'adminPass123!')
INSERT INTO `admins` (`username`, `email`, `password_hash`) VALUES
('superadmin', 'admin@medilife.ai', 'pbkdf2:sha256:600000$q1w2e3r4t5y6$67c0f16fdb1284a1d821217e108cf70a1a0e5b721867e3ba9341eb2023db1234');

-- Seed Patients (Password hash corresponds to 'patientPass123!')
INSERT INTO `patients` (`first_name`, `last_name`, `email`, `password_hash`, `phone`, `date_of_birth`, `gender`, `blood_group`, `address`) VALUES
('Alice', 'Smith', 'alice.smith@example.com', 'pbkdf2:sha256:600000$q1w2e3r4t5y6$bd157c13a0e5c9b743ab98d1a1b4ffb0a6e765ef39343ba09a32cba934f82631', '+15550192', '1990-05-15', 'Female', 'A+', '123 Health Ave, Suite 400, Chicago, IL'),
('Bob', 'Johnson', 'bob.johnson@example.com', 'pbkdf2:sha256:600000$q1w2e3r4t5y6$bd157c13a0e5c9b743ab98d1a1b4ffb0a6e765ef39343ba09a32cba934f82631', '+15550293', '1985-11-20', 'Male', 'O-', '456 Wellness Blvd, Denver, CO');

-- Seed Doctors (Password hash corresponds to 'doctorPass123!')
INSERT INTO `doctors` (`first_name`, `last_name`, `email`, `password_hash`, `phone`, `specialization`, `license_number`, `experience_years`, `bio`) VALUES
('Sarah', 'Connor', 'sarah.connor@medilife.ai', 'pbkdf2:sha256:600000$q1w2e3r4t5y6$ff77d12a9e34bd7818aa925f3cdb7b049d53ea1234c9fa38cba912a783da321a', '+15559812', 'Cardiology', 'LIC-99210-MD', 12, 'Board-certified cardiologist specializing in cardiovascular health analysis and AI assisted risk detection.'),
('David', 'Miller', 'david.miller@medilife.ai', 'pbkdf2:sha256:600000$q1w2e3r4t5y6$ff77d12a9e34bd7818aa925f3cdb7b049d53ea1234c9fa38cba912a783da321a', '+15557766', 'Neurology', 'LIC-88301-MD', 8, 'Specialist in neurodegenerative diseases and brain-signal telemetry analysis.');

-- Seed Appointments
INSERT INTO `appointments` (`patient_id`, `doctor_id`, `appointment_date`, `status`, `reason`) VALUES
(1, 1, '2026-08-10 09:30:00', 'Confirmed', 'Routine cardiovascular health screening and heart-rate telemetry check.'),
(2, 2, '2026-08-11 14:00:00', 'Completed', 'Evaluation of migraine headache frequency and sleep tracking reports.');

-- Seed Consultations
INSERT INTO `consultations` (`appointment_id`, `patient_id`, `doctor_id`, `consultation_date`, `symptoms`, `diagnosis`, `prescription`, `notes`) VALUES
(2, 2, 2, '2026-08-11 14:30:00', 'Intermittent temples headache, sensitivity to bright screen lighting, mild sleep deprivation (under 6 hours average).', 'Chronic Migraines secondary to screen-fatigue and mild insomnia.', 'Sumatriptan 50mg (as needed during onset); Melatonin 3mg before sleep; 20-20-20 screen rest rule.', 'Follow up in 4 weeks. Patient to maintain headache/migraine logs via the patient portal.');
