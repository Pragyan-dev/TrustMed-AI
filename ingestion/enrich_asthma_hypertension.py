"""
TrustMed-AI Knowledge Base Enrichment Script
=============================================
Enriches the ChromaDB vector database with comprehensive clinical content
for Asthma and Hypertension to improve retrieval quality.

Adds documents across all 3 collections: diseases, symptoms, medicines
Uses the same embedding model (all-MiniLM-L6-v2) and document format.

Usage:
    python ingestion/enrich_asthma_hypertension.py
"""

import os
import sys
import json
import chromadb
from sentence_transformers import SentenceTransformer

# ─── Configuration ───────────────────────────────────────────────────────────

CHROMA_DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
MAX_CHARS_PER_CHUNK = 2000
CHUNK_OVERLAP = 200
BATCH_SIZE = 64

# ─── Comprehensive Asthma Documents ─────────────────────────────────────────

ASTHMA_DISEASES = [
    {
        "id_prefix": "enrich_asthma_subtypes",
        "disease_name": "Asthma - Subtypes and Classification",
        "url": "https://www.nhlbi.nih.gov/health/asthma/types",
        "text": """Table: diseases
Name: Asthma - Subtypes and Classification
URL: https://www.nhlbi.nih.gov/health/asthma/types

Description:
Asthma is classified into several distinct subtypes based on triggers, severity, and underlying mechanisms. Understanding asthma subtypes is critical for targeted treatment. The major classifications include allergic asthma, non-allergic asthma, exercise-induced bronchoconstriction, occupational asthma, and aspirin-exacerbated respiratory disease. Severity is graded as intermittent, mild persistent, moderate persistent, and severe persistent based on symptom frequency, nighttime awakenings, rescue inhaler use, and lung function tests. Eosinophilic asthma is characterized by high eosinophil counts and often responds to biologic therapies. Neutrophilic asthma is more common in adults and may be steroid-resistant. Allergic asthma accounts for approximately 60% of all asthma cases and is driven by IgE-mediated immune responses to environmental allergens.

Symptoms:
Intermittent asthma involves symptoms less than 2 days per week and nighttime awakenings less than 2 times per month. Mild persistent asthma involves symptoms more than 2 days per week but not daily. Moderate persistent asthma involves daily symptoms and nighttime awakenings more than once per week. Severe persistent asthma involves symptoms throughout the day with frequent nighttime awakenings. Exercise-induced bronchoconstriction typically occurs 5-20 minutes after starting exercise, with peak symptoms at 8-15 minutes after stopping. Cough-variant asthma presents primarily with chronic cough without typical wheezing. Occupational asthma symptoms worsen during work exposure and improve on weekends or vacations.

Causes:
Allergic asthma is triggered by allergens including dust mites, cockroach droppings, pet dander, pollen, and mold spores. Non-allergic asthma can be triggered by viral respiratory infections, exercise, cold air, stress, GERD, smoke, chemical fumes, and strong odors. Occupational asthma is caused by workplace irritants including isocyanates, flour dust, wood dust, latex, animal proteins, and chemical agents. Aspirin-exacerbated respiratory disease involves a triad of asthma, nasal polyps, and sensitivity to aspirin and NSAIDs. Genetic factors include polymorphisms in genes encoding IL-4, IL-13, ADAM33, and beta-2 adrenergic receptors. Obesity-associated asthma involves complex interactions between adipose tissue inflammation and airway hyperresponsiveness.

Treatment:
Step-wise approach to asthma management: Step 1 (Intermittent) uses SABA as needed. Step 2 (Mild Persistent) adds low-dose ICS. Step 3 (Moderate Persistent) uses low-dose ICS plus LABA or medium-dose ICS. Step 4 uses medium-dose ICS plus LABA. Step 5 (Severe Persistent) uses high-dose ICS plus LABA. Step 6 adds oral corticosteroids or biologic therapies. Biologic therapies for severe asthma include omalizumab (anti-IgE), mepolizumab (anti-IL-5), benralizumab (anti-IL-5R), dupilumab (anti-IL-4R), and tezepelumab (anti-TSLP). Bronchial thermoplasty is a procedure for severe refractory asthma that reduces airway smooth muscle mass.

Prevention:
Allergen avoidance strategies include encasing mattresses and pillows, using HEPA filters, maintaining indoor humidity below 50%, removing carpeting, and regular cleaning. Immunotherapy (allergy shots or sublingual tablets) can modify the underlying allergic disease. Annual influenza vaccination is recommended. Avoiding known triggers, maintaining an asthma action plan, and regular follow-up appointments are essential. Smoking cessation is critical. Weight management can improve asthma control in obese patients.
"""
    },
    {
        "id_prefix": "enrich_asthma_pathophysiology",
        "disease_name": "Asthma - Pathophysiology and Mechanisms",
        "url": "https://www.ncbi.nlm.nih.gov/books/NBK430901/",
        "text": """Table: diseases
Name: Asthma - Pathophysiology and Mechanisms
URL: https://www.ncbi.nlm.nih.gov/books/NBK430901/

Description:
Asthma pathophysiology involves chronic airway inflammation, bronchial hyperresponsiveness, and reversible airflow obstruction. The inflammatory process involves multiple cell types including mast cells, eosinophils, T lymphocytes (particularly Th2 cells), macrophages, neutrophils, and epithelial cells. In allergic asthma, inhaled allergens are processed by dendritic cells which present antigens to T helper cells, promoting Th2 differentiation. Th2 cells release cytokines including IL-4, IL-5, and IL-13 which drive IgE production, eosinophil recruitment, and mucus hypersecretion. Mast cell degranulation releases histamine, prostaglandins, and leukotrienes causing immediate bronchoconstriction. The late-phase response occurs 4-8 hours later with eosinophilic inflammation. Chronic inflammation leads to airway remodeling including subepithelial fibrosis, smooth muscle hypertrophy, angiogenesis, and goblet cell hyperplasia.

Symptoms:
Airway inflammation causes mucosal edema, mucus plugging, and smooth muscle contraction leading to narrowing of airways. Patients experience wheezing (a high-pitched whistling sound during expiration), dyspnea (difficulty breathing), chest tightness, and cough. Peak expiratory flow (PEF) variability greater than 20% is suggestive of asthma. FEV1/FVC ratio below 0.70 indicates airflow obstruction. Bronchodilator reversibility is defined as an increase in FEV1 of 12% and 200 mL after inhaling a short-acting beta-agonist. Diurnal variation in symptoms is characteristic, with worsening typically at night and early morning due to circadian changes in cortisol, epinephrine, and vagal tone. Status asthmaticus is a severe, life-threatening asthma exacerbation that does not respond to standard bronchodilator therapy.

Causes:
The hygiene hypothesis proposes that reduced microbial exposure in early childhood leads to immune dysregulation favoring allergic responses. Viral respiratory infections, particularly rhinovirus and respiratory syncytial virus (RSV), are major triggers for asthma exacerbations and may contribute to asthma development in children. Air pollution including particulate matter (PM2.5), nitrogen dioxide, ozone, and sulfur dioxide can worsen asthma. Genetic susceptibility involves over 100 genes associated with asthma risk, including ORMDL3, GSDMB, IL33, and TSLP. Epigenetic modifications including DNA methylation and histone acetylation can be influenced by environmental exposures and may transmit asthma risk across generations. Microbiome alterations in early life, particularly reduced bacterial diversity, have been associated with increased asthma risk.

Diagnosis:
Spirometry is the gold standard for diagnosing asthma, showing reversible airflow obstruction. Methacholine challenge testing demonstrates bronchial hyperresponsiveness with a provocative concentration causing a 20% fall in FEV1 (PC20) less than 16 mg/mL. Fractional exhaled nitric oxide (FeNO) levels above 50 ppb in adults suggest eosinophilic airway inflammation. Blood eosinophil counts above 300 cells per microliter and total IgE levels help identify allergic asthma phenotype. Skin prick testing or specific IgE blood tests identify relevant allergens. Chest X-ray is usually normal but may show hyperinflation during exacerbations. High-resolution CT can reveal airway wall thickening and mucus plugging in severe cases.

Treatment:
Inhaled corticosteroids (ICS) are the cornerstone of asthma controller therapy, reducing airway inflammation, decreasing exacerbation risk, and improving lung function. Common ICS include beclomethasone, budesonide, ciclesonide, fluticasone propionate, fluticasone furoate, and mometasone. Long-acting beta-agonists (LABAs) including salmeterol and formoterol are always used in combination with ICS, never as monotherapy. Long-acting muscarinic antagonists (LAMAs) such as tiotropium can be added as triple therapy. Leukotriene receptor antagonists like montelukast and zafirlukast offer additional anti-inflammatory effects. Short-acting beta-agonists (SABAs) like albuterol and levalbuterol are used for acute symptom relief. Systemic corticosteroids (prednisone, methylprednisolone) are used for moderate-to-severe exacerbations, typically for 5-7 days.
"""
    },
    {
        "id_prefix": "enrich_asthma_pediatric",
        "disease_name": "Asthma - Pediatric and Special Populations",
        "url": "https://www.aap.org/asthma",
        "text": """Table: diseases
Name: Asthma - Pediatric and Special Populations
URL: https://www.aap.org/asthma

Description:
Pediatric asthma is the most common chronic disease of childhood, affecting approximately 6 million children in the United States. Asthma in children under 5 years is particularly challenging to diagnose due to the inability to perform reliable spirometry. Recurrent wheezing in early childhood may represent transient viral-induced wheezing rather than true asthma. The modified Asthma Predictive Index (mAPI) helps predict which wheezing children will develop persistent asthma. Asthma in pregnancy requires careful management as both poorly controlled asthma and overtreatment pose risks to mother and fetus. Asthma in the elderly is often underdiagnosed and may coexist with COPD (asthma-COPD overlap syndrome, or ACOS). Severe asthma affects approximately 5-10% of all asthma patients but accounts for over 50% of asthma healthcare costs.

Symptoms:
Children may present with recurrent cough (especially at night, during exercise, or with viral infections), wheezing, chest tightness, and shortness of breath. In infants, feeding difficulties, poor weight gain, and respiratory distress may be the primary manifestations. Exercise-induced symptoms are very common in children and may be the only presenting complaint. Nocturnal symptoms are particularly common in pediatric asthma. Cough-variant asthma is common in children, presenting with persistent cough without overt wheezing. In pregnancy, approximately one-third of women experience worsening asthma, one-third improve, and one-third remain stable. Elderly patients may have atypical presentations including isolated dyspnea or reduced exercise tolerance without wheezing.

Causes:
Respiratory viral infections (particularly rhinovirus and RSV) are the most common triggers in children. Early life risk factors include maternal smoking during pregnancy, premature birth, low birth weight, early respiratory infections, and family history of atopy. Allergen sensitization in early childhood, particularly to indoor allergens (dust mites, cockroach, cat, dog), is strongly associated with asthma development. Outdoor air pollution exposure, particularly traffic-related, increases asthma risk in children. Obesity in children is both a risk factor for developing asthma and a factor in more severe disease. In pregnancy, hormonal changes, GERD, and rhinitis can worsen asthma control.

Treatment:
Pediatric asthma treatment follows age-specific stepwise guidelines. For children 0-4 years: Step 1 uses SABA as needed; Step 2 adds low-dose ICS; Step 3 uses medium-dose ICS; Step 4 uses medium-dose ICS plus LABA or montelukast. For children 5-11 years, the steps parallel adult guidelines with age-appropriate dosing. Nebulized medications may be preferred for young children unable to use inhalers. Spacer devices with valved holding chambers are essential for children using metered-dose inhalers. Montelukast is an alternative controller for mild persistent asthma in children. In pregnancy, budesonide is the preferred ICS due to the most safety data. Stepping down therapy should be attempted when asthma is well-controlled for at least 3 months.

Prevention:
Breastfeeding for at least 4-6 months may reduce early childhood wheezing. Avoidance of tobacco smoke exposure during pregnancy and early childhood is critical. Early introduction of diverse foods may reduce allergic sensitization. School-based asthma management programs improve outcomes in children. Indoor environmental interventions targeting multiple allergens and irritants can reduce asthma morbidity. Regular physical activity should be encouraged with appropriate pretreatment. Asthma action plans tailored for schools help ensure appropriate emergency response. Preconception counseling for women with asthma helps optimize control before pregnancy.
"""
    },
    {
        "id_prefix": "enrich_asthma_emergency",
        "disease_name": "Asthma - Acute Exacerbation and Emergency Management",
        "url": "https://www.nhlbi.nih.gov/health/asthma/management",
        "text": """Table: diseases
Name: Asthma - Acute Exacerbation and Emergency Management
URL: https://www.nhlbi.nih.gov/health/asthma/management

Description:
An asthma exacerbation is an acute or subacute worsening of symptoms and lung function that requires a change in treatment. Exacerbations can range from mild (managed at home with increased rescue inhaler use) to severe (requiring emergency department treatment or hospitalization) to life-threatening (status asthmaticus requiring intensive care). Approximately 1.8 million emergency department visits and 439,000 hospitalizations occur annually in the US due to asthma. Risk factors for fatal asthma include previous near-fatal exacerbation requiring intubation, hospitalization or ED visit in the past year, currently using or recently discontinued systemic corticosteroids, not currently using ICS, over-reliance on SABA (using more than 1 canister per month), history of psychiatric disease or psychosocial problems, poor adherence to medications, and food allergy in a patient with asthma.

Symptoms:
Mild exacerbation: increased cough, wheeze, chest tightness; PEF greater than 70% predicted; able to speak in full sentences; respiratory rate mildly increased. Moderate exacerbation: significant dyspnea, speaking in phrases, PEF 40-69% predicted, accessory muscle use, respiratory rate 20-30 breaths per minute. Severe exacerbation: breathless at rest, speaking in single words, PEF less than 40% predicted, significant accessory muscle use, respiratory rate greater than 30, heart rate greater than 120, oxygen saturation less than 90%. Life-threatening features include silent chest (no wheeze due to minimal airflow), cyanosis, bradycardia, hypotension, confusion, altered consciousness, and exhaustion. Peak flow less than 25% predicted or unable to perform PEF indicates critical airflow limitation.

Treatment:
Home management: increase SABA use to 4-8 puffs every 20 minutes for up to 3 treatments. Begin or increase ICS dose (quadrupling the dose). If no improvement after 1 hour, seek emergency care. Emergency department treatment: continuous nebulized albuterol 2.5-5 mg every 20 minutes for 3 doses, then 2.5-5 mg every 1-4 hours as needed. Add ipratropium bromide 0.5 mg nebulized every 20 minutes for 3 doses in moderate-severe exacerbations. Systemic corticosteroids: prednisone 40-60 mg orally or methylprednisolone 125 mg IV for severe cases. Magnesium sulfate 2 g IV over 20 minutes for severe exacerbations not responding to initial treatment. Oxygen therapy to maintain SpO2 94-98%. For life-threatening cases: consider IV aminophylline, IV salbutamol, heliox, and noninvasive ventilation. Mechanical ventilation for respiratory failure with permissive hypercapnia strategy. Discharge criteria: PEF greater than 70% predicted, symptom improvement, ability to use inhaler correctly, written asthma action plan provided.

Living With:
Every asthma patient should have a written asthma action plan with three zones: Green (doing well, continue controller medications), Yellow (getting worse, increase medications and call doctor), Red (medical alert, use rescue medications and seek emergency care immediately). Asthma action plans should include specific PEF values or symptom criteria for each zone, medication names and doses, and emergency contact numbers. Patients should carry rescue inhalers at all times. Regular peak flow monitoring helps detect worsening before symptoms become severe. After an exacerbation, follow-up within 1-4 weeks is essential to review triggers, adjust medications, and reinforce the action plan.
"""
    },
]

