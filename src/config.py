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
GENERATOR_MODEL = "gemini-3.6-flash"
GENERATOR_TEMPERATURE = 0.0

# LLM Judge (cross-model evaluation)
# Judge uses a different Gemini family (3.1-flash-lite) than the generator
# (gemini-3.6-flash) to avoid self-judging. Older 2.x/2.5 models are no
# longer available to new users.
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
