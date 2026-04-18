"""
Knowledge Graph Treatment Enrichment

Enriches the Neo4j knowledge graph with:
1. Drug nodes: name, drug_class, mechanism, common_dosage
2. TREATS relationships: Drug → Disease (with line of treatment)
3. CONTRAINDICATED_WITH relationships: Drug → Disease/Condition
4. INTERACTS_WITH relationships: Drug ↔ Drug (with severity and effect)

This enables deterministic (non-LLM) drug interaction checking against
patient medication lists from MIMIC, demonstrating true neuro-symbolic reasoning.

Usage:
    python -m ingestion.enrich_kg_treatments
    # or
    cd ingestion && python enrich_kg_treatments.py
"""

import os
import sys
import json
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Force UTF-8 encoding for Windows terminals
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Add project root for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

# =============================================================================
# Configuration
# =============================================================================

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# =============================================================================
# Curated Treatment Data
# =============================================================================

# Drug nodes: name, drug_class, mechanism, common_dosage, cui (UMLS if available)
DRUGS = [
    # Antibiotics
    {"name": "Amoxicillin", "drug_class": "Antibiotic (Penicillin)", "mechanism": "Inhibits bacterial cell wall synthesis", "common_dosage": "500mg TID or 875mg BID", "cui": "C0002645"},
    {"name": "Azithromycin", "drug_class": "Antibiotic (Macrolide)", "mechanism": "Inhibits bacterial protein synthesis via 50S ribosome binding", "common_dosage": "500mg day 1, then 250mg daily x4 days", "cui": "C0052796"},
    {"name": "Ciprofloxacin", "drug_class": "Antibiotic (Fluoroquinolone)", "mechanism": "Inhibits DNA gyrase and topoisomerase IV", "common_dosage": "250-500mg BID", "cui": "C0008809"},
    {"name": "Nitrofurantoin", "drug_class": "Antibiotic (Nitrofuran)", "mechanism": "Damages bacterial DNA via reactive intermediates", "common_dosage": "100mg BID x5 days", "cui": "C0028156"},
    {"name": "Doxycycline", "drug_class": "Antibiotic (Tetracycline)", "mechanism": "Inhibits bacterial protein synthesis via 30S ribosome", "common_dosage": "100mg BID", "cui": "C0013090"},
    {"name": "Levofloxacin", "drug_class": "Antibiotic (Fluoroquinolone)", "mechanism": "Inhibits DNA gyrase and topoisomerase IV", "common_dosage": "500-750mg daily", "cui": "C0282386"},

    # Cardiovascular
    {"name": "Lisinopril", "drug_class": "ACE Inhibitor", "mechanism": "Blocks angiotensin-converting enzyme, reducing vasoconstriction", "common_dosage": "10-40mg daily", "cui": "C0065374"},
    {"name": "Amlodipine", "drug_class": "Calcium Channel Blocker", "mechanism": "Blocks L-type calcium channels in vascular smooth muscle", "common_dosage": "5-10mg daily", "cui": "C0051696"},
    {"name": "Losartan", "drug_class": "ARB (Angiotensin II Receptor Blocker)", "mechanism": "Blocks angiotensin II AT1 receptors", "common_dosage": "50-100mg daily", "cui": "C0126174"},
    {"name": "Carvedilol", "drug_class": "Beta Blocker (non-selective)", "mechanism": "Blocks beta-1, beta-2, and alpha-1 adrenergic receptors", "common_dosage": "6.25-25mg BID", "cui": "C0071012"},
    {"name": "Metoprolol", "drug_class": "Beta Blocker (selective)", "mechanism": "Selectively blocks beta-1 adrenergic receptors", "common_dosage": "25-200mg daily", "cui": "C0025859"},
    {"name": "Hydrochlorothiazide", "drug_class": "Thiazide Diuretic", "mechanism": "Inhibits sodium-chloride cotransporter in distal tubule", "common_dosage": "12.5-25mg daily", "cui": "C0020261"},
    {"name": "Furosemide", "drug_class": "Loop Diuretic", "mechanism": "Inhibits Na-K-2Cl cotransporter in loop of Henle", "common_dosage": "20-80mg daily", "cui": "C0016860"},
    {"name": "Spironolactone", "drug_class": "Potassium-Sparing Diuretic", "mechanism": "Aldosterone receptor antagonist", "common_dosage": "25-50mg daily", "cui": "C0037982"},
    {"name": "Warfarin", "drug_class": "Anticoagulant (Vitamin K antagonist)", "mechanism": "Inhibits vitamin K epoxide reductase, blocking clotting factor synthesis", "common_dosage": "2-10mg daily (INR-guided)", "cui": "C0043031"},
    {"name": "Heparin", "drug_class": "Anticoagulant (Direct)", "mechanism": "Potentiates antithrombin III, inhibiting thrombin and Factor Xa", "common_dosage": "5000 units SC BID-TID (prophylaxis)", "cui": "C0019134"},
    {"name": "Digoxin", "drug_class": "Cardiac Glycoside", "mechanism": "Inhibits Na+/K+ ATPase, increases intracellular calcium in cardiac myocytes", "common_dosage": "0.125-0.25mg daily", "cui": "C0012265"},
    {"name": "Amiodarone", "drug_class": "Antiarrhythmic (Class III)", "mechanism": "Blocks potassium channels, prolonging action potential", "common_dosage": "200-400mg daily (maintenance)", "cui": "C0002598"},
    {"name": "Atorvastatin", "drug_class": "Statin (HMG-CoA Reductase Inhibitor)", "mechanism": "Inhibits HMG-CoA reductase, reducing cholesterol synthesis", "common_dosage": "10-80mg daily", "cui": "C0286651"},

    # Diabetes
    {"name": "Metformin", "drug_class": "Biguanide", "mechanism": "Decreases hepatic glucose production, increases insulin sensitivity", "common_dosage": "500-2000mg daily in divided doses", "cui": "C0025598"},
    {"name": "Insulin Glargine", "drug_class": "Long-Acting Insulin", "mechanism": "Basal insulin replacement, promotes glucose uptake", "common_dosage": "10-80 units SC daily", "cui": "C0907402"},
    {"name": "Glipizide", "drug_class": "Sulfonylurea", "mechanism": "Stimulates pancreatic beta-cell insulin secretion", "common_dosage": "5-20mg daily", "cui": "C0017654"},

    # Respiratory
    {"name": "Albuterol", "drug_class": "Short-Acting Beta-2 Agonist (SABA)", "mechanism": "Relaxes bronchial smooth muscle via beta-2 receptor stimulation", "common_dosage": "2 puffs PRN (90mcg/puff)", "cui": "C0001927"},
    {"name": "Tiotropium", "drug_class": "Long-Acting Muscarinic Antagonist (LAMA)", "mechanism": "Blocks M3 muscarinic receptors in bronchial smooth muscle", "common_dosage": "18mcg inhaled daily", "cui": "C0268475"},
    {"name": "Fluticasone", "drug_class": "Inhaled Corticosteroid (ICS)", "mechanism": "Reduces airway inflammation via glucocorticoid receptor activation", "common_dosage": "100-500mcg inhaled BID", "cui": "C0082607"},
    {"name": "Budesonide", "drug_class": "Inhaled Corticosteroid (ICS)", "mechanism": "Reduces airway inflammation via glucocorticoid receptor activation", "common_dosage": "180-360mcg inhaled BID", "cui": "C0054201"},
    {"name": "Prednisone", "drug_class": "Systemic Corticosteroid", "mechanism": "Broad anti-inflammatory and immunosuppressive effects", "common_dosage": "5-60mg daily (taper)", "cui": "C0032952"},

    # CNS / Psychiatric
    {"name": "Sertraline", "drug_class": "SSRI (Selective Serotonin Reuptake Inhibitor)", "mechanism": "Inhibits serotonin reuptake in synaptic cleft", "common_dosage": "50-200mg daily", "cui": "C0074393"},
    {"name": "Fluoxetine", "drug_class": "SSRI", "mechanism": "Inhibits serotonin reuptake in synaptic cleft", "common_dosage": "20-80mg daily", "cui": "C0016365"},
    {"name": "Buspirone", "drug_class": "Anxiolytic (Azapirone)", "mechanism": "Partial agonist at serotonin 5-HT1A receptors", "common_dosage": "7.5-30mg BID", "cui": "C0006462"},
    {"name": "Gabapentin", "drug_class": "Anticonvulsant / Neuropathic Pain", "mechanism": "Modulates calcium channels via alpha-2-delta subunit binding", "common_dosage": "300-1200mg TID", "cui": "C0060926"},
    {"name": "Levetiracetam", "drug_class": "Anticonvulsant", "mechanism": "Binds synaptic vesicle protein SV2A, modulating neurotransmitter release", "common_dosage": "500-1500mg BID", "cui": "C0377401"},
    {"name": "Levodopa/Carbidopa", "drug_class": "Dopamine Precursor", "mechanism": "Levodopa converts to dopamine in CNS; carbidopa prevents peripheral conversion", "common_dosage": "25/100mg TID", "cui": "C0023570"},

    # Endocrine
    {"name": "Levothyroxine", "drug_class": "Thyroid Hormone", "mechanism": "Synthetic T4, converts to active T3 for metabolic regulation", "common_dosage": "25-200mcg daily", "cui": "C0023175"},

    # Pain / Anti-inflammatory
    {"name": "Ibuprofen", "drug_class": "NSAID", "mechanism": "Non-selective COX-1/COX-2 inhibitor, reduces prostaglandin synthesis", "common_dosage": "200-800mg TID", "cui": "C0020740"},
    {"name": "Naproxen", "drug_class": "NSAID", "mechanism": "Non-selective COX inhibitor", "common_dosage": "250-500mg BID", "cui": "C0027396"},
    {"name": "Acetaminophen", "drug_class": "Analgesic/Antipyretic", "mechanism": "Central COX inhibition, exact mechanism debated", "common_dosage": "325-1000mg Q4-6H (max 4g/day)", "cui": "C0000970"},
    {"name": "Colchicine", "drug_class": "Anti-Gout", "mechanism": "Inhibits microtubule polymerization, reducing neutrophil migration", "common_dosage": "0.6mg BID", "cui": "C0009262"},
    {"name": "Allopurinol", "drug_class": "Xanthine Oxidase Inhibitor", "mechanism": "Reduces uric acid production by inhibiting xanthine oxidase", "common_dosage": "100-300mg daily", "cui": "C0002144"},

    # GI
    {"name": "Omeprazole", "drug_class": "Proton Pump Inhibitor (PPI)", "mechanism": "Irreversibly inhibits H+/K+ ATPase in gastric parietal cells", "common_dosage": "20-40mg daily", "cui": "C0028978"},

    # Immunosuppressant / Autoimmune
    {"name": "Methotrexate", "drug_class": "DMARD / Antimetabolite", "mechanism": "Inhibits dihydrofolate reductase, reducing cell proliferation and inflammation", "common_dosage": "7.5-25mg weekly", "cui": "C0025677"},
    {"name": "Hydroxychloroquine", "drug_class": "DMARD / Antimalarial", "mechanism": "Modulates immune cell function, inhibits TLR signaling", "common_dosage": "200-400mg daily", "cui": "C0020336"},
]

