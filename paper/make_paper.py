"""Build the project paper as a Word document.

Produces ``paper/OntoGate-RAG-paper.docx`` plus three figures under
``paper/figures``. Re-running overwrites the outputs.

    uv run --with python-docx --with matplotlib python paper/make_paper.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
PAPER_DIR = ROOT / "paper"
FIG_DIR = PAPER_DIR / "figures"

BODY_FONT = "Times New Roman"
BODY_SIZE = Pt(11)


# ----------------------------------------------------------------------
# Figures
# ----------------------------------------------------------------------
def _box(ax, x, y, w, h, text, fc, ec="#333333", fs=8.2, bold=False):
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2),
        w,
        h,
        boxstyle="round,pad=0.6,rounding_size=1.2",
        linewidth=1.0,
        edgecolor=ec,
        facecolor=fc,
        zorder=2,
    )
    ax.add_patch(patch)
    ax.text(
        x,
        y,
        text,
        ha="center",
        va="center",
        fontsize=fs,
        zorder=3,
        fontweight="bold" if bold else "normal",
        linespacing=1.35,
    )


def _arrow(ax, x1, y1, x2, y2, style="-|>", ls="-", color="#444444", lw=1.1):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle=style,
            mutation_scale=11,
            linewidth=lw,
            linestyle=ls,
            color=color,
            zorder=1,
            shrinkA=1,
            shrinkB=1,
        )
    )


def make_fig_architecture(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.0, 4.6), dpi=220)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    blue = "#DCE7F4"
    grey = "#EFEFEF"
    green = "#DFF0E2"

    ax.text(17, 97, "DATA AND ASSETS", fontsize=8, fontweight="bold", color="#555555")
    ax.text(65, 97, "PIPELINE", fontsize=8, fontweight="bold", color="#555555")

    _box(ax, 17, 84, 26, 13, "PubMedQA\n1,000 labelled questions\n3,000 abstracts", grey)
    _box(ax, 17, 66, 26, 13, "MeSH 2026 + Hetionet\n31,110 terms · 147,591 edges", grey)
    _box(ax, 17, 48, 26, 13, "Response cache\n(prompt-keyed JSON)", grey)

    _box(ax, 65, 84, 32, 12, "1. Dense retrieval (FAISS)\ntop-10 abstracts", blue)
    _box(ax, 65, 68, 32, 12, "2. Ontology linking\nconcept sets + coverage", blue)
    _box(ax, 65, 52, 32, 12, "3. LLM evidence judge\none call per question", blue)
    _box(ax, 65, 36, 32, 12, "4. Gate\njudge score + is-maybe", blue)
    _box(ax, 65, 20, 32, 12, "Answer (yes / no)\nor abstain", green)

    for y1, y2 in [(78, 74), (62, 58), (46, 42), (30, 26)]:
        _arrow(ax, 65, y1, 65, y2)

    _arrow(ax, 30, 84, 49, 84)
    _arrow(ax, 30, 66, 49, 68)
    _arrow(ax, 30, 48, 49, 52, ls="--")

    ax.text(39.5, 87.6, "questions", fontsize=7.4, color="#555555", ha="center")
    ax.text(39.5, 69.6, "concepts", fontsize=7.4, color="#555555", ha="center")
    ax.text(39.5, 51.6, "cached output", fontsize=7.4, color="#555555", ha="center")

    ax.text(
        65,
        8.5,
        "One paid call per question; the ontology pre-screen can skip it entirely.",
        ha="center",
        fontsize=7.6,
        style="italic",
        color="#444444",
    )
    fig.tight_layout(pad=0.2)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def make_fig_workflow(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.0, 5.5), dpi=220)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    blue = "#DCE7F4"
    grey = "#EFEFEF"
    red = "#F6E2DE"
    green = "#DFF0E2"

    cx = 42
    _box(ax, cx, 94, 28, 8, "Question", grey, bold=True)
    _box(ax, cx, 81, 40, 9, "Retrieve 10 abstracts\n(dense index, no API call)", blue)
    _box(ax, cx, 67, 40, 10, "Link question and abstracts to\nMeSH / Hetionet concepts", blue)
    _box(ax, cx, 53, 38, 9, "Coverage at or below\nscreen threshold?", "#FFF6D9")

    _box(ax, 86, 53, 24, 9, "ABSTAIN\nzero API calls", red)

    _box(ax, cx, 39, 40, 9, "LLM judge (one call):\nsufficient? yes / partial / no", blue)
    _box(ax, cx, 25, 40, 9, "sufficient = yes and\nanswer is not 'maybe'?", "#FFF6D9")

    _box(ax, 86, 25, 24, 9, "ABSTAIN\ninsufficient evidence", red)
    _box(ax, cx, 10, 26, 9, "ANSWER yes / no", green)

    for y1, y2 in [(90, 85.5), (76.5, 72), (62, 57.5), (48.5, 43.5), (34.5, 29.5), (20.5, 14.5)]:
        _arrow(ax, cx, y1, cx, y2)

    _arrow(ax, 61, 53, 73.5, 53)
    ax.text(67, 55.6, "yes", fontsize=7.6, color="#7a2e22", ha="center")
    _arrow(ax, 62, 25, 73.5, 25)
    ax.text(67.5, 27.6, "no", fontsize=7.6, color="#7a2e22", ha="center")

    fig.tight_layout(pad=0.2)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ----------------------------------------------------------------------
# Word helpers
# ----------------------------------------------------------------------
def set_style(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = BODY_SIZE
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)
    pf = normal.paragraph_format
    pf.space_after = Pt(6)
    pf.space_before = Pt(0)
    pf.line_spacing = 1.18
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def add_page_numbers(section) -> None:
    footer = section.footer
    paragraph = footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)
    run.font.name = BODY_FONT
    run.font.size = Pt(9)


def para(doc, text="", *, bold=False, italic=False, size=None, align=None, space_after=None, space_before=None, indent=None):
    p = doc.add_paragraph()
    if text:
        run = p.add_run(text)
        run.bold = bold
        run.italic = italic
        if size:
            run.font.size = size
    if align is not None:
        p.alignment = align
    if space_after is not None:
        p.paragraph_format.space_after = space_after
    if space_before is not None:
        p.paragraph_format.space_before = space_before
    if indent is not None:
        p.paragraph_format.left_indent = indent
    return p


def h1(doc, text) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(13)
    run.font.name = BODY_FONT
    run.font.color.rgb = RGBColor(0x11, 0x11, 0x11)


def h2(doc, text) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.bold = True
    run.italic = True
    run.font.size = Pt(11.5)
    run.font.name = BODY_FONT


def bullets(doc, items) -> None:
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.left_indent = Cm(0.75)
        p.add_run(item)


def numbered(doc, items) -> None:
    for index, item in enumerate(items, start=1):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.left_indent = Cm(0.85)
        p.paragraph_format.first_line_indent = Cm(-0.85)
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.add_run(f"{index}.\t{item}")


def add_caption(doc, text, *, before=Pt(2), after=Pt(10)) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = before
    p.paragraph_format.space_after = after
    run = p.add_run(text)
    run.italic = True
    run.font.size = Pt(9)
    run.font.name = BODY_FONT


def add_figure(doc, path: Path, caption: str, width_in: float) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Inches(width_in))
    add_caption(doc, caption)


def shade(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def add_table(doc, caption, headers, rows, widths=None, font_size=Pt(9), align_right_from=None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(caption)
    run.bold = True
    run.font.size = Pt(9.5)
    run.font.name = BODY_FONT

    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    def fill_cell(cell, text, *, bold=False, right=False):
        cell.text = ""
        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.space_after = Pt(1)
        paragraph.paragraph_format.space_before = Pt(1)
        paragraph.paragraph_format.line_spacing = 1.0
        paragraph.alignment = (
            WD_ALIGN_PARAGRAPH.RIGHT if right else WD_ALIGN_PARAGRAPH.LEFT
        )
        run = paragraph.add_run(str(text))
        run.bold = bold
        run.font.size = font_size
        run.font.name = BODY_FONT

    for i, header in enumerate(headers):
        fill_cell(table.rows[0].cells[i], header, bold=True)
        shade(table.rows[0].cells[i], "EDEDED")
    set_repeat_header(table.rows[0])

    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            fill_cell(
                cells[i],
                value,
                right=align_right_from is not None and i >= align_right_from,
            )

    for row in table.rows:
        tr_pr = row._tr.get_or_add_trPr()
        cant_split = OxmlElement("w:cantSplit")
        cant_split.set(qn("w:val"), "true")
        tr_pr.append(cant_split)

    if widths:
        for row in table.rows:
            for i, width in enumerate(widths):
                row.cells[i].width = Cm(width)

    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def set_repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


# ----------------------------------------------------------------------
# Document
# ----------------------------------------------------------------------
def build() -> Path:
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    fig1 = FIG_DIR / "fig1_architecture.png"
    fig2 = FIG_DIR / "fig2_workflow.png"
    make_fig_architecture(fig1)
    make_fig_workflow(fig2)

    fig3 = FIG_DIR / "fig3_risk_coverage.png"
    shutil.copyfile(ROOT / "results" / "plots" / "risk_coverage.png", fig3)
    fig4 = FIG_DIR / "fig4_gate_auc.png"
    shutil.copyfile(ROOT / "results" / "plots" / "gate_auc.png", fig4)

    doc = Document()
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    section.top_margin = Cm(2.2)
    section.bottom_margin = Cm(2.2)
    section.left_margin = Cm(2.3)
    section.right_margin = Cm(2.3)
    set_style(doc)
    add_page_numbers(section)

    # ---------------- Title block ----------------
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(0)
    title.paragraph_format.space_after = Pt(10)
    run = title.add_run(
        "OntoGate-RAG: Selective Biomedical Question Answering with an "
        "LLM Evidence Judge and Ontology-Based Cost Screening"
    )
    run.bold = True
    run.font.size = Pt(17)
    run.font.name = BODY_FONT

    authors = doc.add_paragraph()
    authors.alignment = WD_ALIGN_PARAGRAPH.CENTER
    authors.paragraph_format.space_after = Pt(2)
    run = authors.add_run("[Author Name]")
    run.font.size = Pt(11)
    run.bold = True

    affiliation = doc.add_paragraph()
    affiliation.alignment = WD_ALIGN_PARAGRAPH.CENTER
    affiliation.paragraph_format.space_after = Pt(14)
    run = affiliation.add_run("[Department], [Institution]\n[email address]")
    run.font.size = Pt(10)
    run.italic = True

    # ---------------- Abstract ----------------
    h1(doc, "Abstract")
    para(
        doc,
        "Retrieval-augmented question answering systems usually answer every "
        "question they are given. When the retrieved evidence is thin the "
        "answer is often wrong but still confident, which is a poor fit for "
        "medicine. We present OntoGate-RAG, a system for PubMedQA-style "
        "yes/no/maybe questions that decides, for each question, whether to "
        "answer or to stay silent. It retrieves ten candidate abstracts with a "
        "dense index, then makes one call to a small language model that "
        "returns two things at once: a three-level verdict on whether the "
        "evidence is sufficient, and a provisional answer. A small gate turns "
        "those outputs into an answer or an abstention. A MeSH\u2013Hetionet "
        "ontology layer links question and evidence text to medical concepts "
        "and measures concept coverage, both as a gate feature and as a free "
        "pre-screen. On the 500-question test half the gated system answers "
        "65.2% of questions at 78.2% accuracy (95% confidence interval "
        "73.6\u201382.5), against 58.8% when the same model answers "
        "everything. Three results are less obvious. Ontology coverage on its "
        "own is no better than chance as an accuracy signal (AUC 0.49). The "
        "fitted gate makes exactly the same decisions as an untrained rule "
        "that trusts only fully confident, non-\u201cmaybe\u201d judge outputs. "
        "And the ontology\u2019s measurable value is cost rather than "
        "accuracy: as a pre-screen it removes 19.4% of judge calls for a cost "
        "of 0.9 accuracy points. We report the negative results alongside the "
        "positive ones."
    )
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    run = p.add_run("Keywords: ")
    run.bold = True
    run.font.size = Pt(10)
    run = p.add_run(
        "biomedical question answering; selective prediction; retrieval-augmented "
        "generation; ontology; confidence estimation; abstention; PubMedQA"
    )
    run.font.size = Pt(10)

    # ---------------- 1 Introduction ----------------
    h1(doc, "1. Introduction")
    para(
        doc,
        "Retrieval-augmented generation (RAG) has become the default way to "
        "ground a language model in a document collection [2]. The model is "
        "shown a handful of retrieved passages and writes an answer that "
        "should follow from them. The design assumes the passages are useful. "
        "In practice they sometimes are not: the search may return related "
        "but uninformative text, or the collection may simply not contain the "
        "answer. The model still responds, usually in a confident tone. In "
        "medicine this failure mode is expensive, because a fluent wrong "
        "answer is harder to catch than a refusal."
    )
    para(
        doc,
        "Selective prediction gives a model a third option: abstain [4], [5]. "
        "Instead of always answering, the system decides per input whether it "
        "knows enough. The two quantities that matter are coverage, the share "
        "of inputs that receive an answer, and selective accuracy, the "
        "accuracy on that answered subset. Their trade-off is usually plotted "
        "as a risk\u2013coverage curve. Two conventions keep such numbers "
        "honest. First, an abstention is never counted as correct, so a system "
        "cannot raise its score by refusing everything. Second, the decision "
        "threshold must be fixed on data that is not used for the final "
        "report."
    )
    para(
        doc,
        "Prior work offers several kinds of confidence signal. Sampling-based "
        "methods estimate uncertainty by generating multiple answers [12], "
        "critic models learn when retrieval is needed [3], and prompting "
        "methods ask a model how sure it is [9]\u2013[11]. These approaches "
        "work, but they cost extra model calls, extra training, or access to "
        "internal model state. Ontologies, meanwhile, are widely used in "
        "biomedical search for entity normalisation and query expansion "
        "[6]\u2013[8]. What is less explored is whether ontology coverage alone "
        "can tell us that retrieved evidence is sufficient to answer a "
        "question. Our experiments suggest it cannot, but it is useful in a "
        "different role: as a free filter that decides when not to pay for a "
        "model call."
    )
    para(
        doc,
        "This paper asks a practical question: can a single structured "
        "judgement from a small language model, combined with ontology "
        "coverage, decide when retrieved biomedical evidence is good enough "
        "to answer, and at what cost? We study this on PubMedQA [1], which "
        "provides expert-labelled yes/no/maybe questions about published "
        "abstracts. Our system, OntoGate-RAG, is deliberately simple: one "
        "retrieval step, one judge call per question, one two-feature gate, "
        "and an optional ontology pre-screen. The evaluation is fully paired, "
        "so every arm sees the same retrieved passages and the same model "
        "output; the only difference is whether the system was allowed to "
        "abstain."
    )
    para(doc, "The contributions of the work are as follows.", space_after=Pt(3))
    numbered(
        doc,
        [
            "A selective question-answering pipeline for PubMedQA in which a "
            "single LLM call produces both the candidate answer and the "
            "sufficiency signal used to gate it, so the gating costs no extra "
            "API calls.",
            "Evidence that the judge\u2019s own uncertainty is the strongest "
            "available signal: its sufficiency label reaches AUC 0.736 on the "
            "test half, adding the fact that it answered \u201cmaybe\u201d "
            "raises this to 0.770, and the fitted two-feature gate reduces to "
            "an untrained rule that makes identical decisions.",
            "A quantified account of what the ontology contributes. MeSH and "
            "Hetionet coverage is a near-chance accuracy gate (AUC 0.49) but "
            "a useful cost filter, removing 19.4% of judge calls for a 0.9 "
            "point accuracy loss.",
            "A set of documented negative results \u2014 ontology reranking, "
            "query expansion, many-feature gates and alternative confidence "
            "features \u2014 reported with both dev and test numbers so that "
            "overfitting is visible.",
        ],
    )
    para(
        doc,
        "The rest of the paper describes related work (Section 2), the system "
        "architecture (Section 3), the implemented workflows (Section 4), the "
        "evaluation protocol (Section 5), results and discussion (Section 6), "
        "limitations and future work (Section 7), and conclusions (Section 8)."
    )

    # ---------------- 2 Related work ----------------
    h1(doc, "2. Related Work")
    para(
        doc,
        "Four threads meet in this project: selective prediction, "
        "retrieval-augmented biomedical question answering, biomedical "
        "ontologies, and confidence elicitation from language models."
    )
    h2(doc, "2.1 Selective Prediction and Abstention")
    para(
        doc,
        "The reject option has a long history in pattern recognition. Chow "
        "showed that an optimal error\u2013reject trade-off exists when a "
        "classifier may decline low-confidence inputs [5]. Geifman and "
        "El-Yaniv brought the idea to deep networks, selecting a threshold on "
        "a confidence score to guarantee a target risk [4]. Their framing "
        "assumes a score that is already calibrated on held-out data. Our "
        "setting is different in one respect: the score comes from a language "
        "model\u2019s judgement about evidence, not from the classifier that "
        "produces the label. The threshold is still fitted on a development "
        "split and applied once to a test split."
    )
    h2(doc, "2.2 Retrieval-Augmented Biomedical QA")
    para(
        doc,
        "PubMedQA introduced 1,000 expert-labelled questions whose answers "
        "are yes, no or maybe, each accompanied by abstracts from the source "
        "paper [1]. It remains a standard test bed for biomedical reading "
        "comprehension. RAG [2] pairs a dense retriever with a generator; "
        "later systems improve either side, for example with domain-specific "
        "biomedical encoders such as MedCPT [15]. Dense retrieval with "
        "sentence-transformer encoders [16] and approximate nearest-neighbour "
        "search [17] is now routine. Retrieval benchmarks such as BEIR [13] "
        "and claim-verification datasets such as SciFact [14] show that "
        "retrieval quality depends strongly on the corpus. In PubMedQA\u2019s "
        "open-book setting the relevant abstracts are present and questions "
        "share vocabulary with them, so retrieval is close to ceiling. That "
        "is why our work concentrates on the decision after retrieval rather "
        "than on ranking."
    )
    h2(doc, "2.3 Biomedical Ontologies and Knowledge Graphs")
    para(
        doc,
        "MeSH provides a controlled vocabulary and hierarchy maintained by "
        "the U.S. National Library of Medicine [8]; UMLS integrates many "
        "biomedical vocabularies into one terminology [7]. Hetionet combines "
        "curated pharmacological and genetic relationships into a single "
        "graph and has been used to prioritise drug repurposing candidates "
        "[6]. In question answering, ontologies usually serve entity linking, "
        "query expansion, or graph-based reranking. Using coverage of "
        "question concepts as a proxy for evidence sufficiency is less common. "
        "Our results explain why: on a corpus where ten abstracts are "
        "retrieved per question, the concepts are almost always mentioned "
        "somewhere, so coverage saturates and loses discriminative power."
    )
    h2(doc, "2.4 Language Models and Their Own Uncertainty")
    para(
        doc,
        "Large language models can often tell when they do not know. Kadavath "
        "et al. show that models assign higher probability to their own "
        "correct answers [9]; Lin et al. teach models to express uncertainty "
        "in words [10]; Xiong et al. compare several confidence elicitation "
        "strategies [11]. Self-RAG trains a model to emit reflection tokens "
        "that decide when to retrieve and when to trust its output [3]. "
        "Semantic entropy uses meaning-level sampling to detect confabulation "
        "[12]. These methods are more elaborate than ours. We test a cheaper "
        "version of the same idea: ask the model for a coarse sufficiency "
        "verdict, and treat its explicit \u201cmaybe\u201d as a refusal. The "
        "finding that this single bit matches a fitted gate is, to our "
        "knowledge, a useful practical result for low-budget systems."
    )
    h2(doc, "2.5 Literature Review Matrix")
    para(
        doc,
        "Table I compares representative prior work with this project. The "
        "column \u201climitation\u201d is relative to our goal, not a criticism "
        "of the original work."
    )
    add_table(
        doc,
        "Table I. Literature review matrix for selective biomedical QA.",
        ["Work", "Core problem", "Approach", "Main finding / limitation"],
        [
            [
                "Jin et al. (2019) [1]",
                "Expert-labelled biomedical QA",
                "1,000 questions from PubMed abstracts with yes/no/maybe labels",
                "Strong benchmark; no mechanism for deciding when evidence is insufficient",
            ],
            [
                "Lewis et al. (2020) [2]",
                "Grounding generation in retrieved documents",
                "Dense retriever plus sequence-to-sequence generator",
                "Effective grounding; always generates, so retrieval failures become confident errors",
            ],
            [
                "Asai et al. (2024) [3]",
                "Deciding when to retrieve and when to trust output",
                "Self-reflection tokens produced by a fine-tuned critic",
                "Accurate control; needs additional training and multiple inference passes",
            ],
            [
                "Geifman and El-Yaniv (2017) [4]",
                "Selective classification with a risk target",
                "Threshold on a learned confidence score, risk\u2013coverage analysis",
                "Principled abstention; assumes a calibrated in-model score and retraining",
            ],
            [
                "Himmelstein et al. (2017) [6]",
                "Integrating biomedical knowledge for drug repurposing",
                "Hetionet graph of curated clinical and genetic relations",
                "Rich relational resource; not designed to estimate answerability of a QA instance",
            ],
        ],
        widths=[3.4, 3.6, 4.6, 5.0],
        font_size=Pt(8.5),
    )

    # ---------------- 3 Architecture ----------------
    h1(doc, "3. System Architecture")
    para(
        doc,
        "The system is a linear pipeline with two early exits (Fig. 1). Each "
        "stage is a separate module with a small interface, which made it "
        "possible to swap gates and features without touching retrieval or "
        "the judge. All derived artefacts are cached on disk, so an "
        "experiment can be stopped and resumed."
    )
    h2(doc, "3.1 Data Layer")
    para(
        doc,
        "We use the 1,000 expert-labelled PubMedQA questions (552 yes, 338 "
        "no, 110 maybe) and the public corpus of 3,000 abstracts. The "
        "questions were split once, at random with a fixed seed, into a "
        "development half and a test half of 500 each. The retrieval corpus "
        "is shared by both halves. Following the standard open-book protocol, "
        "the question\u2019s own source abstract is left in the corpus; the "
        "system is not told which abstract it is. We later confirmed that "
        "removing it makes the task close to unsolvable for this judge, which "
        "is consistent with the benchmark\u2019s design and is reported as a "
        "hard-mode result rather than used for the headline."
    )
    h2(doc, "3.2 Retrieval")
    para(
        doc,
        "Abstracts are embedded once with the multi-qa-MiniLM-L6-cos-v1 "
        "sentence-transformer model [16] and indexed with FAISS [17] using "
        "inner-product search over normalised vectors. At query time the "
        "question is embedded with the same model and the ten nearest "
        "abstracts are returned. Ten is the top-k used throughout; it is also "
        "the depth at which coverage was measured. Retrieval is fast and free "
        "after the index is built, and on this corpus it is already close to "
        "ceiling (Section 6.6)."
    )
    h2(doc, "3.3 Ontology Layer")
    para(
        doc,
        "The ontology is built from two public sources. MeSH 2026 contributes "
        "31,110 descriptors and 65,242 hierarchy edges [8]. Hetionet v1.0 "
        "contributes 147,591 edges over six clinical relation types, such as "
        "compound\u2013treats\u2013disease and disease\u2013associates\u2013gene "
        "[6]. No part of the graph is generated by a language model, and the "
        "build records the source files and licences."
    )
    para(
        doc,
        "At inference time, question and passage text are scanned for "
        "mentions of ontology labels and synonyms. Each question is reduced "
        "to a small set of weighted concepts, typically one or two. The "
        "layer then computes several features: coverage of the question\u2019s "
        "concepts by the retrieved abstracts (top-1, top-3, or all ten); "
        "coverage of the concept in section headings; whether two question "
        "concepts occur in the same sentence; and whether the relation "
        "implied by the question is asserted near both concepts. A separate "
        "pass assigns each question a MeSH disease category (C01\u2013C26) so "
        "that results can be reported per specialty. The features are "
        "deliberately inspectable: every number can be traced back to a "
        "concept label and a passage."
    )
    h2(doc, "3.4 The Evidence Judge")
    para(
        doc,
        "The judge receives the question and the ten abstracts in one prompt "
        "and must return a small JSON object: a sufficiency label "
        "(yes / partial / no) and a provisional answer (yes / no / maybe). "
        "The labels are mapped to scores 1.0, 0.5 and 0.0. The prompt "
        "instructs the model to say \u201cmaybe\u201d only when the evidence is "
        "genuinely ambiguous or conflicting, and to mark evidence as "
        "\u201cpartial\u201d when the passages are related but do not settle "
        "the question. This design serves two purposes. It yields a candidate "
        "answer, so no second generation call is needed, and it yields an "
        "explicit uncertainty statement that can be used as a gate feature. "
        "We use gemini-3.1-flash-lite [18] with thinking disabled, "
        "temperature 0, "
        "and a hard output cap. Responses are cached by a hash of the prompt, "
        "and quota errors stop the run immediately instead of retrying, "
        "because retrying cannot help until the quota resets."
    )
    h2(doc, "3.5 Gate and Cascade")
    para(
        doc,
        "The gate is a two-feature logistic model over the judge\u2019s "
        "sufficiency score and a binary indicator for \u201cthe judge answered "
        "maybe\u201d. Features are standardised with statistics from the "
        "development split. For a target coverage, the threshold is the "
        "smallest score whose coverage still meets the target, and it is "
        "stored with the model so that a demo or a re-run reproduces the same "
        "decisions. The two-feature restriction is a deliberate defence "
        "against overfitting: with only 283 development rows, larger feature "
        "sets improve dev AUC and lose on test (Section 6.3)."
    )
    para(
        doc,
        "In front of the judge sits an optional pre-screen. If the ontology "
        "coverage of the retrieved evidence is at or below a threshold, the "
        "question is answered with an abstention without calling the model. "
        "The threshold is the only free parameter, and it is selected on "
        "development data. The cascade is therefore a cost control, not an "
        "accuracy mechanism."
    )
    h2(doc, "3.6 Reproducibility and Cost Control")
    para(
        doc,
        "Every experiment is driven by scripts that write JSONL records, one "
        "per question, containing the retrieved passage ids, the judge "
        "output, the coverage features and the final decision. The analysis "
        "script reads those records and refits the gates, so tables and plots "
        "can be regenerated without any API calls. The response cache means a "
        "question is never paid for twice. The observed free-tier envelope "
        "was about 500 judge calls in one day, which is why the test half was "
        "completed first and the development half is reported at 283 of 500 "
        "rows. The run resumes by skipping questions that already have a "
        "record."
    )
    add_figure(
        doc,
        fig1,
        "Fig. 1. System architecture. Data assets on the left feed a linear pipeline; "
        "the ontology pre-screen can bypass the paid judge call.",
        6.1,
    )

    # ---------------- 4 Workflows ----------------
    h1(doc, "4. Implemented Workflows")
    para(
        doc,
        "The pipeline has three observable paths. All three are exercised by "
        "the demo script, which prints the retrieved evidence, the linked "
        "concepts, the judge output and the final decision for a single "
        "question. The examples below are real test questions, quoted by "
        "their PubMed identifier."
    )
    h2(doc, "4.1 Answer Path")
    para(
        doc,
        "Question 21645374 asks whether mitochondria play a role in "
        "remodelling lace plant leaves during programmed cell death. "
        "Retrieval returns ten abstracts, the top one with cosine similarity "
        "0.73. The ontology links two concepts, \u201cMitochondria\u201d and "
        "\u201cPlant Leaves\u201d, and both are covered by the retrieved "
        "evidence, so coverage is 1.0 and the pre-screen does not fire. The "
        "judge marks the evidence as sufficient and answers \u201cyes\u201d. "
        "The gate score is above the threshold, so the system answers "
        "\u201cyes\u201d. The gold label is also yes."
    )
    h2(doc, "4.2 Abstention from Judge Uncertainty")
    para(
        doc,
        "Question 10966337 asks whether a short-stay ward in a children\u2019s "
        "hospital is effective. Coverage is 1.0, because the concept "
        "\u201cHospitals\u201d appears in the evidence, so the ontology has no "
        "reason to object. The judge, however, returns \u201cpartial\u201d and "
        "answers \u201cmaybe\u201d. The system abstains. The gold label is yes, "
        "so this is a lost point in principle, but it is the kind of case "
        "where a committed answer would have had no clear support: the "
        "abstracts discuss the ward but do not settle its effectiveness. "
        "Across the test half, questions on which the judge said "
        "\u201cmaybe\u201d were answered correctly only 18.6% of the time when "
        "forced."
    )
    h2(doc, "4.3 Abstention from the Free Pre-Screen")
    para(
        doc,
        "Question 26852225 asks whether adjustment for reporting "
        "heterogeneity is necessary in sleep disorders. The only linked "
        "concept is \u201cSleep Disorders\u201d, and none of the ten retrieved "
        "abstracts mentions it. Coverage is 0.0, the pre-screen fires, and the "
        "system abstains without a model call. In this case the judge would "
        "also have abstained, so the screen saved a call without changing the "
        "decision. Section 6.4 reports how often that is true across the test "
        "half."
    )
    add_figure(
        doc,
        fig2,
        "Fig. 2. Decision workflow. Two early exits produce an abstention without "
        "committing to an answer; both are evaluated under the same scoring rule.",
        5.8,
    )
    h2(doc, "4.4 Analysis Workflow")
    para(
        doc,
        "After a sweep, an offline script loads the records, computes "
        "risk\u2013coverage curves and AUC for every candidate signal, fits "
        "each gate on the development rows, applies the stored thresholds to "
        "the test rows, and writes a Markdown report plus three plots. A "
        "second script evaluates retrieval recall and MRR, and a third "
        "compares the gate against a plain-prompt baseline on the questions "
        "both runs share. None of these steps calls the API."
    )

    # ---------------- 5 Evaluation ----------------
    h1(doc, "5. Evaluation Methodology")
    h2(doc, "5.1 Protocol")
    para(
        doc,
        "All design choices were made on the development half. The test half "
        "was processed once, after the gates, thresholds and the feature list "
        "had been fixed, and no test number was used to revise them. The "
        "primary comparison was specified before the test run: the "
        "two-feature gate at a 60% coverage target, fitted on development "
        "data, evaluated on test. Secondary comparisons are reported with "
        "both dev and test values. Every arm is evaluated on the same 500 "
        "questions and the same retrieved passages, so differences cannot "
        "come from retrieval randomness. An abstention receives no credit, "
        "even when the gold label is \u201cmaybe\u201d."
    )
    para(
        doc,
        "Thresholds are matched-coverage thresholds: for a target coverage c, "
        "the threshold is the smallest score whose coverage on the fitting "
        "split is at least c. This makes dev and test comparisons fair even "
        "when the score distributions differ slightly. The 95% confidence "
        "interval for the headline accuracy is a bootstrap over test "
        "questions (1,000 resamples)."
    )
    h2(doc, "5.2 Metrics")
    para(doc, "Four metrics are used throughout.", space_after=Pt(3))
    bullets(
        doc,
        [
            "Coverage: the fraction of questions that receive a yes or no "
            "answer. An abstention lowers coverage.",
            "Selective accuracy: accuracy on the answered subset only. This "
            "is the headline number.",
            "AUC: the probability that a randomly chosen correct question "
            "scores higher than a randomly chosen incorrect one, computed "
            "over all questions. It measures ranking quality independent of "
            "any threshold.",
            "AURC: the area under the risk\u2013coverage curve. Lower is "
            "better; it summarises the whole trade-off rather than one "
            "operating point.",
        ],
    )
    h2(doc, "5.3 Gate Variants")
    para(
        doc,
        "Several signals and gates were compared. Table II groups them by "
        "family. The ontology features are included so that their "
        "contribution can be measured, not because we expected them to win. "
        "Two variants exist solely as overfitting checks: a gate that adds "
        "coverage to the two-feature model, and a gate that adds all features "
        "including a one-hot encoding of the disease specialty."
    )
    add_table(
        doc,
        "Table II. Gate variants evaluated in this study.",
        ["Signal or gate", "What it measures", "Role in the study"],
        [
            ["Retrieval similarity", "Cosine score of the closest abstract, mean and spread over ten", "Baseline signal"],
            ["Ontology coverage, top-3 / all ten", "Share of question concepts mentioned in the abstracts", "Gate feature and pre-screen"],
            ["Heading coverage", "Concept matches in abstract section headings", "Ablation"],
            ["Sentence-pair coverage", "Whether two question concepts occur in one sentence", "Ablation"],
            ["Relation coverage", "Whether the question\u2019s relation is asserted near both concepts", "Ablation"],
            ["Judge score (1.0 / 0.5 / 0.0)", "Three-level verdict on evidence sufficiency", "Gate feature"],
            ["Judge answered \u201cmaybe\u201d", "The model\u2019s own refusal signal", "Gate feature"],
            ["Two-feature gate", "Judge score plus the maybe indicator", "Primary gate"],
            ["Gate with coverage", "Two-feature gate plus ontology coverage", "Overfitting check"],
            ["All features", "Eleven features including specialty one-hot", "Overfitting check"],
        ],
        widths=[4.6, 7.4, 4.4],
        font_size=Pt(8.5),
    )
    h2(doc, "5.4 Baselines")
    para(
        doc,
        "The main baseline is the same model answering with the judge prompt "
        "and no abstention. This is the strictest paired comparison, because "
        "the passages and the model output are identical. Two weaker "
        "reference points are also reported: a forced-answer variant in which "
        "every \u201cmaybe\u201d is converted to \u201cyes\u201d, and the "
        "majority-class rate. Finally, an earlier plain-prompt RAG run with a "
        "different model version is compared on the 50 questions the two runs "
        "share; that comparison is indicative only, because the model version "
        "differs."
    )

    # ---------------- 6 Results ----------------
    h1(doc, "6. Results and Discussion")
    h2(doc, "6.1 Main Results")
    para(
        doc,
        "Table III reports the test half. The always-answer arm reaches 58.8%, "
        "which is close to the majority-class rate of 55.3% and well below "
        "the 67.4% obtained by forcing every \u201cmaybe\u201d to \u201cyes\u201d. "
        "The judge prompt therefore costs some raw accuracy when no "
        "abstention is allowed. The gate recovers much more than it loses: it "
        "answers 326 of 500 questions (65.2% coverage) with 78.2% accuracy, "
        "an absolute gain of 19.4 points over the same model answering "
        "everything. The 95% confidence interval is 73.6\u201382.5, so the "
        "gain is clearly separated from zero. The development estimate was "
        "83.2% at 67.1% coverage; the 5-point gap between dev and test is the "
        "honest measure of how much the fitted threshold and gate benefited "
        "from the fitting data."
    )
    add_table(
        doc,
        "Table III. Test-half results (n = 500). Coverage is the share of questions answered; accuracy is measured on that answered subset. An abstention is never counted as correct.",
        ["System", "Coverage", "Accuracy"],
        [
            ["Always answer (judge prompt)", "100.0%", "58.8%"],
            ["Forced answer (\u201cmaybe\u201d \u2192 \u201cyes\u201d)", "100.0%", "67.4%"],
            ["Majority class (\u201cyes\u201d)", "100.0%", "55.3%"],
            ["Judge score threshold (dev-fitted)", "69.2%", "75.1%"],
            ["Judge self-abstention score", "65.2%", "78.2%"],
            ["Two-feature gate (primary)", "65.2%", "78.2% [73.6, 82.5]"],
            ["Gate plus ontology coverage", "62.2%", "78.1%"],
        ],
        widths=[9.0, 3.4, 4.4],
        font_size=Pt(9),
        align_right_from=1,
    )
    para(
        doc,
        "Two ablations deserve their own sentence. Adding ontology coverage to "
        "the gate slightly lowers both coverage and accuracy at the matched "
        "target (78.1% at 62.2%). Adding every feature, including the "
        "specialty one-hot, produces the best development AUC (0.834) and a "
        "worse test AUC than the two-feature gate (0.772 versus 0.774). The "
        "lesson is not that these features are uninformative in principle; it "
        "is that with 283 development rows, extra parameters buy dev-set "
        "noise."
    )
    h2(doc, "6.2 Signal Quality")
    para(
        doc,
        "Table IV ranks the candidate signals by AUC. The ordering is "
        "unambiguous. Ontology features sit between 0.461 and 0.559 on test, "
        "which is chance level or slightly below it. Retrieval similarity is "
        "also chance level (0.527). The judge score is far ahead at 0.736. "
        "Adding the binary \u201cmaybe\u201d indicator raises the ranking to "
        "0.770, and the fitted two-feature gate reaches 0.774. The AURC "
        "column tells the same story: the risk\u2013coverage curve of the "
        "judge-based signals is flatter across coverage levels, meaning that "
        "the accuracy penalty for answering more questions is smaller."
    )
    add_table(
        doc,
        "Table IV. AUC and AURC of candidate signals. AUC is computed over all questions; higher is better. AURC summarises the risk\u2013coverage curve; lower is better.",
        ["Signal", "Dev AUC", "Test AUC", "Test AURC"],
        [
            ["Retrieval similarity", "0.552", "0.527", "0.395"],
            ["Ontology coverage (top-3)", "0.502", "0.493", "0.409"],
            ["Ontology coverage (all ten)", "0.497", "0.491", "0.413"],
            ["Ontology heading coverage", "0.512", "0.534", "0.382"],
            ["Ontology relation (sentence)", "0.461", "0.559", "0.383"],
            ["LLM judge score", "0.768", "0.736", "0.291"],
            ["Judge score + self-abstention", "0.812", "0.770", "0.254"],
            ["Judge fully confident (rule)", "0.803", "0.761", "0.256"],
            ["Two-feature gate", "0.816", "0.774", "0.254"],
            ["Gate + ontology coverage", "0.815", "0.766", "0.262"],
            ["All features", "0.834", "0.772", "0.247"],
        ],
        widths=[7.4, 3.0, 3.0, 3.4],
        font_size=Pt(9),
        align_right_from=1,
    )
    add_figure(
        doc,
        fig3,
        "Fig. 3. Risk\u2013coverage curves on the test half (lower risk is better). "
        "Judge-based gates stay well below the always-answer risk as coverage grows; "
        "ontology and similarity signals do not.",
        5.6,
    )
    add_figure(
        doc,
        fig4,
        "Fig. 4. Test-set AUC of the main candidate signals. The dashed line marks "
        "chance; the judge-based signals are the only ones clearly above it.",
        5.6,
    )
    h2(doc, "6.3 The Fitted Gate Collapses to a Rule")
    para(
        doc,
        "The most interesting result is not visible in a table of accuracies. "
        "When the two-feature gate is fitted on the development half, its "
        "weights are +0.376 for the standardised judge score and \u22121.222 "
        "for the maybe indicator, with a bias of +0.532. The resulting "
        "probability for a question with score 1.0 and no \u201cmaybe\u201d is "
        "0.8261. The threshold chosen for a 60% target is 0.8261 as well. In "
        "other words, the learned boundary lands exactly on the score level "
        "that corresponds to the rule \u201canswer only when the judge is "
        "fully confident and did not answer maybe\u201d. Because score levels "
        "are discrete, the gate includes the whole tie group, and the "
        "decision set is identical to the rule\u2019s decision set. The rule, "
        "with no training at all, gives the same 78.2% at 65.2% coverage on "
        "test and 83.2% at 67.1% on dev."
    )
    para(
        doc,
        "This has a practical consequence. For this task, a deployable system "
        "does not need a learned gate; it needs a judge that is asked the "
        "right question and is allowed to say \u201cmaybe\u201d. The gate is "
        "still useful as an analysis tool, because it shows where a "
        "threshold would sit if the label distribution changed, but its "
        "contribution to accuracy is nil. We report both numbers so that the "
        "claim \u201cthe gate works\u201d is not confused with the claim "
        "\u201cthe gate is necessary\u201d. It is not necessary here."
    )
    h2(doc, "6.4 The Ontology as a Cost Filter")
    para(
        doc,
        "If coverage cannot rank questions by answerability, can it at least "
        "identify hopeless ones? Table V shows the cascade on test. With the "
        "screen at zero coverage, 5.6% of judge calls are skipped and "
        "accuracy is unchanged, because the removed questions were almost all "
        "ones the system would have answered incorrectly. At a screen "
        "threshold of 0.5, 14.4% of calls "
        "are skipped and accuracy falls by 0.2 points. At 0.75, 19.4% of "
        "calls are skipped and accuracy falls by 0.9 points (78.2% to "
        "77.3%). The development half shows the same pattern (20.5% saved, "
        "0.7 points lost), so the effect is not a test-set accident."
    )
    add_table(
        doc,
        "Table V. Ontology pre-screen cascade. A question whose coverage is at or below the screen threshold abstains without a judge call. Accuracy is on the remaining, answered questions.",
        ["Screen threshold", "Dev calls saved", "Dev accuracy", "Test calls saved", "Test accuracy"],
        [
            ["0.00", "5.3%", "83.6%", "5.6%", "78.2%"],
            ["0.50", "13.8%", "82.4%", "14.4%", "78.0%"],
            ["0.75", "20.5%", "83.2%", "19.4%", "77.3%"],
        ],
        widths=[3.4, 3.4, 3.0, 3.4, 3.0],
        font_size=Pt(9),
        align_right_from=1,
    )
    para(
        doc,
        "The saving is real but modest, and it comes from a specific "
        "population: questions with almost no ontology evidence. Those "
        "questions are, if anything, slightly easier than average (0.619 "
        "versus 0.581 forced accuracy), which is the opposite of what a "
        "cost-aware screen usually hopes for. The reason is saturation: mean "
        "document coverage is 0.932, and 87.1% of questions have coverage "
        "1.0. A feature that is constant for most of the data cannot separate "
        "hard from easy questions; it can only flag the small tail where the "
        "evidence shares no vocabulary with the question."
    )
    h2(doc, "6.5 Error Analysis")
    para(
        doc,
        "On the 500 test questions the judge answered \u201cyes\u201d 215 "
        "times, \u201cno\u201d 124 times and \u201cmaybe\u201d 161 times. "
        "Forced accuracy was 79.5% on the yes group and 75.0% on the no "
        "group. The maybe group is the interesting one: forced accuracy was "
        "18.6%. The sufficiency label shows the same structure. When the "
        "judge called the evidence sufficient, forced accuracy was 75.1% "
        "(n = 346); for partial evidence it was 24.4% (n = 90); for "
        "insufficient evidence it was 18.8% (n = 64). The gate is therefore "
        "not exploiting a quirk of the answer field; the sufficiency label and "
        "the maybe answer are two views of the same uncertainty, and both are "
        "informative."
    )
    para(
        doc,
        "Per specialty, the gate improves selective accuracy in every group "
        "with at least ten questions except one. That exception is a group of "
        "ten methodology questions (analytical and diagnostic techniques) on "
        "which the judge called the evidence sufficient with high confidence "
        "on all ten and was wrong on eight. It is a genuine failure of the "
        "judge, not an abstention pattern, and it is the clearest example of "
        "why a confident judge is not the same as a correct one. The largest "
        "groups in the test half are neoplasms (n = 93), pathological "
        "conditions and symptoms (n = 57) and cardiovascular diseases "
        "(n = 53); all three follow the overall trend."
    )
    h2(doc, "6.6 Retrieval Saturation and Negative Results")
    para(
        doc,
        "Retrieval was measured on a 200-question development sample. Recall "
        "at 1 is 0.885, at 3 is 0.940, at 5 is 0.950 and at 10 is 0.970; MRR "
        "is 0.916. The question\u2019s own abstract is usually ranked first. "
        "This is expected in PubMedQA\u2019s open-book setting, where "
        "questions are written from the source abstract and the source is in "
        "the corpus. Because recall at 10 is 97%, there is very little room "
        "for a reranker to help."
    )
    para(
        doc,
        "We tested that conclusion rather than assuming it. Blending the "
        "dense score with ontology coverage over a grid of weights changed "
        "recall at 1 from 0.885 to at best 0.890 and recall at 3 to 0.945, "
        "differences that are within noise for 200 questions. Adding ontology "
        "terms to the query reduced performance, because the expanded query "
        "drifted towards generic disease vocabulary. These results are "
        "negative and are reported as such. They also explain why the "
        "ontology could not act as an accuracy gate: the information it "
        "captures is already present in the retrieved text, and the ranking "
        "step has no headroom."
    )
    h2(doc, "6.7 Comparison with a Plain-Prompt Baseline")
    para(
        doc,
        "The always-answer baseline in Table III uses the judge prompt, which "
        "is not how a standard RAG system is usually prompted. The judge "
        "prompt invites \u201cmaybe\u201d and therefore abstains on some "
        "questions even when no gate is applied, which makes the ungated "
        "number a conservative baseline. To check how much this matters, we "
        "compared the gated system with an earlier plain-prompt RAG run on "
        "the 50 test questions the two runs share. That run used a different "
        "model version (gemini-3.5-flash-lite), so the comparison is "
        "indicative. On the 32 questions the gate answered, gate accuracy was "
        "75.0% and plain-prompt accuracy was 71.9%, a difference of +3.1 "
        "points (McNemar p = 1.0): the direction favours the gate, but the "
        "sample is too small to claim significance. We report this openly "
        "rather than presenting the 19-point paired gain as if it were a gain "
        "over standard RAG. A same-model plain-prompt runner is included in "
        "the repository and is the first planned follow-up."
    )
    h2(doc, "6.8 Discussion")
    para(
        doc,
        "Three lessons generalise beyond this dataset. First, the cheapest "
        "useful confidence signal in a RAG system may be an explicit "
        "uncertainty label produced by the generator itself. It costs one "
        "field in an existing prompt, needs no extra sampling, and, in our "
        "case, matched a fitted gate exactly. Second, ontologies are better "
        "at telling you what a question is about than at telling you whether "
        "the answer is present. That makes them natural candidates for cost "
        "control, entity-level auditing and specialty routing, not for "
        "accuracy gating on a saturated open-book corpus. Third, a "
        "matched-coverage protocol with a single test pass is what makes the "
        "comparison credible; without it, a 19-point gain could easily be an "
        "artefact of a weak baseline or of fitting thresholds on the test "
        "set."
    )
    para(
        doc,
        "A practical system would combine the two roles: use the ontology "
        "screen to avoid calls for questions outside the corpus\u2019s "
        "vocabulary, then rely on the judge\u2019s own uncertainty for the "
        "final decision. In our measurements that combination saves roughly "
        "one call in five and keeps 99% of the accuracy of always calling the "
        "judge."
    )

    # ---------------- 7 Limitations ----------------
    h1(doc, "7. Limitations and Future Work")
    h2(doc, "7.1 Current Limitations")
    para(doc, "We list the limitations that a reader should keep in mind.", space_after=Pt(3))
    numbered(
        doc,
        [
            "Development data is incomplete. The test half is complete "
            "(500 questions), but only 283 of the 500 development questions "
            "have judge records because of the free-tier quota. The fitted "
            "thresholds are therefore noisier than the test-side confidence "
            "interval suggests. Finishing the dev sweep can only refine the "
            "thresholds; it cannot change the test half, which is already "
            "fixed.",
            "The main baseline uses the judge prompt. It is the correct paired "
            "baseline for the gating question, but it is weaker than a "
            "conventional plain-answer prompt. The plain-prompt comparison we "
            "have uses a different model version and only 50 shared questions, "
            "so the size of the gain over standard RAG remains uncertain.",
            "One model and one prompt. All judge behaviour comes from "
            "gemini-3.1-flash-lite with a single prompt template. A larger "
            "model, a different provider, or a differently worded prompt "
            "could change both the sufficiency distribution and the "
            "usefulness of the \u201cmaybe\u201d signal.",
            "The corpus is small and open-book. Three thousand abstracts for "
            "1,000 questions, with the source abstract present, makes "
            "retrieval easy. The findings about retrieval saturation and "
            "ontology reranking are specific to this setting.",
            "Label noise. Only 11% of gold labels are \u201cmaybe\u201d, and "
            "inter-annotator agreement on that class is known to be lower "
            "than on yes/no. Per-class error rates, especially for "
            "three-way scoring, are correspondingly noisy.",
            "No human evaluation of the abstentions. We measure whether "
            "abstaining helps accuracy, not whether the stated reason would "
            "convince a clinician. The system outputs no explanation, only a "
            "decision.",
            "Single run per configuration. The test half was processed once; "
            "the bootstrap interval captures sampling variability of the "
            "metric, not variability across API runs or model snapshots.",
        ],
    )
    h2(doc, "7.2 Future Work")
    para(
        doc,
        "The first priority is a same-model plain-prompt baseline on the full "
        "test half, which removes the model-version confound from the "
        "comparison. The second is to finish the development sweep and refit "
        "the thresholds on 500 rows. Third, the ontology could be used at the "
        "level of claims rather than terms: extract the relation asserted by "
        "the question and check whether the passage asserts the same "
        "relation, instead of checking whether two labels co-occur. That is a "
        "harder feature, but it is the version of \u201contology coverage\u201d "
        "that could plausibly estimate sufficiency. Fourth, specialty-aware "
        "thresholds are tempting because the judge behaves differently in "
        "method-oriented categories, but our experiments with class-aware gates "
        "overfit badly at the current data size; they should be revisited "
        "only with more development rows. Finally, the system should be "
        "tested with a different judge model and with a short rationale field, "
        "to see whether explanations improve trust without hurting the "
        "calibration of the \u201cmaybe\u201d signal."
    )

    # ---------------- 8 Conclusion ----------------
    h1(doc, "8. Conclusion")
    para(
        doc,
        "OntoGate-RAG shows that a small, cheap language-model judgement can "
        "make a biomedical RAG system selective. One structured call per "
        "question, asking for a sufficiency label and a provisional answer, "
        "produces a signal strong enough to raise accuracy from 58.8% to "
        "78.2% while answering 65.2% of questions on a held-out test half. "
        "The fitted gate that achieves this turns out to make exactly the "
        "same decisions as a rule that trusts only fully confident, "
        "non-\u201cmaybe\u201d outputs, so the learning adds interpretability "
        "rather than accuracy."
    )
    para(
        doc,
        "The ontology plays a different role than we originally expected. "
        "MeSH and Hetionet coverage is a near-chance accuracy signal on this "
        "corpus, and ontology-aware reranking and query expansion do not "
        "improve an already saturated retriever. Used as a pre-screen, "
        "however, coverage removes 19.4% of paid judge calls at a cost of 0.9 "
        "accuracy points. Reporting that honestly is part of the "
        "contribution: it delimits when curated biomedical knowledge helps a "
        "question-answering system, and when the evidence itself already "
        "contains everything the graph can say."
    )

    # ---------------- References ----------------
    h1(doc, "References")
    references = [
        "[1] Q. Jin, B. Dhingra, Z. Liu, W. W. Cohen, and X. Lu, \u201cPubMedQA: A dataset for biomedical research question answering,\u201d in Proc. EMNLP-IJCNLP, 2019, pp. 2567\u20132577.",
        "[2] P. Lewis et al., \u201cRetrieval-augmented generation for knowledge-intensive NLP tasks,\u201d in Proc. NeurIPS, 2020.",
        "[3] A. Asai, Z. Wu, Y. Wang, A. Sil, and H. Hajishirzi, \u201cSelf-RAG: Learning to retrieve, generate and critique through self-reflection,\u201d in Proc. ICLR, 2024.",
        "[4] Y. Geifman and R. El-Yaniv, \u201cSelective classification for deep neural networks,\u201d in Proc. NeurIPS, 2017.",
        "[5] C. K. Chow, \u201cOn optimum recognition error and reject tradeoff,\u201d IEEE Trans. Inf. Theory, vol. 16, no. 1, pp. 41\u201346, 1970.",
        "[6] D. S. Himmelstein et al., \u201cSystematic integration of biomedical knowledge prioritizes drugs for repurposing,\u201d eLife, vol. 6, e26726, 2017.",
        "[7] O. Bodenreider, \u201cThe Unified Medical Language System (UMLS): Integrating biomedical terminology,\u201d Nucleic Acids Research, vol. 32, suppl. 1, pp. D267\u2013D270, 2004.",
        "[8] U.S. National Library of Medicine, \u201cMedical Subject Headings (MeSH),\u201d 2026. [Online]. Available: https://www.nlm.nih.gov/mesh/",
        "[9] S. Kadavath et al., \u201cLanguage models (mostly) know what they know,\u201d arXiv:2207.05221, 2022.",
        "[10] S. Lin, J. Hilton, and O. Evans, \u201cTeaching models to express their uncertainty in words,\u201d Trans. Machine Learning Research, 2022.",
        "[11] M. Xiong et al., \u201cCan LLMs express their uncertainty? An empirical evaluation of confidence elicitation in LLMs,\u201d in Proc. ICLR, 2024.",
        "[12] J. Kuhn, Y. Gal, and S. Farquhar, \u201cSemantic uncertainty: Linguistic invariances for uncertainty estimation in natural language generation,\u201d in Proc. ICLR, 2023.",
        "[13] N. Thakur, N. Reimers, A. R\u00fcckl\u00e9, A. Srivastava, and I. Gurevych, \u201cBEIR: A heterogeneous benchmark for zero-shot evaluation of information retrieval models,\u201d in Proc. NeurIPS Datasets and Benchmarks, 2021.",
        "[14] D. Wadden et al., \u201cFact or fiction: Verifying scientific claims,\u201d in Proc. EMNLP, 2020.",
        "[15] Q. Jin, W. Kim, Q. Chen, D. C. Comeau, L. Yeganova, W. J. Wilbur, and Z. Lu, \u201cMedCPT: Contrastive pre-trained transformers with large-scale PubMed search logs for zero-shot biomedical information retrieval,\u201d Bioinformatics, vol. 39, no. 11, btad651, 2023.",
        "[16] N. Reimers and I. Gurevych, \u201cSentence-BERT: Sentence embeddings using Siamese BERT-networks,\u201d in Proc. EMNLP-IJCNLP, 2019.",
        "[17] J. Johnson, M. Douze, and H. J\u00e9gou, \u201cBillion-scale similarity search with GPUs,\u201d IEEE Trans. Big Data, vol. 7, no. 3, pp. 535\u2013547, 2021.",
        "[18] Google, \u201cGemini API documentation,\u201d 2026. [Online]. Available: https://ai.google.dev/",
    ]
    for reference in references:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.9)
        p.paragraph_format.first_line_indent = Cm(-0.9)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.05
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(reference)
        run.font.size = Pt(9)

    out_path = PAPER_DIR / "OntoGate-RAG-paper.docx"
    doc.save(out_path)
    return out_path


if __name__ == "__main__":
    path = build()
    print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KB)")
