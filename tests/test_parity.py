"""Parity tests for the Fortran and Rust FIR implementations."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import fir_parity as fp  # noqa: E402

FIXTURES = ROOT / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def built():
    try:
        info = fp.build()
    except RuntimeError as exc:
        pytest.skip(str(exc))
    assert Path(info["gfortran"]).exists()
    assert fp.FORTRAN_BIN.exists() and fp.RUST_BIN.exists()


def case(taps: str, signal: str) -> dict:
    return fp.compare(FIXTURES / taps, FIXTURES / signal, fp.BUILD / "tmp")


def test_sine_signal_matches():
    result = case("taps.txt", "signal.txt")
    assert result["samples"] == 32
    assert result["within_tolerance"]
    assert result["max_fortran_rust_difference"] <= fp.TOLERANCE
    assert result["max_fortran_reference_difference"] <= fp.TOLERANCE


def test_short_signal_uses_zero_padded_history():
    result = case("taps.txt", "short.txt")
    assert result["samples"] == 3
    assert result["within_tolerance"]


def test_impulse_response_equals_taps():
    result = case("taps.txt", "impulse.txt")
    assert result["within_tolerance"]
    values = fp.parse_output(fp.BUILD / "tmp" / "fortran.txt")
    assert values[:5] == pytest.approx([0.2, 0.2, 0.2, 0.2, 0.2])
    assert all(value == 0.0 for value in values[5:])


def test_constant_signal_sums_taps():
    result = case("taps.txt", "constant.txt")
    assert result["within_tolerance"]
    values = fp.parse_output(fp.BUILD / "tmp" / "rust.txt")
    assert values[-1] == pytest.approx(2.0)


def test_single_tap_is_a_scaled_copy():
    result = case("single_taps.txt", "single_tap.txt")
    assert result["within_tolerance"]
    values = fp.parse_output(fp.BUILD / "tmp" / "fortran.txt")
    assert values == pytest.approx([2.25, -0.75, 0.375, 1.5])


def test_empty_signal_is_allowed():
    result = case("taps.txt", "empty.txt")
    assert result["samples"] == 0
    assert result["within_tolerance"]


def test_zero_taps_is_rejected_by_both(tmp_path):
    bad = tmp_path / "taps_zero.txt"
    bad.write_text("0\n", encoding="utf-8")
    fortran = fp.run_binary(fp.FORTRAN_BIN, bad, FIXTURES / "signal.txt", tmp_path / "f.txt")
    rust = fp.run_binary(fp.RUST_BIN, bad, FIXTURES / "signal.txt", tmp_path / "r.txt")
    assert fortran.returncode != 0
    assert rust.returncode != 0


def test_invalid_numbers_are_rejected(tmp_path):
    bad = tmp_path / "signal_bad.txt"
    bad.write_text("2\n1.0\nnot-a-number\n", encoding="utf-8")
    fortran = fp.run_binary(fp.FORTRAN_BIN, FIXTURES / "taps.txt", bad, tmp_path / "f.txt")
    rust = fp.run_binary(fp.RUST_BIN, FIXTURES / "taps.txt", bad, tmp_path / "r.txt")
    assert fortran.returncode != 0
    assert rust.returncode != 0


def test_reference_implementation_is_independent():
    count, taps = fp.read_case(FIXTURES / "taps.txt")
    _, signal = fp.read_case(FIXTURES / "signal.txt")
    assert count == len(taps) == 5
    values = fp.expected(taps, signal)
    assert values[0] == 0.0
    assert values[1] == pytest.approx(0.2 * signal[1])
    assert values[-1] == pytest.approx(sum(0.2 * signal[-1 - index] for index in range(5)))