# =============================================================================
# TREATS Relationships: Drug → Disease (with treatment line)
# =============================================================================

TREATS_RELATIONSHIPS = [
    # Pneumonia
    {"drug": "Amoxicillin", "disease": "Pneumonia", "line": "first_line", "notes": "Community-acquired pneumonia, typical pathogens"},
    {"drug": "Azithromycin", "disease": "Pneumonia", "line": "first_line", "notes": "Atypical coverage, monotherapy for mild CAP"},
    {"drug": "Levofloxacin", "disease": "Pneumonia", "line": "second_line", "notes": "Respiratory fluoroquinolone for CAP with comorbidities"},
    {"drug": "Doxycycline", "disease": "Pneumonia", "line": "second_line", "notes": "Alternative for atypical coverage"},

    # Hypertension
    {"drug": "Lisinopril", "disease": "Hypertension", "line": "first_line", "notes": "ACE inhibitor, preferred with diabetes or CKD"},
    {"drug": "Amlodipine", "disease": "Hypertension", "line": "first_line", "notes": "CCB, effective monotherapy"},
    {"drug": "Losartan", "disease": "Hypertension", "line": "first_line", "notes": "ARB, alternative if ACE-I intolerant (cough)"},
    {"drug": "Hydrochlorothiazide", "disease": "Hypertension", "line": "first_line", "notes": "Thiazide diuretic, low-cost first-line"},
    {"drug": "Metoprolol", "disease": "Hypertension", "line": "second_line", "notes": "Beta blocker, preferred if concurrent tachycardia or HF"},

    # Heart Failure
    {"drug": "Carvedilol", "disease": "Heart Failure", "line": "first_line", "notes": "Beta blocker with alpha blockade, mortality benefit in HFrEF"},
    {"drug": "Lisinopril", "disease": "Heart Failure", "line": "first_line", "notes": "ACE inhibitor, cornerstone of HF therapy"},
    {"drug": "Spironolactone", "disease": "Heart Failure", "line": "first_line", "notes": "Aldosterone antagonist, mortality benefit in severe HF"},
    {"drug": "Furosemide", "disease": "Heart Failure", "line": "first_line", "notes": "Loop diuretic for fluid overload/congestion"},
    {"drug": "Digoxin", "disease": "Heart Failure", "line": "second_line", "notes": "Improves symptoms, no mortality benefit"},

    # Type 2 Diabetes
    {"drug": "Metformin", "disease": "Type 2 Diabetes", "line": "first_line", "notes": "First-line oral agent per ADA guidelines"},
    {"drug": "Insulin Glargine", "disease": "Type 2 Diabetes", "line": "second_line", "notes": "Basal insulin for uncontrolled diabetes"},
    {"drug": "Glipizide", "disease": "Type 2 Diabetes", "line": "second_line", "notes": "Sulfonylurea, add-on to metformin"},

    # COPD
    {"drug": "Albuterol", "disease": "COPD", "line": "first_line", "notes": "Rescue inhaler for acute exacerbations"},
    {"drug": "Tiotropium", "disease": "COPD", "line": "first_line", "notes": "LAMA maintenance therapy, GOLD guidelines"},
    {"drug": "Budesonide", "disease": "COPD", "line": "second_line", "notes": "ICS for frequent exacerbators (GOLD D)"},
    {"drug": "Prednisone", "disease": "COPD", "line": "second_line", "notes": "Short course for acute exacerbation (5-7 days)"},

    # Asthma
    {"drug": "Fluticasone", "disease": "Asthma", "line": "first_line", "notes": "ICS controller therapy, Steps 2+"},
    {"drug": "Albuterol", "disease": "Asthma", "line": "first_line", "notes": "Rescue inhaler for acute bronchospasm"},
    {"drug": "Budesonide", "disease": "Asthma", "line": "first_line", "notes": "ICS alternative controller"},
    {"drug": "Prednisone", "disease": "Asthma", "line": "second_line", "notes": "Oral steroid burst for acute exacerbation"},

    # UTI
    {"drug": "Nitrofurantoin", "disease": "Urinary Tract Infection", "line": "first_line", "notes": "Uncomplicated cystitis, 5-day course"},
    {"drug": "Ciprofloxacin", "disease": "Urinary Tract Infection", "line": "second_line", "notes": "Complicated UTI or pyelonephritis"},

    # Depression
    {"drug": "Sertraline", "disease": "Depression", "line": "first_line", "notes": "SSRI, best evidence for efficacy + tolerability"},
    {"drug": "Fluoxetine", "disease": "Depression", "line": "first_line", "notes": "SSRI, longest track record"},

    # Anxiety Disorder
    {"drug": "Sertraline", "disease": "Anxiety Disorder", "line": "first_line", "notes": "SSRI for GAD, first-line per APA guidelines"},
    {"drug": "Buspirone", "disease": "Anxiety Disorder", "line": "first_line", "notes": "Non-addictive anxiolytic for GAD"},

    # Hypothyroidism
    {"drug": "Levothyroxine", "disease": "Hypothyroidism", "line": "first_line", "notes": "Gold standard thyroid replacement"},

    # Atrial Fibrillation
    {"drug": "Metoprolol", "disease": "Atrial Fibrillation", "line": "first_line", "notes": "Rate control strategy"},
    {"drug": "Amiodarone", "disease": "Atrial Fibrillation", "line": "second_line", "notes": "Rhythm control, pharmacologic cardioversion"},
    {"drug": "Warfarin", "disease": "Atrial Fibrillation", "line": "first_line", "notes": "Anticoagulation for stroke prevention (CHA2DS2-VASc)"},
    {"drug": "Digoxin", "disease": "Atrial Fibrillation", "line": "second_line", "notes": "Rate control in sedentary patients"},

    # GERD
    {"drug": "Omeprazole", "disease": "Gastroesophageal Reflux Disease", "line": "first_line", "notes": "PPI therapy, 4-8 week course"},

    # Osteoarthritis
    {"drug": "Acetaminophen", "disease": "Osteoarthritis", "line": "first_line", "notes": "First-line analgesic per ACR guidelines"},
    {"drug": "Ibuprofen", "disease": "Osteoarthritis", "line": "first_line", "notes": "NSAID for moderate-severe pain"},
    {"drug": "Naproxen", "disease": "Osteoarthritis", "line": "first_line", "notes": "NSAID alternative, longer duration"},

    # Rheumatoid Arthritis
    {"drug": "Methotrexate", "disease": "Rheumatoid Arthritis", "line": "first_line", "notes": "Anchor DMARD per ACR guidelines"},
    {"drug": "Hydroxychloroquine", "disease": "Rheumatoid Arthritis", "line": "first_line", "notes": "Mild RA or combination DMARD therapy"},
    {"drug": "Prednisone", "disease": "Rheumatoid Arthritis", "line": "second_line", "notes": "Bridge therapy during DMARD initiation"},

    # Gout
    {"drug": "Colchicine", "disease": "Gout", "line": "first_line", "notes": "Acute gout flare within 36h onset"},
    {"drug": "Allopurinol", "disease": "Gout", "line": "first_line", "notes": "Urate-lowering therapy for chronic gout"},
    {"drug": "Ibuprofen", "disease": "Gout", "line": "first_line", "notes": "NSAID for acute gout flare pain"},

    # Epilepsy
    {"drug": "Levetiracetam", "disease": "Epilepsy", "line": "first_line", "notes": "Broad-spectrum anticonvulsant, favorable side effect profile"},
    {"drug": "Gabapentin", "disease": "Epilepsy", "line": "second_line", "notes": "Adjunctive therapy for focal seizures"},

    # Parkinson's Disease
    {"drug": "Levodopa/Carbidopa", "disease": "Parkinson's Disease", "line": "first_line", "notes": "Gold standard dopamine replacement"},

    # Lupus
    {"drug": "Hydroxychloroquine", "disease": "Lupus", "line": "first_line", "notes": "Background therapy for all SLE patients"},
    {"drug": "Prednisone", "disease": "Lupus", "line": "first_line", "notes": "Flare management, lowest effective dose"},

    # Hyperlipidemia
    {"drug": "Atorvastatin", "disease": "Hyperlipidemia", "line": "first_line", "notes": "High-intensity statin per ACC/AHA guidelines"},

    # Coronary Artery Disease
    {"drug": "Atorvastatin", "disease": "Coronary Artery Disease", "line": "first_line", "notes": "High-intensity statin for secondary prevention"},
    {"drug": "Metoprolol", "disease": "Coronary Artery Disease", "line": "first_line", "notes": "Beta blocker post-MI, rate control"},
    {"drug": "Lisinopril", "disease": "Coronary Artery Disease", "line": "first_line", "notes": "ACE inhibitor for post-MI remodeling prevention"},
]

