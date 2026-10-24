# Real Medical Corpus

Place JSON document files here. Each file should follow this schema:

```json
{
    "doc_id": "pubmed_12345",
    "title": "Document title",
    "text": "Full document text content...",
    "source": "PubMed",
    "url": "https://...",
    "concepts": ["Hypertension", "ACEInhibitor"]
}
```

The `concepts` field should contain ontology concept local names (from medical_ontology.ttl) that this document covers. This is the ground-truth annotation used for evaluation.

## Sources to collect from:
- **PubMed**: Use `scripts/collect_pubmed.py` for automated download
- **MedlinePlus**: https://medlineplus.gov/
- **WHO**: https://www.who.int/news-room/fact-sheets
- **CDC**: https://www.cdc.gov/az/
- **Mayo Clinic**: https://www.mayoclinic.org/diseases-conditions
