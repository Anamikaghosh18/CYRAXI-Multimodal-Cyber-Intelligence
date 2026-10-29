"""Start the CYRAXI investigation and graph APIs from one command."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SERVICES = (
    ("Investigation API", "modules.investigation.api:app", 8002),
    ("Graph API", "modules.graph_enrichment_mapper.api.server:app", 8001),
)


def main() -> int:
    processes: list[tuple[str, int, subprocess.Popen]] = []
    try:
        for name, app, port in SERVICES:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    app,
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=ROOT,
            )
            processes.append((name, port, process))
            print(f"{name} starting at http://localhost:{port}", flush=True)

        while True:
            for name, port, process in processes:
                exit_code = process.poll()
                if exit_code is not None:
                    if exit_code != 0:
                        print(f"{name} stopped with exit code {exit_code}.", file=sys.stderr)
                    return exit_code
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("Stopping CYRAXI backend services...", flush=True)
        return 0
    finally:
        for _, _, process in processes:
            if process.poll() is None:
                process.terminate()
        for _, _, process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