# =============================================================================
# CONTRAINDICATED_WITH Relationships: Drug → Condition
# =============================================================================

CONTRAINDICATIONS = [
    # ACE Inhibitors
    {"drug": "Lisinopril", "condition": "Chronic Kidney Disease", "severity": "major", "reason": "Can worsen renal function; use with extreme caution, monitor creatinine"},
    {"drug": "Lisinopril", "condition": "Angioedema", "severity": "major", "reason": "History of ACE-inhibitor angioedema is absolute contraindication"},
    {"drug": "Losartan", "condition": "Chronic Kidney Disease", "severity": "moderate", "reason": "Monitor potassium and renal function closely"},

    # Beta Blockers
    {"drug": "Carvedilol", "condition": "Asthma", "severity": "major", "reason": "Non-selective beta blockade can trigger severe bronchospasm"},
    {"drug": "Metoprolol", "condition": "Asthma", "severity": "moderate", "reason": "Selective beta-1 blocker, but can still worsen bronchospasm at high doses"},

    # Metformin
    {"drug": "Metformin", "condition": "Chronic Kidney Disease", "severity": "major", "reason": "Risk of lactic acidosis with eGFR <30; contraindicated"},
    {"drug": "Metformin", "condition": "Cirrhosis", "severity": "major", "reason": "Impaired lactate clearance increases lactic acidosis risk"},

    # NSAIDs
    {"drug": "Ibuprofen", "condition": "Chronic Kidney Disease", "severity": "major", "reason": "Reduces renal blood flow, can precipitate acute kidney injury"},
    {"drug": "Ibuprofen", "condition": "Heart Failure", "severity": "major", "reason": "Causes fluid retention, worsens heart failure"},
    {"drug": "Ibuprofen", "condition": "Peptic Ulcer", "severity": "major", "reason": "Increases GI bleeding risk significantly"},
    {"drug": "Naproxen", "condition": "Chronic Kidney Disease", "severity": "major", "reason": "Nephrotoxic, avoid in CKD"},
    {"drug": "Naproxen", "condition": "Heart Failure", "severity": "major", "reason": "Fluid retention and sodium retention worsen HF"},

    # Anticoagulants
    {"drug": "Warfarin", "condition": "Cirrhosis", "severity": "major", "reason": "Impaired clotting factor synthesis increases bleeding risk unpredictably"},
    {"drug": "Heparin", "condition": "Thrombocytopenia", "severity": "major", "reason": "Risk of heparin-induced thrombocytopenia (HIT)"},

    # Fluoroquinolones
    {"drug": "Ciprofloxacin", "condition": "Epilepsy", "severity": "moderate", "reason": "Lowers seizure threshold"},
    {"drug": "Levofloxacin", "condition": "Epilepsy", "severity": "moderate", "reason": "Lowers seizure threshold"},

    # Digoxin
    {"drug": "Digoxin", "condition": "Chronic Kidney Disease", "severity": "major", "reason": "Renally cleared; accumulation causes toxicity (arrhythmias, nausea)"},

    # Methotrexate
    {"drug": "Methotrexate", "condition": "Cirrhosis", "severity": "major", "reason": "Hepatotoxic; liver disease increases toxicity risk"},
    {"drug": "Methotrexate", "condition": "Chronic Kidney Disease", "severity": "major", "reason": "Renally cleared; accumulation causes bone marrow suppression"},
]

