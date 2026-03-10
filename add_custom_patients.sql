-- ============================================
-- TrustMed-AI: Inject Custom Patients
-- ============================================
-- Adds specific targeted patients for Pneumonia and Heart Disease
-- Run: psql -d health -f add_custom_patients.sql
-- ============================================

-- ============================================
-- 1. Heart Failure & CAD Patient (ID: 99900001)
-- ============================================
-- Vitals
INSERT INTO mimic_vitals (subject_id, heart_rate, sbp, dbp, resp_rate, temperature, spo2) 
VALUES (99900001, 105, 155, 95, 24, 37.1, 91);

-- Diagnoses
INSERT INTO mimic_diagnoses (subject_id, icd_code, long_title) VALUES 
(99900001, 'I509', 'Heart failure, unspecified'),
(99900001, 'I2510', 'Atherosclerotic heart disease of native coronary artery without angina pectoris'),
(99900001, 'I10', 'Essential (primary) hypertension'),
(99900001, 'E785', 'Hyperlipidemia, unspecified');

-- Medications
INSERT INTO mimic_prescriptions (subject_id, drug, dose_val_rx, dose_unit_rx, route) VALUES 
(99900001, 'Lisinopril', '20', 'mg', 'PO'),
(99900001, 'Atorvastatin', '40', 'mg', 'PO'),
(99900001, 'Metoprolol Tartrate', '50', 'mg', 'PO'),
(99900001, 'Furosemide', '40', 'mg', 'PO'),
(99900001, 'Aspirin', '81', 'mg', 'PO');

-- ============================================
-- 2. Acute Pneumonia Patient (ID: 99900002)
-- ============================================
-- Vitals (Feverish, tachycardic, tachypneic, slightly hypoxic)
INSERT INTO mimic_vitals (subject_id, heart_rate, sbp, dbp, resp_rate, temperature, spo2) 
VALUES (99900002, 115, 110, 65, 28, 39.2, 88);

-- Diagnoses
INSERT INTO mimic_diagnoses (subject_id, icd_code, long_title) VALUES 
(99900002, 'J159', 'Unspecified bacterial pneumonia'),
(99900002, 'J90', 'Pleural effusion, not elsewhere classified'),
(99900002, 'E860', 'Dehydration');

-- Medications
INSERT INTO mimic_prescriptions (subject_id, drug, dose_val_rx, dose_unit_rx, route) VALUES 
(99900002, 'Ceftriaxone', '1', 'g', 'IV'),
(99900002, 'Azithromycin', '500', 'mg', 'IV'),
(99900002, 'Acetaminophen', '650', 'mg', 'PO'),
(99900002, 'Albuterol Inhaler', '90', 'mcg', 'INH');

-- ============================================
-- 3. Complex Heart & Lung Overlap (ID: 99900003)
-- ============================================
-- Vitals
INSERT INTO mimic_vitals (subject_id, heart_rate, sbp, dbp, resp_rate, temperature, spo2) 
VALUES (99900003, 98, 165, 90, 22, 37.4, 93);

-- Diagnoses
INSERT INTO mimic_diagnoses (subject_id, icd_code, long_title) VALUES 
(99900003, 'I110', 'Hypertensive heart disease with heart failure'),
(99900003, 'J449', 'Chronic obstructive pulmonary disease, unspecified'),
(99900003, 'J189', 'Pneumonia, unspecified organism');

-- Medications
INSERT INTO mimic_prescriptions (subject_id, drug, dose_val_rx, dose_unit_rx, route) VALUES 
(99900003, 'Amlodipine', '10', 'mg', 'PO'),
(99900003, 'Budesonide-Formoterol', '160/4.5', 'mcg', 'INH'),
(99900003, 'Levofloxacin', '750', 'mg', 'IV'),
(99900003, 'Furosemide', '20', 'mg', 'IV');
