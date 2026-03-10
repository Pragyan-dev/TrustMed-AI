-- ============================================
-- TrustMed-AI: Health Database Setup Script
-- ============================================
-- This script creates the 'health' database with
-- medicines, diseases, and symptoms tables,
-- and populates them with sample medical data.
-- ============================================

-- Run this first to create the database:
-- psql -c "CREATE DATABASE health;"
-- Then run: psql -d health -f setup_health_db.sql

-- ============================================
-- TABLE: medicines
-- ============================================

DROP TABLE IF EXISTS medicines CASCADE;

CREATE TABLE medicines (
    id SERIAL PRIMARY KEY,
    source_url TEXT,
    title TEXT NOT NULL,
    introduction TEXT,
    body TEXT,
    primary_topic TEXT,
    further_reading TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- TABLE: symptoms
-- ============================================

DROP TABLE IF EXISTS symptoms CASCADE;

CREATE TABLE symptoms (
    id SERIAL PRIMARY KEY,
    disease_name TEXT NOT NULL,
    source_url TEXT,
    overview TEXT,
    symptoms TEXT,
    causes TEXT,
    risk_factors TEXT,
    complications TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- TABLE: diseases
-- ============================================

DROP TABLE IF EXISTS diseases CASCADE;

CREATE TABLE diseases (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    main_url TEXT,
    description TEXT,
    symptoms TEXT,
    causes TEXT,
    diagnosis TEXT,
    prevention TEXT,
    treatment TEXT,
    living_with TEXT,
    questions_to_ask TEXT,
    resources TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- SAMPLE DATA: medicines
-- ============================================

INSERT INTO medicines (source_url, title, introduction, body, primary_topic, further_reading) VALUES
(
    'https://www.drugs.com/metformin.html',
    'Metformin',
    'Metformin is an oral diabetes medicine that helps control blood sugar levels.',
    'Metformin is used together with diet and exercise to improve blood sugar control in adults with type 2 diabetes mellitus. Metformin works by decreasing glucose production in the liver, decreasing intestinal absorption of glucose, and improving insulin sensitivity. Common side effects include nausea, vomiting, stomach upset, diarrhea, weakness, or a metallic taste in the mouth. The usual starting dose is 500 mg twice daily or 850 mg once daily with meals.',
    'Diabetes Medication',
    'American Diabetes Association guidelines on metformin therapy'
),
(
    'https://www.drugs.com/lisinopril.html',
    'Lisinopril',
    'Lisinopril is an ACE inhibitor used to treat high blood pressure and heart failure.',
    'Lisinopril belongs to a class of drugs called angiotensin-converting enzyme (ACE) inhibitors. It works by relaxing blood vessels so blood can flow more easily. It is used to treat high blood pressure (hypertension), congestive heart failure, and to improve survival after a heart attack. Common side effects include dizziness, headache, fatigue, and a persistent dry cough. Typical dosing starts at 10 mg once daily.',
    'Cardiovascular Medication',
    'American Heart Association hypertension guidelines'
),
(
    'https://www.drugs.com/atorvastatin.html',
    'Atorvastatin (Lipitor)',
    'Atorvastatin is a statin medication used to lower cholesterol and reduce cardiovascular risk.',
    'Atorvastatin is used along with diet, exercise, and weight loss to reduce the risk of heart attack and stroke in people who have heart disease or risk factors for heart disease. It works by reducing the amount of cholesterol made by the liver. Common side effects include muscle pain, diarrhea, and nausea. The typical starting dose is 10-20 mg once daily, which can be increased to 80 mg daily.',
    'Cholesterol Medication',
    'ACC/AHA cholesterol management guidelines'
),
(
    'https://www.drugs.com/albuterol.html',
    'Albuterol (Ventolin)',
    'Albuterol is a bronchodilator used to treat asthma and chronic obstructive pulmonary disease (COPD).',
    'Albuterol relaxes muscles in the airways and increases air flow to the lungs. It is used to treat bronchospasm in people with reversible obstructive airway disease, and to prevent exercise-induced bronchospasm. The inhaler provides quick relief of asthma symptoms including wheezing, coughing, chest tightness, and shortness of breath. Each actuation delivers 90 mcg of albuterol. Common side effects include nervousness, shaking, headache, and rapid heartbeat.',
    'Respiratory Medication',
    'GINA asthma management guidelines'
),
(
    'https://www.drugs.com/ibuprofen.html',
    'Ibuprofen (Advil, Motrin)',
    'Ibuprofen is a nonsteroidal anti-inflammatory drug (NSAID) used for pain relief and reducing inflammation.',
    'Ibuprofen is used to reduce fever and treat pain or inflammation caused by headaches, toothaches, back pain, arthritis, menstrual cramps, or minor injuries. It works by reducing hormones that cause inflammation and pain in the body. Typical adult dose is 200-400 mg every 4-6 hours as needed. Do not exceed 1200 mg in 24 hours without doctor supervision. Common side effects include stomach pain, heartburn, nausea, and dizziness.',
    'Pain Relief',
    'FDA guidelines on NSAID use'
),
(
    'https://www.drugs.com/omeprazole.html',
    'Omeprazole (Prilosec)',
    'Omeprazole is a proton pump inhibitor (PPI) used to treat gastroesophageal reflux disease (GERD).',
    'Omeprazole decreases the amount of acid produced in the stomach. It is used to treat symptoms of GERD, erosive esophagitis, and conditions involving excessive stomach acid. It may also be used in combination with antibiotics to treat Helicobacter pylori infection. The typical dose is 20 mg once daily before eating. Common side effects include headache, abdominal pain, nausea, diarrhea, and gas.',
    'Gastrointestinal Medication',
    'ACG guidelines on GERD management'
),
(
    'https://www.drugs.com/sertraline.html',
    'Sertraline (Zoloft)',
    'Sertraline is a selective serotonin reuptake inhibitor (SSRI) antidepressant.',
    'Sertraline is used to treat depression, panic attacks, obsessive compulsive disorder, post-traumatic stress disorder, social anxiety disorder, and premenstrual dysphoric disorder. It works by helping to restore the balance of serotonin in the brain. Treatment typically starts at 50 mg once daily. Common side effects include nausea, diarrhea, tremor, sexual dysfunction, drowsiness, and dry mouth. It may take 4-6 weeks to feel the full benefit.',
    'Antidepressant',
    'APA depression treatment guidelines'
),
(
    'https://www.drugs.com/insulin.html',
    'Insulin (Various Types)',
    'Insulin is a hormone used to control blood sugar in people with diabetes.',
    'Insulin is essential for people with type 1 diabetes and some people with type 2 diabetes. There are different types: rapid-acting (lispro, aspart), short-acting (regular), intermediate-acting (NPH), and long-acting (glargine, detemir). Insulin is injected subcutaneously, and dosing is individualized based on blood glucose monitoring. Side effects include hypoglycemia (low blood sugar), weight gain, and injection site reactions. Regular monitoring of blood glucose is essential.',
    'Diabetes Medication',
    'ADA Standards of Medical Care in Diabetes'
);

-- ============================================
-- SAMPLE DATA: diseases
-- ============================================

INSERT INTO diseases (name, main_url, description, symptoms, causes, diagnosis, prevention, treatment, living_with, questions_to_ask, resources) VALUES
(
    'Type 2 Diabetes',
    'https://www.mayoclinic.org/diseases-conditions/type-2-diabetes',
    'Type 2 diabetes is a chronic condition that affects the way the body processes blood sugar (glucose). With type 2 diabetes, the body either resists the effects of insulin — a hormone that regulates the movement of sugar into cells — or does not produce enough insulin to maintain normal glucose levels.',
    'Increased thirst, frequent urination, increased hunger, unintended weight loss, fatigue, blurred vision, slow-healing sores, frequent infections, numbness or tingling in hands or feet, areas of darkened skin',
    'Type 2 diabetes develops when the body becomes resistant to insulin or when the pancreas is unable to produce enough insulin. Exactly why this happens is unknown, but being overweight and physical inactivity are major contributing factors. Genetics and family history also play a role.',
    'Glycated hemoglobin (A1C) test measures average blood sugar over past 2-3 months. Fasting blood sugar test requires overnight fasting. Oral glucose tolerance test measures blood sugar before and after drinking a sugary liquid. Random blood sugar test can be done at any time.',
    'Maintain a healthy weight through diet and exercise. Get regular physical activity - at least 150 minutes per week of moderate aerobic activity. Eat a balanced diet rich in fruits, vegetables, and whole grains. Limit refined carbohydrates and sugary foods. Have regular health checkups.',
    'Healthy eating and regular exercise are foundational. Medications may include metformin, sulfonylureas, DPP-4 inhibitors, GLP-1 receptor agonists, SGLT2 inhibitors, or insulin. Blood sugar monitoring is essential. Some patients may need bariatric surgery for weight management.',
    'Monitor blood sugar regularly as directed. Take medications as prescribed. Follow meal plans and maintain regular eating schedules. Stay physically active. Attend regular medical appointments. Check feet daily for sores or injuries. Manage stress effectively.',
    'What is my target blood sugar range? How often should I check my blood sugar? What medications do I need? What diet changes should I make? How much exercise do I need? What are signs of complications? When should I seek emergency care?',
    'American Diabetes Association: diabetes.org, CDC Diabetes Resources, National Institute of Diabetes and Digestive and Kidney Diseases'
),
(
    'Hypertension (High Blood Pressure)',
    'https://www.heart.org/en/health-topics/high-blood-pressure',
    'Hypertension is a common condition in which the long-term force of the blood against the artery walls is high enough that it may eventually cause health problems, such as heart disease. Blood pressure is determined by the amount of blood the heart pumps and the resistance in the arteries.',
    'Most people with high blood pressure have no signs or symptoms. Some may experience headaches, shortness of breath, nosebleeds, dizziness, chest pain, visual changes, blood in urine. These symptoms typically occur when blood pressure reaches a dangerously high level.',
    'Primary hypertension develops gradually over many years with no identifiable cause. Secondary hypertension can be caused by kidney problems, adrenal gland tumors, thyroid problems, certain medications, obstructive sleep apnea, congenital blood vessel defects, or illegal drugs.',
    'Blood pressure is measured using a sphygmomanometer. Normal is less than 120/80 mmHg. Elevated is 120-129/<80. Stage 1 hypertension is 130-139/80-89. Stage 2 is 140+/90+. Additional tests may include urine tests, blood tests, cholesterol test, ECG, and echocardiogram.',
    'Eat a heart-healthy diet low in sodium (DASH diet). Maintain a healthy weight. Exercise regularly - at least 30 minutes most days. Limit alcohol. Do not smoke. Manage stress. Get adequate sleep. Monitor blood pressure at home.',
    'Lifestyle modifications are first-line treatment. Medications include thiazide diuretics, ACE inhibitors, ARBs, calcium channel blockers, and beta blockers. Treatment is often started with one drug and adjusted based on response. Combination therapy may be needed.',
    'Take medications consistently as prescribed. Monitor blood pressure at home regularly. Maintain a low-sodium diet. Stay physically active. Limit caffeine and alcohol. Manage stress through relaxation techniques. Keep all medical appointments.',
    'What is my blood pressure goal? How often should I check my blood pressure? What lifestyle changes are most important? What medications will I need? What are the side effects? How long will I need treatment? What symptoms should prompt emergency care?',
    'American Heart Association: heart.org, National Heart Lung and Blood Institute, CDC High Blood Pressure Resources'
),
(
    'Coronary Artery Disease',
    'https://www.heart.org/en/health-topics/heart-attack/about-heart-attacks',
    'Coronary artery disease (CAD) is the most common type of heart disease. It occurs when the arteries that supply blood to the heart muscle become hardened and narrowed due to plaque buildup (atherosclerosis). This reduces blood flow to the heart, which can lead to chest pain (angina) or heart attack.',
    'Chest pain or discomfort (angina), shortness of breath especially with exertion, fatigue, heart palpitations, weakness, dizziness, nausea, sweating. Heart attack symptoms include crushing chest pain radiating to arm or jaw, severe shortness of breath, cold sweats.',
    'Atherosclerosis is caused by damage to the inner layer of arteries from high blood pressure, high cholesterol, smoking, diabetes, obesity, and physical inactivity. Plaque builds up at damage sites, narrowing arteries and reducing blood flow to heart muscle.',
    'ECG to detect heart rhythm abnormalities. Stress testing during exercise. Echocardiogram to visualize heart function. Coronary angiography uses dye and X-rays to visualize blockages. CT coronary angiogram. Blood tests for cholesterol and cardiac enzymes.',
    'Quit smoking and avoid secondhand smoke. Control blood pressure and diabetes. Lower cholesterol through diet and medication. Maintain healthy weight. Exercise regularly. Eat a heart-healthy diet. Manage stress. Limit alcohol consumption.',
    'Lifestyle changes are fundamental. Medications include aspirin, statins, beta blockers, ACE inhibitors, nitroglycerin for angina. Procedures include angioplasty with stent placement or coronary artery bypass graft (CABG) surgery for severe blockages.',
    'Take all medications as prescribed. Participate in cardiac rehabilitation. Follow a heart-healthy diet. Exercise as recommended by your doctor. Monitor and manage risk factors. Recognize warning signs of heart attack. Carry nitroglycerin if prescribed.',
    'How severe is my coronary artery disease? What treatment options do I have? What lifestyle changes are most important? What medications do I need? When should I seek emergency care? Can I exercise safely? What is my prognosis?',
    'American Heart Association, National Heart Lung and Blood Institute, American College of Cardiology Foundation'
),
(
    'Asthma',
    'https://www.lung.org/lung-health-diseases/lung-disease-lookup/asthma',
    'Asthma is a chronic disease of the airways that makes breathing difficult. With asthma, the airways are inflamed and narrowed, filled with excess mucus, and overly sensitive to triggers. During an asthma attack, the muscles around the airways tighten, causing further narrowing.',
    'Shortness of breath, chest tightness or pain, wheezing when exhaling, trouble sleeping due to breathing problems, coughing or wheezing attacks worsened by respiratory virus, whistling or wheezing sound when breathing, cough especially at night or early morning',
    'Asthma triggers include airborne allergens (pollen, dust mites, pet dander, mold), respiratory infections like colds and flu, physical activity, cold air, air pollutants and irritants, certain medications, stress and strong emotions, food preservatives, GERD.',
    'Lung function tests (spirometry) measure airflow. Peak flow meter measures how hard you can breathe out. Methacholine challenge test. Imaging tests like chest X-ray. Allergy testing to identify triggers. Nitric oxide test measures airway inflammation.',
    'Identify and avoid triggers. Get flu vaccine annually. Monitor breathing and recognize warning signs. Use air conditioning and purifiers. Keep humidity optimal. Cover bedding with allergen-proof covers. Regular cleaning to reduce dust and mold.',
    'Quick-relief medications (rescue inhalers) like albuterol provide rapid symptom relief. Long-term control medications include inhaled corticosteroids, combination inhalers, leukotriene modifiers, theophylline, and biologic therapies for severe asthma.',
    'Follow asthma action plan. Take controller medications daily as prescribed. Keep rescue inhaler accessible. Know your triggers and avoid them. Monitor peak flow readings. Recognize early warning signs. Maintain regular doctor visits.',
    'What triggers my asthma? How do I use my inhalers correctly? When should I use my rescue inhaler vs controller medication? What peak flow readings indicate worsening? When should I go to the emergency room? Can I exercise with asthma?',
    'American Lung Association, Asthma and Allergy Foundation of America, National Heart Lung and Blood Institute'
),
(
    'Migraine',
    'https://www.mayoclinic.org/diseases-conditions/migraine-headache',
    'Migraine is a neurological condition that causes intense, debilitating headaches along with other symptoms. Migraines are typically characterized by severe throbbing pain, usually on one side of the head, and are often accompanied by nausea, vomiting, and extreme sensitivity to light and sound.',
    'Throbbing or pulsing head pain usually on one side, sensitivity to light (photophobia), sensitivity to sound (phonophobia), nausea and vomiting, visual disturbances (aura), tingling in face or extremities, difficulty speaking, weakness, dizziness',
    'The exact cause is not fully understood but involves abnormal brain activity affecting nerve signals, chemicals, and blood vessels. Triggers include hormonal changes, certain foods and drinks, stress, sensory stimuli, sleep changes, weather changes, medications.',
    'Diagnosis is primarily clinical based on symptom history. Neurological examination. CT scan or MRI to rule out other conditions. Lumbar puncture if infection is suspected. Keeping a headache diary helps identify patterns and triggers.',
    'Identify and avoid personal triggers. Maintain regular sleep schedule. Stay hydrated. Exercise regularly. Manage stress. Eat regular meals. Limit caffeine and alcohol. Consider preventive medications if attacks are frequent.',
    'Acute treatment includes pain relievers (NSAIDs, acetaminophen), triptans, ergotamines, anti-nausea medications, and newer CGRP antagonists. Preventive medications include beta blockers, antidepressants, anti-seizure drugs, CGRP monoclonal antibodies, and Botox.',
    'Rest in a dark, quiet room during attacks. Apply cold or warm compresses. Practice relaxation techniques. Maintain headache diary. Take medications at first sign of attack. Stay consistent with preventive medications if prescribed.',
    'How often should I take acute medications? What preventive options are available? Are there lifestyle changes that help? When should I seek emergency care? Could my headaches indicate something more serious? What new treatments are available?',
    'American Migraine Foundation, National Headache Foundation, Migraine Research Foundation'
),
(
    'Major Depressive Disorder',
    'https://www.nimh.nih.gov/health/topics/depression',
    'Major depressive disorder (clinical depression) is a common and serious mood disorder that causes persistent feelings of sadness and loss of interest. It affects how you feel, think, and handle daily activities such as sleeping, eating, or working.',
    'Persistent sad, anxious, or empty mood, feelings of hopelessness or pessimism, irritability, loss of interest in hobbies and activities, decreased energy and fatigue, difficulty concentrating and making decisions, sleep disturbances, appetite changes, thoughts of death or suicide',
    'Depression likely results from a combination of genetic, biological, environmental, and psychological factors. Risk factors include personal or family history, major life changes or trauma, certain medications, chronic illness, substance abuse.',
    'Clinical evaluation including detailed interview about symptoms, duration, and impact on functioning. Physical exam and lab tests to rule out medical conditions. Psychological evaluation. Criteria include symptoms present most days for at least 2 weeks.',
    'Regular exercise has antidepressant effects. Maintain social connections. Develop healthy coping skills. Limit alcohol. Get adequate sleep. Seek help early if symptoms develop. Manage chronic health conditions.',
    'Psychotherapy (cognitive behavioral therapy, interpersonal therapy) is effective. Antidepressant medications include SSRIs, SNRIs, and others. Combination of medication and therapy is often most effective. ECT for treatment-resistant cases. Newer options include TMS and ketamine.',
    'Take medications as prescribed - do not stop suddenly. Attend therapy sessions regularly. Maintain healthy routines. Stay connected with supportive people. Be patient - recovery takes time. Recognize warning signs of worsening. Have a crisis plan.',
    'How long before treatment works? What are medication side effects? How long will I need treatment? What if this treatment does not work? Can I drink alcohol? What should family members know? What are signs I need immediate help?',
    'National Institute of Mental Health, Depression and Bipolar Support Alliance, National Alliance on Mental Illness'
),
(
    'Chronic Obstructive Pulmonary Disease (COPD)',
    'https://www.lung.org/lung-health-diseases/lung-disease-lookup/copd',
    'COPD is a chronic inflammatory lung disease that causes obstructed airflow from the lungs. It includes emphysema and chronic bronchitis. Emphysema involves damage to the air sacs (alveoli), while chronic bronchitis involves inflammation and narrowing of the bronchial tubes.',
    'Shortness of breath especially during physical activities, wheezing, chest tightness, chronic cough with mucus production, frequent respiratory infections, lack of energy, unintended weight loss, swelling in ankles feet or legs, bluish lips or fingernails',
    'Long-term exposure to irritating gases or particulate matter, most often from cigarette smoke. Other factors include exposure to secondhand smoke, occupational dust and chemicals, fumes from burning fuel, alpha-1-antitrypsin deficiency (genetic).',
    'Spirometry measures how much air you can inhale and exhale. Chest X-ray shows emphysema. CT scan provides detailed images. Arterial blood gas analysis measures oxygen and carbon dioxide levels. Alpha-1-antitrypsin testing for genetic cause.',
    'The most essential step is to never smoke or quit smoking. Avoid occupational exposure to lung irritants. Get vaccinated against flu and pneumonia. Avoid air pollution. Exercise regularly to maintain lung function.',
    'Bronchodilators (short and long-acting) relax airway muscles. Inhaled steroids reduce inflammation. Combination inhalers. Oral steroids for flare-ups. Phosphodiesterase-4 inhibitors. Antibiotics for infections. Supplemental oxygen therapy. Pulmonary rehabilitation. Surgery in severe cases.',
    'Quit smoking and avoid secondhand smoke. Take medications exactly as prescribed. Use oxygen therapy as recommended. Participate in pulmonary rehabilitation. Pace daily activities. Maintain healthy weight. Control stress and anxiety.',
    'What stage is my COPD? What can I do to slow progression? What trigger should I avoid? When do I need oxygen therapy? What exercises are safe? What symptoms indicate an emergency? What end-of-life planning should I consider?',
    'American Lung Association, COPD Foundation, Global Initiative for Chronic Obstructive Lung Disease'
),
(
    'Gastroesophageal Reflux Disease (GERD)',
    'https://www.mayoclinic.org/diseases-conditions/gerd',
    'GERD occurs when stomach acid frequently flows back into the esophagus. This acid reflux can irritate the lining of the esophagus. Many people experience acid reflux occasionally, but frequent reflux that affects quality of life is considered GERD.',
    'Heartburn (burning sensation in chest after eating that may be worse at night), chest pain, difficulty swallowing, regurgitation of food or sour liquid, sensation of lump in throat, chronic cough, laryngitis, new or worsening asthma, disrupted sleep',
    'GERD is caused by frequent acid reflux due to weakening or abnormal relaxation of the lower esophageal sphincter. Contributing factors include obesity, hiatal hernia, pregnancy, delayed stomach emptying, smoking, eating large meals late at night, fatty or fried foods, certain medications.',
    'Upper endoscopy visualizes the esophagus and stomach. Ambulatory acid probe test measures acid reflux over 24-48 hours. Esophageal manometry measures esophageal muscle function. X-ray of upper digestive system.',
    'Maintain healthy weight. Avoid foods that trigger reflux (fatty foods, alcohol, chocolate, caffeine, mint). Eat smaller meals. Do not lie down right after eating. Elevate head of bed. Do not smoke. Wear loose-fitting clothes.',
    'Over-the-counter antacids provide quick relief. H2 receptor blockers reduce acid production. Proton pump inhibitors (PPIs) like omeprazole heal the esophagus and are most effective. Surgery (fundoplication) may be needed for severe cases.',
    'Identify and avoid trigger foods. Eat slowly and chew thoroughly. Wait at least 3 hours after eating before lying down. Elevate head of bed 6-8 inches. Maintain healthy weight. Take medications as directed.',
    'What lifestyle changes will help most? How long should I take medications? Are there long-term risks of PPIs? When is surgery considered? Could my symptoms indicate something more serious? What foods should I avoid?',
    'American College of Gastroenterology, American Gastroenterological Association, International Foundation for Gastrointestinal Disorders'
);

-- ============================================
-- SAMPLE DATA: symptoms
-- ============================================

INSERT INTO symptoms (disease_name, source_url, overview, symptoms, causes, risk_factors, complications) VALUES
(
    'Type 2 Diabetes Symptoms',
    'https://www.mayoclinic.org/diseases-conditions/type-2-diabetes/symptoms-causes',
    'Type 2 diabetes symptoms often develop slowly over several years and may be mild enough to go unnoticed. Some people with type 2 diabetes have no symptoms.',
    'Increased thirst (polydipsia), frequent urination (polyuria), increased hunger (polyphagia), unintended weight loss, fatigue and weakness, blurred vision, slow-healing sores and frequent infections, numbness or tingling in hands and feet, areas of darkened skin (acanthosis nigricans)',
    'Type 2 diabetes develops when the body becomes resistant to insulin or when the pancreas cannot produce enough insulin. This is influenced by genetics, weight, physical inactivity, fat distribution, and age.',
    'Being overweight or obese, fat distribution mainly in abdomen, physical inactivity, family history of diabetes, age over 45, history of gestational diabetes, polycystic ovary syndrome, prediabetes, high blood pressure, abnormal cholesterol levels',
    'Heart and blood vessel disease, nerve damage (neuropathy), kidney damage (nephropathy), eye damage (retinopathy), foot damage, skin and mouth conditions, hearing impairment, Alzheimer disease, depression'
),
(
    'Heart Attack Warning Signs',
    'https://www.heart.org/en/health-topics/heart-attack/warning-signs-of-a-heart-attack',
    'Heart attack symptoms can vary, but most heart attacks involve discomfort in the center of the chest that lasts more than a few minutes or comes and goes. Recognizing symptoms quickly saves lives.',
    'Uncomfortable pressure, squeezing, fullness or pain in the center of the chest, pain or discomfort in one or both arms, the back, neck, jaw or stomach, shortness of breath, cold sweat, nausea, lightheadedness',
    'Heart attacks occur when blood flow to part of the heart is blocked, usually by a blood clot. The blockage is typically caused by buildup of plaque (fat, cholesterol, and other substances) in coronary arteries (atherosclerosis).',
    'High blood pressure, high cholesterol, smoking, diabetes, obesity, family history of heart disease, age (men over 45, women over 55), lack of physical activity, unhealthy diet, excessive alcohol, stress',
    'Heart failure, arrhythmias (abnormal heart rhythms), cardiogenic shock, cardiac arrest, mechanical complications including heart muscle rupture, pericarditis, blood clots, depression and anxiety'
),
(
    'Asthma Attack Symptoms',
    'https://www.lung.org/lung-health-diseases/lung-disease-lookup/asthma/asthma-symptoms-causes-risk-factors',
    'Asthma symptoms vary from person to person and can range from minor to severe. During an asthma attack, the airways become inflamed, swollen, and produce extra mucus while the muscles around them tighten.',
    'Shortness of breath, chest tightness or chest pain, wheezing when exhaling, trouble sleeping due to coughing or wheezing, coughing attacks worsened by cold or flu, whistling sound when breathing, rapid breathing, difficulty talking',
    'Asthma is caused by a combination of genetic and environmental factors. Triggers include allergens (pollen, dust mites, pet dander, mold), respiratory infections, exercise, cold air, smoke, strong odors, stress.',
    'Family history of asthma or allergies, having allergies (atopic dermatitis, allergic rhinitis), being overweight, smoking or exposure to secondhand smoke, exposure to exhaust fumes or pollution, occupational chemical exposure',
    'Permanent narrowing of airways (airway remodeling), side effects from long-term medication use, missed school or work, trouble sleeping, emergency room visits, hospitalization, respiratory failure in severe attacks'
),
(
    'Migraine Symptoms',
    'https://www.mayoclinic.org/diseases-conditions/migraine-headache/symptoms-causes',
    'Migraines are characterized by a pulsating headache usually on one side of the head, accompanied by other symptoms. Some migraines are preceded by warning symptoms called aura.',
    'Prodrome symptoms (mood changes, food cravings, neck stiffness), aura (visual phenomena, vision loss, pins and needles in arm or leg), attack phase (throbbing pain, sensitivity to light/sound/smell, nausea/vomiting), postdrome (confusion, moodiness, dizziness, weakness)',
    'Exact cause unknown but involves changes in the brainstem and interactions with the trigeminal nerve. Triggers include hormonal changes, foods, alcohol, stress, sensory stimuli, sleep changes, weather, medications.',
    'Family history of migraines, age (peak in 30s), being female (3x more common than men), hormonal changes (menstruation, pregnancy, menopause), history of motion sickness, depression or anxiety',
    'Chronic migraines (15+ days per month), medication overuse headache, status migrainosus (attack lasting 72+ hours), persistent aura without infarction, migrainous infarction (stroke during migraine with aura), mental health problems'
),
(
    'Depression Symptoms',
    'https://www.nimh.nih.gov/health/topics/depression',
    'Depression is more than just feeling sad or going through a rough patch. It is a serious mental health condition that requires treatment. Symptoms must last at least two weeks for a depression diagnosis.',
    'Persistent sad, anxious, or empty mood, feelings of hopelessness, pessimism, guilt or worthlessness, loss of interest in hobbies, decreased energy and fatigue, difficulty concentrating, sleep disturbances (insomnia or oversleeping), appetite changes, restlessness, suicidal thoughts',
    'Depression does not have a single cause but results from complex interactions of brain chemistry, hormones, inherited traits, and life circumstances. Trauma, chronic stress, and certain medical conditions can trigger depression.',
    'Personal or family history of depression, major life transitions or stressors, trauma or abuse, chronic illness especially chronic pain, certain medications, substance abuse, being a woman (2x higher risk), social isolation',
    'Worsening mental health, substance abuse, relationship problems, work or school difficulties, physical health problems, self-harm, suicide attempts, decreased quality of life'
),
(
    'Stroke Warning Signs',
    'https://www.stroke.org/en/about-stroke/stroke-symptoms',
    'Stroke is a medical emergency. The sooner treatment is received, the better the outcome. Use F.A.S.T. to remember warning signs: Face drooping, Arm weakness, Speech difficulty, Time to call 911.',
    'Sudden numbness or weakness in face, arm, or leg especially on one side, sudden confusion or trouble speaking or understanding, sudden trouble seeing in one or both eyes, sudden trouble walking, dizziness, or loss of balance, sudden severe headache with no known cause',
    'Ischemic stroke (87% of strokes) occurs when a blood clot blocks an artery to the brain. Hemorrhagic stroke occurs when a blood vessel in the brain bursts. Transient ischemic attack (TIA) is a warning sign of future stroke.',
    'High blood pressure, heart disease, diabetes, high cholesterol, smoking, obesity, physical inactivity, excessive alcohol use, atrial fibrillation, family history, age, prior stroke or TIA, sickle cell disease',
    'Paralysis or weakness on one side of the body, difficulty speaking or swallowing, cognitive impairment, emotional problems, pain, numbness, loss of independence in daily activities, depression, risk of additional strokes'
);

-- ============================================
-- CREATE INDEXES FOR PERFORMANCE
-- ============================================

CREATE INDEX IF NOT EXISTS idx_medicines_title ON medicines(title);
CREATE INDEX IF NOT EXISTS idx_diseases_name ON diseases(name);
CREATE INDEX IF NOT EXISTS idx_symptoms_disease_name ON symptoms(disease_name);

-- ============================================
-- VERIFICATION QUERIES
-- ============================================

SELECT 'medicines' as table_name, COUNT(*) as row_count FROM medicines
UNION ALL
SELECT 'diseases', COUNT(*) FROM diseases
UNION ALL
SELECT 'symptoms', COUNT(*) FROM symptoms;
