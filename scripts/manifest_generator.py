import argparse
import csv
import json
import sys
from pathlib import Path

# Make the project root importable when this script is run directly.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.dataset_adapter.reader import PhishpediaDatasetReader


def generate_manifest(archive, output_dir, limit=0, offset=0):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = output_dir / "phishpedia_manifest.jsonl"
    csv_path = output_dir / "phishpedia_manifest.csv"

    count = 0
    reader = PhishpediaDatasetReader(str(archive))

    # Only a compact set of fields goes into the CSV.
    csv_fields = [
        "observation_id",
        "source_record_id",
        "url",
        "normalized_label",
        "has_screenshot",
        "has_html",
        "has_ocr",
    ]

    with jsonl_path.open("w", encoding="utf-8") as jsonl_file, \
         csv_path.open("w", encoding="utf-8", newline="") as csv_file:

        writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
        writer.writeheader()

        stream_limit = limit if limit > 0 else 2**63 - 1

        for obs in reader.stream_observations(
            limit=stream_limit, offset=offset
        ):
            jsonl_file.write(
                json.dumps(obs, ensure_ascii=False) + "\n"
            )

            row = {
                "observation_id": obs.get("observation_id", ""),
                "source_record_id": obs.get("source_record_id", ""),
                "url": obs.get("url", {}).get("raw", ""),
                "normalized_label": (
                    obs.get("label", {})
                    .get("ground_truth", {})
                    .get("normalized_label", "unknown")
                ),
                "has_screenshot": obs.get("availability", {}).get(
                    "has_screenshot", False
                ),
                "has_html": obs.get("availability", {}).get("has_html", False),
                "has_ocr": obs.get("availability", {}).get("has_ocr", False),
            }
            writer.writerow(row)
            count += 1

    return count, jsonl_path, csv_path


def main():
    parser = argparse.ArgumentParser(
        description="Stream Phishpedia observations into JSONL and CSV manifests."
    )
    parser.add_argument(
        "--archive", default="data/phish_sample_30k.zip",
        help="Path to the dataset ZIP archive."
    )
    parser.add_argument(
        "--output-dir", default="outputs/manifest",
        help="Directory in which to write the manifest files."
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Maximum records to process; 0 means all records."
    )
    parser.add_argument("--offset", type=int, default=0)

    args = parser.parse_args()

    if args.limit < 0 or args.offset < 0:
        parser.error("--limit and --offset cannot be negative")

    try:
        count, jsonl_path, csv_path = generate_manifest(
            args.archive,
            args.output_dir,
            args.limit,
            args.offset,
        )
    except FileNotFoundError as exc:
        print(f"Dataset not found: {exc}", file=sys.stderr)
        print(
            "Place the archive at the configured path, or pass --archive.",
            file=sys.stderr,
        )
        return 1

    print(f"Records written: {count}")
    print(f"JSONL manifest: {jsonl_path}")
    print(f"CSV manifest: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
