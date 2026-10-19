"""Build and compare the Fortran and Rust FIR implementations."""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
FORTRAN_SRC = ROOT / "fortran" / "fir.f90"
RUST_SRC = ROOT / "rust" / "fir.rs"
FORTRAN_BIN = BUILD / ("fir_fortran.exe" if os.name == "nt" else "fir_fortran")
RUST_BIN = BUILD / ("fir_rust.exe" if os.name == "nt" else "fir_rust")
TOLERANCE = 1e-12


def find_compiler(name: str, candidates: list[Path]) -> Path | None:
    override = os.environ.get(name.upper())
    if override:
        path = Path(override)
        return path if path.exists() else None
    found = shutil.which(name)
    if found:
        return Path(found)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def find_gfortran() -> Path | None:
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    candidates = []
    if local.exists():
        candidates.extend(local.glob("BrechtSanders.WinLibs*/mingw64/bin/gfortran.exe"))
    return find_compiler("gfortran", candidates)


def find_rustc() -> Path | None:
    home = Path(os.environ.get("USERPROFILE", os.environ.get("HOME", "")))
    return find_compiler("rustc", [
        home / ".rustup" / "toolchains" / "stable-x86_64-pc-windows-gnu" / "bin" / "rustc.exe",
        home / ".cargo" / "bin" / "rustc.exe",
        home / ".cargo" / "bin" / "rustc",
    ])


def build(force: bool = False) -> dict:
    gfortran = find_gfortran()
    rustc = find_rustc()
    if gfortran is None:
        raise RuntimeError("gfortran not found; set GFORTRAN to its executable")
    if rustc is None:
        raise RuntimeError("rustc not found; set RUSTC to its executable")
    BUILD.mkdir(exist_ok=True)
    commands = []
    if force or not FORTRAN_BIN.exists() or FORTRAN_SRC.stat().st_mtime > FORTRAN_BIN.stat().st_mtime:
        command = [str(gfortran), "-O2", "-std=f2008", "-Wall", "-static", "-o", str(FORTRAN_BIN), str(FORTRAN_SRC)]
        subprocess.run(command, check=True, capture_output=True, text=True)
        commands.append(" ".join(command))
    if force or not RUST_BIN.exists() or RUST_SRC.stat().st_mtime > RUST_BIN.stat().st_mtime:
        command = [str(rustc), "-O", "-o", str(RUST_BIN), str(RUST_SRC)]
        subprocess.run(command, check=True, capture_output=True, text=True)
        commands.append(" ".join(command))
    return {"gfortran": str(gfortran), "rustc": str(rustc), "commands": commands}


def read_case(path: Path) -> tuple[int, list[float]]:
    tokens = path.read_text(encoding="utf-8").split()
    if not tokens:
        raise ValueError(f"{path.name}: empty file")
    count = int(tokens[0])
    values = [float(token) for token in tokens[1:]]
    if count < 0 or not all(math.isfinite(value) for value in values):
        raise ValueError('finite values and nonnegative counts required')
    if len(values) != count:
        raise ValueError(f"{path.name}: expected {count} values, got {len(values)}")
    return count, values


def expected(taps: list[float], signal: list[float]) -> list[float]:
    result = []
    for index in range(len(signal)):
        acc = 0.0
        for tap_index, tap in enumerate(taps):
            if index >= tap_index:
                acc += tap * signal[index - tap_index]
        result.append(acc)
    return result


def parse_output(path: Path) -> list[float]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"{path.name}: empty output")
    count = int(lines[0])
    values = [float(line) for line in lines[1:]]
    if count < 0 or not all(math.isfinite(value) for value in values):
        raise ValueError('non-finite or invalid output')
    if len(values) != count:
        raise ValueError(f"{path.name}: header says {count}, found {len(values)}")
    return values


def run_binary(binary: Path, taps: Path, signal: Path, output: Path, timeout: float = 20.0) -> subprocess.CompletedProcess:
    environment = os.environ.copy()
    if binary == FORTRAN_BIN:
        compiler = find_gfortran()
        if compiler is not None:
            environment["PATH"] = str(compiler.parent) + os.pathsep + environment.get("PATH", "")
    return subprocess.run(
        [str(binary), str(taps), str(signal), str(output)],
        capture_output=True, text=True, timeout=timeout, env=environment,
    )


def compare(taps_path: Path, signal_path: Path, workdir: Path) -> dict:
    build()
    fortran_out = workdir / "fortran.txt"
    rust_out = workdir / "rust.txt"
    workdir.mkdir(parents=True, exist_ok=True)
    for owned_output in [fortran_out, rust_out]:
        if owned_output.resolve() in {taps_path.resolve(), signal_path.resolve()}:
            raise ValueError('output must not overwrite an input')
        owned_output.unlink(missing_ok=True)
    first = run_binary(FORTRAN_BIN, taps_path, signal_path, fortran_out)
    second = run_binary(RUST_BIN, taps_path, signal_path, rust_out)
    if first.returncode != 0 or second.returncode != 0:
        raise RuntimeError(f"filter failed: fortran={first.returncode} rust={second.returncode} stderr={first.stderr}{second.stderr}")
    fortran_values = parse_output(fortran_out)
    rust_values = parse_output(rust_out)
    if len(fortran_values) != len(rust_values):
        raise AssertionError("length mismatch")
    max_difference = max((abs(a - b) for a, b in zip(fortran_values, rust_values)), default=0.0)
    _, taps = read_case(taps_path)
    _, signal = read_case(signal_path)
    reference = expected(taps, signal)
    if len(reference) != len(fortran_values) or not all(math.isfinite(value) for value in reference):
        raise AssertionError('reference/output count mismatch or non-finite result')
    reference_difference = max((abs(a - b) for a, b in zip(fortran_values, reference)), default=0.0)
    return {
        "taps": str(taps_path.name),
        "signal": str(signal_path.name),
        "samples": len(fortran_values),
        "max_fortran_rust_difference": max_difference,
        "max_fortran_reference_difference": reference_difference,
        "within_tolerance": max_difference <= TOLERANCE and reference_difference <= TOLERANCE,
        "fortran": fortran_values[:4],
        "rust": rust_values[:4],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taps", type=Path, default=ROOT / "fixtures" / "taps.txt")
    parser.add_argument("--signal", type=Path, default=ROOT / "fixtures" / "signal.txt")
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "parity.json")
    arguments = parser.parse_args(argv)
    try:
        build()
        result = compare(arguments.taps, arguments.signal, BUILD / "tmp")
    except (RuntimeError, subprocess.CalledProcessError, OSError) as exc:
        print(f"fir-parity: {exc}", file=sys.stderr)
        return 2
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0 if result["within_tolerance"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
