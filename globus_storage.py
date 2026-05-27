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

# data_access_scope = f"urn:globus:auth:scope:transfer.api.globus.org:all[data_access[{GLOBUS_ENDPOINT_ID}]]"

# tokens = client.oauth2_client_credentials_tokens(
#     requested_scopes=data_access_scope
# )

print("--- DEBUG: VERIFYING CODE IS RUNNING WITH TRANSFER SCOPES ---")
tokens = client.oauth2_client_credentials_tokens(
    requested_scopes=TransferScopes.all
)

transfer_token = (
    tokens.by_resource_server["transfer.api.globus.org"]["access_token"]
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

    # Construct the Globus HTTPS download URL for your collection
    # Format: https://data.transfer.api.globus.org/v1.0/collections/{endpoint_id}/items/{path}
    url = f"https://data.transfer.api.globus.org/v1.0/collections/{GLOBUS_ENDPOINT_ID}/items/{remote_path}"
    
    headers = {
        "Authorization": f"Bearer {transfer_token}"
    }

    print(f"Downloading {remote_path} via Globus HTTPS...")
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        with open(local_path, 'wb') as f:
            f.write(response.content)
        return local_path
    else:
        raise Exception(f"HTTPS Download failed: {response.status_code} - {response.text}")

# def ensure_local(remote_path):
#     """
#     Download remote file to local cache if needed.
#     Returns local cached path.
#     """

#     local_path = cache_path(remote_path)

#     if os.path.exists(local_path):
#         return local_path

#     os.makedirs(
#         os.path.dirname(local_path),
#         exist_ok=True
#     )

#     transfer_client.operation_get(
#         GLOBUS_ENDPOINT_ID,
#         remote_path,
#         local_path
#     )

#     return local_path


def list_remote_dir(remote_path):
    response = transfer_client.operation_ls(
        GLOBUS_ENDPOINT_ID,
        path=remote_path
    )

    return [item for item in response]