import json
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fir_parity as fp


@pytest.fixture(scope='module', autouse=True)
def compilers_required():
    fp.build()


def series(path, values):
    path.write_text(str(len(values)) + '\n' + ''.join(f'{x:.17e}\n' for x in values), encoding='ascii')
    return path


@pytest.mark.parametrize('text', ['1\nNaN\n', '1\nInf\n', '1\n1e999\n', '1\n1\n2\n',
                                 '2\n1\n', '-1\n', '1000001\n', '1\n1 2\n', '1\n1,2\n'])
def test_both_binaries_reject_invalid_series(tmp_path, text):
    bad = tmp_path / 'bad.txt'
    bad.write_text(text, encoding='ascii')
    for index, binary in enumerate([fp.FORTRAN_BIN, fp.RUST_BIN]):
        output = tmp_path / f'{index}.txt'
        assert fp.run_binary(binary, fp.ROOT / 'fixtures/taps.txt', bad, output).returncode != 0
        assert not output.exists()


def test_overflow_and_existing_output_are_rejected(tmp_path):
    taps = series(tmp_path / 'taps.txt', [1e308])
    signal = series(tmp_path / 'signal.txt', [1e308])
    for binary in [fp.FORTRAN_BIN, fp.RUST_BIN]:
        output = tmp_path / 'result.txt'
        assert fp.run_binary(binary, taps, signal, output).returncode != 0
        assert not output.exists()
        output.write_text('preserve', encoding='ascii')
        assert fp.run_binary(binary, fp.ROOT / 'fixtures/taps.txt', fp.ROOT / 'fixtures/signal.txt', output).returncode != 0
        assert output.read_text() == 'preserve'
        output.unlink()


@pytest.mark.parametrize('size,tap_count', [(257, 17), (1, 1), (0, 3), (7, 31), (1024, 9)])
def test_seeded_random_signed_signals_and_taps(tmp_path, size, tap_count):
    rng = random.Random(20261019 + size)
    taps = series(tmp_path / 'random-taps.txt', [rng.uniform(-1, 1) for _ in range(tap_count)])
    signal = series(tmp_path / 'random-signal.txt', [rng.uniform(-3, 3) for _ in range(size)])
    result = fp.compare(taps, signal, tmp_path / 'work')
    assert result['within_tolerance']
    assert result['samples'] == size


def test_comparison_rejects_matching_but_truncated_outputs(tmp_path, monkeypatch):
    class Result:
        returncode = 0
        stderr = ''
    def truncated(binary, taps, signal, output, timeout=20):
        output.write_text('0\n', encoding='ascii')
        return Result()
    monkeypatch.setattr(fp, 'run_binary', truncated)
    with pytest.raises(AssertionError, match='count mismatch'):
        fp.compare(fp.ROOT / 'fixtures/taps.txt', fp.ROOT / 'fixtures/signal.txt', tmp_path)


def test_harness_rejects_nonfinite_output(tmp_path):
    path = tmp_path / 'output.txt'
    path.write_text('1\nNaN\n', encoding='ascii')
    with pytest.raises(ValueError, match='non-finite'):
        fp.parse_output(path)
