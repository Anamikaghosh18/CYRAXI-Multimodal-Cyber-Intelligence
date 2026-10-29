"""Stream Phishpedia ZIP entries into a local RustFS/S3 bucket."""

import argparse
import mimetypes
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.dataset_adapter.s3_artifacts import load_project_env


def _object_key(name: str) -> str | None:
    key = name.replace("\\", "/").lstrip("/")
    parts = key.split("/")
    if not key or any(part in {"", ".", ".."} for part in parts):
        return None
    return key


def _ensure_bucket(client, bucket: str) -> None:
    from botocore.exceptions import ClientError

    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code not in {"404", "NoSuchBucket", "NotFound"}:
            raise
        client.create_bucket(Bucket=bucket)


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", default=os.getenv("PHISHPEDIA_ARCHIVE_PATH", "data/phish_sample_30k.zip"))
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET", "cyraxi-artifacts"))
    parser.add_argument("--limit-files", type=int, default=0, help="Upload only the first N files (0 means all).")
    args = parser.parse_args()

    archive_path = Path(args.archive)
    if not archive_path.is_file():
        parser.error(f"Archive not found: {archive_path}")

    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        print("RustFS import requires boto3. Install it with: pip install -r requirements-rustfs.txt", file=sys.stderr)
        return 2

    client = boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT_URL", "http://localhost:9000"),
        region_name=os.getenv("S3_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID", "cyraxiadmin"),
        aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY", "cyraxi-local-change-this"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )

    print(f"Checking RustFS bucket '{args.bucket}' at {os.getenv('S3_ENDPOINT_URL', 'http://localhost:9000')}...")
    _ensure_bucket(client, args.bucket)

    uploaded = 0
    uploaded_bytes = 0
    skipped = 0
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                key = _object_key(info.filename)
                if key is None:
                    skipped += 1
                    continue
                content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
                with archive.open(info, "r") as body:
                    client.put_object(
                        Bucket=args.bucket,
                        Key=key,
                        Body=body,
                        ContentLength=info.file_size,
                        ContentType=content_type,
                    )
                uploaded += 1
                uploaded_bytes += info.file_size
                if uploaded % 250 == 0:
                    print(f"Uploaded {uploaded} objects ({uploaded_bytes / (1024 ** 3):.2f} GiB)...", flush=True)
                if args.limit_files and uploaded >= args.limit_files:
                    break
    except (OSError, zipfile.BadZipFile) as exc:
        print(f"Archive import failed: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()

    print(f"Import complete: {uploaded} objects, {uploaded_bytes / (1024 ** 3):.2f} GiB uploaded, {skipped} unsafe keys skipped.")
    print("You can now set CYRAXI_ARTIFACT_STORAGE=s3 and start the backend.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
