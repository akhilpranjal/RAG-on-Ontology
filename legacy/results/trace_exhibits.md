# Ontology Reasoning Traces — Worked Examples

Pipeline 3 (ontology expansion) traces for the 66-query evaluation set, grouped by query category. Generated from `results/reasoning_logs/pipeline_3_ontology_full_reasoning_logs.json`.

## Per-Category Aggregates

| Category | Queries | Avg matched concepts | Total expansions | Top relation families |
|---|---|---|---|---|
| Lay Terminology | 12 | 1.42 | 77 | subClassOf (child, depth=1) (23), subClassOf (child, depth=2) (22), equivalentClass (12) |
| Disease Hierarchy | 12 | 1.25 | 143 | subClassOf (child, depth=2) (60), subClassOf (child, depth=1) (24), hasSymptom (16) |
| Symptom Reasoning | 10 | 1.90 | 152 | subClassOf (child, depth=1) (41), hasSymptom (inverse) (37), subClassOf (child, depth=2) (24) |
| Treatment Reasoning | 10 | 1.10 | 79 | subClassOf (child, depth=1) (17), treatedBy (15), subClassOf (child, depth=2) (11) |
| Multi-Hop | 10 | 1.50 | 92 | subClassOf (child, depth=2) (33), subClassOf (child, depth=1) (21), hasSymptom (inverse) (15) |
| Control: Exact Clinical | 12 | 1.67 | 149 | hasSymptom (40), treatedBy (35), subClassOf (parent) (20) |

## Lay Terminology
*12 queries*

> **Query:** What causes high blood pressure?
**Matched concept:** `high blood pressure` → `HighBloodPressure` (High Blood Pressure)
- `HighBloodPressure` *is equivalent to* `Hypertension` (Hypertension)

**Expanded query terms:** `Hypertension`

> **Query:** What are the emergency signs of a heart attack?
**Matched concept:** `heart attack` → `HeartAttack` (Heart Attack)
- `HeartAttack` *is equivalent to* `MyocardialInfarction` (Myocardial Infarction)

**Expanded query terms:** `Myocardial Infarction`


## Disease Hierarchy
*12 queries*

> **Query:** What specific conditions fall under cardiovascular disease?
**Matched concept:** `cardiovascular disease` → `CardiovascularDisease` (Cardiovascular Disease)
**Matched concept:** `disease` → `Disease` (Disease)
- `CardiovascularDisease` *is equivalent to* `HeartDisease` (Heart Disease)
- `CardiovascularDisease` *is subclass of* `Disease` (Disease)
- `CardiovascularDisease` *has subclass (direct)* `Atherosclerosis` (Atherosclerosis)
- `CardiovascularDisease` *has subclass (direct)* `HeartFailure` (Heart Failure)
- `CardiovascularDisease` *has subclass (direct)* `PeripheralArteryDisease` (Peripheral Artery Disease)
- `CardiovascularDisease` *has subclass (direct)* `Arrhythmia` (Arrhythmia)
- `Arrhythmia` *has subclass (nested)* `AtrialFibrillation` (Atrial Fibrillation)
- `CardiovascularDisease` *has subclass (direct)* `Hypertension` (Hypertension)
- `CardiovascularDisease` *has subclass (direct)* `Stroke` (Stroke)
- `Stroke` *has subclass (nested)* `HemorrhagicStroke` (Hemorrhagic Stroke)
- `Stroke` *has subclass (nested)* `IschemicStroke` (Ischemic Stroke)
- `CardiovascularDisease` *has subclass (direct)* `CoronaryArteryDisease` (Coronary Artery Disease)
- `CoronaryArteryDisease` *has subclass (nested)* `Angina` (Angina Pectoris)
- `CoronaryArteryDisease` *has subclass (nested)* `MyocardialInfarction` (Myocardial Infarction)
- `CardiovascularDisease` *is related to (inv)* `DiabetesMellitus` (Diabetes Mellitus)
- `Disease` *has subclass (direct)* `MetabolicDisease` (Metabolic Disease)
- `MetabolicDisease` *has subclass (nested)* `MetabolicSyndrome` (Metabolic Syndrome)
- `MetabolicDisease` *has subclass (nested)* `Obesity` (Obesity)
- `MetabolicDisease` *has subclass (nested)* `Hyperlipidemia` (Hyperlipidemia)
- `MetabolicDisease` *has subclass (nested)* `DiabetesMellitus` (Diabetes Mellitus)
- `Disease` *has subclass (direct)* `CardiovascularDisease` (Cardiovascular Disease)
- `CardiovascularDisease` *has subclass (nested)* `Atherosclerosis` (Atherosclerosis)
- `CardiovascularDisease` *has subclass (nested)* `HeartFailure` (Heart Failure)
- `CardiovascularDisease` *has subclass (nested)* `PeripheralArteryDisease` (Peripheral Artery Disease)
- `CardiovascularDisease` *has subclass (nested)* `Arrhythmia` (Arrhythmia)
- `CardiovascularDisease` *has subclass (nested)* `Hypertension` (Hypertension)
- `CardiovascularDisease` *has subclass (nested)* `Stroke` (Stroke)
- `CardiovascularDisease` *has subclass (nested)* `CoronaryArteryDisease` (Coronary Artery Disease)

