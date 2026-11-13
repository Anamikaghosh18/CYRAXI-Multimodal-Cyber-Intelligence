# CYRAXI — Multimodal Cybercrime Intelligence Platform

CYRAXI is a multimodal AI platform for phishing detection and digital forensics. It fuses signals from five analysis modalities — URL structure, HTML content, OCR, computer vision, and multimodal fusion — into a unified verdict, backed by a knowledge graph for campaign attribution.

---

## Modules

| Module | Description |
|---|---|
| **Dataset Adapter** | Streams and indexes the phishing dataset into a canonical observation manifest |
| **URL Analysis** | Extracts lexical and statistical indicators from raw URLs to classify phishing intent |
| **HTML / NLP Analysis** | Parses page structure, form actions, and text semantics to detect credential harvesting |
| **OCR Extraction** | Reads rendered text from page screenshots to surface hidden phishing indicators |
| **Computer Vision** | Matches visual brand logos against a reference gallery to detect impersonation |
| **Multimodal Fusion** | Combines all modality outputs into a single calibrated verdict with conflict detection |
| **Knowledge Graph** | Maps observations, predictions, domains, brands, and campaigns into a graph for relational reasoning |
| **Evaluation & Dashboard** | Benchmarks each modality and presents results through a web dashboard |

---

## Documentation

- [Project Overview](docs/CYRAXI_PROJECT_OVERVIEW.md) — architecture, module pipeline, benchmark results, graph schema, and API reference
- [Metrics Report](docs/evaluation/CYRAXI_MULTIMODAL_METRICS_REPORT.md) — cross-validation benchmarks and evaluation figures