# =============================================================================
# INTERACTS_WITH Relationships: Drug ↔ Drug
# =============================================================================

DRUG_INTERACTIONS = [
    # ACE Inhibitor + Potassium-Sparing Diuretic
    {"drug1": "Lisinopril", "drug2": "Spironolactone", "severity": "major", "effect": "Hyperkalemia risk — both increase serum potassium. Monitor K+ closely."},
    {"drug1": "Losartan", "drug2": "Spironolactone", "severity": "major", "effect": "Hyperkalemia risk — ARB + aldosterone antagonist combination."},

    # Anticoagulant interactions
    {"drug1": "Warfarin", "drug2": "Ibuprofen", "severity": "major", "effect": "Greatly increased bleeding risk — NSAID inhibits platelet function + GI erosion."},
    {"drug1": "Warfarin", "drug2": "Naproxen", "severity": "major", "effect": "Greatly increased bleeding risk — avoid combination."},
    {"drug1": "Warfarin", "drug2": "Amiodarone", "severity": "major", "effect": "Amiodarone inhibits warfarin metabolism (CYP2C9). Reduce warfarin dose 30-50%."},
    {"drug1": "Heparin", "drug2": "Ibuprofen", "severity": "major", "effect": "Additive bleeding risk — NSAID impairs platelet function."},
    {"drug1": "Heparin", "drug2": "Naproxen", "severity": "major", "effect": "Additive bleeding risk — avoid concurrent use."},

    # Digoxin interactions
    {"drug1": "Digoxin", "drug2": "Amiodarone", "severity": "major", "effect": "Amiodarone increases digoxin levels 70-100%. Reduce digoxin dose by half."},
    {"drug1": "Digoxin", "drug2": "Furosemide", "severity": "moderate", "effect": "Furosemide-induced hypokalemia increases digoxin toxicity risk. Monitor K+."},
    {"drug1": "Digoxin", "drug2": "Hydrochlorothiazide", "severity": "moderate", "effect": "Thiazide-induced hypokalemia/hypomagnesemia increases digoxin toxicity."},
    {"drug1": "Digoxin", "drug2": "Spironolactone", "severity": "moderate", "effect": "Spironolactone increases digoxin levels by ~25%. Monitor levels."},

    # ACE Inhibitor + NSAID
    {"drug1": "Lisinopril", "drug2": "Ibuprofen", "severity": "moderate", "effect": "NSAID reduces antihypertensive effect and increases renal impairment risk."},
    {"drug1": "Lisinopril", "drug2": "Naproxen", "severity": "moderate", "effect": "NSAID reduces antihypertensive effect and increases renal impairment risk."},

    # ACE Inhibitor + Diuretic (beneficial but monitor)
    {"drug1": "Lisinopril", "drug2": "Furosemide", "severity": "moderate", "effect": "First-dose hypotension risk. Beneficial combination in HF but monitor BP and renal function."},

    # Metformin + Contrast / Alcohol
    {"drug1": "Metformin", "drug2": "Ciprofloxacin", "severity": "moderate", "effect": "Ciprofloxacin may alter blood glucose (hypo- or hyperglycemia). Monitor closely."},

    # SSRI + NSAID
    {"drug1": "Sertraline", "drug2": "Ibuprofen", "severity": "moderate", "effect": "SSRIs impair platelet function; combined with NSAID increases GI bleeding risk 2-3x."},
    {"drug1": "Fluoxetine", "drug2": "Ibuprofen", "severity": "moderate", "effect": "SSRIs impair platelet function; combined with NSAID increases GI bleeding risk."},
    {"drug1": "Sertraline", "drug2": "Naproxen", "severity": "moderate", "effect": "SSRI + NSAID increases GI bleeding risk. Consider PPI prophylaxis."},

    # Fluoxetine specific CYP2D6 interactions
    {"drug1": "Fluoxetine", "drug2": "Metoprolol", "severity": "moderate", "effect": "Fluoxetine inhibits CYP2D6, increasing metoprolol levels. Risk of bradycardia/hypotension."},
    {"drug1": "Fluoxetine", "drug2": "Carvedilol", "severity": "moderate", "effect": "Fluoxetine inhibits CYP2D6, increasing carvedilol levels."},

    # Statin interactions
    {"drug1": "Atorvastatin", "drug2": "Amiodarone", "severity": "moderate", "effect": "Amiodarone increases statin levels. Limit atorvastatin to 40mg/day."},

    # Corticosteroid + NSAID
    {"drug1": "Prednisone", "drug2": "Ibuprofen", "severity": "moderate", "effect": "Additive GI ulceration risk. Use PPI prophylaxis if combination necessary."},
    {"drug1": "Prednisone", "drug2": "Naproxen", "severity": "moderate", "effect": "Additive GI ulceration risk."},

    # Allopurinol interactions
    {"drug1": "Allopurinol", "drug2": "Warfarin", "severity": "moderate", "effect": "Allopurinol may increase warfarin anticoagulant effect. Monitor INR."},
]


