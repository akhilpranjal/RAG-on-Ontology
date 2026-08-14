"""Generate evaluation dataset — 66 medical queries across 6 categories with ground-truth relevance judgments.

Categories:
  A. lay_terminology
  B. disease_hierarchy
  C. symptom_reasoning
  D. treatment_reasoning
  E. multi_hop
  F. control_exact_clinical
"""

from __future__ import annotations

import json
from pathlib import Path

from src.config import QUERIES_FILE, RELEVANCE_JUDGMENTS_FILE, EVALUATION_DIR


QUERIES = [
    # ──────────────────────────────────────────
    # Category A: Lay Terminology (Vocabulary Mismatch)
    # ──────────────────────────────────────────
    {"id": "q_A01", "category": "lay_terminology", "text": "What causes high blood pressure?", "target_concepts": ["Hypertension", "CardiovascularDisease"]},
    {"id": "q_A02", "category": "lay_terminology", "text": "What are the emergency signs of a heart attack?", "target_concepts": ["MyocardialInfarction", "ChestPain", "ShortnessOfBreath"]},
    {"id": "q_A03", "category": "lay_terminology", "text": "How is sugar disease diagnosed?", "target_concepts": ["DiabetesMellitus", "FastingGlucose", "HbA1c"]},
    {"id": "q_A04", "category": "lay_terminology", "text": "What do water pills do for heart problems?", "target_concepts": ["Diuretic", "HeartFailure", "Hypertension"]},
    {"id": "q_A05", "category": "lay_terminology", "text": "What causes leg pain when walking?", "target_concepts": ["Claudication", "PeripheralArteryDisease", "Atherosclerosis"]},
    {"id": "q_A06", "category": "lay_terminology", "text": "What is the treatment for high cholesterol?", "target_concepts": ["Hyperlipidemia", "Statin", "LifestyleModification"]},
    {"id": "q_A07", "category": "lay_terminology", "text": "Why do blood thinners prevent stroke?", "target_concepts": ["Anticoagulant", "Stroke", "AtrialFibrillation"]},
    {"id": "q_A08", "category": "lay_terminology", "text": "What causes an irregular heartbeat?", "target_concepts": ["Arrhythmia", "AtrialFibrillation", "Palpitations"]},
    {"id": "q_A09", "category": "lay_terminology", "text": "What causes chest tightness and breathlessness?", "target_concepts": ["ChestPain", "ShortnessOfBreath", "Angina", "MyocardialInfarction"]},
    {"id": "q_A10", "category": "lay_terminology", "text": "What causes swollen legs in heart disease?", "target_concepts": ["Edema", "HeartFailure", "CardiovascularDisease"]},
    {"id": "q_A11", "category": "lay_terminology", "text": "What causes hardening of the arteries?", "target_concepts": ["Atherosclerosis", "Hyperlipidemia", "Hypertension"]},
    {"id": "q_A12", "category": "lay_terminology", "text": "What is the difference between a mini stroke and a stroke?", "target_concepts": ["Stroke", "IschemicStroke"]},

    # ──────────────────────────────────────────
    # Category B: Disease Hierarchy (Subclass Enumeration)
    # ──────────────────────────────────────────
    {"id": "q_B01", "category": "disease_hierarchy", "text": "What specific conditions fall under cardiovascular disease?", "target_concepts": ["CardiovascularDisease", "Hypertension", "CoronaryArteryDisease", "HeartFailure", "Arrhythmia", "Stroke"]},
    {"id": "q_B02", "category": "disease_hierarchy", "text": "What are the types of diabetes mellitus?", "target_concepts": ["DiabetesMellitus", "Type1Diabetes", "Type2Diabetes"]},
    {"id": "q_B03", "category": "disease_hierarchy", "text": "What diseases are classified as metabolic disorders?", "target_concepts": ["MetabolicDisease", "DiabetesMellitus", "Obesity", "Hyperlipidemia", "MetabolicSyndrome"]},
    {"id": "q_B04", "category": "disease_hierarchy", "text": "What forms of stroke exist?", "target_concepts": ["Stroke", "IschemicStroke", "HemorrhagicStroke"]},
    {"id": "q_B05", "category": "disease_hierarchy", "text": "What cardiac arrhythmias affect the heart rhythm?", "target_concepts": ["Arrhythmia", "AtrialFibrillation"]},
    {"id": "q_B06", "category": "disease_hierarchy", "text": "What clinical manifestations are related to coronary artery disease?", "target_concepts": ["CoronaryArteryDisease", "MyocardialInfarction", "Angina"]},
    {"id": "q_B07", "category": "disease_hierarchy", "text": "What metabolic conditions are associated with obesity?", "target_concepts": ["Obesity", "Type2Diabetes", "Hyperlipidemia", "MetabolicSyndrome"]},
    {"id": "q_B08", "category": "disease_hierarchy", "text": "What vascular diseases involve arterial occlusion?", "target_concepts": ["Atherosclerosis", "PeripheralArteryDisease", "CoronaryArteryDisease"]},
    {"id": "q_B09", "category": "disease_hierarchy", "text": "What disorders are categorized under metabolic syndrome?", "target_concepts": ["MetabolicSyndrome", "Hypertension", "Type2Diabetes", "Hyperlipidemia", "Obesity"]},
    {"id": "q_B10", "category": "disease_hierarchy", "text": "What types of angina pectoris occur in heart disease?", "target_concepts": ["Angina", "CoronaryArteryDisease"]},
    {"id": "q_B11", "category": "disease_hierarchy", "text": "What high blood pressure sub-conditions or complications exist?", "target_concepts": ["Hypertension", "HeartFailure", "Stroke"]},
    {"id": "q_B12", "category": "disease_hierarchy", "text": "What disorders involve lipid metabolism impairment?", "target_concepts": ["Hyperlipidemia", "MetabolicSyndrome", "Atherosclerosis"]},

    # ──────────────────────────────────────────
    # Category C: Symptom Reasoning (hasSymptom Traversal)
    # ──────────────────────────────────────────
    {"id": "q_C01", "category": "symptom_reasoning", "text": "What diseases present with chest pain and shortness of breath?", "target_concepts": ["MyocardialInfarction", "HeartFailure", "CoronaryArteryDisease", "Angina"]},
    {"id": "q_C02", "category": "symptom_reasoning", "text": "What condition causes polyuria, polydipsia, and unexplained weight loss?", "target_concepts": ["DiabetesMellitus", "Type1Diabetes", "FrequentUrination", "ExcessiveThirst"]},
    {"id": "q_C03", "category": "symptom_reasoning", "text": "What cardiovascular disorders produce peripheral edema and fatigue?", "target_concepts": ["HeartFailure", "Edema", "Fatigue"]},
    {"id": "q_C04", "category": "symptom_reasoning", "text": "What condition causes sudden facial numbness, dizziness, and vision disturbance?", "target_concepts": ["Stroke", "IschemicStroke", "Numbness", "Dizziness", "BlurredVision"]},
    {"id": "q_C05", "category": "symptom_reasoning", "text": "What arrhythmia presents with palpitations and lightheadedness?", "target_concepts": ["AtrialFibrillation", "Arrhythmia", "Palpitations", "Dizziness"]},
    {"id": "q_C06", "category": "symptom_reasoning", "text": "What vascular disorder produces leg pain specifically triggered by walking?", "target_concepts": ["PeripheralArteryDisease", "Claudication", "Atherosclerosis"]},
    {"id": "q_C07", "category": "symptom_reasoning", "text": "What symptoms accompany acute myocardial infarction besides chest pain?", "target_concepts": ["MyocardialInfarction", "ShortnessOfBreath", "Sweating", "Nausea", "JawPain"]},
    {"id": "q_C08", "category": "symptom_reasoning", "text": "What symptoms indicate severe uncontrolled hypertension?", "target_concepts": ["Hypertension", "Headache", "Dizziness", "BlurredVision"]},
    {"id": "q_C09", "category": "symptom_reasoning", "text": "What cardiac condition causes exertional angina radiating to the jaw?", "target_concepts": ["Angina", "CoronaryArteryDisease", "JawPain", "ChestPain"]},
    {"id": "q_C10", "category": "symptom_reasoning", "text": "What metabolic disease causes constant fatigue and blurred vision?", "target_concepts": ["DiabetesMellitus", "Type2Diabetes", "Fatigue", "BlurredVision"]},

    # ──────────────────────────────────────────
    # Category D: Treatment Reasoning (treatedBy Traversal)
    # ──────────────────────────────────────────
    {"id": "q_D01", "category": "treatment_reasoning", "text": "What conditions are treated using ACE inhibitors and ARBs?", "target_concepts": ["ACEInhibitor", "ARB", "Hypertension", "HeartFailure"]},
    {"id": "q_D02", "category": "treatment_reasoning", "text": "What diseases require statin therapy for cholesterol reduction?", "target_concepts": ["Statin", "Hyperlipidemia", "Atherosclerosis", "CoronaryArteryDisease"]},
    {"id": "q_D03", "category": "treatment_reasoning", "text": "What conditions are treated with intravenous thrombolytic agents?", "target_concepts": ["Thrombolytic", "IschemicStroke", "MyocardialInfarction"]},
    {"id": "q_D04", "category": "treatment_reasoning", "text": "What medications are prescribed for Type 2 Diabetes management?", "target_concepts": ["Metformin", "Insulin", "LifestyleModification", "Type2Diabetes"]},
    {"id": "q_D05", "category": "treatment_reasoning", "text": "What drug classes control heart rate in atrial fibrillation?", "target_concepts": ["BetaBlocker", "CalciumChannelBlocker", "Anticoagulant", "AtrialFibrillation"]},
    {"id": "q_D06", "category": "treatment_reasoning", "text": "What medication provides rapid relief for acute angina pectoris?", "target_concepts": ["Nitroglycerin", "Angina", "CoronaryArteryDisease"]},
    {"id": "q_D07", "category": "treatment_reasoning", "text": "What surgical revascularization procedures treat severe coronary artery stenosis?", "target_concepts": ["CABG", "Angioplasty", "CoronaryArteryDisease"]},
    {"id": "q_D08", "category": "treatment_reasoning", "text": "What therapeutic options treat fluid overload in heart failure?", "target_concepts": ["Diuretic", "ACEInhibitor", "BetaBlocker", "HeartFailure"]},
    {"id": "q_D09", "category": "treatment_reasoning", "text": "What first-line pharmacological treatment is given for Type 1 Diabetes?", "target_concepts": ["Insulin", "Type1Diabetes"]},
    {"id": "q_D10", "category": "treatment_reasoning", "text": "What antiplatelet and anticoagulant medications reduce thrombosis risk?", "target_concepts": ["Antiplatelet", "Anticoagulant", "Stroke", "MyocardialInfarction", "AtrialFibrillation"]},

    # ──────────────────────────────────────────
    # Category E: Multi-hop Reasoning (Multi-Relation Traversal)
    # ──────────────────────────────────────────
    {"id": "q_E01", "category": "multi_hop", "text": "What medications treat diseases that cause leg swelling and shortness of breath?", "target_concepts": ["HeartFailure", "Edema", "ShortnessOfBreath", "ACEInhibitor", "BetaBlocker", "Diuretic"]},
    {"id": "q_E02", "category": "multi_hop", "text": "What diagnostic tests evaluate conditions treated with metformin?", "target_concepts": ["Type2Diabetes", "Metformin", "FastingGlucose", "HbA1c"]},
    {"id": "q_E03", "category": "multi_hop", "text": "What surgical procedures treat conditions that present with crushing chest pain?", "target_concepts": ["MyocardialInfarction", "CoronaryArteryDisease", "Angina", "CABG", "Angioplasty"]},
    {"id": "q_E04", "category": "multi_hop", "text": "What diagnostic tests assess diseases that cause facial numbness and vision loss?", "target_concepts": ["Stroke", "IschemicStroke", "Numbness", "BlurredVision", "CTAngiography"]},
    {"id": "q_E05", "category": "multi_hop", "text": "What medications treat heart diseases caused by lipid accumulation in arteries?", "target_concepts": ["Hyperlipidemia", "Atherosclerosis", "CoronaryArteryDisease", "Statin", "Antiplatelet"]},
    {"id": "q_E06", "category": "multi_hop", "text": "What treatments address metabolic conditions characterized by central obesity and high fasting glucose?", "target_concepts": ["MetabolicSyndrome", "Type2Diabetes", "Obesity", "Metformin", "LifestyleModification"]},
    {"id": "q_E07", "category": "multi_hop", "text": "What drugs treat heart rhythm disorders diagnosed by electrocardiogram?", "target_concepts": ["Arrhythmia", "AtrialFibrillation", "ECG", "BetaBlocker", "CalciumChannelBlocker", "Anticoagulant"]},
    {"id": "q_E08", "category": "multi_hop", "text": "What procedures treat arterial occlusions causing leg pain during exercise?", "target_concepts": ["PeripheralArteryDisease", "Claudication", "Angioplasty", "Statin", "Antiplatelet"]},
    {"id": "q_E09", "category": "multi_hop", "text": "What medications treat high blood pressure complications that lead to swollen legs?", "target_concepts": ["Hypertension", "HeartFailure", "Edema", "Diuretic", "ACEInhibitor"]},
    {"id": "q_E10", "category": "multi_hop", "text": "What diagnostic tests confirm conditions presenting with excessive thirst and frequent urination?", "target_concepts": ["DiabetesMellitus", "FrequentUrination", "ExcessiveThirst", "FastingGlucose", "HbA1c"]},

    # ──────────────────────────────────────────
    # Category F: Control (Exact Clinical Terminology)
    # ──────────────────────────────────────────
    {"id": "q_F01", "category": "control_exact_clinical", "text": "What is the diagnostic role of Hemoglobin A1c in Diabetes Mellitus?", "target_concepts": ["HbA1c", "DiabetesMellitus"]},
    {"id": "q_F02", "category": "control_exact_clinical", "text": "How does Metformin improve glycemic control in Type 2 Diabetes Mellitus?", "target_concepts": ["Metformin", "Type2Diabetes"]},
    {"id": "q_F03", "category": "control_exact_clinical", "text": "What are the indication criteria for Coronary Artery Bypass Grafting?", "target_concepts": ["CABG", "CoronaryArteryDisease"]},
    {"id": "q_F04", "category": "control_exact_clinical", "text": "What is the mechanism of action of ACE Inhibitors in Hypertension?", "target_concepts": ["ACEInhibitor", "Hypertension"]},
    {"id": "q_F05", "category": "control_exact_clinical", "text": "What ECG findings characterize Atrial Fibrillation?", "target_concepts": ["ECG", "AtrialFibrillation"]},
    {"id": "q_F06", "category": "control_exact_clinical", "text": "How is Percutaneous Coronary Intervention performed in Myocardial Infarction?", "target_concepts": ["Angioplasty", "MyocardialInfarction"]},
    {"id": "q_F07", "category": "control_exact_clinical", "text": "What is the therapeutic window for Thrombolytic therapy in Acute Ischemic Stroke?", "target_concepts": ["Thrombolytic", "IschemicStroke"]},
    {"id": "q_F08", "category": "control_exact_clinical", "text": "What components constitute a comprehensive Lipid Panel assessment?", "target_concepts": ["LipidPanel", "Hyperlipidemia"]},
    {"id": "q_F09", "category": "control_exact_clinical", "text": "How does Sublingual Nitroglycerin relieve Angina Pectoris?", "target_concepts": ["Nitroglycerin", "Angina"]},
    {"id": "q_F10", "category": "control_exact_clinical", "text": "What are the clinical diagnostic criteria for Metabolic Syndrome?", "target_concepts": ["MetabolicSyndrome"]},
    {"id": "q_F11", "category": "control_exact_clinical", "text": "How is Echocardiography utilized to measure ejection fraction in Heart Failure?", "target_concepts": ["Echocardiogram", "HeartFailure"]},
    {"id": "q_F12", "category": "control_exact_clinical", "text": "What is the role of Anticoagulant therapy in Atrial Fibrillation stroke prevention?", "target_concepts": ["Anticoagulant", "AtrialFibrillation", "Stroke"]},
]


