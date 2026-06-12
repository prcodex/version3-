from m3xa_souls.assembler import assemble, DATA_PLACEHOLDER


def test_output_module_is_last():
    prompt, report = assemble("global", ["iran"])
    assert report.files[-1] == "souls/output/global.md"
    assert prompt.rstrip().endswith("— WHY.\"")  # last line of output/global.md


def test_data_placeholder_before_output():
    prompt, _ = assemble("brazil", [])
    assert prompt.index(DATA_PLACEHOLDER) < prompt.index("Formato de Saída")


def test_budget_worst_case():
    _, report = assemble("global", ["iran", "polymarket_data"])
    assert report.total_tokens <= 2600, report.tokens_per_file
    assert not report.over_budget


def test_core_first():
    _, report = assemble("global", [])
    assert report.files[0] == "souls/core/soul_core.md"
