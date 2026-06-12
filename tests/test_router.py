from m3xa_souls.router import route


def test_geo_routes():
    assert route("global", ["iran"]) == ["souls/modules/geo.md"]


def test_priority_and_cap():
    mods = route("global", ["iran", "polymarket_data", "price_action"])
    assert mods == ["souls/modules/geo.md", "souls/modules/polymarket.md"]  # cap 2, charts dropped


def test_brazilbrief_locale_gated():
    assert "souls/modules/brazilbrief.md" not in route("global", ["brazilbrief"])
    assert "souls/modules/brazilbrief.md" in route("brazil", ["brazilbrief"])


def test_no_tags_no_modules():
    assert route("global", []) == []
