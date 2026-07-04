"""Unit tests for app.events.streams."""

from app.events.streams import Group, Stream, dlq_of


def test_stream_names_prefixed():
    """All stream names start with 'hindsight:'."""
    assert Stream.INGEST_REQUESTED.startswith("hindsight:")
    assert Stream.DOC_FETCHED.startswith("hindsight:")


def test_dlq_of_appends_suffix():
    assert dlq_of("hindsight:ingest.requested") == "hindsight:ingest.requested.dlq"
    assert dlq_of("any.stream") == "any.stream.dlq"


def test_group_names_exist():
    """At least the echo consumer group is defined."""
    assert Group.ECHO == "echo-cg"
