import zipfile
from pathlib import Path


def _get_artifact_path(observation, artifact_name):
    artifacts = observation.get("artifacts", {})

    if artifact_name == "yolo_coords":
        return artifacts.get("auxiliary", {}).get("yolo_coords_path")

    artifact = artifacts.get(artifact_name)
    if not isinstance(artifact, dict):
        return None

    return artifact.get("relative_path")


def read_artifact_bytes(archive_path, observation, artifact_name):
    """Read one referenced artifact without extracting the dataset."""
    relative_path = _get_artifact_path(observation, artifact_name)
    if not relative_path:
        return None

    if not isinstance(archive_path, (str, Path, zipfile.ZipFile)):
        read_bytes = getattr(archive_path, "read_bytes", None)
        if callable(read_bytes):
            return read_bytes(relative_path)

    if isinstance(archive_path, zipfile.ZipFile):
        try:
            return archive_path.read(relative_path)
        except (KeyError, OSError, ValueError):
            return None

    root = Path(archive_path)

    try:
        if root.is_file() and zipfile.is_zipfile(root):
            with zipfile.ZipFile(root, "r") as archive:
                try:
                    return archive.read(relative_path)
                except KeyError:
                    return None

        file_path = root / relative_path
        if file_path.is_file():
            return file_path.read_bytes()

    except (OSError, zipfile.BadZipFile):
        return None

    return None


def read_artifact(archive_path, observation, artifact_name, encoding="utf-8"):
    """Read one textual artifact without extracting the dataset."""
    content = read_artifact_bytes(
        archive_path, observation, artifact_name
    )
    if content is None:
        return None

    try:
        return content.decode(encoding)
    except (UnicodeDecodeError, AttributeError):
        return None