ASTHMA_SYMPTOMS = [
    {
        "id_prefix": "enrich_asthma_symp_detailed",
        "disease_name": "Asthma",
        "text": """Table: symptoms
Disease name: Asthma
URL: https://www.mayoclinic.org/diseases-conditions/asthma/symptoms-causes

Overview:
Asthma is a chronic respiratory condition characterized by inflammation and narrowing of the airways, leading to recurrent episodes of wheezing, breathlessness, chest tightness, and coughing. It affects approximately 339 million people worldwide and 25 million Americans. Asthma severity ranges from intermittent to severe persistent and can vary over time. The condition involves bronchial hyperresponsiveness where airways react excessively to various triggers. Asthma can begin at any age but most commonly starts in childhood.

Symptoms:
The cardinal symptoms of asthma include recurrent wheezing (a high-pitched whistling sound during breathing, especially on expiration), shortness of breath (dyspnea), chest tightness or pressure, and cough (particularly at night, early morning, or during exercise). Symptoms characteristically vary in intensity over time and are often worse at night or early morning. Exercise-induced bronchoconstriction causes symptoms during or after physical activity including running, swimming, or exposure to cold dry air. Cough-variant asthma presents predominantly with dry, nonproductive cough without typical wheezing. Nocturnal asthma involves worsening of symptoms during sleep, typically between 2-4 AM. Symptoms may include difficulty speaking in complete sentences during moderate attacks, visible use of neck and chest accessory muscles during severe attacks, nasal flaring and intercostal retractions in children, audible wheezing even without a stethoscope in severe cases, and inability to lie flat (orthopnea) during acute episodes. Asthma symptoms may be accompanied by allergic rhinitis (sneezing, runny nose, nasal congestion), allergic conjunctivitis (itchy watery eyes), and atopic dermatitis (eczema) as part of the atopic triad.

Causes:
Asthma triggers include aeroallergens (house dust mites, cockroach allergens, animal dander from cats and dogs, mold spores, pollen from trees, grasses, and weeds), respiratory infections (rhinovirus, influenza, respiratory syncytial virus, parainfluenza), irritants (tobacco smoke, wood smoke, air pollution, strong odors, chemical fumes, cleaning products), occupational exposures (isocyanates, flour dust, wood dust, latex, animal proteins, chemical agents), medications (aspirin, NSAIDs, beta-blockers), physical factors (exercise, cold air, hyperventilation, laughing), gastroesophageal reflux disease (GERD), emotional stress and anxiety, hormonal changes (menstrual cycle, pregnancy), food allergens and sulfites in wine and dried fruits, weather changes (thunderstorms, cold fronts, humidity changes).

Risk factors:
Family history of asthma or allergic diseases (atopy), personal history of atopic dermatitis or allergic rhinitis, obesity (BMI greater than 30), tobacco smoke exposure (active or passive), occupational chemical or dust exposure, living in urban areas with high air pollution, premature birth or low birth weight, respiratory infections in early childhood (particularly RSV bronchiolitis), African American and Puerto Rican ethnicity (higher prevalence and severity), low socioeconomic status, indoor allergen exposure, lack of breastfeeding, maternal smoking during pregnancy, stress and psychosocial factors, vitamin D deficiency.

Complications:
Poorly controlled asthma can lead to permanent airway remodeling with fixed airflow obstruction, recurrent emergency department visits and hospitalizations, status asthmaticus requiring ICU admission and mechanical ventilation, pneumothorax (air leak around the lung), atelectasis (lung collapse from mucus plugging), respiratory failure, medication side effects from chronic systemic corticosteroid use (osteoporosis, adrenal suppression, diabetes, cataracts, growth suppression in children, immunosuppression), decreased quality of life with limitation of physical activities, missed school or work days, sleep disruption, anxiety and depression, impaired growth in children with poorly controlled severe asthma, increased risk of pneumonia, and rarely death (approximately 3,500 deaths per year in the US).
"""
    },
    {
        "id_prefix": "enrich_asthma_symp_triggers",
        "disease_name": "Asthma - Trigger Management",
        "text": """Table: symptoms
Disease name: Asthma - Trigger Management
URL: https://www.epa.gov/asthma/asthma-triggers

Overview:
Identifying and managing asthma triggers is a cornerstone of asthma management. Triggers vary between individuals and understanding personal triggers allows for targeted avoidance strategies. Environmental control measures can significantly reduce asthma symptoms and exacerbation frequency. The most common indoor triggers are dust mites, pet dander, cockroach allergens, mold, and secondhand smoke. Outdoor triggers include pollen, air pollution, and weather changes.

Symptoms:
Trigger exposure leads to two phases of airway response. The early-phase response occurs within minutes and involves mast cell degranulation causing bronchospasm, mucus secretion, and vasodilation. Symptoms include sudden onset of wheezing, cough, and chest tightness lasting 1-2 hours. The late-phase response occurs 4-8 hours after exposure and involves eosinophil and lymphocyte infiltration causing prolonged inflammation, increased mucus production, and sustained airway narrowing. This phase can last 12-24 hours and contributes to persistent symptoms. Repeated trigger exposure leads to chronic airway inflammation and increased bronchial hyperresponsiveness, making airways more sensitive to lower levels of triggers over time.

Causes:
Dust mites thrive in warm, humid environments and are found in bedding, upholstered furniture, and carpeting. Their fecal particles are the primary allergen. Pet allergens come from saliva, urine, and skin flakes and can remain airborne for hours. Cat allergen (Fel d 1) is particularly small and sticky, persisting in environments months after cat removal. Cockroach allergens are prevalent in urban settings and are found in kitchens, bathrooms, and basements. Mold grows in damp areas including bathrooms, basements, and around windows. Common indoor molds include Aspergillus, Penicillium, and Cladosporium. Tobacco smoke contains over 7,000 chemicals that directly irritate and inflame airways. Nitrogen dioxide from gas stoves and heaters is a significant indoor air pollutant. Volatile organic compounds from paints, cleaning products, and air fresheners can trigger symptoms.

Risk factors:
Living in older housing with poor ventilation, high indoor humidity above 60%, presence of pets in the home, cockroach infestation, water damage or visible mold growth, gas stove without exhaust ventilation, carpeted flooring especially in bedrooms, use of wood-burning stoves or fireplaces, proximity to highways or industrial areas, seasonal pollen exposure, occupational exposures in healthcare, farming, baking, painting, and woodworking.

Complications:
Failure to identify and manage triggers results in chronic inflammation and progressive airway damage. Persistent allergen exposure can lead to allergic sensitization where the immune system becomes increasingly reactive. Continued exposure to respiratory irritants accelerates airway remodeling. Occupational trigger exposure without proper protection may lead to permanent lung damage. Mold exposure in water-damaged buildings can cause severe exacerbations and rarely allergic bronchopulmonary aspergillosis (ABPA). Secondhand smoke exposure increases exacerbation frequency, reduces medication efficacy, and accelerates lung function decline.
"""
    },
]

