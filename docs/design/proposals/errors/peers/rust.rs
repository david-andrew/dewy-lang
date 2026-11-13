// Paper comparison idioms, std only; not a compiled workload suite.
use std::{backtrace::Backtrace, error::Error, fmt, io};

#[derive(Debug)]
enum Failure {
    Io(io::Error),
    Invalid(&'static str),
    Canceled,
    Omitted(usize),
    Row(usize),
    Many(Vec<Failure>),
    Context { message: String, cause: Box<Failure> },
}
impl fmt::Display for Failure {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result { write!(f, "{self:?}") }
}
impl Error for Failure {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::Io(e) => Some(e),
            Self::Context { cause, .. } => Some(cause.as_ref()),
            _ => None, // a Vec of simultaneous causes does not fit Error::source
        }
    }
}
fn joined(mut errors: Vec<Failure>) -> Result<(), Failure> {
    match errors.len() {
        0 => Ok(()),
        1 => Err(errors.remove(0)),
        _ => Err(Failure::Many(errors)),
    }
}
fn cleanup(body: impl FnOnce() -> Result<(), Failure>,
           close: impl FnOnce() -> Result<(), Failure>) -> Result<(), Failure> {
    let a = body();
    let b = close();
    joined(a.err().into_iter().chain(b.err()).collect())
}
fn validate(name: &str, age: i64) -> Result<(), Failure> {
    let mut bad = Vec::new();
    if name.is_empty() { bad.push(Failure::Invalid("name is required")); }
    if age < 18 { bad.push(Failure::Invalid("age must be at least 18")); }
    joined(bad)
}
fn canceled(e: &Failure) -> bool {
    match e {
        Failure::Canceled => true,
        Failure::Many(xs) => xs.iter().any(canceled),
        Failure::Context { cause, .. } => canceled(cause),
        _ => false,
    }
}
fn batch(items: &[String], read: impl Fn(&str) -> Result<String, Failure>)
    -> Result<Vec<String>, Failure> {
    let mut bad = Vec::new();
    let mut good = Vec::new();
    for item in items {
        match read(item) {
            Ok(x) => good.push(x),
            Err(e) => {
                let stop = canceled(&e);
                bad.push(Failure::Context { message: item.clone(), cause: Box::new(e) });
                if stop { joined(bad)?; unreachable!(); }
            }
        }
    }
    joined(bad)?;
    Ok(good)
}
fn parallel(items: &[String], check: &(impl Fn(&str) -> Result<(), Failure> + Sync))
    -> Result<(), Failure> {
    std::thread::scope(|s| {
        let handles: Vec<_> = items.iter().map(|x| s.spawn(move || check(x))).collect();
        let bad = handles.into_iter().filter_map(|h| {
            // Thread panic is outside this application's Failure contract.
            h.join().expect("worker panicked").err()
        }).collect();
        joined(bad)
    })
}
fn split(e: Failure, test: &impl Fn(&Failure) -> bool) -> (Vec<Failure>, Vec<Failure>) {
    match e {
        Failure::Many(xs) => {
            let (mut yes, mut no) = (Vec::new(), Vec::new());
            for x in xs { let (a,b) = split(x, test); yes.extend(a); no.extend(b); }
            (yes, no)
        }
        x if test(&x) => (vec![x], vec![]),
        x => (vec![], vec![x]),
    }
}
#[derive(Debug)]
struct Located { error: Failure, origin: &'static std::panic::Location<'static>, trace: Backtrace }
#[track_caller]
fn locate(error: Failure) -> Located {
    Located { error, origin: std::panic::Location::caller(), trace: Backtrace::capture() }
}
// A domain enum may preserve concrete child kinds; Many erases the per-occurrence type shape.
// ? forwards one Result error; explicit accumulation is required to keep multiple failures.
// Drop::drop returns (), so fallible completion must be an explicit operation or side channel.
// A standard Error reporter follows source(), not all children of Many; implement a tree renderer.
// Retry/bounded diagnostics reuse Vec push + joined and the explicit canceled() policy above.
// Cancellation is an application enum here, not a claim about a universal Rust runtime protocol.
fn retry(count: usize, attempt: impl Fn(usize) -> Result<String, Failure>) -> Result<String, Failure> {
    if count == 0 { return Err(Failure::Invalid("count must be positive")); }
    let mut bad = Vec::new();
    for n in 1..=count {
        match attempt(n) {
            Ok(x) => return Ok(x),
            Err(e) => {
                let stop = canceled(&e);
                bad.push(Failure::Context { message: format!("attempt {n}"), cause: Box::new(e) });
                if stop { return Err(Failure::Many(bad)); }
            }
        }
    }
    Err(Failure::Many(bad))
}
fn bounded(items: &[String], keep: usize) -> Result<(), Failure> {
    let mut bad = Vec::new();
    let mut omitted = 0;
    for (i, text) in items.iter().enumerate() {
        if text.parse::<i64>().is_err() {
            if bad.len() < keep { bad.push(Failure::Row(i+1)); }
            else { omitted += 1; }
        }
    }
    if omitted > 0 { bad.push(Failure::Omitted(omitted)); }
    joined(bad)
}
