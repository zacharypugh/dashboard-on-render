# globus_storage.py

import os
import time
import globus_sdk
import requests

from globus_sdk import ConfidentialAppAuthClient
from globus_sdk import TransferClient
from globus_sdk.scopes import TransferScopes

from config import (
    GLOBUS_CLIENT_ID,
    GLOBUS_CLIENT_SECRET,
    GLOBUS_ENDPOINT_ID,
    CACHE_DIR,
)

client = ConfidentialAppAuthClient(
    GLOBUS_CLIENT_ID,
    GLOBUS_CLIENT_SECRET
)

print("--- DEBUG: VERIFYING CODE IS RUNNING WITH TRANSFER SCOPES ---")

# 1. Define the specific HTTPS data access scope for your distinct collection
HTTPS_SCOPE = f"https://auth.globus.org/scopes/{GLOBUS_ENDPOINT_ID}/https"

# Request both standard transfer management scopes and collection-specific download scopes
tokens = client.oauth2_client_credentials_tokens(
    requested_scopes=[TransferScopes.all, HTTPS_SCOPE]
)

# Token for the central Globus Transfer API (used for directory listings / ls)
transfer_token = (
    tokens.by_resource_server["transfer.api.globus.org"]["access_token"]
)

# Token specifically assigned for direct HTTPS file downloads from this collection
https_token = (
    tokens.by_resource_server.get(GLOBUS_ENDPOINT_ID, {}).get("access_token")
)

authorizer = globus_sdk.AccessTokenAuthorizer(
    transfer_token
)

transfer_client = TransferClient(
    authorizer=authorizer
)


def cache_path(remote_path):
    clean = remote_path.strip("/").replace("/", "__")
    return os.path.join(CACHE_DIR, clean)


def ensure_local(remote_path):
    """
    Download remote file to local cache using Globus HTTPS if needed.
    """
    local_path = cache_path(remote_path)

    if os.path.exists(local_path):
        return local_path

    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    # 2. Dynamically retrieve your collection's dedicated HTTPS server URL
    endpoint_info = transfer_client.get_endpoint(GLOBUS_ENDPOINT_ID)
    https_base_url = endpoint_info.get("https_server")
    
    if not https_base_url:
        raise Exception(
            f"HTTPS data access is not enabled or supported on collection {GLOBUS_ENDPOINT_ID}."
        )

    # 3. Construct the direct file URL off that unique domain base
    # (Stripping slashes ensures no accidental double "//" or missing "/" path errors occur)
    url = f"{https_base_url.rstrip('/')}/{remote_path.lstrip('/')}"
    
    # Use the dedicated HTTPS data access token, falling back to transfer token if needed
    auth_token = https_token or transfer_token
    headers = {
        "Authorization": f"Bearer {auth_token}"
    }

    print(f"Downloading {remote_path} via Globus HTTPS from {url}...")
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        with open(local_path, 'wb') as f:
            f.write(response.content)
        return local_path
    else:
        raise Exception(f"HTTPS Download failed: {response.status_code} - {response.text}")


def list_remote_dir(remote_path):
    response = transfer_client.operation_ls(
        GLOBUS_ENDPOINT_ID,
        path=remote_path
    )

    return [item for item in response]