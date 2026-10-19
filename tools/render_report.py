"""Draw the synthetic signal and actual compiled FIR outputs as a standalone SVG."""
import json
from pathlib import Path

import fir_parity as fp

ROOT = Path(__file__).resolve().parents[1]
_, signal = fp.read_case(ROOT / 'fixtures/signal.txt')
fp.compare(ROOT / 'fixtures/taps.txt', ROOT / 'fixtures/signal.txt', ROOT / 'build/tmp')
output = fp.parse_output(ROOT / 'build/tmp/fortran.txt')
def line(values):
    return ' '.join(f'{60 + i * 680 / (len(values) - 1):.2f},{235 - v * 115:.2f}' for i, v in enumerate(values))
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 440">
<rect width="800" height="440" fill="#101a24"/><g fill="#eff5f9" font-family="sans-serif">
<text x="50" y="48" font-size="26">FIR parity: compiled Fortran and Rust</text>
<text x="50" y="80" font-size="15">Synthetic 32-sample input. Causal 5-tap moving average.</text>
<path d="M60 110V365H750M60 235H750" fill="none" stroke="#496176"/>
<polyline points="{line(signal)}" fill="none" stroke="#899eb5" stroke-width="2"/>
<polyline points="{line(output)}" fill="none" stroke="#6de3cb" stroke-width="3"/>
<text x="60" y="403" fill="#899eb5">Input signal</text><text x="210" y="403" fill="#6de3cb">Compiled output (Fortran = Rust for this fixture)</text>
</g></svg>'''
(ROOT / 'docs').mkdir(exist_ok=True)
(ROOT / 'docs/preview.svg').write_text(svg, encoding='utf-8', newline='\n')
