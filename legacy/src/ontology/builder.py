"""Ontology builder — constructs the lightweight medical OWL/Turtle ontology.

Builds a purpose-built medical ontology covering Cardiovascular and Metabolic
diseases with four top-level classes: Disease, Symptom, Treatment, DiagnosticTest.

Relations:
    - owl:equivalentClass  — lay-term synonyms
    - rdfs:subClassOf      — disease/symptom hierarchies
    - hasSymptom           — disease → symptom
    - treatedBy            — disease → treatment
    - diagnosedBy          — disease → diagnostic test
    - relatedCondition     — disease → disease
    - contraindicatedWith  — treatment → condition
"""

from __future__ import annotations

from rdflib import Graph, Namespace, Literal, URIRef, RDF, RDFS, OWL
from rdflib.namespace import XSD

from src.config import ONTOLOGY_FILE, ONTOLOGY_NAMESPACE, ONTOLOGY_DIR

# Define the namespace for our ontology
MED = Namespace(ONTOLOGY_NAMESPACE)


def build_ontology() -> Graph:
    """Build the complete medical ontology and return the RDF graph.

    This constructs a lightweight OWL ontology covering cardiovascular
    and metabolic diseases, inspired by MeSH/MedlinePlus terminology.
    """
    g = Graph()
    g.bind("med", MED)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)

    # ──────────────────────────────────────────
    # Top-Level Classes
    # ──────────────────────────────────────────
    for cls in ["Disease", "Symptom", "Treatment", "DiagnosticTest"]:
        g.add((MED[cls], RDF.type, OWL.Class))
        g.add((MED[cls], RDFS.label, Literal(cls)))

    # ──────────────────────────────────────────
    # Object Properties
    # ──────────────────────────────────────────
    properties = {
        "hasSymptom": ("Disease", "Symptom"),
        "treatedBy": ("Disease", "Treatment"),
        "diagnosedBy": ("Disease", "DiagnosticTest"),
        "relatedCondition": ("Disease", "Disease"),
        "contraindicatedWith": ("Treatment", "Disease"),
    }
    for prop, (domain, range_) in properties.items():
        g.add((MED[prop], RDF.type, OWL.ObjectProperty))
        g.add((MED[prop], RDFS.domain, MED[domain]))
        g.add((MED[prop], RDFS.range, MED[range_]))

    # ──────────────────────────────────────────
    # Disease Hierarchy
    # ──────────────────────────────────────────

    # Cardiovascular Diseases
    _add_subclass(g, "CardiovascularDisease", "Disease", "Cardiovascular Disease")
    _add_subclass(g, "Hypertension", "CardiovascularDisease", "Hypertension")
    _add_subclass(g, "CoronaryArteryDisease", "CardiovascularDisease", "Coronary Artery Disease")
    _add_subclass(g, "MyocardialInfarction", "CoronaryArteryDisease", "Myocardial Infarction")
    _add_subclass(g, "HeartFailure", "CardiovascularDisease", "Heart Failure")
    _add_subclass(g, "Arrhythmia", "CardiovascularDisease", "Arrhythmia")
    _add_subclass(g, "AtrialFibrillation", "Arrhythmia", "Atrial Fibrillation")
    _add_subclass(g, "Stroke", "CardiovascularDisease", "Stroke")
    _add_subclass(g, "IschemicStroke", "Stroke", "Ischemic Stroke")
    _add_subclass(g, "HemorrhagicStroke", "Stroke", "Hemorrhagic Stroke")
    _add_subclass(g, "Atherosclerosis", "CardiovascularDisease", "Atherosclerosis")
    _add_subclass(g, "PeripheralArteryDisease", "CardiovascularDisease", "Peripheral Artery Disease")
    _add_subclass(g, "Angina", "CoronaryArteryDisease", "Angina Pectoris")

    # Metabolic Diseases
    _add_subclass(g, "MetabolicDisease", "Disease", "Metabolic Disease")
    _add_subclass(g, "DiabetesMellitus", "MetabolicDisease", "Diabetes Mellitus")
    _add_subclass(g, "Type1Diabetes", "DiabetesMellitus", "Type 1 Diabetes")
    _add_subclass(g, "Type2Diabetes", "DiabetesMellitus", "Type 2 Diabetes")
    _add_subclass(g, "Obesity", "MetabolicDisease", "Obesity")
    _add_subclass(g, "Hyperlipidemia", "MetabolicDisease", "Hyperlipidemia")
    _add_subclass(g, "MetabolicSyndrome", "MetabolicDisease", "Metabolic Syndrome")

    # ──────────────────────────────────────────
    # Symptoms
    # ──────────────────────────────────────────
    symptoms = {
        "ChestPain": "Chest Pain",
        "ShortnessOfBreath": "Shortness of Breath",
        "Fatigue": "Fatigue",
        "Dizziness": "Dizziness",
        "Palpitations": "Palpitations",
        "Edema": "Edema",
        "Headache": "Headache",
        "BlurredVision": "Blurred Vision",
        "FrequentUrination": "Frequent Urination",
        "ExcessiveThirst": "Excessive Thirst",
        "UnexplainedWeightLoss": "Unexplained Weight Loss",
        "Numbness": "Numbness",
        "Claudication": "Claudication",
        "Nausea": "Nausea",
        "Sweating": "Sweating",
        "JawPain": "Jaw Pain",
    }
    for sym_id, sym_label in symptoms.items():
        _add_subclass(g, sym_id, "Symptom", sym_label)

    # ──────────────────────────────────────────
    # Treatments
    # ──────────────────────────────────────────
    treatments = {
        "ACEInhibitor": "ACE Inhibitor",
        "BetaBlocker": "Beta Blocker",
        "CalciumChannelBlocker": "Calcium Channel Blocker",
        "Diuretic": "Diuretic",
        "Statin": "Statin",
        "Anticoagulant": "Anticoagulant",
        "Antiplatelet": "Antiplatelet Agent",
        "Insulin": "Insulin",
        "Metformin": "Metformin",
        "Thrombolytic": "Thrombolytic",
        "Nitroglycerin": "Nitroglycerin",
        "ARB": "Angiotensin II Receptor Blocker",
        "LifestyleModification": "Lifestyle Modification",
        "CABG": "Coronary Artery Bypass Grafting",
        "Angioplasty": "Angioplasty",
    }
    for treat_id, treat_label in treatments.items():
        _add_subclass(g, treat_id, "Treatment", treat_label)

    # ──────────────────────────────────────────
    # Diagnostic Tests
    # ──────────────────────────────────────────
    tests = {
        "ECG": "Electrocardiogram",
        "Echocardiogram": "Echocardiogram",
        "BloodPressureTest": "Blood Pressure Measurement",
        "LipidPanel": "Lipid Panel",
        "FastingGlucose": "Fasting Blood Glucose Test",
        "HbA1c": "Hemoglobin A1c Test",
        "CardiacCatheterization": "Cardiac Catheterization",
        "StressTest": "Cardiac Stress Test",
        "CTAngiography": "CT Angiography",
        "BMI": "Body Mass Index Assessment",
    }
    for test_id, test_label in tests.items():
        _add_subclass(g, test_id, "DiagnosticTest", test_label)

    # ──────────────────────────────────────────
    # Lay-Term Equivalences (owl:equivalentClass)
    # ──────────────────────────────────────────
    equivalences = {
        "HighBloodPressure": ("Hypertension", "High Blood Pressure"),
        "HeartAttack": ("MyocardialInfarction", "Heart Attack"),
        "SugarDisease": ("DiabetesMellitus", "Sugar Disease"),
        "WaterPill": ("Diuretic", "Water Pill"),
        "HeartDisease": ("CardiovascularDisease", "Heart Disease"),
        "HighCholesterol": ("Hyperlipidemia", "High Cholesterol"),
        "BloodThinner": ("Anticoagulant", "Blood Thinner"),
        "IrregularHeartbeat": ("Arrhythmia", "Irregular Heartbeat"),
        "LegPain": ("Claudication", "Leg Pain When Walking"),
        "Breathlessness": ("ShortnessOfBreath", "Breathlessness"),
        "ChestTightness": ("ChestPain", "Chest Tightness"),
        "SwollenLegs": ("Edema", "Swollen Legs"),
    }
    for lay_id, (clinical_id, lay_label) in equivalences.items():
        g.add((MED[lay_id], RDF.type, OWL.Class))
        g.add((MED[lay_id], RDFS.label, Literal(lay_label)))
        g.add((MED[lay_id], OWL.equivalentClass, MED[clinical_id]))

    # ──────────────────────────────────────────
    # Disease → Symptom Relations (hasSymptom)
    # ──────────────────────────────────────────
    disease_symptoms = {
        "Hypertension": ["Headache", "Dizziness", "BlurredVision"],
        "MyocardialInfarction": ["ChestPain", "ShortnessOfBreath", "Sweating", "Nausea", "JawPain"],
        "HeartFailure": ["ShortnessOfBreath", "Fatigue", "Edema", "Palpitations"],
        "CoronaryArteryDisease": ["ChestPain", "ShortnessOfBreath", "Fatigue"],
        "Angina": ["ChestPain", "ShortnessOfBreath"],
        "AtrialFibrillation": ["Palpitations", "Dizziness", "ShortnessOfBreath", "Fatigue"],
        "Stroke": ["Numbness", "Headache", "Dizziness", "BlurredVision"],
        "DiabetesMellitus": ["FrequentUrination", "ExcessiveThirst", "Fatigue", "BlurredVision", "UnexplainedWeightLoss"],
        "Obesity": ["ShortnessOfBreath", "Fatigue"],
        "Atherosclerosis": ["ChestPain", "Claudication", "Numbness"],
        "PeripheralArteryDisease": ["Claudication", "Numbness"],
    }
    for disease, symptom_list in disease_symptoms.items():
        for symptom in symptom_list:
            g.add((MED[disease], MED.hasSymptom, MED[symptom]))

    # ──────────────────────────────────────────
    # Disease → Treatment Relations (treatedBy)
    # ──────────────────────────────────────────
    disease_treatments = {
        "Hypertension": ["ACEInhibitor", "ARB", "CalciumChannelBlocker", "Diuretic", "BetaBlocker", "LifestyleModification"],
        "MyocardialInfarction": ["Thrombolytic", "Antiplatelet", "BetaBlocker", "ACEInhibitor", "Angioplasty", "CABG"],
        "HeartFailure": ["ACEInhibitor", "ARB", "BetaBlocker", "Diuretic", "LifestyleModification"],
        "CoronaryArteryDisease": ["Statin", "Antiplatelet", "BetaBlocker", "Nitroglycerin", "Angioplasty", "CABG"],
        "Angina": ["Nitroglycerin", "BetaBlocker", "CalciumChannelBlocker"],
        "AtrialFibrillation": ["Anticoagulant", "BetaBlocker", "CalciumChannelBlocker"],
        "Stroke": ["Thrombolytic", "Anticoagulant", "Antiplatelet"],
        "Type1Diabetes": ["Insulin"],
        "Type2Diabetes": ["Metformin", "Insulin", "LifestyleModification"],
        "Hyperlipidemia": ["Statin", "LifestyleModification"],
        "Obesity": ["LifestyleModification"],
        "Atherosclerosis": ["Statin", "Antiplatelet", "LifestyleModification"],
    }
    for disease, treatment_list in disease_treatments.items():
        for treatment in treatment_list:
            g.add((MED[disease], MED.treatedBy, MED[treatment]))

    # ──────────────────────────────────────────
    # Disease → Diagnostic Test Relations (diagnosedBy)
    # ──────────────────────────────────────────
    disease_diagnostics = {
        "Hypertension": ["BloodPressureTest"],
        "MyocardialInfarction": ["ECG", "CardiacCatheterization"],
        "HeartFailure": ["Echocardiogram", "ECG"],
        "CoronaryArteryDisease": ["StressTest", "CardiacCatheterization", "CTAngiography"],
        "AtrialFibrillation": ["ECG"],
        "Stroke": ["CTAngiography"],
        "DiabetesMellitus": ["FastingGlucose", "HbA1c"],
        "Hyperlipidemia": ["LipidPanel"],
        "Obesity": ["BMI"],
    }
    for disease, test_list in disease_diagnostics.items():
        for test in test_list:
            g.add((MED[disease], MED.diagnosedBy, MED[test]))

    # ──────────────────────────────────────────
    # Related Conditions
    # ──────────────────────────────────────────
    related = [
        ("Hypertension", "CoronaryArteryDisease"),
        ("Hypertension", "Stroke"),
        ("Hypertension", "HeartFailure"),
        ("DiabetesMellitus", "CardiovascularDisease"),
        ("Obesity", "Type2Diabetes"),
        ("Obesity", "Hypertension"),
        ("Hyperlipidemia", "Atherosclerosis"),
        ("Atherosclerosis", "CoronaryArteryDisease"),
        ("Atherosclerosis", "PeripheralArteryDisease"),
        ("MetabolicSyndrome", "Type2Diabetes"),
        ("MetabolicSyndrome", "Hypertension"),
        ("MetabolicSyndrome", "Hyperlipidemia"),
    ]
    for disease_a, disease_b in related:
        g.add((MED[disease_a], MED.relatedCondition, MED[disease_b]))

    return g


def save_ontology(graph: Graph | None = None) -> None:
    """Build (if needed) and save the ontology to the configured Turtle file."""
    if graph is None:
        graph = build_ontology()

    ONTOLOGY_DIR.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=str(ONTOLOGY_FILE), format="turtle")
    print(f"Ontology saved to {ONTOLOGY_FILE}")
    print(f"  Triples: {len(graph)}")


def load_ontology() -> Graph:
    """Load the ontology from the saved Turtle file."""
    g = Graph()
    g.parse(str(ONTOLOGY_FILE), format="turtle")
    return g


def _add_subclass(g: Graph, child_id: str, parent_id: str, label: str) -> None:
    """Helper to add a subclass with label to the graph."""
    g.add((MED[child_id], RDF.type, OWL.Class))
    g.add((MED[child_id], RDFS.subClassOf, MED[parent_id]))
    g.add((MED[child_id], RDFS.label, Literal(label)))


if __name__ == "__main__":
    save_ontology()
