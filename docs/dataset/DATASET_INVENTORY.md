# Phishpedia Dataset Inventory and Physical Audit

**Document Status:** Verified Baseline  
**Date of Audit:** October 2026  
**Auditor:** Multimodal Cybercrime Intelligence Platform Engineering Core  
**Dataset Reference:** `phishpedia_primary`  

---

## 1. Executive Summary

This document establishes the verified inventory, physical layout, modality coverage, annotation taxonomy, and operational limitations of the Phishpedia dataset archive present in the project workspace.

The repository initially contained only a 19.3 GB ZIP file located at `data/phish_sample_30k.zip`. Through direct, zero-extraction inspection of the archive's internal central directory headers and sample stream reads, the physical structure, metadata format, and modalities were completely determined without loading the full archive into memory or modifying original files.

---

## 2. Dataset Identification & Origin

- **Archive File:** `data/phish_sample_30k.zip`
- **Formal Dataset Identification:** Phishpedia 30k Phishing Benchmark Dataset
- **Academic Origin:** Lin et al., *"Phishpedia: A Hybrid Deep Learning Based Approach to Uncover Phishing Attacks"* (USENIX Security 2021).
- **Source Nature:** Raw phishing webpage crawls collected primarily between July 2019 and September 2020.
- **Local Location Resolution:** Configurable via environment variable `PHISHPEDIA_DATA_DIR` or `PHISHPEDIA_ARCHIVE_PATH` (defaulting to relative path `data/phish_sample_30k.zip`).

---

## 3. Physical Storage Metrics

The storage footprint and entry distribution were comprehensively measured:

| Metric | Measured Value |
|---|---|
| **Archive File Size (Compressed)** | 19,301,131,139 bytes (~17.98 GiB / 19.30 GB) |
| **Total Uncompressed Size** | 20,711,382,360 bytes (~19.29 GiB) |
| **Total Archive Entries** | 201,712 entries |
| **Unique Observation Directories** | 29,496 directories |
| **Overall Compression Ratio** | ~1.075:1 (low ratio due to pre-compressed PNG screenshots) |

### Storage & Count Breakdown by Extension

| File Extension | File Count | Uncompressed Size (MB) | Uncompressed Size (GB) | Primary Role |
|---|---|---|---|---|
| `.png` | 29,507 | 18,100.08 MB | 17.68 GB | Full webpage viewport screenshot (`shot.png`) |
| `.txt` | 142,590 | 1,651.52 MB | 1.61 GB | HTML DOM, metadata, OCR, coords, CSS |
| `.pwc` | 2 | 0.13 MB | < 0.01 GB | Archived crawled resource |
| `.css` | 6 | 0.11 MB | < 0.01 GB | Archived stylesheet |
| `.svg` | 27 | 0.04 MB | < 0.01 GB | Archived vector icons |
| `.html` | 1 | 0.02 MB | < 0.01 GB | Archived HTML subpage |
| `.ico` / `.gif` | 10 | 0.01 MB | < 0.01 GB | Archived favicon / media |

---

## 4. Directory Structure & Observation Architecture

The dataset is organized as a flat collection of **29,496 observation directories** directly inside the archive root:

```text
phish_sample_30k.zip
└── <BrandName>+<Timestamp>/
    ├── info.txt                  [Metadata & Network Annotation] (29,496 / 29,496 = 100%)
    ├── shot.png                  [Webpage Screenshot Image]      (29,496 / 29,496 = 100%)
    ├── yolo_coords.txt           [YOLO Logo Candidate BBoxes]    (29,496 / 29,496 = 100%)
    ├── html.txt                  [Raw Captured HTML Source]      (29,048 / 29,496 = 98.48%)
    ├── all_coordinates.txt       [All Detected Web Elements]     (18,236 / 29,496 = 61.83%)
    ├── html_overlap_yolo.txt     [HTML Element Overlap BBoxes]   (18,236 / 29,496 = 61.83%)
    ├── coordinates.txt           [Refined Element Coordinates]   ( 4,695 / 29,496 = 15.92%)
    ├── ocr.txt                   [Extracted Text Content]        ( 4,325 / 29,496 = 14.66%)
    ├── css_filename.txt          [External CSS URLs]             ( 2,745 / 29,496 =  9.31%)
    └── <0..N>.txt                [Locally Cached CSS Files]      (varies per capture)
```

