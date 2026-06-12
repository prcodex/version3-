from m3xa_souls.router import route, pick_model


def test_geo_routes_m3xa():
    mods = route("m3xa", ["iran"])
    assert [m["file"] for m in mods] == ["m3xa/souls/modules/geo.md"]
    assert mods[0]["structured_output"] == "schemas/geo_response.schema.json"


def test_priority_and_cap():
    mods = route("m3xa", ["iran", "polymarket_data", "price_action"])
    assert [m["file"] for m in mods] == [
        "m3xa/souls/modules/geo.md", "m3xa/souls/modules/polymarket.md"]


def test_brazilbrief_disabled():
    assert route("m3xabr", ["brazilbrief"]) == []


def test_products_isolated():
    assert all(m["file"].startswith("m3xabr/") for m in route("m3xabr", ["polymarket_data"]))
    assert all(m["file"].startswith("m3xa/") for m in route("m3xa", ["polymarket_data"]))


def test_model_tiering():
    assert pick_model("m3xa", ["broad"]) == "claude-sonnet-4-6"
    assert pick_model("m3xa", ["iran"]) == "claude-haiku-4-5"
    assert pick_model("m3xabr", []) == "claude-haiku-4-5"
