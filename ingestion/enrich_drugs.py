"""
KG Drug Enrichment Script
Adds Drug nodes + TREATS / INTERACTS_WITH / CONTRAINDICATED_WITH relationships
for the 60 diseases currently lacking drug coverage.

All data is curated from clinical guidelines (FDA labels, UpToDate, BNF).
Run once — uses MERGE so it's idempotent.
"""

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# ── Drug definitions ─────────────────────────────────────────────────────────
# Each drug: (name, drug_class, common_dosage)
NEW_DRUGS = [
    # GI
    ("Omeprazole", "Proton Pump Inhibitor", "20-40mg daily"),
    ("Pantoprazole", "Proton Pump Inhibitor", "40mg daily"),
    ("Ranitidine", "H2 Receptor Antagonist", "150mg twice daily"),
    ("Ondansetron", "5-HT3 Antagonist", "4-8mg as needed"),
    ("Loperamide", "Antidiarrheal", "2mg after each loose stool, max 16mg/day"),
    ("Mesalamine", "5-ASA Anti-inflammatory", "2.4-4.8g daily"),
    ("Sulfasalazine", "5-ASA / DMARD", "2-3g daily in divided doses"),
    ("Infliximab", "TNF-alpha Inhibitor", "5mg/kg IV at 0, 2, 6 weeks then q8w"),
    ("Adalimumab", "TNF-alpha Inhibitor", "160mg then 80mg then 40mg every 2 weeks"),
    ("Bismuth Subsalicylate", "Antacid / GI Protectant", "524mg every 30-60 min, max 8 doses/day"),

    # Neurology
    ("Sumatriptan", "Triptan", "50-100mg at onset, max 200mg/day"),
    ("Topiramate", "Anticonvulsant", "25-100mg daily for prevention"),
    ("Propranolol", "Beta Blocker", "40-160mg daily for migraine prevention"),
    ("Donepezil", "Cholinesterase Inhibitor", "5-10mg daily"),
    ("Memantine", "NMDA Antagonist", "5-20mg daily"),
    ("Riluzole", "Glutamate Inhibitor", "50mg twice daily"),
    ("Gabapentin", "Anticonvulsant / Analgesic", "300-3600mg daily in divided doses"),
    ("Pregabalin", "Anticonvulsant / Analgesic", "150-450mg daily in divided doses"),
    ("Valproic Acid", "Anticonvulsant", "500-2000mg daily in divided doses"),
    ("Phenytoin", "Anticonvulsant", "300-400mg daily"),
    ("Interferon Beta-1a", "Immunomodulator", "30mcg IM weekly"),
    ("Dimethyl Fumarate", "Immunomodulator", "240mg twice daily"),
    ("CPAP Therapy", "Mechanical Ventilation", "Continuous positive airway pressure nightly"),

    # Anti-infectives
    ("Chloroquine", "Antimalarial", "600mg base then 300mg at 6, 24, 48 hours"),
    ("Artemether-Lumefantrine", "Antimalarial (ACT)", "4 tablets twice daily for 3 days"),
    ("Isoniazid", "Anti-tubercular", "300mg daily"),
    ("Rifampin", "Anti-tubercular", "600mg daily"),
    ("Pyrazinamide", "Anti-tubercular", "15-30mg/kg daily"),
    ("Ethambutol", "Anti-tubercular", "15-25mg/kg daily"),
    ("Acyclovir", "Antiviral", "800mg 5x/day for 7 days (VZV), 200mg 5x/day (HSV)"),
    ("Oseltamivir", "Neuraminidase Inhibitor", "75mg twice daily for 5 days"),
    ("Paxlovid (Nirmatrelvir/Ritonavir)", "Protease Inhibitor", "300mg/100mg twice daily for 5 days"),
    ("Remdesivir", "Nucleotide Analogue", "200mg IV day 1, then 100mg IV daily for 5 days"),
    ("Entecavir", "Nucleoside Analogue", "0.5-1mg daily"),
    ("Sofosbuvir/Velpatasvir", "NS5A/NS5B Inhibitor", "400mg/100mg daily for 12 weeks"),
    ("Tenofovir", "Nucleotide Analogue", "300mg daily"),
    ("Ribavirin", "Nucleoside Analogue", "800-1200mg daily in divided doses"),
    ("Ceftriaxone", "Cephalosporin", "1-2g IV daily"),
    ("Vancomycin", "Glycopeptide", "15-20mg/kg IV every 8-12 hours"),
    ("Meropenem", "Carbapenem", "1-2g IV every 8 hours"),
    ("Fluconazole", "Azole Antifungal", "150-400mg daily"),
    ("Terbinafine", "Antifungal", "250mg daily for 6-12 weeks"),

    # Endocrine / Metabolic
    ("Methimazole", "Antithyroid", "5-30mg daily"),
    ("Propylthiouracil", "Antithyroid", "100-150mg three times daily"),
    ("Glucagon", "Hormone", "1mg IM/SC for severe hypoglycemia"),
    ("Dextrose 50%", "Glucose Solution", "25-50mL IV for hypoglycemia"),
    ("Alendronate", "Bisphosphonate", "70mg weekly"),
    ("Denosumab", "RANKL Inhibitor", "60mg SC every 6 months"),
    ("Calcium + Vitamin D", "Supplement", "1000-1200mg Ca + 800-1000IU Vit D daily"),
    ("Potassium Citrate", "Alkalinizing Agent", "30-60mEq daily in divided doses"),
    ("Tamsulosin", "Alpha Blocker", "0.4mg daily"),
    ("Allopurinol", "Xanthine Oxidase Inhibitor", "100-800mg daily"),

    # Dermatology
    ("Benzoyl Peroxide", "Topical Antimicrobial", "2.5-10% applied once/twice daily"),
    ("Adapalene", "Topical Retinoid", "0.1% gel applied nightly"),
    ("Isotretinoin", "Systemic Retinoid", "0.5-1mg/kg/day for 15-20 weeks"),
    ("Hydrocortisone Cream", "Topical Corticosteroid", "1% applied twice daily"),
    ("Tacrolimus Ointment", "Topical Calcineurin Inhibitor", "0.03-0.1% applied twice daily"),
    ("Metronidazole Gel", "Topical Antibiotic", "0.75% applied twice daily"),
    ("Ivermectin Cream", "Topical Antiparasitic", "1% applied once daily"),
    ("Calcipotriol", "Topical Vitamin D Analogue", "0.005% applied twice daily"),
    ("Mupirocin", "Topical Antibiotic", "2% applied three times daily"),

    # Cardiovascular
    ("Alteplase", "Thrombolytic", "0.9mg/kg IV (max 90mg), 10% bolus then infuse 60 min"),
    ("Clopidogrel", "Antiplatelet", "75mg daily"),
    ("Aspirin", "Antiplatelet / NSAID", "81-325mg daily"),
    ("Nitroglycerin", "Vasodilator", "0.4mg SL every 5 min, max 3 doses"),

    # Hematology
    ("Ferrous Sulfate", "Iron Supplement", "325mg (65mg elemental Fe) 1-3x daily"),
    ("Folic Acid", "B-Vitamin", "1-5mg daily"),
    ("Epoetin Alfa", "Erythropoietin", "50-300 units/kg SC/IV 3x weekly"),

    # Pulmonary
    ("Albuterol", "Short-acting Beta Agonist", "2 puffs every 4-6 hours as needed"),
    ("Tiotropium", "Long-acting Anticholinergic", "18mcg inhaled daily"),
    ("Budesonide/Formoterol", "ICS/LABA Combination", "160/4.5mcg, 2 puffs twice daily"),

    # Ophthalmology
    ("Timolol Ophthalmic", "Beta Blocker Eye Drop", "0.5% one drop twice daily"),
    ("Latanoprost", "Prostaglandin Analogue", "0.005% one drop nightly"),

    # Anti-retroviral
    ("Tenofovir/Emtricitabine/Efavirenz", "NRTI + NNRTI Combo", "1 tablet daily"),

    # Duloxetine for fibromyalgia
    ("Duloxetine", "SNRI", "60mg daily"),

    # Vascular
    ("Diosmin", "Venotonic", "500mg twice daily"),
    ("Compression Stockings", "Mechanical Therapy", "20-30 mmHg knee-high daily"),
]