ASTHMA_MEDICINES = [
    {
        "id_prefix": "enrich_asthma_med_ics",
        "title": "Inhaled Corticosteroids for Asthma",
        "text": """Table: medicines
URL: https://www.nhlbi.nih.gov/health/asthma/treatment
Title: Inhaled Corticosteroids for Asthma

Introduction:
Inhaled corticosteroids (ICS) are the most effective long-term controller medications for persistent asthma. They reduce airway inflammation, decrease mucus production, reduce bronchial hyperresponsiveness, and prevent airway remodeling. ICS are recommended as first-line controller therapy for all severity levels of persistent asthma.

Body:
Available ICS medications include beclomethasone dipropionate (QVAR), budesonide (Pulmicort), ciclesonide (Alvesco), fluticasone propionate (Flovent), fluticasone furoate (Arnuity Ellipta), and mometasone furoate (Asmanex). Low-dose ICS equivalents: beclomethasone 80-240 mcg/day, budesonide 180-600 mcg/day, fluticasone propionate 88-264 mcg/day. Medium-dose: beclomethasone 240-480 mcg/day, budesonide 600-1200 mcg/day, fluticasone propionate 264-440 mcg/day. High-dose: beclomethasone greater than 480 mcg/day, budesonide greater than 1200 mcg/day, fluticasone propionate greater than 440 mcg/day. ICS take 1-2 weeks for noticeable benefit and up to 4-8 weeks for maximum effect. Common local side effects include oral candidiasis (thrush) and dysphonia (hoarseness), which can be minimized by using a spacer device and rinsing the mouth after each use. Systemic side effects at high doses may include adrenal suppression, decreased bone mineral density, cataracts, glaucoma, and growth suppression in children (typically less than 1 cm/year reduction). ICS are generally safe during pregnancy, with budesonide having the most safety data (FDA Category B).

Primary topic: Inhaled Corticosteroid

Further reading: NHLBI Expert Panel Report 4, GINA 2024 Guidelines, Cochrane Review on ICS for Asthma
"""
    },
    {
        "id_prefix": "enrich_asthma_med_laba",
        "title": "Long-Acting Beta-Agonists and Combination Inhalers for Asthma",
        "text": """Table: medicines
URL: https://www.drugs.com/drug-class/long-acting-beta-agonists.html
Title: Long-Acting Beta-Agonists and Combination Inhalers for Asthma

Introduction:
Long-acting beta-agonists (LABAs) provide sustained bronchodilation for 12 hours and are used as add-on therapy to inhaled corticosteroids for moderate-to-severe persistent asthma. LABAs should never be used as monotherapy for asthma due to increased risk of severe exacerbations and asthma-related death.

Body:
Available LABAs include salmeterol (Serevent, 50 mcg twice daily) and formoterol (Foradil, 12 mcg twice daily). Formoterol has a faster onset of action (1-3 minutes) compared to salmeterol (15-30 minutes). Vilanterol is an ultra-LABA with 24-hour duration, available only in combination products. Combination ICS/LABA inhalers provide both anti-inflammatory and bronchodilator effects in a single device, improving adherence. Major combination products include fluticasone propionate/salmeterol (Advair Diskus, Advair HFA), budesonide/formoterol (Symbicort), fluticasone furoate/vilanterol (Breo Ellipta), and mometasone/formoterol (Dulera). The SMART (Single Maintenance And Reliever Therapy) approach uses budesonide/formoterol as both daily controller and as-needed reliever, reducing exacerbation risk compared to fixed-dose ICS/LABA plus SABA rescue. Common side effects include tremor, palpitations, tachycardia, headache, and muscle cramps. Drug interactions: beta-blockers may reduce LABA efficacy; MAO inhibitors and tricyclic antidepressants may potentiate cardiovascular effects. Contraindicated as monotherapy without ICS due to FDA black box warning based on SMART, MIST, and other trials.

Primary topic: Long-Acting Beta-Agonist, Combination Inhaler

Further reading: FDA Safety Communication on LABA, GINA Step 3-5 Treatment Guidelines
"""
    },
    {
        "id_prefix": "enrich_asthma_med_biologics",
        "title": "Biologic Therapies for Severe Asthma",
        "text": """Table: medicines
URL: https://www.aaaai.org/conditions-treatments/drug-guide/biologics
Title: Biologic Therapies for Severe Asthma

Introduction:
Biologic therapies are targeted monoclonal antibody treatments for severe, uncontrolled asthma that persists despite high-dose ICS/LABA therapy. They target specific inflammatory pathways and have transformed the management of severe asthma, reducing exacerbations and corticosteroid dependence.

Body:
Omalizumab (Xolair): Anti-IgE monoclonal antibody. Indicated for moderate-to-severe allergic asthma in patients 6 years and older with elevated serum IgE (30-1500 IU/mL) and sensitization to perennial aeroallergens. Administered subcutaneously every 2-4 weeks. Dose based on body weight and baseline IgE level. Reduces exacerbations by 25-50%. Risk of anaphylaxis (0.1-0.2%), requiring 2-hour observation after first 3 doses. Mepolizumab (Nucala): Anti-IL-5 monoclonal antibody. Indicated for severe eosinophilic asthma in patients 6 years and older with blood eosinophils 150 cells/mcL or higher. Administered as 100 mg subcutaneous injection every 4 weeks. Reduces exacerbations by approximately 50% and allows oral corticosteroid dose reduction. Benralizumab (Fasenra): Anti-IL-5 receptor alpha monoclonal antibody. Indicated for severe eosinophilic asthma in patients 12 years and older. Administered as 30 mg subcutaneous injection every 4 weeks for first 3 doses, then every 8 weeks. Causes near-complete eosinophil depletion through antibody-dependent cell-mediated cytotoxicity. Dupilumab (Dupixent): Anti-IL-4 receptor alpha monoclonal antibody blocking both IL-4 and IL-13 signaling. Indicated for moderate-to-severe eosinophilic asthma or oral corticosteroid-dependent asthma in patients 6 years and older. Administered as 200-300 mg subcutaneously every 2 weeks. Also approved for atopic dermatitis, nasal polyps, and eosinophilic esophagitis. Tezepelumab (Tezspire): Anti-TSLP monoclonal antibody. First biologic approved for severe asthma regardless of phenotype. Targets thymic stromal lymphopoietin, an upstream epithelial cytokine. Administered as 210 mg subcutaneously every 4 weeks. Reduces exacerbations across eosinophilic and non-eosinophilic phenotypes.

Primary topic: Biologic Therapy, Monoclonal Antibody, Severe Asthma

Further reading: ERS/ATS Guidelines on Severe Asthma Biologics, GINA Difficult-to-Treat and Severe Asthma Guide
"""
    },
    {
        "id_prefix": "enrich_asthma_med_ltra",
        "title": "Leukotriene Modifiers and Other Asthma Controllers",
        "text": """Table: medicines
URL: https://www.drugs.com/drug-class/leukotriene-modifiers.html
Title: Leukotriene Modifiers and Other Asthma Controllers

Introduction:
Leukotriene receptor antagonists (LTRAs) and other controller medications provide additional anti-inflammatory and bronchodilator effects for asthma management. These medications can be used as alternatives or add-on therapies to inhaled corticosteroids.

Body:
Montelukast (Singulair): Leukotriene receptor antagonist taken as 10 mg tablet once daily at bedtime for adults, 5 mg chewable for children 6-14, and 4 mg granules for children 2-5. Blocks cysteinyl leukotrienes (CysLT1 receptor) which mediate bronchoconstriction, mucus secretion, and eosinophil recruitment. Particularly effective for exercise-induced bronchoconstriction and aspirin-sensitive asthma. FDA black box warning (2020) regarding neuropsychiatric events including agitation, depression, suicidal thoughts, and sleep disturbances. Zafirlukast (Accolate): Another LTRA, 20 mg twice daily for adults. Must be taken on an empty stomach. Less commonly used due to hepatotoxicity risk and drug interactions with warfarin. Zileuton (Zyflo): 5-lipoxygenase inhibitor, 600 mg four times daily (immediate release) or 1200 mg twice daily (extended release). Inhibits leukotriene synthesis rather than blocking receptors. Requires liver function monitoring due to hepatotoxicity risk. Theophylline: Methylxanthine bronchodilator with mild anti-inflammatory properties. Narrow therapeutic index requiring serum drug level monitoring (target 5-15 mcg/mL). Interactions with numerous medications including erythromycin, ciprofloxacin, and cimetidine. Side effects include nausea, headache, insomnia, tachycardia, and seizures at toxic levels. Tiotropium bromide (Spiriva Respimat): Long-acting muscarinic antagonist (LAMA) approved as add-on therapy for asthma in patients 6 years and older. 2.5 mcg two puffs once daily. Reduces exacerbations when added to ICS/LABA in severe asthma. Cromolyn sodium: Mast cell stabilizer, alternative controller for mild persistent asthma. Requires nebulization 4 times daily. Extremely safe but less effective than ICS. Primarily used in pediatric patients.

Primary topic: Leukotriene Modifier, Asthma Controller

Further reading: FDA Montelukast Safety Alert, NAEPP Step Therapy Guidelines
"""
    },
]