**Expanded query terms:** `Angina Pectoris`, `Arrhythmia`, `Atherosclerosis`, `Atrial Fibrillation`, `Cardiovascular Disease`, `Coronary Artery Disease`, `Diabetes Mellitus`, `Disease`, `Heart Disease`, `Heart Failure`, `Hemorrhagic Stroke`, `Hyperlipidemia`, `Hypertension`, `Ischemic Stroke`, `Metabolic Disease`, `Metabolic Syndrome`, `Myocardial Infarction`, `Obesity`, `Peripheral Artery Disease`, `Stroke`

> **Query:** What are the types of diabetes mellitus?
**Matched concept:** `diabetes mellitus` → `DiabetesMellitus` (Diabetes Mellitus)
- `DiabetesMellitus` *is equivalent to* `SugarDisease` (Sugar Disease)
- `DiabetesMellitus` *is subclass of* `MetabolicDisease` (Metabolic Disease)
- `DiabetesMellitus` *has subclass (direct)* `Type1Diabetes` (Type 1 Diabetes)
- `DiabetesMellitus` *has subclass (direct)* `Type2Diabetes` (Type 2 Diabetes)
- `DiabetesMellitus` *has symptom* `BlurredVision` (Blurred Vision)
- `DiabetesMellitus` *has symptom* `ExcessiveThirst` (Excessive Thirst)
- `DiabetesMellitus` *has symptom* `Fatigue` (Fatigue)
- `DiabetesMellitus` *has symptom* `FrequentUrination` (Frequent Urination)
- `DiabetesMellitus` *has symptom* `UnexplainedWeightLoss` (Unexplained Weight Loss)
- `DiabetesMellitus` *is diagnosed by* `FastingGlucose` (Fasting Blood Glucose Test)
- `DiabetesMellitus` *is diagnosed by* `HbA1c` (Hemoglobin A1c Test)
- `DiabetesMellitus` *is related to* `CardiovascularDisease` (Cardiovascular Disease)

**Expanded query terms:** `Blurred Vision`, `Cardiovascular Disease`, `Excessive Thirst`, `Fasting Blood Glucose Test`, `Fatigue`, `Frequent Urination`, `Hemoglobin A1c Test`, `Metabolic Disease`, `Sugar Disease`, `Type 1 Diabetes`, `Type 2 Diabetes`, `Unexplained Weight Loss`


## Symptom Reasoning
*10 queries*