# ── TREATS relationships ─────────────────────────────────────────────────────
# (drug_name, disease_name, line)
TREATS_RELS = [
    # GERD
    ("Omeprazole", "GERD", "first_line"),
    ("Pantoprazole", "GERD", "first_line"),
    ("Ranitidine", "GERD", "second_line"),

    # Gastroenteritis
    ("Ondansetron", "Gastroenteritis", "first_line"),
    ("Loperamide", "Gastroenteritis", "second_line"),

    # Peptic Ulcer
    ("Omeprazole", "Peptic ulcer diseae", "first_line"),
    ("Omeprazole", "Peptic Ulcer", "first_line"),
    ("Pantoprazole", "Peptic Ulcer", "first_line"),
    ("Bismuth Subsalicylate", "Peptic Ulcer", "second_line"),

    # Ulcerative Colitis
    ("Mesalamine", "Ulcerative Colitis", "first_line"),
    ("Sulfasalazine", "Ulcerative Colitis", "first_line"),
    ("Infliximab", "Ulcerative Colitis", "second_line"),
    ("Adalimumab", "Ulcerative Colitis", "second_line"),

    # Crohn's Disease
    ("Infliximab", "Crohn's Disease", "first_line"),
    ("Adalimumab", "Crohn's Disease", "first_line"),
    ("Mesalamine", "Crohn's Disease", "second_line"),

    # Migraine
    ("Sumatriptan", "Migraine", "first_line"),
    ("Topiramate", "Migraine", "first_line"),
    ("Propranolol", "Migraine", "second_line"),

    # Alzheimer's Disease
    ("Donepezil", "Alzheimer's Disease", "first_line"),
    ("Memantine", "Alzheimer's Disease", "second_line"),

    # Multiple Sclerosis
    ("Interferon Beta-1a", "Multiple Sclerosis", "first_line"),
    ("Dimethyl Fumarate", "Multiple Sclerosis", "first_line"),

    # Epilepsy
    ("Valproic Acid", "Epilepsy", "first_line"),
    ("Phenytoin", "Epilepsy", "second_line"),

    # Fibromyalgia
    ("Pregabalin", "Fibromyalgia", "first_line"),
    ("Duloxetine", "Fibromyalgia", "first_line"),
    ("Gabapentin", "Fibromyalgia", "second_line"),

    # Sleep Apnea
    ("CPAP Therapy", "Sleep Apnea", "first_line"),

    # Malaria
    ("Chloroquine", "Malaria", "first_line"),
    ("Artemether-Lumefantrine", "Malaria", "first_line"),

    # Tuberculosis
    ("Isoniazid", "Tuberculosis", "first_line"),
    ("Rifampin", "Tuberculosis", "first_line"),
    ("Pyrazinamide", "Tuberculosis", "first_line"),
    ("Ethambutol", "Tuberculosis", "first_line"),

    # Chicken pox
    ("Acyclovir", "Chicken pox", "first_line"),

    # Influenza
    ("Oseltamivir", "Influenza", "first_line"),

    # COVID-19
    ("Paxlovid (Nirmatrelvir/Ritonavir)", "COVID-19", "first_line"),
    ("Remdesivir", "COVID-19", "first_line"),

    # Dengue (supportive — no specific antiviral)
    ("Acetaminophen", "Dengue", "first_line"),

    # Hepatitis A (supportive)
    ("Acetaminophen", "hepatitis A", "first_line"),

    # Hepatitis B
    ("Entecavir", "Hepatitis B", "first_line"),
    ("Tenofovir", "Hepatitis B", "first_line"),

    # Hepatitis C
    ("Sofosbuvir/Velpatasvir", "Hepatitis C", "first_line"),

    # Hepatitis D
    ("Interferon Beta-1a", "Hepatitis D", "first_line"),
    ("Tenofovir", "Hepatitis D", "second_line"),

    # Hepatitis E (supportive)
    ("Ribavirin", "Hepatitis E", "first_line"),

    # Sepsis
    ("Ceftriaxone", "Sepsis", "first_line"),
    ("Vancomycin", "Sepsis", "first_line"),
    ("Meropenem", "Sepsis", "second_line"),

    # Typhoid
    ("Ciprofloxacin", "Typhoid", "first_line"),
    ("Azithromycin", "Typhoid", "first_line"),
    ("Ceftriaxone", "Typhoid", "second_line"),

    # Fungal infection
    ("Fluconazole", "Fungal infection", "first_line"),
    ("Terbinafine", "Fungal infection", "first_line"),

    # Impetigo
    ("Mupirocin", "Impetigo", "first_line"),
    ("Amoxicillin", "Impetigo", "second_line"),

    # Hyperthyroidism
    ("Methimazole", "Hyperthyroidism", "first_line"),
    ("Propylthiouracil", "Hyperthyroidism", "second_line"),
    ("Propranolol", "Hyperthyroidism", "first_line"),

    # Hypoglycemia
    ("Glucagon", "Hypoglycemia", "first_line"),
    ("Dextrose 50%", "Hypoglycemia", "first_line"),

    # Osteoporosis
    ("Alendronate", "Osteoporosis", "first_line"),
    ("Denosumab", "Osteoporosis", "second_line"),
    ("Calcium + Vitamin D", "Osteoporosis", "first_line"),

    # Kidney Stones
    ("Potassium Citrate", "Kidney Stones", "first_line"),
    ("Tamsulosin", "Kidney Stones", "first_line"),
    ("Ibuprofen", "Kidney Stones", "first_line"),

    # Acne
    ("Benzoyl Peroxide", "Acne", "first_line"),
    ("Adapalene", "Acne", "first_line"),
    ("Isotretinoin", "Acne", "second_line"),

    # Eczema / Dermatitis
    ("Hydrocortisone Cream", "Eczema", "first_line"),
    ("Tacrolimus Ointment", "Eczema", "second_line"),
    ("Hydrocortisone Cream", "Dermatitis", "first_line"),
    ("Tacrolimus Ointment", "Dermatitis", "second_line"),

    # Rosacea
    ("Metronidazole Gel", "Rosacea", "first_line"),
    ("Ivermectin Cream", "Rosacea", "first_line"),

    # Psoriasis
    ("Calcipotriol", "Psoriasis", "first_line"),
    ("Methotrexate", "Psoriasis", "second_line"),
    ("Adalimumab", "Psoriasis", "second_line"),

    # Heart attack
    ("Aspirin", "Heart attack", "first_line"),
    ("Clopidogrel", "Heart attack", "first_line"),
    ("Nitroglycerin", "Heart attack", "first_line"),
    ("Heparin", "Heart attack", "first_line"),

    # Stroke
    ("Alteplase", "Stroke", "first_line"),
    ("Aspirin", "Stroke", "first_line"),
    ("Clopidogrel", "Stroke", "second_line"),

    # Anemia
    ("Ferrous Sulfate", "Anemia", "first_line"),
    ("Folic Acid", "Anemia", "first_line"),
    ("Epoetin Alfa", "Anemia", "second_line"),

    # Bronchitis / Bronchial Asthma
    ("Albuterol", "Bronchitis", "first_line"),
    ("Doxycycline", "Bronchitis", "second_line"),
    ("Albuterol", "Bronchial Asthma", "first_line"),
    ("Budesonide/Formoterol", "Bronchial Asthma", "first_line"),

    # COPD (already has some, add more)
    ("Tiotropium", "COPD", "first_line"),
    ("Budesonide/Formoterol", "COPD", "first_line"),

    # Common Cold (supportive)
    ("Acetaminophen", "Common Cold", "first_line"),
    ("Ibuprofen", "Common Cold", "first_line"),

    # Allergy
    ("Cetirizine", "Allergy", "first_line"),
    ("Diphenhydramine", "Allergy", "second_line"),

    # AIDS
    ("Tenofovir/Emtricitabine/Efavirenz", "AIDS", "first_line"),

    # Glaucoma
    ("Timolol Ophthalmic", "Glaucoma", "first_line"),
    ("Latanoprost", "Glaucoma", "first_line"),

    # Chronic Kidney Disease (supportive)
    ("Losartan", "Chronic Kidney Disease", "first_line"),
    ("Amlodipine", "Chronic Kidney Disease", "second_line"),

    # Cirrhosis
    ("Furosemide", "Cirrhosis", "first_line"),
    ("Spironolactone", "Cirrhosis", "first_line"),

    # Alcoholic hepatitis
    ("Prednisone", "Alcoholic hepatitis", "first_line"),

    # Irritable Bowel Syndrome
    ("Loperamide", "Irritable Bowel Syndrome", "first_line"),
    ("Ondansetron", "Irritable Bowel Syndrome", "second_line"),

    # Varicose veins
    ("Diosmin", "Varicose veins", "first_line"),
    ("Compression Stockings", "Varicose veins", "first_line"),

    # Jaundice (treat underlying cause)
    ("Omeprazole", "Jaundice", "second_line"),

    # Cervical spondylosis
    ("Ibuprofen", "Cervical spondylosis", "first_line"),
    ("Gabapentin", "Cervical spondylosis", "second_line"),

    # Arthritis (generic)
    ("Ibuprofen", "Arthritis", "first_line"),
    ("Naproxen", "Arthritis", "first_line"),
    ("Methotrexate", "Arthritis", "second_line"),

    # Vertigo
    ("Meclizine", "(vertigo) Paroymsal  Positional Vertigo", "first_line"),

    # Diabetes (generic node — different from Type 2 Diabetes)
    ("Metformin", "Diabetes", "first_line"),
    ("Insulin Glargine", "Diabetes", "second_line"),

    # Chronic cholestasis
    ("Ursodiol", "Chronic cholestasis", "first_line"),

    # Dimorphic hemorrhoids
    ("Hydrocortisone Cream", "Dimorphic hemmorhoids(piles)", "first_line"),
    ("Diosmin", "Dimorphic hemmorhoids(piles)", "first_line"),

    # Cataract — no drug, surgical
    # Drug Reaction — discontinue offending drug
    # Paralysis (brain hemorrhage) — supportive care
]