# ─── Comprehensive Hypertension Documents ────────────────────────────────────

HYPERTENSION_DISEASES = [
    {
        "id_prefix": "enrich_htn_classification",
        "disease_name": "Hypertension - Classification and Staging",
        "url": "https://www.heart.org/en/health-topics/high-blood-pressure/understanding-blood-pressure-readings",
        "text": """Table: diseases
Name: Hypertension - Classification and Staging
URL: https://www.heart.org/en/health-topics/high-blood-pressure/understanding-blood-pressure-readings

Description:
Hypertension (high blood pressure) is classified according to the 2017 ACC/AHA guidelines into distinct categories based on systolic and diastolic blood pressure readings. Normal blood pressure is defined as systolic less than 120 mmHg and diastolic less than 80 mmHg. Elevated blood pressure is systolic 120-129 mmHg and diastolic less than 80 mmHg. Stage 1 hypertension is systolic 130-139 mmHg or diastolic 80-89 mmHg. Stage 2 hypertension is systolic 140 mmHg or higher or diastolic 90 mmHg or higher. Hypertensive crisis is systolic greater than 180 mmHg and/or diastolic greater than 120 mmHg. Hypertension affects approximately 1.28 billion adults worldwide and nearly half of US adults (47%). It is the leading modifiable risk factor for cardiovascular disease, stroke, chronic kidney disease, and death globally. Primary (essential) hypertension accounts for 90-95% of cases with no identifiable cause, while secondary hypertension accounts for 5-10% and has an identifiable underlying cause.

Symptoms:
Hypertension is often called the silent killer because most people have no symptoms even with dangerously high readings. When symptoms occur, they may include severe headaches (particularly occipital, present upon waking), shortness of breath, nosebleeds, dizziness or lightheadedness, chest pain, visual changes (blurred vision, double vision), palpitations, fatigue, confusion, blood in urine. Hypertensive urgency presents with severely elevated blood pressure (greater than 180/120 mmHg) without evidence of target organ damage. Hypertensive emergency presents with severely elevated blood pressure with evidence of acute target organ damage including hypertensive encephalopathy (confusion, seizures), acute heart failure with pulmonary edema, acute coronary syndrome, aortic dissection, eclampsia, acute renal failure, or retinal hemorrhages and papilledema.

Causes:
Primary hypertension develops from complex interactions between genetic predisposition, environmental factors, and physiological mechanisms. Key pathophysiological mechanisms include increased peripheral vascular resistance, sodium and water retention by the kidneys, overactivation of the renin-angiotensin-aldosterone system (RAAS), increased sympathetic nervous system activity, endothelial dysfunction with reduced nitric oxide production, arterial stiffness from vascular remodeling, and inflammation. Secondary causes include renal parenchymal disease (most common secondary cause), renovascular disease (renal artery stenosis), primary aldosteronism (Conn syndrome), pheochromocytoma, Cushing syndrome, thyroid disorders (both hypo and hyperthyroidism), obstructive sleep apnea, coarctation of the aorta, medications (NSAIDs, oral contraceptives, decongestants, corticosteroids, cyclosporine), and illicit drugs (cocaine, amphetamines).

Diagnosis:
Blood pressure should be measured on at least 2-3 separate occasions using proper technique: patient seated quietly for 5 minutes, feet flat on floor, arm supported at heart level, appropriate cuff size (bladder encircling at least 80% of arm circumference). Ambulatory blood pressure monitoring (ABPM) over 24 hours is the gold standard for confirming hypertension and detecting white-coat hypertension and masked hypertension. Home blood pressure monitoring (HBPM) is an alternative using validated oscillometric devices. Laboratory evaluation includes basic metabolic panel (electrolytes, creatinine, glucose), lipid panel, complete blood count, urinalysis with albumin-to-creatinine ratio, thyroid-stimulating hormone, and 12-lead electrocardiogram. Additional testing for secondary causes when clinically suspected includes plasma aldosterone-to-renin ratio, 24-hour urine catecholamines and metanephrines, renal artery duplex ultrasonography, and sleep study.

Treatment:
Lifestyle modifications are recommended for all patients with elevated blood pressure or hypertension. The DASH diet (Dietary Approaches to Stop Hypertension) emphasizes fruits, vegetables, whole grains, lean proteins, and low-fat dairy while limiting sodium to less than 2300 mg/day (ideally less than 1500 mg/day). Regular aerobic exercise of 150 minutes per week of moderate intensity or 75 minutes of vigorous intensity. Weight loss targeting BMI 18.5-24.9 kg/m2 (approximately 1 mmHg reduction per 1 kg weight loss). Limit alcohol to 2 or fewer drinks per day for men, 1 or fewer for women. Smoking cessation. Pharmacological treatment is recommended for Stage 1 hypertension with cardiovascular risk factors or 10-year ASCVD risk of 10% or greater, and for all Stage 2 hypertension. First-line medications include thiazide diuretics, ACE inhibitors, ARBs, and calcium channel blockers.

Prevention:
Regular blood pressure screening starting at age 18 with annual checks after age 40 or earlier if risk factors present. Maintaining a healthy weight, following the DASH diet, regular physical activity, limiting sodium and alcohol intake, managing stress through relaxation techniques and adequate sleep, avoiding tobacco, and treating underlying conditions promptly. Population-level strategies include reducing sodium content in processed foods, promoting active lifestyles, and increasing access to healthy foods.
"""
    },
    {
        "id_prefix": "enrich_htn_complications",
        "disease_name": "Hypertension - Complications and Target Organ Damage",
        "url": "https://www.nhlbi.nih.gov/health/high-blood-pressure/complications",
        "text": """Table: diseases
Name: Hypertension - Complications and Target Organ Damage
URL: https://www.nhlbi.nih.gov/health/high-blood-pressure/complications

Description:
Chronic uncontrolled hypertension causes progressive damage to multiple organ systems through mechanisms including arteriosclerosis, endothelial injury, and increased mechanical stress on blood vessel walls. The major target organs affected include the heart, brain, kidneys, eyes, and peripheral vasculature. Cardiovascular complications are the leading cause of death in hypertensive patients. The relationship between blood pressure and cardiovascular risk is continuous, consistent, and independent of other risk factors, beginning at blood pressures as low as 115/75 mmHg. For every 20 mmHg increase in systolic blood pressure or 10 mmHg increase in diastolic blood pressure above 115/75, the risk of cardiovascular death doubles.

Symptoms:
Cardiac complications include left ventricular hypertrophy (LVH) causing diastolic dysfunction, heart failure (both HFpEF and HFrEF), coronary artery disease with angina and myocardial infarction, atrial fibrillation, and sudden cardiac death. Cerebrovascular complications include ischemic stroke, hemorrhagic stroke, transient ischemic attacks, vascular dementia, and cognitive decline. Renal complications include hypertensive nephrosclerosis leading to chronic kidney disease and potentially end-stage renal disease, microalbuminuria progressing to macroalbuminuria, and accelerated decline in glomerular filtration rate. Ophthalmologic complications include hypertensive retinopathy (graded I-IV by Keith-Wagener-Barker classification), retinal hemorrhages, cotton-wool spots, papilledema, and vision loss. Vascular complications include aortic aneurysm and dissection, peripheral artery disease, and erectile dysfunction.

Causes:
Sustained elevated blood pressure increases the workload on the heart, causing left ventricular hypertrophy and eventually heart failure. Mechanical stress on arterial walls promotes atherosclerosis and plaque formation. Endothelial damage reduces nitric oxide availability and promotes a prothrombotic state. Glomerular hyperfiltration and afferent arteriolar sclerosis damage kidney nephrons progressively. Small vessel disease in the brain from chronic hypertension leads to lacunar infarcts, white matter disease, and microbleeds. Hypertension accelerates the aging process of blood vessels through oxidative stress and inflammation.

Treatment:
Blood pressure targets vary by patient population: less than 130/80 mmHg for most adults with hypertension per 2017 ACC/AHA guidelines, less than 130/80 mmHg for patients with diabetes, less than 130/80 mmHg for patients with chronic kidney disease, less than 120 mmHg systolic for high-risk patients based on SPRINT trial results. For heart failure, preferred agents are ACE inhibitors or ARBs, beta-blockers, and mineralocorticoid receptor antagonists. For CKD with proteinuria, ACE inhibitors or ARBs are preferred to reduce proteinuria and slow progression. For stroke prevention, any antihypertensive that achieves target BP is effective, but thiazide diuretics and calcium channel blockers may have slight advantages. For coronary artery disease, ACE inhibitors/ARBs and beta-blockers are preferred. Resistant hypertension (uncontrolled despite 3 drugs including a diuretic at optimal doses) may benefit from adding spironolactone, renal denervation, or evaluation for secondary causes.

Prevention:
Early detection and aggressive treatment of hypertension prevents target organ damage. Regular monitoring of kidney function (creatinine, eGFR, urine albumin), cardiac assessment (ECG, echocardiography), and fundoscopic examination are recommended. Achieving and maintaining blood pressure control reduces cardiovascular events by 20-25%, stroke by 35-40%, and heart failure by over 50%. Adherence to medication and lifestyle modifications is critical for long-term outcomes.
"""
    },
    {
        "id_prefix": "enrich_htn_special_populations",
        "disease_name": "Hypertension - Special Populations",
        "url": "https://www.acc.org/guidelines/hypertension",
        "text": """Table: diseases
Name: Hypertension - Special Populations
URL: https://www.acc.org/guidelines/hypertension

Description:
Hypertension management requires tailored approaches for specific patient populations including the elderly, pregnant women, patients with diabetes, chronic kidney disease, and different racial/ethnic groups. Gestational hypertension affects 6-8% of pregnancies and includes chronic hypertension, gestational hypertension, preeclampsia, and eclampsia. In the elderly (age 65 and older), isolated systolic hypertension is the most common pattern due to arterial stiffening. Hypertension in African Americans is more prevalent, develops earlier, is more severe, and causes more target organ damage. Resistant hypertension affects 10-15% of treated hypertensive patients.

Symptoms:
In pregnancy, preeclampsia presents with new-onset hypertension (greater than 140/90 mmHg) after 20 weeks gestation with proteinuria or end-organ dysfunction including thrombocytopenia, renal insufficiency, liver dysfunction, pulmonary edema, and visual or cerebral symptoms. Eclampsia adds seizures to the clinical picture. HELLP syndrome (Hemolysis, Elevated Liver enzymes, Low Platelets) is a severe variant. In the elderly, orthostatic hypotension (drop in systolic BP of 20 mmHg or diastolic of 10 mmHg upon standing) is common and can cause falls and syncope. Pseudohypertension from calcified arteries should be considered. In CKD patients, fluid overload and uremic symptoms may complicate the clinical picture. Renovascular hypertension may present with flash pulmonary edema or acute kidney injury after starting ACE inhibitors.

Causes:
Pregnancy-related hypertension involves abnormal placentation with inadequate spiral artery remodeling, leading to placental ischemia and release of antiangiogenic factors (sFlt-1, soluble endoglin). In the elderly, arterial stiffening from collagen deposition, elastin fragmentation, and calcification increases pulse pressure. In African Americans, increased salt sensitivity, lower renin levels, enhanced vascular reactivity, and socioeconomic factors contribute to higher prevalence and severity. Resistant hypertension may be due to medication nonadherence, white-coat effect, suboptimal drug combinations, interfering substances, or secondary hypertension (particularly primary aldosteronism and obstructive sleep apnea).

Treatment:
In pregnancy, methyldopa is the best-studied antihypertensive (FDA Category B). Labetalol and nifedipine are also first-line options. ACE inhibitors, ARBs, and direct renin inhibitors are contraindicated in pregnancy due to teratogenicity. For preeclampsia with severe features, IV magnesium sulfate prevents seizures, IV labetalol or hydralazine controls acute hypertension, and delivery is the definitive treatment. Aspirin 81 mg daily from 12-28 weeks is recommended for preeclampsia prevention in high-risk women. In the elderly, start with lower doses and titrate slowly to avoid orthostatic hypotension. Thiazide diuretics and calcium channel blockers are preferred in this population based on HYVET and other trials. In African Americans, thiazide diuretics and calcium channel blockers are more effective as monotherapy than ACE inhibitors or ARBs. Combination therapy with a CCB plus an ACE inhibitor or ARB is effective across all racial groups. In diabetes, ACE inhibitors or ARBs are preferred, especially with microalbuminuria. In CKD, ACE inhibitors or ARBs reduce proteinuria and slow disease progression. For resistant hypertension, spironolactone 25-50 mg is the most effective add-on agent. Renal denervation is an emerging interventional option for resistant hypertension.

Prevention:
Preconception counseling for women with chronic hypertension, early prenatal screening for preeclampsia risk factors, and aspirin prophylaxis for high-risk pregnancies. Screening for secondary causes in young hypertensives, resistant hypertension, and sudden onset or worsening of blood pressure control. Fall prevention strategies in elderly hypertensive patients including gradual medication changes and avoidance of standing quickly. Community-based screening programs targeting high-risk populations.
"""
    },
    {
        "id_prefix": "enrich_htn_lifestyle",
        "disease_name": "Hypertension - Lifestyle Modifications and DASH Diet",
        "url": "https://www.nhlbi.nih.gov/education/dash-eating-plan",
        "text": """Table: diseases
Name: Hypertension - Lifestyle Modifications and DASH Diet
URL: https://www.nhlbi.nih.gov/education/dash-eating-plan

Description:
Lifestyle modifications are the foundation of hypertension management and can reduce systolic blood pressure by 5-20 mmHg. The DASH (Dietary Approaches to Stop Hypertension) diet is one of the most effective dietary interventions, reducing systolic BP by approximately 8-14 mmHg. When combined with sodium restriction, physical activity, weight loss, and moderate alcohol intake, lifestyle changes can be as effective as single-drug therapy. Lifestyle modifications are recommended for all patients with elevated blood pressure or hypertension, regardless of whether pharmacotherapy is also used.

Symptoms:
Improved blood pressure control through lifestyle modifications leads to reduced symptoms of high blood pressure including headaches, fatigue, and shortness of breath. Weight loss improves exercise tolerance and reduces sleep apnea severity. Sodium restriction decreases fluid retention and peripheral edema. Regular exercise improves cardiovascular fitness, reduces resting heart rate, and improves endothelial function. These modifications also improve comorbid conditions including dyslipidemia, insulin resistance, and diabetes.

Treatment:
DASH Diet: Emphasizes 4-5 servings of fruits daily, 4-5 servings of vegetables, 2-3 servings of low-fat dairy, 6-8 servings of whole grains, limited lean meats (6 oz or less), 4-5 servings of nuts, seeds, and legumes per week, limited fats and sweets. Expected BP reduction: 8-14 mmHg systolic. Sodium Restriction: Target less than 2300 mg/day, ideally less than 1500 mg/day for greater effect. Expected BP reduction: 5-6 mmHg systolic. Tips: read food labels, cook at home, avoid processed foods, use herbs and spices instead of salt. Physical Activity: 150 minutes per week of moderate-intensity aerobic exercise (brisk walking, cycling, swimming) or 75 minutes of vigorous activity. Dynamic resistance training 2-3 times per week. Expected BP reduction: 4-9 mmHg systolic. Weight Management: Target BMI 18.5-24.9 kg/m2. Expected BP reduction: approximately 1 mmHg per 1 kg of weight loss. Even 5-10% weight loss provides significant benefit. Alcohol Moderation: Limit to 2 drinks per day for men, 1 for women. Expected BP reduction: 2-4 mmHg systolic. Excessive alcohol intake directly raises blood pressure and reduces medication efficacy. Smoking Cessation: While not directly reducing BP, smoking cessation dramatically reduces overall cardiovascular risk. Nicotine causes acute increases in blood pressure through sympathetic activation. Stress Management: Techniques include deep breathing exercises, meditation, progressive muscle relaxation, yoga, cognitive behavioral therapy, and biofeedback. Adequate sleep of 7-8 hours per night, as short sleep duration is associated with hypertension risk. Potassium Intake: Aim for 3500-5000 mg/day through dietary sources (bananas, potatoes, spinach, beans). Potassium helps counter sodium's hypertensive effects. Expected BP reduction: 2-5 mmHg systolic.

Living With:
Successfully implementing lifestyle changes requires a gradual approach, starting with one or two modifications and building over time. Keeping a food diary, using fitness tracking apps, and regular blood pressure monitoring help maintain motivation. Working with a dietitian can personalize the DASH diet. Setting realistic goals, involving family members, and celebrating small achievements support long-term adherence. Joining community exercise programs or walking groups provides social support.
"""
    },
]

