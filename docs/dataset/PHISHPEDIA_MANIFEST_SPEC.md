# Phishpedia Dataset Manifest Specification

**Document Version:** 1.0.0  
**Target Dataset:** `phishpedia_primary`  
**Purpose:** Define the canonical manifest tabular and JSON format mapping each webpage capture to its on-disk or in-archive artifacts.

---

## 1. Overview & Purpose

A manifest serves as the primary catalog and index for dataset iteration, batch inference, training splits, and database ingestion. Rather than unzipping 19 GB of data or walking directory trees during model execution, workers read the manifest to access exact relative paths, modality availability flags, and ground truth labels.

---

## 2. Manifest File Formats

The manifest is produced in two interchange formats:
1. **JSONL (`phishpedia_manifest.jsonl`)**: Highly structured, line-delimited canonical observation records matching `schemas/observation.schema.json`.
2. **Parquet / CSV (`phishpedia_manifest.csv`)**: Flattened tabular view for data science pipelines (Pandas/Polars/PyTorch Dataset).

---

## 3. Tabular Manifest Column Specification

| Column Name | Type | Required | Description & Mapping |
|---|---|---|---|
| `observation_id` | `string` | **Yes** | `obs_<md5(dataset_id + ':' + source_record_id)>` |
| `dataset_id` | `string` | **Yes** | Constant `phishpedia_primary` |
| `source_record_id` | `string` | **Yes** | Exact folder name in archive (e.g., `1&1 Ionos+2019-07-28-22`34`40`) |
| `url` | `string` | **Yes** | Landing URL from `info.txt['url']` |
| `host` | `string` | No | Extracted host/FQDN from `info.txt['host']` |
| `domain` | `string` | No | Registered domain (SLD + TLD) or null |
| `original_label` | `string` | **Yes** | Constant `'phishing'` for primary archive |
| `normalized_label` | `string` | **Yes** | Constant `'phishing'` |
| `target_brand` | `string` | **Yes** | Ground truth brand from `info.txt['brand']` |
| `target_sector` | `string` | No | Ground truth industry sector from `info.txt['sector']` |
| `ip` | `string` | No | Resolved IP from `info.txt['ip']` |
| `asn` | `string` | No | Autonomous System from `info.txt['asn']` |
| `asn_name` | `string` | No | AS Name from `info.txt['asn_name']` |
| `country_code` | `string` | No | 2-letter ISO country code from `info.txt['country_code']` |
| `family_id` | `string` | No | Campaign cluster ID from `info.txt['family_id']` |
| `captured_at` | `string` | **Yes** | ISO-8601 discovery timestamp from `info.txt['isotime']` |
| `screenshot_path` | `string` | **Yes** | Relative path to screenshot (e.g., `<folder>/shot.png`) |
| `html_path` | `string` | No | Relative path to HTML (e.g., `<folder>/html.txt`) or null |
| `ocr_path` | `string` | No | Relative path to precomputed OCR or null |
| `info_path` | `string` | **Yes** | Relative path to metadata (`<folder>/info.txt`) |
| `yolo_coords_path`| `string` | No | Relative path to YOLO box coordinates |
| `availability_status`| `string` | **Yes** | Enum: `full_multimodal`, `partial_no_ocr`, `partial_no_html`, `minimal` |
| `split` | `string` | No | Proposed split: `train`, `val`, `test`, or `unassigned` |

---

## 4. Path Resolution Rules

