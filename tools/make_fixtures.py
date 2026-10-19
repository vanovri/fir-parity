"""Generate the synthetic FIR fixtures deterministically."""
from pathlib import Path
import math

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
FIXTURES.mkdir(exist_ok=True)


def write(name: str, first: int, values: list[float]) -> None:
    lines = [str(first)] + [f"{value:.12f}" for value in values]
    (FIXTURES / name).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


write("taps.txt", 5, [0.2, 0.2, 0.2, 0.2, 0.2])
write("signal.txt", 32, [math.sin(2 * math.pi * index / 16) for index in range(32)])
write("short.txt", 3, [1.0, -2.0, 3.5])
write("impulse.txt", 6, [1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
write("constant.txt", 8, [2.0] * 8)
write("single_tap.txt", 4, [3.0, -1.0, 0.5, 2.0])
write("single_taps.txt", 1, [0.75])
write("empty.txt", 0, [])
print("fixtures written")
