
# Medical dictionary for instant lookup of common terms
# Sources: Mixed clinical knowledge, formatted for patients & clinicians

MEDICAL_DICTIONARY = {
    "pneumonia": {
        "definition": "An infection that inflames the air sacs in one or both lungs, which may fill with fluid or pus.",
        "clinician_note": "Commonly manifests as consolidation on CXR. Primary types: CAP, HAP, VAP."
    },
    "sepsis": {
        "definition": "A life-threatening medical emergency caused by the body's extreme response to an infection.",
        "clinician_note": "Characterized by systemic inflammatory response syndrome (SIRS) and organ dysfunction."
    },
    "tachycardia": {
        "definition": "A heart rate that's too fast—typically over 100 beats per minute for adults at rest.",
        "clinician_note": "May be sinus, supraventricular (SVT), or ventricular (VT)."
    },
    "bradycardia": {
        "definition": "A slower-than-normal heart rate, usually fewer than 60 beats per minute.",
        "clinician_note": "Can be physiological (athletes) or pathological (av block, sinus node dysfunction)."
    },
    "hypertension": {
        "definition": "High blood pressure; the long-term force of the blood against your artery walls is high enough that it may eventually cause health problems.",
        "clinician_note": "Defined as BP >= 130/80 mmHg (ACC/AHA guidelines)."
    },
    "hypotension": {
        "definition": "Low blood pressure, which can cause fainting or dizziness because the brain doesn't receive enough blood.",
        "clinician_note": "Commonly defined as < 90/60 mmHg. Watch for orthostatic changes."
    },
    "atrial fibrillation": {
        "definition": "An irregular and often very rapid heart rhythm (arrhythmia) that can lead to blood clots in the heart.",
        "clinician_note": "Commonly called AFib. High risk for stroke; usually requires anticoagulation (CHADS-VASC score)."
    },
    "arrhythmia": {
        "definition": "A problem with the rate or rhythm of your heartbeat. It means your heart beats too quickly, too slowly, or with an irregular pattern.",
        "clinician_note": "Broad category including PVCs, AFib, Heart Blocks, and Tachyarrhythmias."
    },
    "edema": {
        "definition": "Swelling caused by excess fluid trapped in your body's tissues.",
        "clinician_note": "Can be pitting or non-pitting. Common causes: heart failure, renal disease, venous insufficiency."
    },
    "effusion": {
        "definition": "An escape of fluid into a body cavity, such as the space around the lungs (pleural effusion) or heart.",
        "clinician_note": "Pleural effusion classification via Light's Criteria (transudate vs. exudate)."
    },
    "embolism": {
        "definition": "The sudden blockage of an artery, typically by a blood clot or an air bubble.",
        "clinician_note": "Commonly Pulmonary Embolism (PE) or Systemic Embolism from AFib."
    },
    "thrombosis": {
        "definition": "The formation of a blood clot inside a blood vessel, obstructing the flow of blood.",
        "clinician_note": "DVT (Deep Vein Thrombosis) is a frequent concern in hospitalized or sedentary patients."
    },
    "stenosis": {
        "definition": "The abnormal narrowing of a passage in the body.",
        "clinician_note": "Commonly refers to heart valves (Aortic Stenosis) or the spinal canal."
    },
    "ischemia": {
        "definition": "A condition in which the blood flow (and thus oxygen) is restricted or reduced in a part of the body.",
        "clinician_note": "Precursor to infarction. Myocardial ischemia presents as angina or EKG changes."
    },
    "infarction": {
        "definition": "The death of tissue (necrosis) due to inadequate blood supply to the affected area.",
        "clinician_note": "Myocardial Infarction (MI) or Cerebral Infarction (Stroke)."
    },
    # Labs
    "creatinine": {
        "definition": "A waste product produced by your muscles; it is filtered out of the blood by the kidneys.",
        "clinician_note": "Key marker for Glomerular Filtration Rate (GFR) and kidney function."
    },
    "troponin": {
        "definition": "A type of protein found in the muscles of your heart. It's usually not in the blood unless heart muscle is damaged.",
        "clinician_note": "Gold standard biomarker for myocardial injury (NSTEMI/STEMI)."
    },
    "d-dimer": {
        "definition": "A protein fragment that's made when a blood clot dissolves in your body.",
        "clinician_note": "High sensitivity but low specificity for VTE/PE. Often used as a rule-out test."
    },
    "systolic": {
        "definition": "The top number in a blood pressure reading, measuring the pressure in your arteries when your heart beats.",
        "clinician_note": "Reflects the maximum pressure exerted during ventricular contraction."
    },
    "diastolic": {
        "definition": "The bottom number in a blood pressure reading, measuring the pressure in your arteries when your heart rests between beats.",
        "clinician_note": "Reflects the minimum pressure in the arteries during ventricular relaxation."
    },
    "spo2": {
        "definition": "A measure of the percentage of hemoglobin binding sites in the bloodstream occupied by oxygen.",
        "clinician_note": "Peripheral capillary oxygen saturation. Target usually >94% (or 88-92% in COPD)."
    },
    "gfr": {
        "definition": "Glomerular Filtration Rate; a test used to check how well the kidneys are working.",
        "clinician_note": "Calculated based on creatinine, age, and sex. Essential for drug dosing."
    },
    # Medications
    "anticoagulant": {
        "definition": "A substance that prevents the blood from clotting.",
        "clinician_note": "Common examples: Heparin, Warfarin, DOACs (Apixaban, Rivaroxaban)."
    },
    "diuretic": {
        "definition": "A medication that helps the kidneys release more sodium into your urine, which carries water with it, reducing blood volume.",
        "clinician_note": "Typically Loop diuretics (Furosemide) or Thiazides."
    },
    "corticosteroid": {
        "definition": "A class of drugs that lower inflammation and reduce immune system activity.",
        "clinician_note": "Examples: Prednisone, Dexamethasone. Watch for hyperglycemia and fluid retention."
    },
    "metformin": {
        "definition": "An oral medication used to control high blood sugar in people with type 2 diabetes.",
        "clinician_note": "First-line therapy for T2DM. Mechanism: reduces hepatic glucose production."
    },
    "lisinopril": {
        "definition": "An ACE inhibitor used to treat high blood pressure and heart failure.",
        "clinician_note": "Common side effect: dry cough. Risk of angioedema and hyperkalemia."
    },
    "diagnoses": {
        "definition": "The identification of the nature of an illness or other problem by examination of the symptoms.",
        "clinician_note": "A clinical assessment based on history, physical exam, labs, and imaging."
    },
    "furosemide": {
        "definition": "A loop diuretic used to treat fluid build-up due to heart failure, liver scarring, or kidney disease.",
        "clinician_note": "Brand name Lasix. Monitor potassium levels and renal function."
    },
}

def get_medical_explanation(term: str) -> dict:
    """Lookup a term in the local dictionary. Term should be lowered/stripped."""
    term_key = term.lower().strip()
    return MEDICAL_DICTIONARY.get(term_key)
