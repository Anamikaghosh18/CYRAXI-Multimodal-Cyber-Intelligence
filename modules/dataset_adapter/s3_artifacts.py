"""RustFS/S3 artifact storage used by local CYRAXI investigations."""

import os
from pathlib import Path


def load_project_env() -> None:
    """Load simple KEY=VALUE entries from the repository .env without overwriting shell values."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


class S3ArtifactStore:
    """Read archived evidence from a local S3-compatible bucket such as RustFS."""

    def __init__(self, endpoint_url=None, bucket=None, region=None, access_key=None, secret_key=None):
        load_project_env()
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise RuntimeError(
                "RustFS artifact storage requires boto3. Install it with "
                "`pip install -r requirements-rustfs.txt`."
            ) from exc

        self.bucket = bucket or os.getenv("S3_BUCKET", "cyraxi-artifacts")
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or os.getenv("S3_ENDPOINT_URL", "http://localhost:9000"),
            region_name=region or os.getenv("S3_REGION", "us-east-1"),
            aws_access_key_id=access_key or os.getenv("S3_ACCESS_KEY_ID", "cyraxiadmin"),
            aws_secret_access_key=secret_key or os.getenv("S3_SECRET_ACCESS_KEY", "cyraxi-local-change-this"),
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def read_bytes(self, object_key: str):
        """Return object bytes, or None when the artifact key is absent."""
        from botocore.exceptions import ClientError

        try:
            response = self.client.get_object(Bucket=self.bucket, Key=object_key)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"NoSuchKey", "NoSuchObject", "404", "NotFound"}:
                return None
            raise
        body = response["Body"]
        try:
            return body.read()
        finally:
            body.close()