HYPERTENSION_SYMPTOMS = [
    {
        "id_prefix": "enrich_htn_symp_detailed",
        "disease_name": "Hypertension",
        "text": """Table: symptoms
Disease name: Hypertension
URL: https://www.heart.org/en/health-topics/high-blood-pressure/why-high-blood-pressure-is-a-silent-killer

Overview:
Hypertension (high blood pressure) is the most prevalent modifiable risk factor for cardiovascular disease worldwide, affecting approximately 1.28 billion adults globally. Blood pressure is the force of blood pushing against artery walls as the heart pumps. It is measured in millimeters of mercury (mmHg) with two numbers: systolic (pressure during heartbeats) over diastolic (pressure between heartbeats). Normal blood pressure is below 120/80 mmHg. Hypertension is diagnosed when blood pressure is consistently 130/80 mmHg or higher on multiple readings taken on separate occasions.

Symptoms:
Most hypertensive patients are asymptomatic, which is why regular screening is essential. When present, symptoms may include persistent headache particularly in the occipital region upon waking in the morning, dizziness or lightheadedness especially when standing quickly, blurred vision or visual disturbances including scotomas and diplopia, epistaxis (nosebleeds) though this is not as common as popularly believed, dyspnea (shortness of breath) particularly with exertion, chest pain or tightness, palpitations and awareness of irregular or forceful heartbeat, fatigue and reduced exercise tolerance, nausea and sometimes vomiting with very high pressures, tinnitus (ringing in ears), flushing of the face, subconjunctival hemorrhage (blood spot in the eye), erectile dysfunction in men as an early sign of vascular damage. In hypertensive crisis (BP greater than 180/120), symptoms become more pronounced and dangerous: severe headache, confusion, difficulty speaking, chest pain, severe shortness of breath, vision loss, seizures, and unresponsiveness. These require immediate emergency treatment.

Causes:
Primary (essential) hypertension (90-95% of cases) develops from a combination of genetic susceptibility and environmental factors. Pathophysiological mechanisms include increased peripheral vascular resistance from arteriolar vasoconstriction and structural remodeling, increased cardiac output, expanded plasma volume from renal sodium and water retention, overactivation of the renin-angiotensin-aldosterone system (RAAS), increased sympathetic nervous system activity, endothelial dysfunction with decreased nitric oxide and increased endothelin-1, insulin resistance and hyperinsulinemia, oxidative stress and chronic low-grade inflammation, and arterial stiffening. Secondary hypertension (5-10%) has identifiable causes: renal parenchymal disease (glomerulonephritis, polycystic kidney disease), renovascular disease (atherosclerotic or fibromuscular dysplasia of renal arteries), primary aldosteronism (Conn syndrome, bilateral adrenal hyperplasia), pheochromocytoma (catecholamine-secreting tumor), Cushing syndrome (cortisol excess), thyroid disorders, obstructive sleep apnea, coarctation of the aorta, and drug-induced hypertension from NSAIDs, oral contraceptives, corticosteroids, sympathomimetics, and cyclosporine.

Risk factors:
Non-modifiable risk factors include age (risk increases with age, over 65 years especially), family history of hypertension, male sex (until age 55, then women catch up post-menopause), race and ethnicity (African Americans have highest prevalence at 54%), and genetic polymorphisms affecting RAAS, sodium channels, and adrenergic receptors. Modifiable risk factors include excessive dietary sodium intake (average American consumes 3400 mg/day vs recommended less than 2300 mg), low potassium intake, obesity and overweight (BMI greater than 25), physical inactivity (less than 150 minutes of moderate exercise per week), excessive alcohol consumption (more than 2 drinks/day for men, 1 for women), tobacco use, chronic stress and poor sleep quality, diabetes and metabolic syndrome, and high-fat diet.

Complications:
Cardiovascular: left ventricular hypertrophy, diastolic and systolic heart failure, coronary artery disease, myocardial infarction, atrial fibrillation, aortic aneurysm and dissection, peripheral artery disease. Cerebrovascular: ischemic stroke, hemorrhagic stroke (intracerebral and subarachnoid), transient ischemic attack, vascular dementia, cognitive decline, hypertensive encephalopathy. Renal: hypertensive nephrosclerosis, chronic kidney disease, end-stage renal disease, microalbuminuria. Ophthalmologic: hypertensive retinopathy (arteriolar narrowing, arteriovenous nicking, flame hemorrhages, cotton-wool spots, papilledema), retinal vein occlusion, ischemic optic neuropathy. Metabolic: accelerated atherosclerosis, insulin resistance, metabolic syndrome. Hypertension is responsible for approximately 10.4 million deaths per year globally and is the largest contributor to disability-adjusted life years lost worldwide.
"""
    },
    {
        "id_prefix": "enrich_htn_symp_measurement",
        "disease_name": "Hypertension - Measurement and Monitoring",
        "text": """Table: symptoms
Disease name: Hypertension - Measurement and Monitoring
URL: https://www.acc.org/guidelines/blood-pressure-measurement

Overview:
Accurate blood pressure measurement is fundamental to hypertension diagnosis and management. Incorrect technique can lead to measurement errors of 5-15 mmHg, potentially causing misdiagnosis or inappropriate treatment. Proper technique, appropriate equipment, and multiple readings on separate occasions are essential for accurate assessment.

Symptoms:
White-coat hypertension occurs in 15-30% of patients and involves elevated office readings but normal out-of-office readings. These patients have slightly higher cardiovascular risk than truly normotensive individuals but lower risk than sustained hypertensives. Masked hypertension is the reverse pattern (normal office readings but elevated out-of-office readings) and affects 10-15% of patients. These patients have cardiovascular risk similar to sustained hypertensives. Morning hypertension (blood pressure surge upon waking) is associated with increased cardiovascular events. Nocturnal hypertension (failure to dip at night) on 24-hour ambulatory monitoring indicates increased cardiovascular risk. Non-dipping pattern (less than 10% nocturnal BP decline) is associated with target organ damage.

Causes:
Measurement errors can arise from incorrect cuff size (too small cuffs overestimate by 5-15 mmHg), unsupported back or arm, crossed legs (adds 2-8 mmHg), talking during measurement, full bladder (adds 10-15 mmHg), smoking or caffeine within 30 minutes, white-coat effect from anxiety in medical settings, and using wrist or finger devices instead of validated upper arm monitors.

Risk factors:
Factors associated with measurement variability include age (elderly have more variability), autonomic dysfunction, arrhythmias such as atrial fibrillation, dehydration, medications, time of day, meal timing, and emotional state. Patients with high visit-to-visit blood pressure variability have increased stroke risk independent of mean blood pressure.

Complications:
Undiagnosed hypertension from inaccurate measurement delays treatment and allows progressive target organ damage. Overdiagnosis of hypertension from white-coat effect leads to unnecessary medication with potential side effects and costs. Failure to detect masked hypertension leaves high-risk patients untreated. Inadequate home monitoring may miss medication nonadherence or treatment resistance.
"""
    },
]

