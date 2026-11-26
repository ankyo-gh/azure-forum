import logging
from datetime import UTC, datetime
from functools import cached_property
from itertools import islice
from uuid import uuid4

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.data.tables import TableServiceClient
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
from flask import current_app

logger = logging.getLogger(__name__)


def entity_key(reverse=False):
    now = datetime.now(UTC)
    millis = int(now.timestamp() * 1000)
    if reverse:
        millis = 9_999_999_999_999 - millis
    return f"{millis:013d}-{uuid4().hex}", now


class AzureStorage:
    def __init__(self, config):
        self.account = config.get("AZURE_STORAGE_ACCOUNT_NAME")
        self.connection = config.get("AZURE_STORAGE_CONNECTION_STRING")
        self.credential = None
        if not self.connection:
            if not self.account:
                raise RuntimeError("AZURE_STORAGE_ACCOUNT_NAME must be configured")
            self.credential = DefaultAzureCredential()

    @cached_property
    def tables(self):
        if self.connection:
            return TableServiceClient.from_connection_string(self.connection)
        return TableServiceClient(
            f"https://{self.account}.table.core.windows.net", credential=self.credential
        )

    @cached_property
    def blobs(self):
        if self.connection:
            return BlobServiceClient.from_connection_string(self.connection)
        return BlobServiceClient(
            f"https://{self.account}.blob.core.windows.net", credential=self.credential
        )

    def list_posts(self, category=None):
        query = "PartitionKey eq @partition"
        params = {"partition": "posts"}
        if category:
            query += " and category eq @category"
            params["category"] = category
        entities = self.tables.get_table_client("Posts").query_entities(
            query_filter=query, parameters=params, results_per_page=50
        )
        return list(islice(entities, 50))

    def get_post(self, post_id):
        try:
            return self.tables.get_table_client("Posts").get_entity("posts", post_id)
        except ResourceNotFoundError:
            return None

    def create_post(self, values, image=None):
        post_id, created_at = entity_key(reverse=True)
        blob_name = ""
        if image:
            data, extension, content_type = image
            blob_name = f"{uuid4().hex}.{extension}"
            self.blobs.get_blob_client("images", blob_name).upload_blob(
                data, content_settings=ContentSettings(content_type=content_type), overwrite=False
            )
        try:
            self.tables.get_table_client("Posts").create_entity(
                {
                    "PartitionKey": "posts",
                    "RowKey": post_id,
                    "created_at": created_at,
                    "image_blob": blob_name,
                    **values,
                }
            )
        except Exception:
            if blob_name:
                try:
                    self.blobs.get_blob_client("images", blob_name).delete_blob()
                except AzureError as error:
                    logger.error("Image compensation failed (%s)", type(error).__name__)
            raise
        return post_id

    def list_comments(self, post_id):
        return list(
            self.tables.get_table_client("Comments").query_entities(
                query_filter="PartitionKey eq @post", parameters={"post": post_id}
            )
        )

    def create_comment(self, post_id, values):
        if not self.get_post(post_id):
            raise ResourceNotFoundError("Post not found")
        comment_id, created_at = entity_key()
        self.tables.get_table_client("Comments").create_entity(
            {
                "PartitionKey": post_id,
                "RowKey": comment_id,
                "created_at": created_at,
                **values,
            }
        )

    def get_image(self, blob_name):
        try:
            blob = self.blobs.get_blob_client("images", blob_name).download_blob()
            return blob.readall(), blob.properties.content_settings.content_type
        except ResourceNotFoundError:
            return None


def get_storage():
    if "STORAGE" in current_app.config:
        return current_app.config["STORAGE"]
    if "forum_storage" not in current_app.extensions:
        current_app.extensions["forum_storage"] = AzureStorage(current_app.config)
    return current_app.extensions["forum_storage"]
