"""Initialize only the local Azurite storage, never an Azure account."""

import os

from azure.core.exceptions import ResourceExistsError
from azure.data.tables import TableServiceClient
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()
connection = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
if "127.0.0.1" not in connection and "localhost" not in connection:
    raise SystemExit("Only a local Azurite connection string is accepted")
tables = TableServiceClient.from_connection_string(connection)
for name in ("Posts", "Comments"):
    tables.create_table_if_not_exists(name)
blobs = BlobServiceClient.from_connection_string(connection)
try:
    blobs.create_container("images")
except ResourceExistsError:
    pass
print("Azurite: Posts, Comments, images ready")