HYPERTENSION_MEDICINES = [
    {
        "id_prefix": "enrich_htn_med_ace_arb",
        "title": "ACE Inhibitors and ARBs for Hypertension",
        "text": """Table: medicines
URL: https://www.heart.org/en/health-topics/high-blood-pressure/changes-you-can-make-to-manage-high-blood-pressure/types-of-blood-pressure-medications
Title: ACE Inhibitors and ARBs for Hypertension

Introduction:
Angiotensin-converting enzyme (ACE) inhibitors and angiotensin II receptor blockers (ARBs) are first-line antihypertensive medications that target the renin-angiotensin-aldosterone system (RAAS). They are particularly beneficial in patients with diabetes, chronic kidney disease with proteinuria, heart failure, and post-myocardial infarction.

Body:
ACE Inhibitors block the conversion of angiotensin I to angiotensin II, reducing vasoconstriction, aldosterone secretion, and sympathetic activation. They also inhibit bradykinin degradation, contributing to vasodilation but also causing the characteristic dry cough in 5-20% of patients. Commonly prescribed ACE inhibitors include lisinopril (Zestril, Prinivil) 10-40 mg once daily, enalapril (Vasotec) 5-40 mg daily in 1-2 doses, ramipril (Altace) 2.5-20 mg daily in 1-2 doses, benazepril (Lotensin) 10-40 mg daily in 1-2 doses, and captopril (Capoten) 25-150 mg twice or three times daily. Angiotensin II Receptor Blockers (ARBs) selectively block the AT1 receptor, preventing angiotensin II effects without affecting bradykinin metabolism, resulting in lower cough rates. Commonly prescribed ARBs include losartan (Cozaar) 50-100 mg daily in 1-2 doses, valsartan (Diovan) 80-320 mg once daily, irbesartan (Avapro) 150-300 mg once daily, candesartan (Atacand) 8-32 mg once daily, olmesartan (Benicar) 20-40 mg once daily, and telmisartan (Micardis) 20-80 mg once daily. Important considerations: Both ACE inhibitors and ARBs are contraindicated in pregnancy (teratogenic causing renal agenesis and oligohydramnios). They should not be combined together. Monitor serum potassium and creatinine 2-4 weeks after initiation or dose change. Risk of hyperkalemia, especially with concurrent potassium-sparing diuretics or in CKD. Angioedema risk is higher with ACE inhibitors (0.1-0.7%) and more common in African Americans. First-dose hypotension can occur, particularly in volume-depleted or elderly patients. Bilateral renal artery stenosis is a contraindication due to risk of acute kidney injury.

Primary topic: ACE Inhibitor, Angiotensin Receptor Blocker, Antihypertensive

Further reading: 2017 ACC/AHA Hypertension Guidelines, ONTARGET Trial, HOPE Trial
"""
    },
    {
        "id_prefix": "enrich_htn_med_ccb",
        "title": "Calcium Channel Blockers for Hypertension",
        "text": """Table: medicines
URL: https://www.drugs.com/drug-class/calcium-channel-blockers.html
Title: Calcium Channel Blockers for Hypertension

Introduction:
Calcium channel blockers (CCBs) are first-line antihypertensive agents that reduce blood pressure by blocking L-type calcium channels in vascular smooth muscle and cardiac tissue. They are divided into two main classes: dihydropyridines (primarily vascular) and non-dihydropyridines (vascular and cardiac effects).

Body:
Dihydropyridine CCBs primarily cause arterial vasodilation with minimal cardiac effects. Amlodipine (Norvasc) 2.5-10 mg once daily is the most commonly prescribed, with a long half-life allowing once-daily dosing and consistent blood pressure control. Nifedipine extended-release (Procardia XL) 30-90 mg once daily. Felodipine (Plendil) 2.5-10 mg once daily. Common side effects include peripheral edema (ankle swelling) due to preferential arteriolar dilation, headache, flushing, dizziness, and palpitations. Peripheral edema is dose-dependent and can be reduced by combining with an ACE inhibitor or ARB. Non-dihydropyridine CCBs have both vascular and cardiac effects, reducing heart rate and contractility. Diltiazem (Cardizem) 120-360 mg daily in extended-release formulation. Verapamil (Calan) 120-360 mg daily in extended-release formulation. These agents are contraindicated in patients with heart failure with reduced ejection fraction, second or third-degree heart block, and sick sinus syndrome. They should not be combined with beta-blockers due to risk of severe bradycardia and heart block. CCBs are particularly effective in elderly patients, African American patients, and patients with isolated systolic hypertension. Amlodipine is safe in heart failure (unlike non-dihydropyridines). CCBs are not affected by dietary sodium intake, making them effective regardless of sodium consumption. Drug interactions: verapamil and diltiazem inhibit CYP3A4, affecting metabolism of statins, cyclosporine, and other drugs. Grapefruit juice increases levels of some dihydropyridine CCBs.

Primary topic: Calcium Channel Blocker, Antihypertensive

Further reading: ALLHAT Trial, VALUE Trial, ASCOT-BPLA Trial
"""
    },
    {
        "id_prefix": "enrich_htn_med_diuretics",
        "title": "Diuretics for Hypertension",
        "text": """Table: medicines
URL: https://www.drugs.com/drug-class/diuretics.html
Title: Diuretics for Hypertension

Introduction:
Thiazide and thiazide-like diuretics are first-line antihypertensive medications that reduce blood pressure through initial natriuresis and volume depletion, followed by sustained reduction in peripheral vascular resistance. They are among the most effective and cost-efficient antihypertensive agents.

Body:
Thiazide diuretics include hydrochlorothiazide (HCTZ) 12.5-50 mg once daily and chlorthalidone 12.5-25 mg once daily. Chlorthalidone is preferred over HCTZ due to longer duration of action (24-72 hours vs 6-12 hours), more potent blood pressure reduction, and stronger evidence for cardiovascular outcome reduction from the ALLHAT trial. Indapamide 1.25-2.5 mg once daily is another thiazide-like diuretic with additional vasodilatory properties. Thiazides work by inhibiting the sodium-chloride co-transporter in the distal convoluted tubule, reducing sodium and water reabsorption. Metabolic side effects include hypokalemia (monitor potassium levels, supplement as needed), hyponatremia (especially in elderly), hyperuricemia (may precipitate gout), hyperglycemia (may worsen diabetes control), hypercalcemia, and hyperlipidemia. Loop diuretics (furosemide 20-80 mg twice daily, bumetanide 0.5-2 mg twice daily, torsemide 5-20 mg once daily) are not first-line for hypertension but used in patients with chronic kidney disease (eGFR less than 30 mL/min) where thiazides are less effective, and in patients with concurrent heart failure requiring volume management. Potassium-sparing diuretics: spironolactone (Aldactone) 25-50 mg once daily is particularly effective as fourth-line therapy for resistant hypertension and in primary aldosteronism. Eplerenone (Inspra) 50-100 mg daily is more selective with fewer antiandrogen effects. Amiloride 5-10 mg daily and triamterene 50-100 mg daily are alternatives. Combination diuretic therapy (thiazide plus potassium-sparing) helps maintain potassium balance.

Primary topic: Diuretic, Antihypertensive

Further reading: ALLHAT Trial, PATHWAY-2 Trial (spironolactone for resistant HTN), SPRINT Trial
"""
    },
    {
        "id_prefix": "enrich_htn_med_betablockers",
        "title": "Beta-Blockers and Other Antihypertensives",
        "text": """Table: medicines
URL: https://www.drugs.com/drug-class/beta-blockers.html
Title: Beta-Blockers and Other Antihypertensives

Introduction:
Beta-adrenergic blockers (beta-blockers) reduce blood pressure by decreasing heart rate, cardiac output, and renin release. While no longer considered first-line for uncomplicated hypertension, they remain essential for hypertensive patients with specific comorbidities including heart failure, post-myocardial infarction, atrial fibrillation, and migraine.

Body:
Cardioselective (beta-1 selective) agents are preferred as they have less effect on beta-2 receptors in the lungs and vasculature. Metoprolol succinate (Toprol XL) 25-200 mg once daily is widely used for hypertension and heart failure. Metoprolol tartrate (Lopressor) 50-100 mg twice daily is used for acute settings. Atenolol 25-100 mg once daily, though evidence for cardiovascular outcomes is weaker based on the LIFE trial. Bisoprolol 2.5-10 mg once daily. Nebivolol 5-40 mg once daily has additional vasodilatory properties via nitric oxide and is better tolerated with fewer metabolic side effects. Non-selective beta-blockers include propranolol 40-160 mg twice daily (also used for migraine, essential tremor, anxiety) and nadolol 40-120 mg once daily. Combined alpha-beta blockers: carvedilol 6.25-25 mg twice daily (used in heart failure), labetalol 100-400 mg twice daily (preferred in pregnancy hypertension). Common side effects include fatigue, cold extremities, bradycardia, exercise intolerance, depression, sexual dysfunction, and weight gain. Beta-blockers should not be abruptly discontinued due to rebound tachycardia and hypertension risk. Use caution in diabetes (may mask hypoglycemia symptoms), asthma (avoid non-selective agents), and peripheral artery disease. Other antihypertensives for resistant or special cases: Alpha-1 blockers (doxazosin, prazosin, terazosin) cause vasodilation but are not first-line due to increased heart failure risk (ALLHAT). Direct vasodilators (hydralazine, minoxidil) for severe resistant hypertension. Centrally acting agents (clonidine, methyldopa) for resistant hypertension, with methyldopa preferred in pregnancy. Direct renin inhibitor (aliskiren) blocks RAAS at the earliest step.

Primary topic: Beta-Blocker, Antihypertensive

Further reading: LIFE Trial, COMET Trial, MERIT-HF Trial
"""
    },
]


