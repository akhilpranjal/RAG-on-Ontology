"""Configuration for OntoGate-RAG (Experiment 3) on PubMedQA."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Data assets
DATA_DIR = PROJECT_ROOT / "data"
PUBMEDQA_DIR = DATA_DIR / "pubmedqa"
ONTOLOGY_RAW_DIR = DATA_DIR / "ontogate" / "raw"
ONTOGATE_DIR = DATA_DIR / "ontogate"
ONTOLOGY_PATH = ONTOGATE_DIR / "ontology.ttl"
LABEL_INDEX_PATH = ONTOGATE_DIR / "label_index.json"
GRAPH_CACHE_PATH = ONTOGATE_DIR / "graph.pkl"
MESH_TREES_PATH = ONTOGATE_DIR / "mesh_trees.json"
PASSAGE_CONCEPTS_PATH = ONTOGATE_DIR / "passage_concepts.json"
SPECIALTY_PATH = PUBMEDQA_DIR / "specialties.json"
INDEX_DIR = DATA_DIR / "index"

RESULTS_DIR = PROJECT_ROOT / "results"
METRICS_DIR = RESULTS_DIR / "metrics"
PLOTS_DIR = RESULTS_DIR / "plots"
RUNS_DIR = RESULTS_DIR / "runs"
CACHE_DIR = DATA_DIR / "cache"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Retrieval
RETRIEVER_BACKEND = "st"  # "st" (sentence-transformers) or "medcpt"
ST_MODEL = "multi-qa-MiniLM-L6-cos-v1"
RETRIEVER_MODEL = "ncbi/MedCPT-Query-Encoder"
PASSAGE_MODEL = "ncbi/MedCPT-Article-Encoder"
TOP_K = 10

# Generation
# gemini-3.5-flash-lite is the historical judge model but its free-tier daily
# quota is easily exhausted; gemini-3.1-flash-lite has a separate free bucket
# and supports thinking_budget=0. Keep this constant in sync with any report.
GENERATOR_MODEL = "gemini-3.1-flash-lite"
GENERATOR_TEMPERATURE = 0.0
GENERATION_PER_MINUTE = 10
MAX_GENERATION_RETRIES = 6

# Dataset
PUBMEDQA_DATASET = "qiaojin/PubMedQA"
DEV_SIZE = 500
TEST_SIZE = 500
SPLIT_SEED = 42
LABEL_NAMES = ["yes", "no", "maybe"]
ABSTAIN_LABEL = "maybe"
ALPHA = 0.05

# Ontology reasoning
MAX_EXPANSION_TERMS = 8
ONTOLOGY_DEPTH = 2


def ensure_directories() -> None:
    for directory in [PUBMEDQA_DIR, ONTOGATE_DIR, INDEX_DIR, METRICS_DIR, PLOTS_DIR, RUNS_DIR, CACHE_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def configure_cpu() -> None:
    """Use every available CPU core for local transformer inference."""
    import torch

    torch.set_num_threads(max(1, os.cpu_count() or 1))
