import pytest

from pydm_mbi import cli


@pytest.fixture
def executed(monkeypatch):
    """The argv of the program pydm-mbi would start."""
    calls = []
    monkeypatch.setattr(cli.shutil, "which", lambda program: f"/bin/{program}")
    monkeypatch.setattr(cli.os, "execve", lambda path, argv, env: calls.append(argv))
    return calls


def test_run_hides_bars(executed):
    cli.main(["run", "display.ui"])
    assert executed == [["pydm", *cli.HIDE_BARS, "display.ui"]]


def test_run_with_bars(executed):
    cli.main(["run", "--bars", "--light", "display.ui"])
    assert executed == [["pydm", "display.ui"]]


def test_run_does_not_repeat_flags(executed):
    cli.main(["run", "--hide-menu-bar", "display.ui"])
    assert executed[0].count("--hide-menu-bar") == 1


def test_designer_keeps_arguments(executed):
    cli.main(["designer", "file.ui"])
    assert executed == [["designer", "file.ui"]]