### Observation Directory Key Format
Every directory name follows the pattern:
```
<BrandName>+<YYYY-MM-DD-HH`MM`SS>
```
*Note on Windows Paths:* The timestamp uses backticks (`` ` ``) rather than colons (`:`) as time separators to ensure filesystem compatibility across Windows and POSIX filesystems.

---

## 5. Metadata Schema & Annotation Fields (`info.txt`)

Every observation directory contains an `info.txt` file formatted as a Python stringified dictionary representation (`ast.literal_eval` compatible).

### Field Inventory & Sample Measurement

Based on stratified sampling across the entire archive:

| Field Name | Data Type | Completeness | Description / Example |
|---|---|---|---|
| `url` | `string` | **100.0%** | Full phishing landing URL (e.g., `http://serv-acamai.com/1und1/de/index.php`) |
| `brand` | `string` | **100.0%** | Targeted legitimate brand (e.g., `1&1 Ionos`, `PayPal Inc.`, `Outlook`) |
| `sector` | `string` | **100.0%** | Industry sector (e.g., `Email Provider`, `Financial`, `Online Services`) |
| `ip` | `string` | **100.0%** | Resolved IPv4 host address at capture time (e.g., `46.30.213.230`) |
| `isotime` | `string (ISO-8601)` | **100.0%** | ISO timestamp of discovery (e.g., `2019-07-02T21:14:13Z`) |
| `discover_time` | `string` | **98.4%** | Human-readable discovery time (`02-07-2019 21:14:13 UTC`) |
| `host` | `string` | **98.4%** | Hostname/FQDN (e.g., `serv-acamai.com`) |
| `tld` | `string` | **98.4%** | Top-level domain / public suffix (e.g., `com`, `net.pl`) |
| `country_code` | `string (2-char)`| **98.4%** | ISO 3166-1 alpha-2 country of IP (e.g., `DK`, `US`, `VN`) |
| `country_name` | `string` | **98.4%** | Full country name (e.g., `Denmark`, `United States of America`) |
| `asn` | `string` | **98.4%** | Autonomous System Number (e.g., `AS51468`) |
| `asn_name` | `string` | **98.4%** | AS Organization (e.g., `One.com A/S`, `Unified Layer`) |
| `family_id` | `string (md5)` | **98.4%** | Phishing cluster / campaign identifier hash |
| `emails` | `list[string]` | **54.3%** | Extracted contact/drop emails (frequently empty `[]`) |
| `phishing_kit` | `string / null`| **50.8%** | Identified phishing kit signature (or `null`) |

---

## 6. Modality Inventory & Coverage Analysis

| Modality / Artifact | Present Observations | Total Coverage | Status & Verification |
|---|---|---|---|
| **URL & Network Metadata** | 29,496 | **100.00%** | Ground truth network indicators, brand, sector |
| **Screenshot (`shot.png`)** | 29,496 | **100.00%** | High-resolution PNG captures (17.68 GB total) |
| **YOLO Boxes (`yolo_coords.txt`)** | 29,496 | **100.00%** | Precomputed bounding boxes with confidence scores |
| **HTML Source (`html.txt`)** | 29,048 | **98.48%** | Raw HTML DOM text; 448 captures lack HTML |
| **HTML Overlap BBoxes** | 18,236 | **61.83%** | Cross-modal mapping between DOM elements and visual boxes |
| **OCR Text (`ocr.txt`)** | 4,325 | **14.66%** | Partial precomputed OCR; **85.34% missing** |
| **Reference Logos / Checkpoints** | 0 in archive | **0.00%** | No weights, models, or brand logo gallery in archive |
| **Benign Baseline Dataset** | 0 in archive | **0.00%** | **Entire archive is positive phishing instances** |

---

## 7. Label Definitions & Class Distribution

1. **Phishing vs. Benign:**
   - The entire archive consists strictly of **confirmed phishing sites**.
   - No benign captures exist in `phish_sample_30k.zip`.
   - **Crucial Engineering Requirement:** For training or evaluating binary classifiers (Phishing vs. Benign), a separate benign corpus (e.g., Tranco/Alexa top 10k captures) must be ingested under the same canonical schema.

2. **Target Brand Distribution:**
   - Sample analysis across 1,000+ observations reveals high concentration among top tech, banking, and email providers:
     - Outlook / Office365: ~23.4%
     - PayPal: ~16.3%
     - Chase, Bank of America, Wells Fargo: ~8.5%
     - Facebook, Netflix, Amazon, Apple, DHL, Adobe: ~15.2%
     - Long tail of international banks and online services across 200+ distinct brands.

3. **Temporal Distribution:**
   - 2019: ~17.3%
   - 2020: ~82.7%

---

## 8. Missing, Incomplete, and Anomalous Artifacts

1. **OCR Text Sparse Coverage:** Only 14.66% of directories contain `ocr.txt`. The platform's OCR module cannot rely on existing files; it must be implemented as an active inference service running on `shot.png`.
2. **Missing HTML:** 448 captures (~1.5%) lack `html.txt`. The HTML/NLP pipeline must gracefully produce `partial` or `skipped` status with warnings.
3. **Missing Phishpedia Logo Database & Checkpoints:** The archive does *not* contain the reference logo target database (the ~200+ legitimate brand logo embeddings used by Phishpedia) or YOLO/Siamese weights. These must be sourced or provided separately.
4. **Encoding Artifacts:** Text files (especially OCR and HTML) contain arbitrary international encodings (CP1252, ISO-8859-1, UTF-8 with BOM). Parsers must use resilient decoding (`errors='replace'`).

---

## 9. Licensing, Attribution, and Usage Restrictions

- **Source:** Lin et al., USENIX Security 2021.
- **Academic Research License:** Intended for academic security research. Contains live phishing domains and malicious code.
- **Handling Constraints:**
  - Artifacts must never be served directly to untrusted web clients without `X-Content-Type-Options: nosniff` and sanitization.
  - Active links must be defanged in user-facing reports.
  - No phishing kits or drop emails may be queried or executed against external networks.

---

## 10. Recommended Next Steps

1. Adopt the canonical schema (`schemas/observation.schema.json`) for all data ingestion.
2. Build an streaming zip reader adapter (`scripts/manifest_generator.py`) to create index manifests without extracting the 19 GB zip to disk.
3. Formulate an external benign ingestion pipeline to complement the 30k phishing dataset for balanced model evaluation.
