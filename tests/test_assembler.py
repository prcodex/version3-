import json
from m3xa_souls.assembler import assemble, bedrock_payload, DATA_PLACEHOLDER


def test_output_module_is_last():
    _, report = assemble("m3xa", ["iran"])
    assert report.files[-1] == "m3xa/souls/output.md"


def test_data_placeholder_before_output():
    prompt, _ = assemble("m3xabr", [])
    assert prompt.index(DATA_PLACEHOLDER) < prompt.index("Formato de Saída")


def test_budgets_both_products():
    for product, tags in [("m3xa", ["iran", "polymarket_data"]),
                          ("m3xabr", ["polymarket_data", "price_action"])]:
        _, report = assemble(product, tags)
        assert report.total_tokens <= 2600, (product, report.tokens_per_file)
        assert not report.over_budget


def test_core_first():
    _, report = assemble("m3xabr", [])
    assert report.files[0] == "m3xabr/souls/core.md"


def test_bedrock_payload_cache_and_schema():
    p = bedrock_payload("m3xa", ["iran"])
    assert p["system"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert "cache_control" not in p["system"][1]          # uncached tail
    assert DATA_PLACEHOLDER not in p["system"][0]["text"]  # data never in cached prefix
    assert p["output_config"]["format"]["type"] == "json_schema"
    assert p["model"] == "claude-haiku-4-5"


def test_bedrock_payload_no_schema_without_geo():
    p = bedrock_payload("m3xabr", ["polymarket_data"])
    assert "output_config" not in p