# =============================================================================
# Neo4j Enrichment Functions
# =============================================================================

def create_drug_nodes(tx):
    """Create Drug nodes with properties."""
    for drug in DRUGS:
        tx.run("""
            MERGE (d:Drug {name: $name})
            SET d.drug_class = $drug_class,
                d.mechanism = $mechanism,
                d.common_dosage = $common_dosage,
                d.cui = $cui
        """, **drug)
    print(f"  ✓ Created/updated {len(DRUGS)} Drug nodes")


def create_treats_relationships(tx):
    """Create TREATS relationships: Drug → Disease."""
    created = 0
    for rel in TREATS_RELATIONSHIPS:
        result = tx.run("""
            MATCH (drug:Drug {name: $drug})
            MATCH (disease:Disease)
            WHERE toLower(disease.name) = toLower($disease)
            MERGE (drug)-[r:TREATS]->(disease)
            SET r.line = $line,
                r.notes = $notes
            RETURN count(r) as cnt
        """, **rel)
        cnt = result.single()["cnt"]
        created += cnt
    print(f"  ✓ Created {created} TREATS relationships")


def create_contraindication_relationships(tx):
    """Create CONTRAINDICATED_WITH relationships: Drug → Disease/Condition."""
    created = 0
    for rel in CONTRAINDICATIONS:
        # Try matching against Disease nodes
        result = tx.run("""
            MATCH (drug:Drug {name: $drug})
            MATCH (cond:Disease)
            WHERE toLower(cond.name) = toLower($condition)
            MERGE (drug)-[r:CONTRAINDICATED_WITH]->(cond)
            SET r.severity = $severity,
                r.reason = $reason
            RETURN count(r) as cnt
        """, **rel)
        cnt = result.single()["cnt"]
        if cnt == 0:
            # Condition not found as Disease node — create a Condition node
            result = tx.run("""
                MATCH (drug:Drug {name: $drug})
                MERGE (cond:Condition {name: $condition})
                MERGE (drug)-[r:CONTRAINDICATED_WITH]->(cond)
                SET r.severity = $severity,
                    r.reason = $reason
                RETURN count(r) as cnt
            """, **rel)
            cnt = result.single()["cnt"]
        created += cnt
    print(f"  ✓ Created {created} CONTRAINDICATED_WITH relationships")