> **Query:** What diseases present with chest pain and shortness of breath?
**Matched concept:** `shortness of breath` → `ShortnessOfBreath` (Shortness of Breath)
**Matched concept:** `chest pain` → `ChestPain` (Chest Pain)
**Matched concept:** `disease` → `Disease` (Disease)
- `ShortnessOfBreath` *is equivalent to* `Breathlessness` (Breathlessness)
- `ShortnessOfBreath` *is subclass of* `Symptom` (Symptom)
- `ShortnessOfBreath` *is a symptom of* `Angina` (Angina Pectoris)
- `ShortnessOfBreath` *is a symptom of* `AtrialFibrillation` (Atrial Fibrillation)
- `ShortnessOfBreath` *is a symptom of* `Obesity` (Obesity)
- `ShortnessOfBreath` *is a symptom of* `HeartFailure` (Heart Failure)
- `ShortnessOfBreath` *is a symptom of* `MyocardialInfarction` (Myocardial Infarction)
- `ShortnessOfBreath` *is a symptom of* `CoronaryArteryDisease` (Coronary Artery Disease)
- `ChestPain` *is equivalent to* `ChestTightness` (Chest Tightness)
- `ChestPain` *is subclass of* `Symptom` (Symptom)
- `ChestPain` *is a symptom of* `Angina` (Angina Pectoris)
- `ChestPain` *is a symptom of* `Atherosclerosis` (Atherosclerosis)
- `ChestPain` *is a symptom of* `MyocardialInfarction` (Myocardial Infarction)
- `ChestPain` *is a symptom of* `CoronaryArteryDisease` (Coronary Artery Disease)
- `Disease` *has subclass (direct)* `MetabolicDisease` (Metabolic Disease)
- `MetabolicDisease` *has subclass (nested)* `MetabolicSyndrome` (Metabolic Syndrome)
- `MetabolicDisease` *has subclass (nested)* `Obesity` (Obesity)
- `MetabolicDisease` *has subclass (nested)* `Hyperlipidemia` (Hyperlipidemia)
- `MetabolicDisease` *has subclass (nested)* `DiabetesMellitus` (Diabetes Mellitus)
- `Disease` *has subclass (direct)* `CardiovascularDisease` (Cardiovascular Disease)
- `CardiovascularDisease` *has subclass (nested)* `Atherosclerosis` (Atherosclerosis)
- `CardiovascularDisease` *has subclass (nested)* `HeartFailure` (Heart Failure)
- `CardiovascularDisease` *has subclass (nested)* `PeripheralArteryDisease` (Peripheral Artery Disease)
- `CardiovascularDisease` *has subclass (nested)* `Arrhythmia` (Arrhythmia)
- `CardiovascularDisease` *has subclass (nested)* `Hypertension` (Hypertension)
- `CardiovascularDisease` *has subclass (nested)* `Stroke` (Stroke)
- `CardiovascularDisease` *has subclass (nested)* `CoronaryArteryDisease` (Coronary Artery Disease)

**Expanded query terms:** `Angina Pectoris`, `Arrhythmia`, `Atherosclerosis`, `Atrial Fibrillation`, `Breathlessness`, `Cardiovascular Disease`, `Chest Tightness`, `Coronary Artery Disease`, `Diabetes Mellitus`, `Heart Failure`, `Hyperlipidemia`, `Hypertension`, `Metabolic Disease`, `Metabolic Syndrome`, `Myocardial Infarction`, `Obesity`, `Peripheral Artery Disease`, `Stroke`, `Symptom`

> **Query:** What condition causes polyuria, polydipsia, and unexplained weight loss?
**Matched concept:** `unexplained weight loss` → `UnexplainedWeightLoss` (Unexplained Weight Loss)
- `UnexplainedWeightLoss` *is subclass of* `Symptom` (Symptom)
- `UnexplainedWeightLoss` *is a symptom of* `DiabetesMellitus` (Diabetes Mellitus)

**Expanded query terms:** `Diabetes Mellitus`, `Symptom`


## Treatment Reasoning
*10 queries*

> **Query:** What conditions are treated using ACE inhibitors and ARBs?
**Matched concept:** `ace inhibitor` → `ACEInhibitor` (ACE Inhibitor)
- `ACEInhibitor` *is subclass of* `Treatment` (Treatment)
- `ACEInhibitor` *treats* `HeartFailure` (Heart Failure)
- `ACEInhibitor` *treats* `MyocardialInfarction` (Myocardial Infarction)
- `ACEInhibitor` *treats* `Hypertension` (Hypertension)

**Expanded query terms:** `Heart Failure`, `Hypertension`, `Myocardial Infarction`, `Treatment`

> **Query:** What diseases require statin therapy for cholesterol reduction?
**Matched concept:** `disease` → `Disease` (Disease)
**Matched concept:** `statin` → `Statin` (Statin)
- `Disease` *has subclass (direct)* `MetabolicDisease` (Metabolic Disease)
- `MetabolicDisease` *has subclass (nested)* `MetabolicSyndrome` (Metabolic Syndrome)
- `MetabolicDisease` *has subclass (nested)* `Obesity` (Obesity)
- `MetabolicDisease` *has subclass (nested)* `Hyperlipidemia` (Hyperlipidemia)
- `MetabolicDisease` *has subclass (nested)* `DiabetesMellitus` (Diabetes Mellitus)
- `Disease` *has subclass (direct)* `CardiovascularDisease` (Cardiovascular Disease)
- `CardiovascularDisease` *has subclass (nested)* `Atherosclerosis` (Atherosclerosis)
- `CardiovascularDisease` *has subclass (nested)* `HeartFailure` (Heart Failure)
- `CardiovascularDisease` *has subclass (nested)* `PeripheralArteryDisease` (Peripheral Artery Disease)
- `CardiovascularDisease` *has subclass (nested)* `Arrhythmia` (Arrhythmia)
- `CardiovascularDisease` *has subclass (nested)* `Hypertension` (Hypertension)
- `CardiovascularDisease` *has subclass (nested)* `Stroke` (Stroke)
- `CardiovascularDisease` *has subclass (nested)* `CoronaryArteryDisease` (Coronary Artery Disease)
- `Statin` *is subclass of* `Treatment` (Treatment)
- `Statin` *treats* `Atherosclerosis` (Atherosclerosis)
- `Statin` *treats* `Hyperlipidemia` (Hyperlipidemia)
- `Statin` *treats* `CoronaryArteryDisease` (Coronary Artery Disease)

