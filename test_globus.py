import os
from dotenv import load_dotenv
from globus_sdk import ConfidentialAppAuthClient

load_dotenv()

CLIENT_ID = os.environ["GLOBUS_CLIENT_ID"]
CLIENT_SECRET = os.environ["GLOBUS_CLIENT_SECRET"]

print("Client ID loaded:", CLIENT_ID is not None)
print("Secret loaded:", CLIENT_SECRET is not None)

client = ConfidentialAppAuthClient(
    CLIENT_ID,
    CLIENT_SECRET
)

tokens = client.oauth2_client_credentials_tokens(
    requested_scopes="urn:globus:auth:scope:transfer.api.globus.org:all"
)

print(tokens.by_resource_server)