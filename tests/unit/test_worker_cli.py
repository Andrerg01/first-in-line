"""Unit tests for the worker CLI."""
from worker.app.cli import cmd_noop


def test_noop_prints_confirmation_and_returns_zero(capsys) -> None:
    """cmd_noop should print confirmation message and return exit code 0."""
    result = cmd_noop()
    captured = capsys.readouterr()

    assert result == 0
    assert captured.out.strip() == "worker noop complete"
