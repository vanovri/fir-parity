// Causal FIR filter with zero-padded history. Mirrors fortran/fir.f90.
use std::env;
use std::fs;
use std::io::Write;
use std::process;

fn read_numbers(path: &str) -> Result<Vec<f64>, String> {
    let text = fs::read_to_string(path).map_err(|error| format!("cannot read {path}: {error}"))?;
    let tokens: Vec<&str> = text.lines().map(str::trim).collect();
    if tokens.is_empty() {
        return Err(format!("{path}: empty file"));
    }
    if tokens[0].len() > 7 || tokens[0].is_empty() || !tokens[0].chars().all(|c| c.is_ascii_digit()) {
        return Err("invalid count".into());
    }
    let count: usize = tokens[0].parse().map_err(|_| format!("{path}: missing count"))?;
    if count > 1_000_000 { return Err("count exceeds limit".into()); }
    let values: Vec<f64> = tokens[1..]
        .iter()
        .map(|token| {
            if token.is_empty() || !token.chars().all(|c| c.is_ascii_digit() || "Ee+-.".contains(c)) {
                return Err(format!("invalid number: {token}"));
            }
            token.parse::<f64>().map_err(|_| format!("invalid number: {token}"))
        })
        .collect::<Result<_, _>>()?;
    if values.len() != count {
        return Err(format!("{path}: expected {count} values, found {}", values.len()));
    }
    Ok(values)
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 4 {
        eprintln!("usage: fir <taps> <signal> <output>");
        process::exit(2);
    }
    let taps = read_numbers(&args[1]).unwrap_or_else(|error| { eprintln!("{error}"); process::exit(3) });
    let signal = read_numbers(&args[2]).unwrap_or_else(|error| { eprintln!("{error}"); process::exit(3) });
    if taps.is_empty() {
        eprintln!("at least one tap is required");
        process::exit(4);
    }
    if taps.iter().chain(signal.iter()).any(|value| !value.is_finite()) {
        eprintln!("finite values are required");
        process::exit(5);
    }
    if taps.len().saturating_mul(signal.len()) > 20_000_000 { eprintln!("work limit"); process::exit(5); }
    let mut output = String::new();
    output.push_str(&format!("{}\n", signal.len()));
    for (index, _) in signal.iter().enumerate() {
        let mut acc = 0.0_f64;
        for (tap_index, tap) in taps.iter().enumerate() {
            if index >= tap_index {
                acc += tap * signal[index - tap_index];
            }
        }
        if !acc.is_finite() { eprintln!("non-finite output"); process::exit(5); }
        output.push_str(&format!("{acc:.16e}\n"));
    }
    let written = fs::OpenOptions::new().write(true).create_new(true).open(&args[3])
        .and_then(|mut file| file.write_all(output.as_bytes()));
    if let Err(error) = written {
        eprintln!("cannot write output: {error}");
        process::exit(6);
    }
}
