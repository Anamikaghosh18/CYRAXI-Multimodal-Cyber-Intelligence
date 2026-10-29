# CYRAXI: Multimodal Cybercrime Intelligence Platform

CYRAXI is a multimodal cybercrime intelligence platform designed to detect, analyze, and attribute phishing infrastructure and campaigns by fusing:
- **URL & Network Analysis:** Lexical, entropy, ASN, and DNS features
- **HTML & NLP Analysis:** DOM structure, form actions, and credential-harvesting intent
- **OCR:** Optical character recognition of rendered text from page screenshots
- **Computer Vision:** Visual logo detection and Siamese visual similarity matching
- **Multimodal Evidence Fusion:** Calibrated reweighting and identity-conflict assessment
- **Neo4j Knowledge Graph:** Relational mapping connecting URLs, hosts, captures, evidence, and campaign candidates

For a client-ready product overview and demo script, see [Client Demo Talk Track](docs/CLIENT_DEMO_TALK_TRACK.md).

## Run the backend

From the repository root, run `python backend_main.py`. This starts the investigation API on port 8002 and the graph API on port 8001. Press Ctrl+C to stop both services. Neo4j must be running for graph-backed requests.

For the local RustFS artifact-storage workflow, follow [Local RustFS setup](docs/RUSTFS_LOCAL_SETUP.md). In short: copy `.env.example` to `.env`, install `requirements-rustfs.txt`, run `docker compose up -d neo4j rustfs`, import the archive with `python scripts/import_archive_to_rustfs.py`, then start the backend. RustFS stores the archive evidence; Neo4j remains the attack index and graph.

## Run the dashboard

In a second terminal, run `cd frontend` followed by `npm run dev`, then open the local URL printed by Vite. Select attack records for a run, then review the evidence and graph in each saved report.

---

## 🧭 Multi-Team Guide & Architecture Navigation

Before writing module code, every team member must follow the canonical contracts:

- 📖 **[Central Team Contracts Guide](docs/contracts/DATA_CONTRACTS_README.md)**: Universal rules, identifiers, missing artifact conventions.
- 📐 **[Canonical Observation Schema](schemas/observation.schema.json)**: The ground-truth input contract for every capture.
- 📦 **[Model Output Envelope Schema](schemas/model-output.schema.json)**: The unified envelope every model output must return.
- 📜 **[Model Module Contracts](docs/contracts/MODEL_CONTRACTS.md)**: Exact input/output specifications for URL, HTML, OCR, CV, and Fusion modules.
- 🕸️ **[Neo4j Knowledge Graph Model](docs/architecture/NEO4J_DATA_MODEL.md)**: Graph entities, relationships, constraints, and Cypher ingestion examples.
- 📊 **[Dataset Inventory & Modality Coverage](docs/dataset/DATASET_INVENTORY.md)**: Comprehensive analysis of the 30k Phishpedia archive.
- 📑 **[Manifest Specification](docs/dataset/PHISHPEDIA_MANIFEST_SPEC.md)**: Tabular index specification for streaming dataset iterations.
- 🚀 **[Modular Implementation Plan](docs/IMPLEMENTATION_PLAN.md)**: Roadmap, hardware requirements, and independent team tasks.
- ❓ **[Dataset Findings & Open Questions](docs/dataset/DATASET_FINDINGS_AND_OPEN_QUESTIONS.md)**: Key strategic questions and decisions.

---

## 🛠️ Repository Layout

```text
CYRAXI/
├── docs/
│   ├── dataset/
│   │   ├── DATASET_INVENTORY.md
│   │   ├── PHISHPEDIA_MANIFEST_SPEC.md
│   │   └── DATASET_FINDINGS_AND_OPEN_QUESTIONS.md
│   ├── contracts/
│   │   ├── DATA_CONTRACTS_README.md
│   │   └── MODEL_CONTRACTS.md
│   ├── architecture/
│   │   └── NEO4J_DATA_MODEL.md
│   └── IMPLEMENTATION_PLAN.md
├── schemas/
│   ├── observation.schema.json
│   └── model-output.schema.json
├── examples/
│   ├── sample_observation.json
│   └── sample_model_output.json
├── scripts/
│   └── validate_schemas.py
├── data/                       (Excluded from git, holds phish_sample_30k.zip)
└── README.md
```

---

## 🧪 Validating Contracts

Run the schema validation suite:

```bash
python scripts/validate_schemas.py
```
