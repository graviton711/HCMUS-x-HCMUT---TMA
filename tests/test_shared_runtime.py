"""Offline tests for shared.runtime fast exit. No signals sent."""

from shared.runtime import INTERRUPTED_EXIT_CODE, run_cli


def test_run_cli_passes_through_return_code():
    assert run_cli(lambda: 3) == 3


def test_run_cli_maps_keyboard_interrupt_to_130():
    def cancelled():
        raise KeyboardInterrupt()

    assert run_cli(cancelled) == INTERRUPTED_EXIT_CODE
    assert INTERRUPTED_EXIT_CODE == 130
