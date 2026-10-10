"""
Dataset Adapter & Manifest Generator
Stream-reads observation directories from Phishpedia zip archives or extracted folders
and converts them into canonical Observation instances or tabular manifest rows.
Never loads the full dataset into memory.
"""

import ast
import hashlib
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Dict, Any, Optional, List
from urllib.parse import urlparse


def generate_observation_id(dataset_id: str, source_record_id: str) -> str:
    """Generate deterministic observation identifier: obs_<md5(dataset_id + ':' + source_record_id)>."""
    seed = f"{dataset_id}:{source_record_id}".encode("utf-8")
    return f"obs_{hashlib.md5(seed).hexdigest()}"


def parse_info_content(content_str: str) -> Dict[str, Any]:
    """Parse python-dict format info.txt string into a dictionary."""
    content_str = content_str.strip()
    if not content_str:
        return {}
    try:
        return ast.literal_eval(content_str)
    except Exception:
        # Fallback regex extraction if malformed syntax occurs
        data = {}
        for line in content_str.splitlines():
            line = line.strip().rstrip(",")
            if ":" in line:
                parts = line.split(":", 1)
                k = parts[0].strip().strip("'\"")
                v = parts[1].strip().strip("'\"")
                data[k] = v
        return data


def parse_url_components(raw_url: str) -> Dict[str, Any]:
    """Parse raw URL into structured components without external dependencies."""
    if not raw_url:
        return {
            "raw": "",
            "scheme": "unknown",
            "host": None,
            "domain": None,
            "subdomain": None,
            "tld": None,
            "port": None,
            "path": None,
            "query": None
        }

    parsed = urlparse(raw_url)
    scheme = parsed.scheme.lower() if parsed.scheme in ["http", "https", "ftp"] else "unknown"
    netloc = parsed.netloc or ""
    
    # Strip port if present
    host = netloc.split(":")[0] if ":" in netloc else netloc
    host = host.lower().strip() if host else None
    
    port = parsed.port if parsed.port else None
    path = parsed.path if parsed.path else None
    query = parsed.query if parsed.query else None
    
    # Simple registered domain extraction
    domain = None
    subdomain = None
    tld = None
    if host:
        # Check if IP address
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", host):
            domain = host
        else:
            host_parts = host.split(".")
            if len(host_parts) >= 2:
                # Handle common multi-part suffixes like .co.uk, .com.au, .net.pl
                if len(host_parts) >= 3 and host_parts[-2] in ["co", "com", "net", "org", "gov", "edu"]:
                    domain = ".".join(host_parts[-3:])
                    tld = ".".join(host_parts[-2:])
                    subdomain = ".".join(host_parts[:-3]) if len(host_parts) > 3 else None
                else:
                    domain = ".".join(host_parts[-2:])
                    tld = host_parts[-1]
                    subdomain = ".".join(host_parts[:-2]) if len(host_parts) > 2 else None
            else:
                domain = host

    return {
        "raw": raw_url,
        "scheme": scheme,
        "host": host,
        "domain": domain,
        "subdomain": subdomain,
        "tld": tld,
        "port": port,
        "path": path,
        "query": query
    }


