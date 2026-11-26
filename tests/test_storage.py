from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

from forum.storage import AzureStorage, entity_key


@pytest.fixture
def storage():
    result = AzureStorage({"AZURE_STORAGE_CONNECTION_STRING": "test-only"})
    result.tables = MagicMock()
    result.blobs = MagicMock()
    return result


def test_post_query_stops_at_50_and_filters_on_server(storage):
    consumed = []

    def rows():
        for i in range(100):
            consumed.append(i)
            yield {"RowKey": str(i)}

    table = storage.tables.get_table_client.return_value
    table.query_entities.return_value = rows()
    assert len(storage.list_posts("study")) == 50
    assert len(consumed) == 50
    kwargs = table.query_entities.call_args.kwargs
    assert kwargs["parameters"] == {"partition": "posts", "category": "study"}
    assert "category eq @category" in kwargs["query_filter"]


def test_keys_are_fixed_width_and_sort_by_time():
    with patch("forum.storage.datetime") as clock:
        clock.now.return_value = datetime(2026, 1, 1, tzinfo=UTC)
        old_post, _ = entity_key(True)
        old_comment, _ = entity_key()
        clock.now.return_value = datetime(2026, 1, 2, tzinfo=UTC)
        new_post, _ = entity_key(True)
        new_comment, _ = entity_key()
    assert len(old_post) == 46
    assert new_post < old_post
    assert old_comment < new_comment


def test_blob_upload_failure_does_not_create_post(storage):
    storage.blobs.get_blob_client.return_value.upload_blob.side_effect = HttpResponseError()
    with pytest.raises(HttpResponseError):
        storage.create_post({"title": "test"}, (b"image", "png", "image/png"))
    storage.tables.get_table_client.assert_not_called()


def test_failed_table_write_compensates_only_its_blob(storage):
    storage.tables.get_table_client.return_value.create_entity.side_effect = HttpResponseError()
    with pytest.raises(HttpResponseError):
        storage.create_post({"title": "test"}, (b"image", "png", "image/png"))
    blob_calls = storage.blobs.get_blob_client.call_args_list
    assert blob_calls[0] == blob_calls[1]
    assert blob_calls[0].args[0] == "images"
    storage.blobs.get_blob_client.return_value.delete_blob.assert_called_once()


def test_missing_post_cannot_receive_comment(storage):
    storage.tables.get_table_client.return_value.get_entity.side_effect = ResourceNotFoundError()
    with pytest.raises(ResourceNotFoundError):
        storage.create_comment("missing", {"body": "comment"})
    storage.tables.get_table_client.return_value.create_entity.assert_not_called()


def test_comment_parent_and_query(storage):
    storage.create_comment("parent", {"body": "comment", "nickname": "匿名"})
    entity = storage.tables.get_table_client.return_value.create_entity.call_args.args[0]
    assert entity["PartitionKey"] == "parent"
    assert entity["body"] == "comment"
    assert entity["created_at"].tzinfo is not None
    storage.list_comments("parent")
    assert storage.tables.get_table_client.return_value.query_entities.call_args.kwargs[
        "parameters"
    ] == {"post": "parent"}