**Expanded query terms:** `Arrhythmia`, `Atherosclerosis`, `Cardiovascular Disease`, `Coronary Artery Disease`, `Diabetes Mellitus`, `Heart Failure`, `Hyperlipidemia`, `Hypertension`, `Metabolic Disease`, `Metabolic Syndrome`, `Obesity`, `Peripheral Artery Disease`, `Stroke`, `Treatment`


## Multi-Hop
*10 queries*

> **Query:** What medications treat diseases that cause leg swelling and shortness of breath?
**Matched concept:** `shortness of breath` → `ShortnessOfBreath` (Shortness of Breath)
**Matched concept:** `disease` → `Disease` (Disease)
- `ShortnessOfBreath` *is equivalent to* `Breathlessness` (Breathlessness)
- `ShortnessOfBreath` *is subclass of* `Symptom` (Symptom)
- `ShortnessOfBreath` *is a symptom of* `Angina` (Angina Pectoris)
- `ShortnessOfBreath` *is a symptom of* `AtrialFibrillation` (Atrial Fibrillation)
- `ShortnessOfBreath` *is a symptom of* `Obesity` (Obesity)
- `ShortnessOfBreath` *is a symptom of* `HeartFailure` (Heart Failure)
- `ShortnessOfBreath` *is a symptom of* `MyocardialInfarction` (Myocardial Infarction)
- `ShortnessOfBreath` *is a symptom of* `CoronaryArteryDisease` (Coronary Artery Disease)
- `Disease` *has subclass (direct)* `MetabolicDisease` (Metabolic Disease)
- `MetabolicDisease` *has subclass (nested)* `MetabolicSyndrome` (Metabolic Syndrome)
- `MetabolicDisease` *has subclass (nested)* `Obesity` (Obesity)
- `MetabolicDisease` *has subclass (nested)* `Hyperlipidemia` (Hyperlipidemia)
- `MetabolicDisease` *has subclass (nested)* `DiabetesMellitus` (Diabetes Mellitus)
- `Disease` *has subclass (direct)* `CardiovascularDisease` (Cardiovascular Disease)
- `CardiovascularDisease` *has subclass (nested)* `Atherosclerosis` (Atherosclerosis)
- `CardiovascularDisease` *has subclass (nested)* `HeartFailure` (Heart Failure)
- `CardiovascularDisease` *has subclass (nested)* `PeripheralArteryDisease` (Peripheral Artery Disease)
- `CardiovascularDisease` *has subclass (nested)* `Arrhythmia` (Arrhythmia)
- `CardiovascularDisease` *has subclass (nested)* `Hypertension` (Hypertension)
- `CardiovascularDisease` *has subclass (nested)* `Stroke` (Stroke)
- `CardiovascularDisease` *has subclass (nested)* `CoronaryArteryDisease` (Coronary Artery Disease)

**Expanded query terms:** `Angina Pectoris`, `Arrhythmia`, `Atherosclerosis`, `Atrial Fibrillation`, `Breathlessness`, `Cardiovascular Disease`, `Coronary Artery Disease`, `Diabetes Mellitus`, `Heart Failure`, `Hyperlipidemia`, `Hypertension`, `Metabolic Disease`, `Metabolic Syndrome`, `Myocardial Infarction`, `Obesity`, `Peripheral Artery Disease`, `Stroke`, `Symptom`

> **Query:** What diagnostic tests evaluate conditions treated with metformin?
**Matched concept:** `metformin` → `Metformin` (Metformin)
- `Metformin` *is subclass of* `Treatment` (Treatment)
- `Metformin` *treats* `Type2Diabetes` (Type 2 Diabetes)

**Expanded query terms:** `Treatment`, `Type 2 Diabetes`


## Control: Exact Clinical
*12 queries*