# Additional drugs referenced but not yet in NEW_DRUGS
EXTRA_DRUGS = [
    ("Cetirizine", "Antihistamine", "10mg daily"),
    ("Diphenhydramine", "Antihistamine", "25-50mg every 4-6 hours"),
    ("Meclizine", "Antihistamine / Antiemetic", "25mg 1-4 times daily"),
    ("Ursodiol", "Bile Acid", "13-15mg/kg/day in divided doses"),
    ("Amlodipine", "Calcium Channel Blocker", "5-10mg daily"),
]

# ── New INTERACTS_WITH relationships ──────────────────────────────────────────
# (drug1, drug2, severity, effect)
NEW_INTERACTIONS = [
    ("Isoniazid", "Rifampin", "moderate", "Both hepatotoxic; combined use increases liver injury risk. Monitor LFTs."),
    ("Isoniazid", "Phenytoin", "major", "Isoniazid inhibits phenytoin metabolism, causing toxicity. Monitor levels."),
    ("Rifampin", "Warfarin", "major", "Rifampin is a potent CYP3A4 inducer; dramatically reduces warfarin effect. Increase warfarin dose and monitor INR."),
    ("Methotrexate", "Ibuprofen", "major", "NSAIDs reduce methotrexate renal clearance, increasing toxicity risk."),
    ("Methotrexate", "Naproxen", "major", "NSAIDs reduce methotrexate renal clearance. Avoid concurrent use."),
    ("Isotretinoin", "Methotrexate", "major", "Both hepatotoxic; additive liver toxicity risk."),
    ("Isotretinoin", "Doxycycline", "major", "Both cause intracranial hypertension (pseudotumor cerebri). Contraindicated together."),
    ("Fluconazole", "Warfarin", "major", "Fluconazole inhibits CYP2C9, increasing warfarin levels and bleeding risk."),
    ("Fluconazole", "Metformin", "moderate", "Fluconazole may increase metformin levels. Monitor blood glucose."),
    ("Valproic Acid", "Aspirin", "major", "Aspirin displaces valproic acid from protein binding, increasing free levels and toxicity."),
    ("Clopidogrel", "Omeprazole", "moderate", "Omeprazole inhibits CYP2C19, reducing clopidogrel activation. Use pantoprazole instead."),
    ("Duloxetine", "Ibuprofen", "moderate", "SNRI + NSAID increases GI bleeding risk. Consider PPI prophylaxis."),
    ("Duloxetine", "Naproxen", "moderate", "SNRI + NSAID increases GI bleeding risk."),
    ("Pregabalin", "Gabapentin", "moderate", "Overlapping mechanism; additive CNS depression (sedation, respiratory depression)."),
    ("Donepezil", "Metoprolol", "moderate", "Cholinesterase inhibitor + beta blocker may cause additive bradycardia."),
    ("Chloroquine", "Digoxin", "major", "Chloroquine increases digoxin levels. Monitor closely."),
    ("Oseltamivir", "Warfarin", "moderate", "Oseltamivir may affect INR. Monitor warfarin therapy."),
    ("Paxlovid (Nirmatrelvir/Ritonavir)", "Atorvastatin", "major", "Ritonavir inhibits CYP3A4, dramatically increasing statin levels. Withhold statin during Paxlovid."),
    ("Paxlovid (Nirmatrelvir/Ritonavir)", "Warfarin", "major", "Ritonavir alters warfarin metabolism unpredictably. Close INR monitoring required."),
    ("Alendronate", "Ibuprofen", "moderate", "Both cause GI irritation; combined use increases ulcer/esophagitis risk."),
    ("Alendronate", "Naproxen", "moderate", "Bisphosphonate + NSAID increases GI ulceration risk."),
]

