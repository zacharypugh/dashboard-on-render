# globus_utils.py

import os
import requests

CACHE_DIR = "/tmp/lane_dash_cache"

os.makedirs(CACHE_DIR, exist_ok=True)

def download_file(url, filename):
    local_path = os.path.join(CACHE_DIR, filename)

    if not os.path.exists(local_path):
        r = requests.get(url)
        r.raise_for_status()

        with open(local_path, "wb") as f:
            f.write(r.content)

    return local_path