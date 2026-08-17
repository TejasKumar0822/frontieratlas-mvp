from src.entity.resolver import normalize, EntityResolver
from src.utils.dates import parse_date


def test_normalization():
    assert normalize("OpenAI, Inc.") == "openai"
    assert EntityResolver(["OpenAI"]).resolve("Open AI, Inc.", "STARTUP").canonical_name == "OpenAI"


def test_relative_date():
    assert parse_date("2 hours ago") is not None
