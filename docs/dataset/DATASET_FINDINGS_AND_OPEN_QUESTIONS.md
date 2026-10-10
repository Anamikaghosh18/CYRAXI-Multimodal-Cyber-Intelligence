# Dataset Findings & Open Questions

**Document Status:** Open Engineering Decisions & Analysis  
**Audience:** Project Lead, Core ML Engineers, Infrastructure Team  

---

## 1. Summary of Confirmed Findings

1. **Physical Layout:** Single uncompressed/compressed ZIP `data/phish_sample_30k.zip` (17.98 GB compressed, 19.29 GB uncompressed) containing 29,496 observation directories.
2. **Missing Modalities:**
   - Precomputed OCR text (`ocr.txt`) is only present in 4,325 captures (**14.66%**). Active OCR must be performed on `shot.png`.
   - Raw HTML DOM (`html.txt`) is missing in 448 captures (**1.52%**).
3. **Class Skew:** The entire dataset of 29,496 captures represents **100% positive phishing instances**.
4. **Missing Checkpoints & Reference Brand Database:** The archive does not contain the original Phishpedia logo reference set or model weights.

---

## 2. Key Decisions & Open Questions for Project Lead

### Decision 1: Source for Benign Benchmark Data
- **Problem:** Because `phish_sample_30k.zip` is purely phishing samples, training or evaluating a binary classification model (phishing vs. benign) directly on this dataset will produce trivial 100% positive class shortcuts.
- **Proposed Solution:** Ingest a complementary benchmark of benign captures (e.g. top 10,000 domains from the Tranco / Alexa list captured via Playwright/Puppeteer) adhering strictly to `schemas/observation.schema.json` with `label.ground_truth.normalized_label: "benign"`.

### Decision 2: In-Memory / Streaming vs. Extraction Strategy
- **Problem:** Extracting 201,712 individual files onto a Windows filesystem can degrade I/O performance and consume over 20 GB of local storage.
- **Proposed Solution:** Implement an indexed zip-stream reader adapter in Python (`scripts/manifest_generator.py`) that reads directly from the ZIP file using byte offsets or standard zip streaming, avoiding extraction altogether.

### Decision 3: Logo Reference Database Sourcing
- **Problem:** Phishpedia’s logo matching requires reference brand logos (icons, clean vector images) to compute visual embedding similarity.
- **Proposed Solution:** Compile a curated brand target gallery for the top 50 targeted brands observed in the dataset (Outlook, PayPal, Chase, Microsoft, Facebook, Apple, etc.) stored in `data/reference_brands/`.
