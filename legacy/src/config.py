"""Configuration module for the RAG-on-Ontology project.

Centralizes all configuration: API keys, model settings, paths, and constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ──────────────────────────────────────────────
# Project Paths
# ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CORPUS_DIR = DATA_DIR / "corpus"
REAL_CORPUS_DIR = CORPUS_DIR / "real"
SYNTHETIC_CORPUS_DIR = CORPUS_DIR / "synthetic"
ONTOLOGY_DIR = DATA_DIR / "ontology"
SYNONYMS_DIR = DATA_DIR / "synonyms"
EVALUATION_DIR = DATA_DIR / "evaluation"
VECTORSTORE_DIR = DATA_DIR / "vectorstore"
RESULTS_DIR = PROJECT_ROOT / "results"
METRICS_DIR = RESULTS_DIR / "metrics"
PLOTS_DIR = RESULTS_DIR / "plots"
REASONING_LOGS_DIR = RESULTS_DIR / "reasoning_logs"

# ──────────────────────────────────────────────
# API Keys
# ──────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ──────────────────────────────────────────────
# Model Configuration
# ──────────────────────────────────────────────
EMBEDDING_MODEL = "gemini-embedding-2"
# Free-tier generation quota is ~20 req/day per model on the newer Flash
# models (gemini-3.5-flash, 3.6-flash, 3.5-flash-lite), which is far too
# small for a 66-query x 6-pipeline answer evaluation (~800 calls).
# gemini-3.1-flash-lite has a ~1000 req/day free budget, so both generation
# and judging use it (the judge rubric is model-independent and the concept
# coverage metric is objective, so this preserves the controlled comparison).
GENERATOR_MODEL = "gemini-3.1-flash-lite"
GENERATOR_TEMPERATURE = 0.0

# LLM Judge
# Uses the same model as the generator (gemini-3.1-flash-lite) because it is
# the only free-tier model with a large enough daily quota; the judge applies
# a separate rubric and is blinded to pipeline identity, and the primary
# answer metric (concept coverage) is objective (no LLM involved).
LLM_JUDGE_MODEL = "gemini-3.1-flash-lite"

# ──────────────────────────────────────────────
# Retrieval Configuration
# ──────────────────────────────────────────────
TOP_K_PRIMARY = 5
TOP_K_EXTENDED = 10
CHUNK_SIZE = 500       # characters per chunk
CHUNK_OVERLAP = 100    # overlap between chunks

# ──────────────────────────────────────────────
# Ontology Configuration
# ──────────────────────────────────────────────
ONTOLOGY_FILE = ONTOLOGY_DIR / "medical_ontology.ttl"
ONTOLOGY_NAMESPACE = "http://example.org/medical-ontology#"

# Relation types for traversal
ONTOLOGY_RELATIONS = {
    "equivalence": "owl:equivalentClass",
    "hierarchy": "rdfs:subClassOf",
    "has_symptom": "hasSymptom",
    "treated_by": "treatedBy",
    "diagnosed_by": "diagnosedBy",
    "related_condition": "relatedCondition",
}

# ──────────────────────────────────────────────
# Synonym Dictionary
# ──────────────────────────────────────────────
SYNONYM_DICT_FILE = SYNONYMS_DIR / "synonym_dict.json"

# ──────────────────────────────────────────────
# Evaluation Configuration
# ──────────────────────────────────────────────
QUERIES_FILE = EVALUATION_DIR / "queries.json"
RELEVANCE_JUDGMENTS_FILE = EVALUATION_DIR / "relevance_judgments.json"
ALPHA = 0.05  # significance level for statistical tests

# Query categories
QUERY_CATEGORIES = [
    "lay_terminology",
    "disease_hierarchy",
    "symptom_reasoning",
    "treatment_reasoning",
    "multi_hop",
    "control_exact_clinical",
]

# ──────────────────────────────────────────────
# ChromaDB Configuration
# ──────────────────────────────────────────────
CHROMA_COLLECTION_NAME = "medical_corpus"
CHROMA_PERSIST_DIR = str(VECTORSTORE_DIR)

# ──────────────────────────────────────────────
# Embedding Cache Configuration
# ──────────────────────────────────────────────
# Disk cache for computed embeddings, keyed by (model, task_type, text).
# Avoids re-burning API quota on repeated queries across runs.
EMBEDDING_CACHE_FILE = VECTORSTORE_DIR / "embedding_cache.json"


def ensure_directories():
    """Create all required project directories if they don't exist."""
    dirs = [
        REAL_CORPUS_DIR,
        SYNTHETIC_CORPUS_DIR,
        ONTOLOGY_DIR,
        SYNONYMS_DIR,
        EVALUATION_DIR,
        VECTORSTORE_DIR,
        METRICS_DIR,
        PLOTS_DIR,
        REASONING_LOGS_DIR,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
