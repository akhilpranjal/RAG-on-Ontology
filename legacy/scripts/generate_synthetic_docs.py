"""Generate synthetic medical documents for under-represented ontology concepts.

Creates structured JSON documents for concepts to ensure all ~70 concepts
in medical_ontology.ttl are well-represented in the corpus.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.config import SYNTHETIC_CORPUS_DIR


SYNTHETIC_TEMPLATES = [
    {
        "doc_id": "synth_001",
        "title": "Clinical Management of Type 1 Diabetes Mellitus",
        "text": "Type 1 Diabetes Mellitus is an autoimmune metabolic disease characterized by the destruction of insulin-producing beta cells in the pancreas. Symptoms include frequent urination, excessive thirst, fatigue, and unexplained weight loss. Exogenous insulin administration is the primary treatment. Diagnostic tests include fasting blood glucose test and hemoglobin A1c test (HbA1c).",
        "source": "Synthetic",
        "concepts": ["Disease", "MetabolicDisease", "DiabetesMellitus", "Type1Diabetes", "FrequentUrination", "ExcessiveThirst", "Fatigue", "UnexplainedWeightLoss", "Insulin", "FastingGlucose", "HbA1c"]
    },
    {
        "doc_id": "synth_002",
        "title": "Diagnosis and Treatment Options for Atrial Fibrillation",
        "text": "Atrial Fibrillation is a common cardiac arrhythmia characterized by rapid and irregular atrial activation. Key symptoms include palpitations, dizziness, fatigue, and shortness of breath. Diagnosis is confirmed using an electrocardiogram (ECG). Treatment strategies involve anticoagulants to prevent stroke, as well as rate control agents such as beta blockers and calcium channel blockers.",
        "source": "Synthetic",
        "concepts": ["Disease", "CardiovascularDisease", "Arrhythmia", "AtrialFibrillation", "Palpitations", "Dizziness", "Fatigue", "ShortnessOfBreath", "ECG", "Anticoagulant", "BetaBlocker", "CalciumChannelBlocker", "Stroke"]
    },
    {
        "doc_id": "synth_003",
        "title": "Metformin Therapy in Type 2 Diabetes Management",
        "text": "Metformin is the first-line oral antihyperglycemic treatment for Type 2 Diabetes Mellitus. It improves insulin sensitivity and reduces hepatic glucose production. Combined with lifestyle modifications such as diet and exercise, metformin helps manage metabolic syndrome and hyperlipidemia. Diagnostic monitoring relies on regular HbA1c testing.",
        "source": "Synthetic",
        "concepts": ["Treatment", "Metformin", "Type2Diabetes", "DiabetesMellitus", "MetabolicDisease", "LifestyleModification", "MetabolicSyndrome", "Hyperlipidemia", "HbA1c"]
    },
    {
        "doc_id": "synth_004",
        "title": "Surgical Revascularization: CABG vs Angioplasty in Coronary Artery Disease",
        "text": "Patients with severe coronary artery disease (CAD) may require revascularization. Coronary Artery Bypass Grafting (CABG) is an open surgical procedure bypasses blocked arteries, whereas angioplasty (percutaneous coronary intervention) utilizes stenting to restore blood flow. Both procedures relieve severe chest pain (angina) and reduce the risk of myocardial infarction.",
        "source": "Synthetic",
        "concepts": ["Treatment", "CABG", "Angioplasty", "CoronaryArteryDisease", "CardiovascularDisease", "ChestPain", "Angina", "MyocardialInfarction"]
    },
    {
        "doc_id": "synth_005",
        "title": "Acute Ischemic Stroke Emergency Intervention with Thrombolytics",
        "text": "Acute Ischemic Stroke occurs when an artery supplying blood to the brain is obstructed by a clot, leading to sudden numbness, severe headache, dizziness, and blurred vision. Intravenous thrombolytic therapy (tPA) must be administered within a narrow time window to dissolve the clot and restore cerebral blood flow. CT angiography is essential for rapid diagnosis.",
        "source": "Synthetic",
        "concepts": ["Disease", "CardiovascularDisease", "Stroke", "IschemicStroke", "Numbness", "Headache", "Dizziness", "BlurredVision", "Thrombolytic", "CTAngiography"]
    },
    {
        "doc_id": "synth_006",
        "title": "Echocardiography in the Evaluation of Heart Failure and Edema",
        "text": "Heart failure is a progressive cardiovascular condition where the cardiac muscle cannot pump sufficient blood. Common manifestations include edema (swollen legs), shortness of breath, and fatigue. Echocardiography is the primary non-invasive diagnostic test used to evaluate ejection fraction and cardiac structural abnormalities.",
        "source": "Synthetic",
        "concepts": ["Disease", "CardiovascularDisease", "HeartFailure", "Edema", "ShortnessOfBreath", "Fatigue", "Echocardiogram", "DiagnosticTest"]
    },
    {
        "doc_id": "synth_007",
        "title": "Pharmacological Management of Hypertension with Diuretics and ACE Inhibitors",
        "text": "Hypertension (high blood pressure) is a major risk factor for heart failure, stroke, and atherosclerosis. Initial therapy often includes ACE inhibitors, Angiotensin II Receptor Blockers (ARBs), calcium channel blockers, and diuretics (water pills). Diagnostic monitoring requires accurate blood pressure measurements.",
        "source": "Synthetic",
        "concepts": ["Disease", "CardiovascularDisease", "Hypertension", "HeartFailure", "Stroke", "Atherosclerosis", "ACEInhibitor", "ARB", "CalciumChannelBlocker", "Diuretic", "BloodPressureTest"]
    },
    {
        "doc_id": "synth_008",
        "title": "Hyperlipidemia, Atherosclerosis, and Statin Therapy",
        "text": "Hyperlipidemia is characterized by elevated blood lipids, contributing to the development of atherosclerosis (hardening of the arteries). Lipid panel blood tests evaluate total cholesterol, LDL, and HDL levels. Statin therapy reduces low-density lipoprotein cholesterol, lowering the incidence of coronary artery disease and myocardial infarction.",
        "source": "Synthetic",
        "concepts": ["Disease", "MetabolicDisease", "Hyperlipidemia", "Atherosclerosis", "CoronaryArteryDisease", "MyocardialInfarction", "LipidPanel", "Statin"]
    },
    {
        "doc_id": "synth_009",
        "title": "Peripheral Artery Disease: Symptoms of Claudication and Treatment",
        "text": "Peripheral Artery Disease (PAD) is caused by atherosclerotic narrowing of leg arteries. The hallmark symptom is intermittent claudication (leg pain when walking) and lower extremity numbness. Treatment includes antiplatelet therapy, statins, exercise therapy, and angioplasty in severe cases.",
        "source": "Synthetic",
        "concepts": ["Disease", "CardiovascularDisease", "PeripheralArteryDisease", "Atherosclerosis", "Claudication", "Numbness", "Antiplatelet", "Statin", "Angioplasty"]
    },
    {
        "doc_id": "synth_010",
        "title": "Emergency Management of Angina and Myocardial Infarction with Nitroglycerin",
        "text": "Angina pectoris presents as crushing chest pain or tightness radiating to the jaw and arm, frequently accompanied by shortness of breath and sweating. Sublingual nitroglycerin acts as a potent vasodilator to relieve acute angina symptoms. If chest pain persists, immediate evaluation for acute myocardial infarction via ECG is required.",
        "source": "Synthetic",
        "concepts": ["Disease", "CoronaryArteryDisease", "Angina", "MyocardialInfarction", "ChestPain", "ShortnessOfBreath", "Sweating", "JawPain", "Nitroglycerin", "ECG"]
    },
    {
        "doc_id": "synth_011",
        "title": "Metabolic Syndrome Diagnostic Criteria and Risk Assessment",
        "text": "Metabolic Syndrome represents a cluster of conditions including central obesity, hypertension, hyperlipidemia, and elevated fasting glucose (insulin resistance). Together, these factors exponentially increase the risk of developing Type 2 Diabetes and coronary artery disease. Management focuses on comprehensive lifestyle modification and pharmacotherapy.",
        "source": "Synthetic",
        "concepts": ["Disease", "MetabolicDisease", "MetabolicSyndrome", "Obesity", "Hypertension", "Hyperlipidemia", "Type2Diabetes", "CoronaryArteryDisease", "LifestyleModification"]
    },
    {
        "doc_id": "synth_012",
        "title": "Diagnostic Testing Overview: Cardiac Stress Test and Catheterization",
        "text": "Evaluation of suspected coronary artery disease includes cardiac stress testing to detect exercise-induced myocardial ischemia. When non-invasive tests are abnormal, cardiac catheterization (coronary angiography) is performed to directly visualize arterial stenoses and guide revascularization via angioplasty or CABG.",
        "source": "Synthetic",
        "concepts": ["DiagnosticTest", "StressTest", "CardiacCatheterization", "CoronaryArteryDisease", "Angioplasty", "CABG"]
    }
]


def generate_synthetic_documents():
    """Write synthetic document templates to the synthetic corpus directory."""
    SYNTHETIC_CORPUS_DIR.mkdir(parents=True, exist_ok=True)

    for doc in SYNTHETIC_TEMPLATES:
        filepath = SYNTHETIC_CORPUS_DIR / f"{doc['doc_id']}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)

    print(f"[OK] Generated {len(SYNTHETIC_TEMPLATES)} synthetic medical documents in {SYNTHETIC_CORPUS_DIR}")


if __name__ == "__main__":
    generate_synthetic_documents()
