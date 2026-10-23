"""MeSH tree-based specialty tagging.

PubMedQA records carry the source article's MeSH headings. MeSH descriptors
carry tree numbers (``C04.588.180`` etc.) in ``desc2026.xml``. Mapping a
question's headings to top-level tree codes yields a coarse specialty label
(C04 = Neoplasms, C10 = Nervous System Diseases, C14 = Cardiovascular
Diseases, ...).

The tag is used *only* for the per-specialty analysis of the results. It never
enters the retrieval or gating logic, so it cannot leak into any decision.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from evidence_gate.config import MESH_TREES_PATH, ONTOGATE_DIR, ONTOLOGY_RAW_DIR

TOP_LEVEL_NAMES = {
    "A": "Anatomy",
    "B": "Organisms",
    "C": "Diseases",
    "D": "Chemicals and Drugs",
    "E": "Analytical/Diagnostic/Therapeutic Techniques",
    "F": "Psychiatry and Psychology",
    "G": "Phenomena and Processes",
    "H": "Disciplines and Occupations",
    "I": "Anthropology/Education/Sociology",
    "J": "Technology, Industry, Agriculture",
    "K": "Humanities",
    "L": "Information Science",
    "M": "Named Groups",
    "N": "Health Care",
    "V": "Publication Characteristics",
    "Z": "Geographicals",
}

DISEASE_LETTER = "C"

# Specific names for the disease top-level codes, taken from the MeSH 2026
# tree itself (the descriptor whose tree number is exactly the code).
DISEASE_CODE_NAMES = {
    "C01": "Infections",
    "C02": "Parasitic Diseases",
    "C03": "Skin and Connective Tissue Diseases",
    "C04": "Neoplasms",
    "C05": "Musculoskeletal Diseases",
    "C06": "Digestive System Diseases",
    "C07": "Stomatognathic Diseases",
    "C08": "Respiratory Tract Diseases",
    "C09": "Otorhinolaryngologic Diseases",
    "C10": "Nervous System Diseases",
    "C11": "Eye Diseases",
    "C12": "Urogenital Diseases",
    "C13": "Male Urogenital Diseases",
    "C14": "Cardiovascular Diseases",
    "C15": "Hemic and Lymphatic Diseases",
    "C16": "Congenital, Hereditary, and Neonatal Diseases",
    "C17": "Skin and Connective Tissue Diseases",
    "C18": "Nutritional and Metabolic Diseases",
    "C19": "Endocrine Diseases",
    "C20": "Immune System Diseases",
    "C21": "Disorders of Environmental Origin",
    "C22": "Animal Diseases",
    "C23": "Pathological Conditions, Signs and Symptoms",
    "C24": "Occupational Diseases",
    "C25": "Chemically-Induced Disorders",
    "C26": "Wounds and Injuries",
}


def normalize_term(text: str) -> str:
    return " ".join(text.strip().lower().split())


def build_tree_index(
    xml_path: Path | str = ONTOLOGY_RAW_DIR / "desc2026.xml",
    cache_path: Path | str = MESH_TREES_PATH,
) -> dict[str, list[str]]:
    """Parse ``desc2026.xml`` into ``{normalized descriptor name: [tree numbers]}``."""
    xml_path = Path(xml_path)
    if not xml_path.exists():
        raise FileNotFoundError(
            f"MeSH descriptor file not found: {xml_path}\n"
            "Run: uv run python scripts/eg_build_ontology.py"
        )
    index: dict[str, list[str]] = defaultdict(list)
    for _, element in ET.iterparse(str(xml_path), events=("end",)):
        if element.tag != "DescriptorRecord":
            continue
        name_el = element.find("DescriptorName/String")
        if name_el is not None and name_el.text:
            trees = [
                t.text.strip()
                for t in element.findall("TreeNumberList/TreeNumber")
                if t.text and t.text.strip()
            ]
            if trees:
                index[normalize_term(name_el.text)].extend(trees)
        element.clear()
    payload = {k: sorted(set(v)) for k, v in index.items()}
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def load_tree_index(cache_path: Path | str = MESH_TREES_PATH) -> dict[str, list[str]]:
    cache_path = Path(cache_path)
    if not cache_path.exists():
        return build_tree_index(cache_path=cache_path)
    return json.loads(cache_path.read_text(encoding="utf-8"))


def top_level_codes(term: str, index: dict[str, list[str]]) -> list[str]:
    """Top-level MeSH tree codes of a heading (``C04.588`` -> ``C04``)."""
    codes = []
    for tree in index.get(normalize_term(term), ()):
        code = tree.split(".")[0]
        if code and code not in codes:
            codes.append(code)
    return codes


def classify(terms: list[str], index: dict[str, list[str]]) -> dict:
    """Specialty label for one question given its MeSH headings."""
    counter: Counter[str] = Counter()
    for term in terms:
        for code in top_level_codes(term, index):
            counter[code] += 1
    disease_codes = {
        code: count
        for code, count in counter.items()
        if code[:1] == DISEASE_LETTER
    }
    pool = disease_codes or counter
    primary = sorted(pool, key=lambda c: (-pool[c], c))[0] if pool else None
    return {
        "categories": sorted(counter),
        "category_counts": dict(sorted(counter.items())),
        "disease_categories": sorted(disease_codes),
        "primary_category": primary,
        "primary_category_name": DISEASE_CODE_NAMES.get(primary)
        or TOP_LEVEL_NAMES.get((primary or "")[:1], "Unknown"),
    }


def build_specialties(labeled_path: Path | str = None, out_path: Path | str = None) -> dict:
    """Write ``{pubid: specialty dict}`` for every labelled PubMedQA question."""
    from evidence_gate.config import PUBMEDQA_DIR

    labeled_path = Path(labeled_path or PUBMEDQA_DIR / "labeled.jsonl")
    out_path = Path(out_path or PUBMEDQA_DIR / "specialties.json")
    index = load_tree_index()
    rows = []
    with open(labeled_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    payload = {}
    for row in rows:
        payload[row["pubid"]] = classify(row.get("meshes") or [], index)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    data = build_specialties()
    counts = Counter(v["primary_category"] for v in data.values())
    print(f"tagged {len(data)} questions")
    for code, count in counts.most_common():
        name = DISEASE_CODE_NAMES.get(code) or TOP_LEVEL_NAMES.get(code[:1], "?")
        print(f"  {code} {name:48s} {count}")
