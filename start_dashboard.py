import os
import subprocess
import sys

print("Downloading Globus data...")

# Run your existing Globus script
result = subprocess.run(
    [sys.executable, "test_globus.py"],
    capture_output=False,
)

if result.returncode != 0:
    raise RuntimeError("Globus download failed")

print("Starting dashboard...")

from app import server
from waitress import serve

port = int(os.environ.get("PORT", 10000))

serve(server, host="0.0.0.0", port=port)