def generate_relevance_judgments(queries: list[dict]) -> dict[str, list[str]]:
    """Automatically map query target concepts to corpus document IDs containing those concepts.

    This generates ground-truth relevance judgments mapping each query ID to document IDs.
    """
    # Load all document JSON files to map concepts -> doc_ids
    from src.corpus.loader import load_documents
    from src.config import REAL_CORPUS_DIR, SYNTHETIC_CORPUS_DIR

    real_docs = load_documents(REAL_CORPUS_DIR)
    synth_docs = load_documents(SYNTHETIC_CORPUS_DIR)
    all_docs = real_docs + synth_docs

    relevance_judgments = {}

    for q in queries:
        q_id = q["id"]
        target_concepts = set(q["target_concepts"])
        matching_doc_ids = []

        for doc in all_docs:
            doc_concepts = set(doc.get("concepts", []))
            # Relevance condition: document covers at least one target concept
            if target_concepts & doc_concepts:
                matching_doc_ids.append(doc["doc_id"])

        relevance_judgments[q_id] = matching_doc_ids

    return relevance_judgments


def main():
    EVALUATION_DIR.mkdir(parents=True, exist_ok=True)

    # Save queries
    with open(QUERIES_FILE, "w", encoding="utf-8") as f:
        json.dump(QUERIES, f, indent=2, ensure_ascii=False)
    print(f"[OK] Saved {len(QUERIES)} evaluation queries to {QUERIES_FILE}")

    # Generate and save relevance judgments
    judgments = generate_relevance_judgments(QUERIES)
    with open(RELEVANCE_JUDGMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(judgments, f, indent=2, ensure_ascii=False)
    print(f"[OK] Saved ground-truth relevance judgments to {RELEVANCE_JUDGMENTS_FILE}")

    # Summary by category
    categories = {}
    for q in QUERIES:
        cat = q["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print("\nQuery counts by category:")
    for cat, count in categories.items():
        print(f"  - {cat}: {count} queries")


if __name__ == "__main__":
    main()
