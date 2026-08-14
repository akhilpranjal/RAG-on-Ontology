"""PubMed abstract downloader using NCBI E-utilities.

Downloads medical abstracts for specified MeSH terms and saves
them as structured JSON files for the corpus.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests
from tqdm import tqdm

from src.config import REAL_CORPUS_DIR, ensure_directories


# NCBI E-utilities base URLs
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# MeSH terms for Cardiovascular + Metabolic domain
DEFAULT_MESH_TERMS = [
    "Hypertension",
    "Myocardial Infarction",
    "Heart Failure",
    "Coronary Artery Disease",
    "Atrial Fibrillation",
    "Stroke",
    "Atherosclerosis",
    "Diabetes Mellitus",
    "Diabetes Mellitus, Type 2",
    "Obesity",
    "Hyperlipidemia",
    "Metabolic Syndrome",
    "ACE Inhibitors",
    "Statins",
    "Metformin",
    "Peripheral Arterial Disease",
    # Expansion terms (wider coverage for corpus growth)
    "Acute Coronary Syndrome",
    "Angina Pectoris",
    "Arrhythmias, Cardiac",
    "Cardiomyopathies",
    "Congestive Heart Failure",
    "Diabetic Nephropathies",
    "Diabetic Retinopathy",
    "Dyslipidemias",
    "Hyperglycemia",
    "Insulin Resistance",
    "Ischemic Stroke",
    "Prediabetic State",
    "Ventricular Fibrillation",
]

# Titles / patterns that indicate unusable placeholder records.
JUNK_TITLE_PATTERNS = [
    "[not available]",
    "pediatric.",
    "retracted",
    "erratum",
]


def search_pubmed(mesh_term: str, max_results: int = 5) -> list[str]:
    """Search PubMed for articles by MeSH term.

    Args:
        mesh_term: The MeSH term to search for.
        max_results: Maximum number of PMIDs to return.

    Returns:
        List of PMID strings.
    """
    params = {
        "db": "pubmed",
        "term": f"{mesh_term}[MeSH Terms]",
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
    }

    response = requests.get(ESEARCH_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    return data.get("esearchresult", {}).get("idlist", [])


def fetch_abstracts(pmids: list[str]) -> list[dict]:
    """Fetch abstracts for a list of PMIDs.

    Args:
        pmids: List of PubMed IDs.

    Returns:
        List of dicts with doc_id, title, text, source, url.
    """
    if not pmids:
        return []

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "xml",
        "retmode": "xml",
    }

    response = requests.get(EFETCH_URL, params=params, timeout=60)
    response.raise_for_status()

    # Simple XML parsing (avoiding heavy lxml dependency)
    articles = _parse_pubmed_xml(response.text)
    return articles


def _is_junk_title(title: str) -> bool:
    """Return True if a title looks like a placeholder / unusable record."""
    title_lower = (title or "").lower().strip()
    return any(pat in title_lower for pat in JUNK_TITLE_PATTERNS)


def _parse_pubmed_xml(xml_text: str) -> list[dict]:
    """Parse PubMed XML response to extract articles.

    Uses xml.etree for lightweight XML parsing. Joins structured abstract
    sections (Background / Methods / Results / Conclusions) into one text.
    """
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_text)
    articles = []

    for article in root.findall(".//PubmedArticle"):
        pmid_elem = article.find(".//PMID")
        title_elem = article.find(".//ArticleTitle")
        abstract_texts = article.findall(".//Abstract/AbstractText")

        if pmid_elem is None or not abstract_texts:
            continue

        pmid = pmid_elem.text or ""
        title = title_elem.text if title_elem is not None else ""
        abstract = " ".join(
            (t.text or "") for t in abstract_texts
        ).strip()

        if not abstract or len(abstract) < 150 or _is_junk_title(title):
            continue

        articles.append({
            "doc_id": f"pubmed_{pmid}",
            "title": title or "",
            "text": abstract,
            "source": "PubMed",
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "concepts": [],  # Filled by annotate_corpus.py
        })

    return articles


def download_corpus(
    mesh_terms: list[str] | None = None,
    abstracts_per_term: int = 3,
    output_dir: Path | None = None,
) -> int:
    """Download PubMed abstracts for a list of MeSH terms.

    Args:
        mesh_terms: List of MeSH terms to search. Defaults to cardiovascular/metabolic terms.
        abstracts_per_term: Number of abstracts to download per term.
        output_dir: Directory to save JSON files. Defaults to config.

    Returns:
        Total number of abstracts downloaded.
    """
    ensure_directories()

    if mesh_terms is None:
        mesh_terms = DEFAULT_MESH_TERMS
    if output_dir is None:
        output_dir = REAL_CORPUS_DIR

    total_downloaded = 0
    seen_pmids = set()
    # Skip PMIDs already saved on disk so re-runs only add genuinely new docs.
    existing_pmids = {f.stem.replace("pubmed_", "") for f in output_dir.glob("pubmed_*.json")}

    for term in tqdm(mesh_terms, desc="Downloading PubMed abstracts"):
        pmids = search_pubmed(term, max_results=abstracts_per_term)

        # Filter out already-downloaded PMIDs (both this run and on disk)
        new_pmids = [p for p in pmids if p not in seen_pmids and p not in existing_pmids]
        if not new_pmids:
            continue

        articles = fetch_abstracts(new_pmids)

        for article in articles:
            pmid = article["doc_id"].replace("pubmed_", "")
            seen_pmids.add(pmid)

            filepath = output_dir / f"{article['doc_id']}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(article, f, indent=2, ensure_ascii=False)

            total_downloaded += 1

        # Be polite to NCBI servers
        time.sleep(0.5)

    print(f"\nDownloaded {total_downloaded} PubMed abstracts to {output_dir}")
    return total_downloaded


if __name__ == "__main__":
    download_corpus()
