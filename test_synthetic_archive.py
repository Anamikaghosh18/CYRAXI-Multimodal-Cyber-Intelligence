
import json
import tempfile
import zipfile
from pathlib import Path

from modules.dataset_adapter.reader import PhishpediaDatasetReader

with tempfile.TemporaryDirectory() as temp:
    archive = Path(temp) / "synthetic.zip"

    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(
            "record_a/info.json",
            json.dumps({
                "url": "https://example.com/login",
                "label": "phishing"
            })
        )
        z.writestr(
            "record_a/html.txt",
            "<html><title>Login</title><body>Verify your account</body></html>"
        )

    reader = PhishpediaDatasetReader(str(archive))

    observations = list(reader.stream_observations(limit=1))

    print("Observations read:", len(observations))
    if observations:
        print(json.dumps(observations[0], indent=2, default=str))