# ── New CONTRAINDICATED_WITH relationships ────────────────────────────────────
# (drug_name, condition_name, severity, reason)
NEW_CONTRAINDICATIONS = [
    ("Isotretinoin", "Pregnancy", "major", "Highly teratogenic — causes severe birth defects. Absolute contraindication."),
    ("Methotrexate", "Pregnancy", "major", "Abortifacient and teratogenic. Contraindicated in pregnancy."),
    ("Valproic Acid", "Pregnancy", "major", "Neural tube defects risk. Avoid in women of childbearing potential."),
    ("Chloroquine", "Epilepsy", "moderate", "Chloroquine lowers seizure threshold. Use caution or avoid."),
    ("Isoniazid", "Cirrhosis", "major", "Hepatotoxic; contraindicated in active liver disease."),
    ("Pyrazinamide", "Cirrhosis", "major", "Hepatotoxic; avoid in severe liver disease."),
    ("Rifampin", "Cirrhosis", "major", "Hepatotoxic; avoid or use with extreme caution in liver disease."),
    ("Propranolol", "Asthma", "major", "Non-selective beta blockade causes bronchospasm. Contraindicated."),
    ("Timolol Ophthalmic", "Asthma", "major", "Systemic beta-blockade from eye drops can trigger bronchospasm."),
    ("Methimazole", "Pregnancy", "major", "Teratogenic in first trimester. Use PTU instead."),
    ("Meropenem", "Epilepsy", "moderate", "May reduce valproic acid levels dramatically. Avoid combination."),
    ("Duloxetine", "Cirrhosis", "major", "Extensively hepatically metabolized. Avoid in liver disease."),
    ("Alendronate", "Chronic Kidney Disease", "major", "Contraindicated when eGFR <35. Risk of worsening renal function."),
    ("Allopurinol", "Chronic Kidney Disease", "moderate", "Dose reduction required. Risk of accumulation and hypersensitivity."),
]


