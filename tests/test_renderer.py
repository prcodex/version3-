from m3xa_souls.renderer import render_geo

SAMPLE = {
    "window": "Last 12 hours",
    "timeline": [{"time_brt": "08:30", "event": "Strike on Kharg loading point", "source": "@DeItaone"}],
    "actors": [{"actor": "Iran/IRGC", "summary": "Claimed retaliation within 48h."}],
    "market_reaction": [{"asset": "Brent", "before": "$88.80", "after": "$92.40", "change_pct": "+4.1%"}],
    "experts": [{"name": "Javier Blas", "take": "Loading capacity matters more than rhetoric.",
                 "source_date": "Jun 11", "disagrees_with": "Bremmer"}],
    "prediction_markets": [],
    "watch": [{"trigger": "Hormuz insurance rates >2%", "market_implication": "Brent +$5 risk"}],
}


def test_renders_sections_and_silence():
    out = render_geo(SAMPLE)
    assert "TIMELINE" in out and "MARKET REACTION" in out and "WHAT TO WATCH" in out
    assert "PREDICTION MARKETS" not in out          # empty array => structural silence
    assert "|" not in out                            # no pipe tables ever
    assert "<pre>" in out and len(out) < 4000


def test_length_guard():
    big = dict(SAMPLE)
    big["actors"] = [{"actor": f"A{i}", "summary": "x" * 600} for i in range(8)]
    assert len(render_geo(big)) <= 4000