def create_interaction_relationships(tx):
    """Create INTERACTS_WITH relationships: Drug ↔ Drug (bidirectional)."""
    created = 0
    for rel in DRUG_INTERACTIONS:
        result = tx.run("""
            MATCH (d1:Drug {name: $drug1})
            MATCH (d2:Drug {name: $drug2})
            MERGE (d1)-[r:INTERACTS_WITH]->(d2)
            SET r.severity = $severity,
                r.effect = $effect
            RETURN count(r) as cnt
        """, **rel)
        created += result.single()["cnt"]
    print(f"  ✓ Created {created} INTERACTS_WITH relationships")


def create_indexes(tx):
    """Create indexes for efficient lookups."""
    tx.run("CREATE INDEX IF NOT EXISTS FOR (d:Drug) ON (d.name)")
    tx.run("CREATE INDEX IF NOT EXISTS FOR (c:Condition) ON (c.name)")
    print("  ✓ Created indexes on Drug.name and Condition.name")


def verify_enrichment(tx):
    """Print summary statistics after enrichment."""
    stats = {}

    result = tx.run("MATCH (d:Drug) RETURN count(d) as cnt")
    stats['drugs'] = result.single()['cnt']

    result = tx.run("MATCH ()-[r:TREATS]->() RETURN count(r) as cnt")
    stats['treats'] = result.single()['cnt']

    result = tx.run("MATCH ()-[r:CONTRAINDICATED_WITH]->() RETURN count(r) as cnt")
    stats['contraindications'] = result.single()['cnt']

    result = tx.run("MATCH ()-[r:INTERACTS_WITH]->() RETURN count(r) as cnt")
    stats['interactions'] = result.single()['cnt']

    # Test query: What treats pneumonia?
    result = tx.run("""
        MATCH (drug:Drug)-[r:TREATS]->(d:Disease)
        WHERE toLower(d.name) = 'pneumonia'
        RETURN drug.name as drug, drug.drug_class as class, r.line as line, r.notes as notes
        ORDER BY r.line
    """)
    pneumonia_treatments = list(result)

    # Test query: Drug interactions for Lisinopril
    result = tx.run("""
        MATCH (d1:Drug {name: 'Lisinopril'})-[r:INTERACTS_WITH]-(d2:Drug)
        RETURN d2.name as drug, r.severity as severity, r.effect as effect
    """)
    lisinopril_interactions = list(result)

    print("\n" + "=" * 60)
    print("📊 ENRICHMENT SUMMARY")
    print("=" * 60)
    print(f"  Drug Nodes:           {stats['drugs']}")
    print(f"  TREATS:               {stats['treats']}")
    print(f"  CONTRAINDICATED_WITH: {stats['contraindications']}")
    print(f"  INTERACTS_WITH:       {stats['interactions']}")

    print(f"\n🧪 Test: What treats Pneumonia?")
    for t in pneumonia_treatments:
        print(f"  [{t['line']}] {t['drug']} ({t['class']}) — {t['notes']}")

    print(f"\n🧪 Test: Lisinopril interactions")
    for i in lisinopril_interactions:
        print(f"  [{i['severity'].upper()}] {i['drug']}: {i['effect'][:80]}...")

    return stats


# =============================================================================
# Main
# =============================================================================

def main():
    print("=" * 60)
    print("TrustMed AI - Knowledge Graph Treatment Enrichment")
    print("=" * 60)

    if not NEO4J_PASSWORD:
        print("X NEO4J_PASSWORD not set. Check your .env file.")
        return

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            print("\nStep 1: Creating Drug nodes...")
            session.execute_write(create_drug_nodes)

            print("\nStep 2: Creating TREATS relationships...")
            session.execute_write(create_treats_relationships)

            print("\nStep 3: Creating CONTRAINDICATED_WITH relationships...")
            session.execute_write(create_contraindication_relationships)

            print("\nStep 4: Creating INTERACTS_WITH relationships...")
            session.execute_write(create_interaction_relationships)

            print("\nStep 5: Creating indexes...")
            session.execute_write(create_indexes)

            print("\nStep 6: Verifying enrichment...")
            session.execute_read(verify_enrichment)

        print("\nKnowledge Graph enrichment complete!")

    except Exception as e:
        print(f"\nEnrichment failed: {e}")
        raise
    finally:
        driver.close()


if __name__ == "__main__":
    main()