# ─── Helper Functions ────────────────────────────────────────────────────────

def chunk_text(text: str, max_chars: int = MAX_CHARS_PER_CHUNK, overlap: int = CHUNK_OVERLAP) -> list:
    """Split text into overlapping chunks."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end < len(text):
            # Try to break at a sentence or paragraph boundary
            for boundary in ['\n\n', '\n', '. ', ', ']:
                last_boundary = text[start:end].rfind(boundary)
                if last_boundary > max_chars * 0.5:
                    end = start + last_boundary + len(boundary)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
    return chunks


EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def get_or_create_collection(client, name: str):
    """Get existing collection or create new one with cosine distance."""
    try:
        collection = client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )
        print(f"  Found collection '{name}' with {collection.count()} documents")
        return collection
    except Exception as e:
        print(f"  Error accessing collection '{name}': {e}")
        raise


def ingest_documents(collection, documents: list, model, collection_type: str):
    """Ingest a list of documents into a ChromaDB collection with embeddings."""
    all_ids = []
    all_texts = []
    all_metadatas = []
    all_embeddings = []

    for doc in documents:
        text = doc["text"]
        chunks = chunk_text(text)

        for chunk_idx, chunk in enumerate(chunks):
            doc_id = f"{doc['id_prefix']}_chunk_{chunk_idx}"

            # Build metadata based on collection type
            metadata = {
                "table": collection_type,
                "collection": collection_type,
                "chunk_index": chunk_idx,
                "source": "enrichment_script",
            }

            if collection_type == "diseases":
                metadata["disease_name"] = doc.get("disease_name", "")
                metadata["url"] = doc.get("url", "")
            elif collection_type == "symptoms":
                metadata["disease_name"] = doc.get("disease_name", "")
            elif collection_type == "medicines":
                metadata["title"] = doc.get("title", "")

            all_ids.append(doc_id)
            all_texts.append(chunk)
            all_metadatas.append(metadata)

    # Generate embeddings using sentence-transformers
    print(f"  Computing embeddings for {len(all_texts)} chunks...")
    for i in range(0, len(all_texts), BATCH_SIZE):
        batch_texts = all_texts[i:i + BATCH_SIZE]
        batch_embeddings = model.encode(batch_texts).tolist()
        all_embeddings.extend(batch_embeddings)

    # Upsert into ChromaDB with embeddings
    print(f"  Upserting {len(all_ids)} documents into '{collection.name}'...")
    for i in range(0, len(all_ids), BATCH_SIZE):
        batch_end = min(i + BATCH_SIZE, len(all_ids))
        collection.upsert(
            ids=all_ids[i:batch_end],
            documents=all_texts[i:batch_end],
            embeddings=all_embeddings[i:batch_end],
            metadatas=all_metadatas[i:batch_end],
        )

    return len(all_ids)


# ─── Main Execution ──────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("TrustMed-AI Knowledge Base Enrichment")
    print("Topics: Asthma & Hypertension")
    print("=" * 60)

    # Resolve ChromaDB path
    chroma_path = os.path.abspath(CHROMA_DB_DIR)
    print(f"\nChromaDB path: {chroma_path}")

    if not os.path.exists(chroma_path):
        print(f"ERROR: ChromaDB directory not found at {chroma_path}")
        sys.exit(1)

    # Load embedding model
    print(f"\nLoading embedding model: {EMBEDDING_MODEL_NAME}")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    print("  Model loaded successfully!")

    # Connect to ChromaDB
    print("\nConnecting to ChromaDB...")
    client = chromadb.PersistentClient(path=chroma_path)

    # Get collections
    diseases_col = get_or_create_collection(client, "diseases")
    symptoms_col = get_or_create_collection(client, "symptoms")
    medicines_col = get_or_create_collection(client, "medicines")

    print(f"\nBefore enrichment:")
    print(f"  diseases:  {diseases_col.count()} documents")
    print(f"  symptoms:  {symptoms_col.count()} documents")
    print(f"  medicines: {medicines_col.count()} documents")

    # ── Ingest Asthma content ──
    print("\n" + "-" * 40)
    print("INGESTING ASTHMA CONTENT")
    print("-" * 40)

    asthma_disease_count = ingest_documents(diseases_col, ASTHMA_DISEASES, model, "diseases")
    print(f"  >> Added {asthma_disease_count} disease chunks for Asthma")

    asthma_symptom_count = ingest_documents(symptoms_col, ASTHMA_SYMPTOMS, model, "symptoms")
    print(f"  >> Added {asthma_symptom_count} symptom chunks for Asthma")

    asthma_medicine_count = ingest_documents(medicines_col, ASTHMA_MEDICINES, model, "medicines")
    print(f"  >> Added {asthma_medicine_count} medicine chunks for Asthma")

    # ── Ingest Hypertension content ──
    print("\n" + "-" * 40)
    print("INGESTING HYPERTENSION CONTENT")
    print("-" * 40)

    htn_disease_count = ingest_documents(diseases_col, HYPERTENSION_DISEASES, model, "diseases")
    print(f"  >> Added {htn_disease_count} disease chunks for Hypertension")

    htn_symptom_count = ingest_documents(symptoms_col, HYPERTENSION_SYMPTOMS, model, "symptoms")
    print(f"  >> Added {htn_symptom_count} symptom chunks for Hypertension")

    htn_medicine_count = ingest_documents(medicines_col, HYPERTENSION_MEDICINES, model, "medicines")
    print(f"  >> Added {htn_medicine_count} medicine chunks for Hypertension")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("ENRICHMENT COMPLETE")
    print("=" * 60)

    total_added = (asthma_disease_count + asthma_symptom_count + asthma_medicine_count +
                   htn_disease_count + htn_symptom_count + htn_medicine_count)

    print(f"\nTotal new chunks added: {total_added}")
    print(f"  Asthma:       {asthma_disease_count + asthma_symptom_count + asthma_medicine_count} chunks")
    print(f"    - diseases:  {asthma_disease_count}")
    print(f"    - symptoms:  {asthma_symptom_count}")
    print(f"    - medicines: {asthma_medicine_count}")
    print(f"  Hypertension: {htn_disease_count + htn_symptom_count + htn_medicine_count} chunks")
    print(f"    - diseases:  {htn_disease_count}")
    print(f"    - symptoms:  {htn_symptom_count}")
    print(f"    - medicines: {htn_medicine_count}")

    print(f"\nAfter enrichment:")
    print(f"  diseases:  {diseases_col.count()} documents")
    print(f"  symptoms:  {symptoms_col.count()} documents")
    print(f"  medicines: {medicines_col.count()} documents")

    print("\nDone! Your knowledge base is now enriched for Asthma and Hypertension.")


if __name__ == "__main__":
    main()
