# Local RustFS artifact storage

CYRAXI uses Neo4j for attack metadata and graph relationships. RustFS stores the captured HTML, OCR text, screenshots, and other archive files. The investigation report reads those objects by the observation's `source_record_id`.

The S3 object keys keep the archive's existing names, for example `record-123/html.txt` and `record-123/shot.png`. This lets the current Neo4j index continue to select records while the evidence is served from RustFS.

## Start the local services

From the repository root in PowerShell:

```powershell
Copy-Item .env.example .env
```

For a local demo, the example has matching development credentials for Docker Compose and the backend. If you change them, update `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` in `.env`; Compose passes those same values to RustFS. Do not expose the development credentials beyond your machine.

Install the optional S3 client and start Neo4j and RustFS:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements-rustfs.txt
docker compose up -d neo4j rustfs
```

- RustFS S3 API: `http://localhost:9000`
- RustFS console: `http://localhost:9001`
- Neo4j Browser: `http://localhost:7474`

RustFS persists data in the `rustfs_data` Docker volume.

## Import the archive

Make sure `PHISHPEDIA_ARCHIVE_PATH` in `.env` points to the local ZIP, then run:

```powershell
python scripts/import_archive_to_rustfs.py
```

The importer streams each ZIP entry into the `S3_BUCKET` bucket. It does not extract the archive to a temporary directory. It creates the bucket if needed and can be rerun; matching object keys are replaced. Use `--limit-files 20` for a small connection check before starting the full import.

The uploaded object data can require more disk space than the compressed ZIP. Keep enough space on the disk backing Docker's `rustfs_data` volume. The importer only moves evidence objects; it does not create or update Neo4j attack records.

## Run CYRAXI

Keep this setting in `.env`:

```dotenv
CYRAXI_ARTIFACT_STORAGE=s3
```

Then start the APIs and frontend as usual:

```powershell
python backend_main.py
```

In another terminal:

```powershell
cd frontend
npm run dev
```

The workflow stays the same: choose random or specific records from Neo4j, run analysis, and open each report. HTML, OCR, screenshot, and coordinate artifacts are fetched from RustFS while analysis runs. Neo4j must already contain the indexed attack metadata and relationships.

To switch back to reading evidence directly from the ZIP, set `CYRAXI_ARTIFACT_STORAGE=zip` in `.env` and restart the backend.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `CYRAXI_ARTIFACT_STORAGE` | `s3` in `.env.example` | Select `s3` or `zip` for evidence reads |
| `S3_ENDPOINT_URL` | `http://localhost:9000` | RustFS S3 API URL from the host backend |
| `S3_BUCKET` | `cyraxi-artifacts` | Bucket used for evidence objects |
| `S3_REGION` | `us-east-1` | S3 signing region |
| `S3_ACCESS_KEY_ID` | `cyraxiadmin` | Backend's RustFS access key |
| `S3_SECRET_ACCESS_KEY` | development value in `.env.example` | Backend's RustFS secret |
| `PHISHPEDIA_ARCHIVE_PATH` | `data/phish_sample_30k.zip` | Source ZIP read by the importer |