> **Query:** What is the diagnostic role of Hemoglobin A1c in Diabetes Mellitus?
**Matched concept:** `diabetes mellitus` → `DiabetesMellitus` (Diabetes Mellitus)
- `DiabetesMellitus` *is equivalent to* `SugarDisease` (Sugar Disease)
- `DiabetesMellitus` *is subclass of* `MetabolicDisease` (Metabolic Disease)
- `DiabetesMellitus` *has subclass (direct)* `Type1Diabetes` (Type 1 Diabetes)
- `DiabetesMellitus` *has subclass (direct)* `Type2Diabetes` (Type 2 Diabetes)
- `DiabetesMellitus` *has symptom* `BlurredVision` (Blurred Vision)
- `DiabetesMellitus` *has symptom* `ExcessiveThirst` (Excessive Thirst)
- `DiabetesMellitus` *has symptom* `Fatigue` (Fatigue)
- `DiabetesMellitus` *has symptom* `FrequentUrination` (Frequent Urination)
- `DiabetesMellitus` *has symptom* `UnexplainedWeightLoss` (Unexplained Weight Loss)
- `DiabetesMellitus` *is diagnosed by* `FastingGlucose` (Fasting Blood Glucose Test)
- `DiabetesMellitus` *is diagnosed by* `HbA1c` (Hemoglobin A1c Test)
- `DiabetesMellitus` *is related to* `CardiovascularDisease` (Cardiovascular Disease)

**Expanded query terms:** `Blurred Vision`, `Cardiovascular Disease`, `Excessive Thirst`, `Fasting Blood Glucose Test`, `Fatigue`, `Frequent Urination`, `Hemoglobin A1c Test`, `Metabolic Disease`, `Sugar Disease`, `Type 1 Diabetes`, `Type 2 Diabetes`, `Unexplained Weight Loss`

> **Query:** How does Metformin improve glycemic control in Type 2 Diabetes Mellitus?
**Matched concept:** `diabetes mellitus` → `DiabetesMellitus` (Diabetes Mellitus)
**Matched concept:** `type 2 diabetes` → `Type2Diabetes` (Type 2 Diabetes)
**Matched concept:** `metformin` → `Metformin` (Metformin)
- `DiabetesMellitus` *is equivalent to* `SugarDisease` (Sugar Disease)
- `DiabetesMellitus` *is subclass of* `MetabolicDisease` (Metabolic Disease)
- `DiabetesMellitus` *has subclass (direct)* `Type1Diabetes` (Type 1 Diabetes)
- `DiabetesMellitus` *has subclass (direct)* `Type2Diabetes` (Type 2 Diabetes)
- `DiabetesMellitus` *has symptom* `BlurredVision` (Blurred Vision)
- `DiabetesMellitus` *has symptom* `ExcessiveThirst` (Excessive Thirst)
- `DiabetesMellitus` *has symptom* `Fatigue` (Fatigue)
- `DiabetesMellitus` *has symptom* `FrequentUrination` (Frequent Urination)
- `DiabetesMellitus` *has symptom* `UnexplainedWeightLoss` (Unexplained Weight Loss)
- `DiabetesMellitus` *is diagnosed by* `FastingGlucose` (Fasting Blood Glucose Test)
- `DiabetesMellitus` *is diagnosed by* `HbA1c` (Hemoglobin A1c Test)
- `DiabetesMellitus` *is related to* `CardiovascularDisease` (Cardiovascular Disease)
- `Type2Diabetes` *is subclass of* `DiabetesMellitus` (Diabetes Mellitus)
- `Type2Diabetes` *is treated by* `Insulin` (Insulin)
- `Type2Diabetes` *is treated by* `LifestyleModification` (Lifestyle Modification)
- `Type2Diabetes` *is treated by* `Metformin` (Metformin)
- `Type2Diabetes` *is related to (inv)* `MetabolicSyndrome` (Metabolic Syndrome)
- `Type2Diabetes` *is related to (inv)* `Obesity` (Obesity)
- `Metformin` *is subclass of* `Treatment` (Treatment)
- `Metformin` *treats* `Type2Diabetes` (Type 2 Diabetes)

**Expanded query terms:** `Blurred Vision`, `Cardiovascular Disease`, `Diabetes Mellitus`, `Excessive Thirst`, `Fasting Blood Glucose Test`, `Fatigue`, `Frequent Urination`, `Hemoglobin A1c Test`, `Insulin`, `Lifestyle Modification`, `Metabolic Disease`, `Metabolic Syndrome`, `Metformin`, `Obesity`, `Sugar Disease`, `Treatment`, `Type 1 Diabetes`, `Type 2 Diabetes`, `Unexplained Weight Loss`