- All artifact paths (`screenshot_path`, `html_path`, etc.) are **relative** to the dataset root or archive root.
- Pipelines must never store machine-dependent paths (such as `C:\Desktop\...` or `/home/user/...`).
- To access an artifact:
  - If reading from extracted folder: `os.path.join(DATASET_ROOT, row['screenshot_path'])`
  - If reading directly from ZIP: `zf.open(row['screenshot_path'])`
  - In Windows environments, directory names contain backticks (`` ` ``) for timestamp colons; path helpers must preserve raw UTF-8 string encoding.

---

## 5. Duplicate and Unmatched File Handling

- **Duplicate URLs:** 1,018 sampled records showed 1,014 unique URLs. When identical URLs occur at different timestamps, each capture receives a distinct `observation_id` based on its directory name, but shares the same `URL` node in Neo4j.
- **Unmatched Artifacts:**
  - If `html.txt` is missing (448 instances in dataset), `html_path` is `null` and `availability_status` is flagged as `partial_no_html`.
  - If `ocr.txt` is missing (25,171 instances), `ocr_path` is `null` and `availability_status` is `partial_no_ocr`.
  - Missing modalities must never cause row drop or unhandled exceptions.

---

## 6. Representative Sample Records (Verified Real Inspections)

The following 5 rows are generated from direct inspection of actual records in `data/phish_sample_30k.zip`:

### Row 1
```json
{
  "observation_id": "obs_6f80a42371d377b212f45c4aa305609c",
  "dataset_id": "phishpedia_primary",
  "source_record_id": "1&1 Ionos+2019-07-28-22`34`40",
  "url": "http://serv-acamai.com/1und1/de/index.php",
  "host": "serv-acamai.com",
  "domain": "serv-acamai.com",
  "original_label": "phishing",
  "normalized_label": "phishing",
  "target_brand": "1&1 Ionos",
  "target_sector": "Online Services",
  "ip": "46.30.213.230",
  "asn": "AS51468",
  "asn_name": "One.com A/S",
  "country_code": "DK",
  "family_id": "a53630ccd2f8d0771873a43b98ae0c0d",
  "captured_at": "2019-07-02T21:14:13Z",
  "screenshot_path": "1&1 Ionos+2019-07-28-22`34`40/shot.png",
  "html_path": "1&1 Ionos+2019-07-28-22`34`40/html.txt",
  "ocr_path": "1&1 Ionos+2019-07-28-22`34`40/ocr.txt",
  "info_path": "1&1 Ionos+2019-07-28-22`34`40/info.txt",
  "yolo_coords_path": "1&1 Ionos+2019-07-28-22`34`40/yolo_coords.txt",
  "availability_status": "full_multimodal",
  "split": "unassigned"
}
```

### Row 2
```json
{
  "observation_id": "obs_bc2301cde954a234f9a12e8bcde59012",
  "dataset_id": "phishpedia_primary",
  "source_record_id": "1&1 Ionos+2020-08-28-13`52`06",
  "url": "http://formacioncis.com/defaultsite",
  "host": "formacioncis.com",
  "domain": "formacioncis.com",
  "original_label": "phishing",
  "normalized_label": "phishing",
  "target_brand": "1&1 Ionos",
  "target_sector": "Online Services",
  "ip": "217.160.0.28",
  "asn": "AS8560",
  "asn_name": "1&1 IONOS SE",
  "country_code": "DE",
  "family_id": "a9a07fabf6eeadccbb59823285653a41",
  "captured_at": "2020-08-27T04:23:11Z",
  "screenshot_path": "1&1 Ionos+2020-08-28-13`52`06/shot.png",
  "html_path": "1&1 Ionos+2020-08-28-13`52`06/html.txt",
  "ocr_path": null,
  "info_path": "1&1 Ionos+2020-08-28-13`52`06/info.txt",
  "yolo_coords_path": "1&1 Ionos+2020-08-28-13`52`06/yolo_coords.txt",
  "availability_status": "partial_no_ocr",
  "split": "unassigned"
}
```

### Row 3
```json
{
  "observation_id": "obs_33d87a41c2e0b540f2bc0a95e20d046f",
  "dataset_id": "phishpedia_primary",
  "source_record_id": "Banco Falabella+2020-08-13-18`29`27",
  "url": "https://www.htlp-wwv-crnr-cl.mitsp.org/personas-cl/",
  "host": "www.htlp-wwv-crnr-cl.mitsp.org",
  "domain": "mitsp.org",
  "original_label": "phishing",
  "normalized_label": "phishing",
  "target_brand": "Banco Falabella",
  "target_sector": "Financial",
  "ip": "162.144.123.218",
  "asn": "AS46606",
  "asn_name": "Unified Layer",
  "country_code": "US",
  "family_id": "2249e0c7a84e2bd9027f8a7e02df595b",
  "captured_at": "2020-08-11T08:08:20Z",
  "screenshot_path": "Banco Falabella+2020-08-13-18`29`27/shot.png",
  "html_path": "Banco Falabella+2020-08-13-18`29`27/html.txt",
  "ocr_path": null,
  "info_path": "Banco Falabella+2020-08-13-18`29`27/info.txt",
  "yolo_coords_path": "Banco Falabella+2020-08-13-18`29`27/yolo_coords.txt",
  "availability_status": "partial_no_ocr",
  "split": "unassigned"
}
```

### Row 4
```json
{
  "observation_id": "obs_4c119e8306df5f8a0cb8b5f3a0982bb2",
  "dataset_id": "phishpedia_primary",
  "source_record_id": "Absa Group+2020-05-18-12`59`58",
  "url": "http://congnghetuoitudong.com/oncr/nsra.html",
  "host": "congnghetuoitudong.com",
  "domain": "congnghetuoitudong.com",
  "original_label": "phishing",
  "normalized_label": "phishing",
  "target_brand": "Absa Group",
  "target_sector": "Financial",
  "ip": "163.44.194.54",
  "asn": "AS131392",
  "asn_name": "GMO-Z.com Runsystem Joint Stock Company",
  "country_code": "VN",
  "family_id": "4abb831c47bde028bb2793c0ea63ef3a",
  "captured_at": "2020-05-15T11:50:10Z",
  "screenshot_path": "Absa Group+2020-05-18-12`59`58/shot.png",
  "html_path": "Absa Group+2020-05-18-12`59`58/html.txt",
  "ocr_path": null,
  "info_path": "Absa Group+2020-05-18-12`59`58/info.txt",
  "yolo_coords_path": "Absa Group+2020-05-18-12`59`58/yolo_coords.txt",
  "availability_status": "partial_no_ocr",
  "split": "unassigned"
}
```

### Row 5
```json
{
  "observation_id": "obs_94df223405f6966113b28b49e0c51ae7",
  "dataset_id": "phishpedia_primary",
  "source_record_id": "Adobe Inc.+2019-07-29-00`23`23",
  "url": "http://meeramu.com/images/privfile",
  "host": "meeramu.com",
  "domain": "meeramu.com",
  "original_label": "phishing",
  "normalized_label": "phishing",
  "target_brand": "Adobe Inc.",
  "target_sector": "Online Services",
  "ip": "184.154.21.178",
  "asn": "AS32475",
  "asn_name": "SingleHop LLC",
  "country_code": "US",
  "family_id": "fd58c372752ce92c8f43c40b4fdd138f",
  "captured_at": "2019-07-10T12:18:19Z",
  "screenshot_path": "Adobe Inc.+2019-07-29-00`23`23/shot.png",
  "html_path": "Adobe Inc.+2019-07-29-00`23`23/html.txt",
  "ocr_path": null,
  "info_path": "Adobe Inc.+2019-07-29-00`23`23/info.txt",
  "yolo_coords_path": "Adobe Inc.+2019-07-29-00`23`23/yolo_coords.txt",
  "availability_status": "partial_no_ocr",
  "split": "unassigned"
}
```