def record_to_canonical_observation(
    dataset_id: str,
    source_record_id: str,
    info_dict: Dict[str, Any],
    available_files: List[str],
    source_archive_path: str,
    split: Optional[str] = None
) -> Dict[str, Any]:
    """Convert an inspected record into a canonical observation dictionary conforming to observation.schema.json."""
    obs_id = generate_observation_id(dataset_id, source_record_id)
    raw_url = info_dict.get("url") or ""
    url_comps = parse_url_components(raw_url)
    
    captured_at = info_dict.get("isotime")
    if not captured_at:
        captured_at = datetime.now(timezone.utc).isoformat()
    elif not captured_at.endswith("Z") and "+" not in captured_at:
        captured_at = f"{captured_at}Z"

    # Artifact availability
    has_screenshot = "shot.png" in available_files
    has_html = "html.txt" in available_files
    has_ocr = "ocr.txt" in available_files
    has_metadata = "info.txt" in available_files
    has_yolo_coords = "yolo_coords.txt" in available_files
    has_html_overlap = "html_overlap_yolo.txt" in available_files

    canonical = {
        "schema_version": "1.0.0",
        "observation_id": obs_id,
        "dataset": {
            "dataset_id": dataset_id,
            "version": "1.0.0",
            "split": split
        },
        "source_record_id": source_record_id,
        "source": {
            "collector_type": "phishpedia_crawler",
            "feed_name": "phishpedia_usenix21_crawl",
            "family_id": info_dict.get("family_id"),
            "phishing_kit": info_dict.get("phishing_kit")
        },
        "url": url_comps,
        "network": {
            "ip": info_dict.get("ip"),
            "asn": info_dict.get("asn"),
            "asn_name": info_dict.get("asn_name"),
            "country_code": info_dict.get("country_code"),
            "country_name": info_dict.get("country_name")
        },
        "label": {
            "ground_truth": {
                "original_label": "phishing",
                "normalized_label": "phishing",
                "target_brand": info_dict.get("brand"),
                "target_sector": info_dict.get("sector"),
                "confidence": 1.0
            }
        },
        "artifacts": {
            "screenshot": {
                "relative_path": f"{source_record_id}/shot.png",
                "format": "png",
                "storage_medium": "zip_entry" if source_archive_path.endswith(".zip") else "filesystem"
            },
            "html": {
                "relative_path": f"{source_record_id}/html.txt",
                "encoding": "utf-8",
                "storage_medium": "zip_entry" if source_archive_path.endswith(".zip") else "filesystem"
            } if has_html else None,
            "ocr": {
                "relative_path": f"{source_record_id}/ocr.txt",
                "storage_medium": "zip_entry" if source_archive_path.endswith(".zip") else "filesystem"
            } if has_ocr else None,
            "metadata_annotation": {
                "relative_path": f"{source_record_id}/info.txt",
                "storage_medium": "zip_entry" if source_archive_path.endswith(".zip") else "filesystem"
            },
            "auxiliary": {
                "yolo_coords_path": f"{source_record_id}/yolo_coords.txt" if has_yolo_coords else None,
                "all_coordinates_path": f"{source_record_id}/all_coordinates.txt" if "all_coordinates.txt" in available_files else None,
                "html_overlap_yolo_path": f"{source_record_id}/html_overlap_yolo.txt" if has_html_overlap else None,
                "css_filename_path": f"{source_record_id}/css_filename.txt" if "css_filename.txt" in available_files else None
            }
        },
        "availability": {
            "has_screenshot": has_screenshot,
            "has_html": has_html,
            "has_ocr": has_ocr,
            "has_metadata": has_metadata,
            "has_yolo_coords": has_yolo_coords,
            "has_html_overlap": has_html_overlap
        },
        "content_hashes": {
            "screenshot_sha256": None,
            "html_sha256": None,
            "info_sha256": None
        },
        "timestamps": {
            "captured_at": captured_at,
            "ingested_at": datetime.now(timezone.utc).isoformat()
        },
        "provenance": {
            "created_by": "phishpedia_archive_adapter",
            "source_archive": source_archive_path,
            "transformation_notes": "Extracted via zip central directory stream."
        }
    }
    return canonical


class PhishpediaDatasetReader:
    """Stream-reader for Phishpedia zip archives or extracted directories."""

    def __init__(self, archive_path: str, dataset_id: str = "phishpedia_primary"):
        self.archive_path = archive_path
        self.dataset_id = dataset_id

    def stream_observations(self, limit: int = 50, offset: int = 0) -> Generator[Dict[str, Any], None, None]:
        """Stream canonical observation objects from archive without loading all records into memory."""
        if not os.path.exists(self.archive_path):
            raise FileNotFoundError(f"Archive not found: {self.archive_path}")

        with zipfile.ZipFile(self.archive_path, "r") as zf:
            # Group entries by top-level capture directory
            dirs_seen = {}
            for name in zf.namelist():
                parts = name.strip("/").split("/")
                if len(parts) >= 2:
                    top_dir = parts[0]
                    file_name = parts[1]
                    if top_dir not in dirs_seen:
                        dirs_seen[top_dir] = []
                    dirs_seen[top_dir].append(file_name)

            sorted_dirs = sorted(dirs_seen.keys())
            target_dirs = sorted_dirs[offset : offset + limit]

            for d in target_dirs:
                available_files = dirs_seen[d]
                info_dict = {}
                if "info.txt" in available_files:
                    try:
                        raw_bytes = zf.read(f"{d}/info.txt")
                        content_str = raw_bytes.decode("utf-8", errors="replace")
                        info_dict = parse_info_content(content_str)
                    except Exception:
                        info_dict = {}

                yield record_to_canonical_observation(
                    dataset_id=self.dataset_id,
                    source_record_id=d,
                    info_dict=info_dict,
                    available_files=available_files,
                    source_archive_path=self.archive_path
                )
