from m3xa_souls.validate import validate


def test_repo_souls_pass_lint():
    assert validate() == 0
