"""Build the OntoGate ontology from standard, citable public sources.

Sources
-------
1. MeSH (Medical Subject Headings), U.S. National Library of Medicine.
   - Descriptor labels, entry terms (synonyms), and tree-number hierarchy.
   - https://www.nlm.nih.gov/mesh/
2. Hetionet v1.0 (Himmelstein et al., eLife 2017), CC0.
   - Clinical relations: treats, palliates, presents, resembles,
     localizes, causes side effect.
   - https://het.io/

Outputs
-------
data/ontogate/ontology.ttl              merged OWL/Turtle graph
data/ontogate/label_index.json          normalized label -> node URIs
data/ontogate/ontology_provenance.json  sources, versions, licenses, counts

No synthetic ontology content is produced: every node and edge is copied
from one of the two sources above.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

from rdflib import Graph, Literal, Namespace, RDF, RDFS, OWL
from rdflib.namespace import DCTERMS, SKOS, XSD

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "ontogate"
RAW_DIR = OUT_DIR / "raw"

MESH_DESC_URL = (
    "https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc2026.xml"
)
HETIONET_NODES_URL = (
    "https://raw.githubusercontent.com/hetio/hetionet/main/hetnet/tsv/"
    "hetionet-v1.0-nodes.tsv"
)
HETIONET_EDGES_URL = (
    "https://media.githubusercontent.com/media/hetio/hetionet/main/hetnet/tsv/"
    "hetionet-v1.0-edges.sif.gz"
)

MESH = Namespace("https://id.nlm.nih.gov/mesh/")
HETIO = Namespace("https://het.io/")
OG = Namespace("https://ontogate.org/ontology/")
MESHV = Namespace("https://id.nlm.nih.gov/mesh/vocab#")

HETIONET_RELATIONS = {
    "CtD": ("treats", "treatedBy", "Compound", "Disease"),
    "CpD": ("palliates", "palliatedBy", "Compound", "Disease"),
    "DpS": ("presents", "hasSymptom", "Disease", "Symptom"),
    "DrD": ("resembles", "resembles", "Disease", "Disease"),
    "DlA": ("localizes", "localizedIn", "Disease", "Anatomy"),
    "CcSE": ("causesSideEffect", "sideEffectOf", "Compound", "Side Effect"),
}

# MeSH tree-number top-level letters -> coarse entity kind.
MESH_KIND_BY_TREE_LETTER = {
    "A": "Anatomy",
    "B": "Organism",
    "C": "Disease",
    "D": "Chemical",
    "E": "Technique",
    "F": "Psychiatry",
    "G": "Phenomenon",
    "H": "Discipline",
    "I": "Occupation",
    "J": "Technology",
    "K": "Humanities",
    "L": "Information Science",
    "M": "Named Group",
    "N": "Health Care",
    "V": "Publication Type",
    "Z": "Geography",
}


def normalize_label(text: str) -> str:
    """Lowercase, strip accents/punctuation, and collapse whitespace."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def label_variants(label: str) -> set[str]:
    """Normalized label plus a crude singular form for matching."""
    base = normalize_label(label)
    variants = {base}
    if base.endswith("ies") and len(base) > 4:
        variants.add(base[:-3] + "y")
    if base.endswith("es") and len(base) > 4:
        variants.add(base[:-2])
    if base.endswith("s") and len(base) > 3:
        variants.add(base[:-1])
    return {v for v in variants if v}


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[skip] {dest.name} already present ({dest.stat().st_size / 1e6:.1f} MB)")
        return
    print(f"[get ] {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "OntoGate/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as fh:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
    tmp.replace(dest)
    print(f"[ok  ] {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def iter_children(elem: ET.Element, name: str):
    for child in elem:
        if local_name(child.tag) == name:
            yield child


def first_text(elem: ET.Element, *path: str) -> str:
    cur = elem
    for name in path:
        found = next(iter_children(cur, name), None)
        if found is None:
            return ""
        cur = found
    return (cur.text or "").strip()


def parse_mesh(xml_path: Path) -> list[dict]:
    """Stream descriptors out of the official MeSH XML file."""
    records: list[dict] = []
    for _, elem in ET.iterparse(xml_path, events=("end",)):
        if local_name(elem.tag) != "DescriptorRecord":
            continue
        ui = first_text(elem, "DescriptorUI")
        name = first_text(elem, "DescriptorName", "String")
        if not ui or not name:
            elem.clear()
            continue

        tree_numbers = [
            (tn.text or "").strip()
            for tn in elem.iter()
            if local_name(tn.tag) == "TreeNumber" and (tn.text or "").strip()
        ]

        synonyms: list[str] = []
        for concept in elem.iter():
            if local_name(concept.tag) != "Concept":
                continue
            preferred = concept.attrib.get("PreferredConceptYN", "N") == "Y"
            for term in concept.iter():
                if local_name(term.tag) == "Term":
                    string = next(
                        (c for c in term if local_name(c.tag) == "String"), None
                    )
                    if string is not None and string.text:
                        synonyms.append(string.text.strip())
            if preferred:
                break

        records.append(
            {
                "ui": ui,
                "label": name,
                "tree_numbers": tree_numbers,
                "synonyms": synonyms,
            }
        )
        elem.clear()
        if len(records) % 5000 == 0:
            print(f"  parsed {len(records)} descriptors ...", flush=True)
    return records


def build_mesh_graph(g: Graph, records: list[dict]) -> dict:
    tree_to_uri: dict[str, "URIRef"] = {}
    for rec in records:
        uri = MESH[rec["ui"]]
        letter = (rec["tree_numbers"][0][:1] if rec["tree_numbers"] else "").upper()
        kind = MESH_KIND_BY_TREE_LETTER.get(letter, "Concept")
        kind_uri = OG[re.sub(r"[^A-Za-z0-9]+", "", kind)]
        g.add((uri, RDF.type, OWL.Class))
        g.add((uri, RDF.type, kind_uri))
        g.add((uri, RDFS.label, Literal(rec["label"], lang="en")))
        for tn in rec["tree_numbers"]:
            tree_to_uri.setdefault(tn, uri)
            g.add((uri, MESHV.treeNumber, Literal(tn)))

        seen = {normalize_label(rec["label"])}
        for syn in rec["synonyms"]:
            norm = normalize_label(syn)
            if norm and norm not in seen:
                g.add((uri, SKOS.altLabel, Literal(syn, lang="en")))
                seen.add(norm)
    return tree_to_uri


def add_mesh_hierarchy(g: Graph, tree_to_uri: dict[str, "URIRef"]) -> int:
    """Link each tree number to its nearest existing ancestor descriptor."""
    by_length = sorted(tree_to_uri, key=len)
    existing = set(by_length)
    edges = 0
    for tn in by_length:
        parts = tn.split(".")
        parent = None
        for cut in range(len(parts) - 1, 0, -1):
            candidate = ".".join(parts[:cut])
            if candidate in existing:
                parent = candidate
                break
        if parent and tree_to_uri[parent] != tree_to_uri[tn]:
            child, ancestor = tree_to_uri[tn], tree_to_uri[parent]
            g.add((child, RDFS.subClassOf, ancestor))
            g.add((ancestor, OG.hasSubclass, child))
            edges += 1
    return edges


def write_graph_cache(g: Graph, dest: Path) -> dict:
    """Write a compact adjacency cache for fast startup (no RDF parsing)."""
    import pickle

    relation_uris = {
        RDFS.subClassOf: "subClassOf",
        OG.hasSubclass: "hasSubclass",
        OG.treats: "treats",
        OG.treatedBy: "treatedBy",
        OG.palliates: "palliates",
        OG.palliatedBy: "palliatedBy",
        OG.presents: "presents",
        OG.hasSymptom: "hasSymptom",
        OG.resembles: "resembles",
        OG.localizes: "localizes",
        OG.localizedIn: "localizedIn",
        OG.causesSideEffect: "causesSideEffect",
        OG.sideEffectOf: "sideEffectOf",
    }
    kind_uris = {
        OG.Disease: "Disease",
        OG.Compound: "Compound",
        OG.Symptom: "Symptom",
        OG.SideEffect: "Side Effect",
        OG.Anatomy: "Anatomy",
        OG.Chemical: "Chemical",
        OG.Technique: "Technique",
        OG.Concept: "Concept",
    }

    nodes: dict[str, dict] = {}
    for subj, _, label in g.triples((None, RDFS.label, None)):
        nodes.setdefault(str(subj), {"label": str(label), "kind": "Concept", "aliases": []})
    for subj, _, alias in g.triples((None, SKOS.altLabel, None)):
        if str(subj) in nodes and str(alias) != nodes[str(subj)]["label"]:
            nodes[str(subj)]["aliases"].append(str(alias))
    for subj, _, kind_uri in g.triples((None, RDF.type, None)):
        if kind_uri in kind_uris:
            nodes.setdefault(str(subj), {"label": "", "kind": "Concept", "aliases": []})
            priority = {
                "Disease": 0,
                "Compound": 1,
                "Symptom": 2,
                "Anatomy": 3,
                "Chemical": 4,
                "Technique": 5,
                "Side Effect": 6,
                "Concept": 7,
            }
            current = nodes[str(subj)]["kind"]
            if priority[kind_uris[kind_uri]] < priority.get(current, 9):
                nodes[str(subj)]["kind"] = kind_uris[kind_uri]

    edges: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    seen = set()
    for subj, pred, obj in g.triples((None, None, None)):
        rel = relation_uris.get(pred)
        if rel is None:
            continue
        key = (str(subj), rel, str(obj))
        if key in seen:
            continue
        seen.add(key)
        edges[str(subj)][rel].append(str(obj))

    payload = {"nodes": nodes, "edges": {k: dict(v) for k, v in edges.items()}}
    with open(dest, "wb") as fh:
        pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
    return {"nodes": len(nodes), "edge_sources": len(edges)}


def read_hetionet_nodes(path: Path) -> dict[str, dict]:
    nodes: dict[str, dict] = {}
    with open(path, encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        idx = {name: i for i, name in enumerate(header)}
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            node_id = parts[idx["id"]]
            nodes[node_id] = {
                "name": parts[idx["name"]],
                "kind": parts[idx["kind"]],
            }
    return nodes


def add_hetionet(
    g: Graph,
    nodes: dict[str, dict],
    edges_path: Path,
    label_to_uri: dict[str, "URIRef"],
) -> dict:
    kind_uris = {
        "Disease": OG.Disease,
        "Compound": OG.Compound,
        "Symptom": OG.Symptom,
        "Side Effect": OG.SideEffect,
        "Anatomy": OG.Anatomy,
    }
    node_uri: dict[str, "URIRef"] = {}
    for node_id, info in nodes.items():
        kind = info["kind"]
        if kind not in kind_uris:
            continue
        label = info["name"]
        norm = normalize_label(label)
        uri = label_to_uri.get(norm, HETIO[quote(node_id, safe="")])
        node_uri[node_id] = uri
        if (uri, RDF.type, OWL.Class) not in g:
            g.add((uri, RDF.type, OWL.Class))
            g.add((uri, RDFS.label, Literal(label, lang="en")))
        g.add((uri, RDF.type, kind_uris[kind]))
        label_to_uri.setdefault(norm, uri)

    counts: dict[str, int] = defaultdict(int)
    with gzip.open(edges_path, "rt", encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue
            source_id, metaedge, target_id = parts
            if metaedge not in HETIONET_RELATIONS:
                continue
            forward, inverse, source_kind, target_kind = HETIONET_RELATIONS[metaedge]
            if nodes.get(source_id, {}).get("kind") != source_kind:
                continue
            if nodes.get(target_id, {}).get("kind") != target_kind:
                continue
            s_uri, t_uri = node_uri.get(source_id), node_uri.get(target_id)
            if s_uri is None or t_uri is None:
                continue
            g.add((s_uri, OG[forward], t_uri))
            g.add((t_uri, OG[inverse], s_uri))
            counts[forward] += 1
    return dict(counts)


def write_label_index(g: Graph, dest: Path) -> dict:
    index: dict[str, list[str]] = defaultdict(list)
    labels: dict[str, str] = {}
    for subj, pred, obj in g.triples((None, RDFS.label, None)):
        norm = normalize_label(str(obj))
        if norm:
            index[norm].append(str(subj))
            labels.setdefault(norm, str(obj))
    for subj, pred, obj in g.triples((None, SKOS.altLabel, None)):
        norm = normalize_label(str(obj))
        if norm:
            index[norm].append(str(subj))
            labels.setdefault(norm, str(obj))
    payload = {
        "labels": {k: labels.get(k, k) for k in index},
        "uris": {k: sorted(set(v)) for k, v in index.items()},
    }
    dest.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh-xml", type=Path, default=RAW_DIR / "desc2026.xml")
    parser.add_argument("--hetionet-nodes", type=Path, default=RAW_DIR / "hetionet_nodes.tsv")
    parser.add_argument("--hetionet-edges", type=Path, default=RAW_DIR / "hetionet_edges.sif.gz")
    parser.add_argument("--out", type=Path, default=OUT_DIR / "ontology.ttl")
    parser.add_argument(
        "--from-ttl",
        action="store_true",
        help="Rebuild the label index and graph cache from an existing TTL "
        "without downloading the raw sources.",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.from_ttl:
        if not args.out.exists():
            raise SystemExit(f"Cannot rebuild from missing TTL: {args.out}")
        print(f"[ttl] loading {args.out}")
        g = Graph()
        g.parse(str(args.out), format="turtle")
        index = write_label_index(g, OUT_DIR / "label_index.json")
        cache_stats = write_graph_cache(g, OUT_DIR / "graph.pkl")
        print(f"[write] label index: {len(index['uris'])} labels")
        print(f"[write] graph cache: {cache_stats}")
        return 0

    download(MESH_DESC_URL, args.mesh_xml)
    download(HETIONET_NODES_URL, args.hetionet_nodes)
    download(HETIONET_EDGES_URL, args.hetionet_edges)

    print("[mesh] parsing descriptors ...", flush=True)
    records = parse_mesh(args.mesh_xml)
    print(f"[mesh] {len(records)} descriptors")

    g = Graph()
    g.bind("mesh", MESH)
    g.bind("meshv", MESHV)
    g.bind("hetio", HETIO)
    g.bind("og", OG)
    g.bind("skos", SKOS)
    g.bind("dcterms", DCTERMS)

    dataset_uri = OG["ontogate_ontology"]
    g.add((dataset_uri, RDF.type, OWL.Ontology))
    g.add((dataset_uri, DCTERMS.title, Literal("OntoGate biomedical ontology")))
    g.add(
        (
            dataset_uri,
            DCTERMS.description,
            Literal(
                "MeSH descriptor hierarchy and synonyms merged with Hetionet "
                "clinical relations. Built only from public, citable sources."
            ),
        )
    )
    g.add((dataset_uri, DCTERMS.source, Literal("MeSH 2026, U.S. National Library of Medicine")))
    g.add((dataset_uri, DCTERMS.source, Literal("Hetionet v1.0, https://het.io/")))
    g.add((dataset_uri, DCTERMS.license, Literal("MeSH: public domain (U.S. Government work); Hetionet: CC0 1.0")))
    g.add((dataset_uri, OWL.versionInfo, Literal("2026.1")))

    tree_to_uri = build_mesh_graph(g, records)
    hierarchy_edges = add_mesh_hierarchy(g, tree_to_uri)
    print(f"[mesh] hierarchy edges: {hierarchy_edges}")

    label_to_uri: dict[str, "URIRef"] = {}
    for rec in records:
        norm = normalize_label(rec["label"])
        label_to_uri.setdefault(norm, MESH[rec["ui"]])

    print("[hetionet] loading nodes ...", flush=True)
    het_nodes = read_hetionet_nodes(args.hetionet_nodes)
    relation_counts = add_hetionet(g, het_nodes, args.hetionet_edges, label_to_uri)
    print(f"[hetionet] relation edges: {relation_counts}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(args.out), format="turtle")
    print(f"[write] {args.out} ({args.out.stat().st_size / 1e6:.1f} MB, {len(g)} triples)")

    index = write_label_index(g, OUT_DIR / "label_index.json")
    print(f"[write] label index: {len(index['uris'])} normalized labels")
    cache_stats = write_graph_cache(g, OUT_DIR / "graph.pkl")
    print(f"[write] graph cache: {cache_stats}")

    provenance = {
        "built_from": [
            {
                "name": "MeSH 2026",
                "url": MESH_DESC_URL,
                "publisher": "U.S. National Library of Medicine",
                "license": "Public domain (U.S. Government work)",
                "descriptors": len(records),
                "hierarchy_edges": hierarchy_edges,
            },
            {
                "name": "Hetionet v1.0",
                "url": "https://het.io/",
                "citation": (
                    "Himmelstein DS et al. Systematic integration of biomedical "
                    "knowledge prioritizes drugs for repurposing. eLife 2017;6:e26726."
                ),
                "license": "CC0 1.0",
                "relation_edges": relation_counts,
            },
        ],
        "triples": len(g),
        "normalized_labels": len(index["uris"]),
        "graph_cache": cache_stats,
        "output": str(args.out.relative_to(ROOT)),
    }
    (OUT_DIR / "ontology_provenance.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )
    print("[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