def run_enrichment():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    stats = {"drugs": 0, "treats": 0, "interactions": 0, "contraindications": 0}

    with driver.session(database="neo4j") as session:
        # 1. Create Drug nodes
        print("💊 Creating Drug nodes...")
        all_drugs = NEW_DRUGS + EXTRA_DRUGS
        for name, drug_class, dosage in all_drugs:
            result = session.run("""
                MERGE (d:Drug {name: $name})
                SET d.drug_class = $drug_class,
                    d.common_dosage = $dosage,
                    d.last_updated = timestamp()
                RETURN d.name
            """, name=name, drug_class=drug_class, dosage=dosage)
            if result.single():
                stats["drugs"] += 1

        print(f"  ✓ {stats['drugs']} Drug nodes merged")

        # 2. TREATS relationships
        print("💉 Creating TREATS relationships...")
        for drug_name, disease_name, line in TREATS_RELS:
            result = session.run("""
                MATCH (drug:Drug {name: $drug_name})
                MATCH (d:Disease)
                WHERE d.name = $disease_name
                   OR toLower(d.name) = toLower($disease_name)
                MERGE (drug)-[r:TREATS]->(d)
                SET r.line = $line
                RETURN drug.name, d.name
            """, drug_name=drug_name, disease_name=disease_name, line=line)
            matches = list(result)
            if matches:
                stats["treats"] += len(matches)
            else:
                print(f"  ⚠ No match: {drug_name} → {disease_name}")

        print(f"  ✓ {stats['treats']} TREATS relationships merged")

        # 3. INTERACTS_WITH relationships
        print("⚠️ Creating INTERACTS_WITH relationships...")
        for drug1, drug2, severity, effect in NEW_INTERACTIONS:
            result = session.run("""
                MATCH (d1:Drug {name: $drug1})
                MATCH (d2:Drug {name: $drug2})
                MERGE (d1)-[r:INTERACTS_WITH]-(d2)
                SET r.severity = $severity,
                    r.effect = $effect
                RETURN d1.name, d2.name
            """, drug1=drug1, drug2=drug2, severity=severity, effect=effect)
            if result.single():
                stats["interactions"] += 1
            else:
                print(f"  ⚠ Drug not found: {drug1} or {drug2}")

        print(f"  ✓ {stats['interactions']} INTERACTS_WITH relationships merged")

        # 4. CONTRAINDICATED_WITH relationships
        print("🚫 Creating CONTRAINDICATED_WITH relationships...")
        for drug_name, cond_name, severity, reason in NEW_CONTRAINDICATIONS:
            # Try matching Disease first, then Condition
            result = session.run("""
                MATCH (drug:Drug {name: $drug_name})
                OPTIONAL MATCH (d:Disease) WHERE d.name = $cond_name OR toLower(d.name) = toLower($cond_name)
                OPTIONAL MATCH (c:Condition) WHERE c.name = $cond_name OR toLower(c.name) = toLower($cond_name)
                WITH drug, COALESCE(d, c) as target
                WHERE target IS NOT NULL
                MERGE (drug)-[r:CONTRAINDICATED_WITH]->(target)
                SET r.severity = $severity,
                    r.reason = $reason
                RETURN drug.name, target.name
            """, drug_name=drug_name, cond_name=cond_name, severity=severity, reason=reason)
            match = result.single()
            if match:
                stats["contraindications"] += 1
            else:
                # Create as Condition node if not found
                session.run("""
                    MATCH (drug:Drug {name: $drug_name})
                    MERGE (c:Condition {name: $cond_name})
                    MERGE (drug)-[r:CONTRAINDICATED_WITH]->(c)
                    SET r.severity = $severity,
                        r.reason = $reason
                """, drug_name=drug_name, cond_name=cond_name, severity=severity, reason=reason)
                stats["contraindications"] += 1
                print(f"  + Created Condition node: {cond_name}")

        print(f"  ✓ {stats['contraindications']} CONTRAINDICATED_WITH relationships merged")

    # Summary
    print("\n" + "=" * 60)
    print("ENRICHMENT COMPLETE")
    print("=" * 60)
    print(f"  💊 Drug nodes:            {stats['drugs']}")
    print(f"  💉 TREATS:                {stats['treats']}")
    print(f"  ⚠️  INTERACTS_WITH:        {stats['interactions']}")
    print(f"  🚫 CONTRAINDICATED_WITH:  {stats['contraindications']}")
    print("=" * 60)

    # Verify final counts
    with driver.session(database="neo4j") as session:
        print("\n📊 FINAL GRAPH COUNTS:")
        for label in ["Drug", "Disease", "Symptom", "Precaution", "Condition"]:
            count = session.run(f"MATCH (n:{label}) RETURN count(n) as c").single()["c"]
            print(f"  {label}: {count}")
        for rel in ["TREATS", "INTERACTS_WITH", "CONTRAINDICATED_WITH", "HAS_SYMPTOM", "HAS_PRECAUTION"]:
            count = session.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) as c").single()["c"]
            print(f"  {rel}: {count}")

        # Check uncovered diseases
        result = session.run("""
            MATCH (d:Disease) WHERE NOT exists { (:Drug)-[:TREATS]->(d) }
            RETURN count(d) as c
        """)
        uncovered = result.single()["c"]
        print(f"\n  Diseases still without drugs: {uncovered}")

    driver.close()


if __name__ == "__main__":
    run_enrichment()
