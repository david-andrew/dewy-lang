// Paper comparison idioms; not a compiled workload suite.
package comparison

import (
    "context"
    "errors"
    "fmt"
    "runtime"
)

func cleanup(body, close func() error) (err error) {
    defer func() { err = errors.Join(err, close()) }()
    return body()
}

func validate(name string, age int) error {
    var bad []error
    if name == "" { bad = append(bad, errors.New("name is required")) }
    if age < 18 { bad = append(bad, errors.New("age must be at least 18")) }
    return errors.Join(bad...)
}

func batch(items []string, read func(string) (string, error)) ([]string, error) {
    var bad []error
    var good []string
    for _, item := range items {
        value, err := read(item)
        if err != nil {
            bad = append(bad, fmt.Errorf("reading %s: %w", item, err))
            if errors.Is(err, context.Canceled) { return nil, errors.Join(bad...) }
        } else { good = append(good, value) }
    }
    if len(bad) != 0 { return nil, errors.Join(bad...) }
    return good, nil
}

func parallel(items []string, check func(string) error) error {
    type result struct { index int; err error }
    done := make(chan result, len(items))
    for i, item := range items {
        go func(i int, item string) { done <- result{i, check(item)} }(i, item)
    }
    ordered := make([]error, len(items))
    for range items { r := <-done; ordered[r.index] = r.err }
    return errors.Join(ordered...)
}

func contextual(err error) error { return fmt.Errorf("loading config: %w", err) }

func retry(count int, attempt func(int) (int, error)) (int, error) {
    if count < 1 { return 0, errors.New("count must be positive") }
    var bad []error
    for n := 1; n <= count; n++ {
        value, err := attempt(n)
        if err == nil { return value, nil }
        bad = append(bad, fmt.Errorf("attempt %d: %w", n, err))
        if errors.Is(err, context.Canceled) { return 0, errors.Join(bad...) }
    }
    return 0, errors.Join(bad...)
}

func children(err error) []error {
    if many, ok := err.(interface{ Unwrap() []error }); ok { return many.Unwrap() }
    return []error{err}
}

func partition(err error, target error) (matched, rest []error) {
    // This application's wrapper policy keeps singly wrapped causes indivisible.
    if many, ok := err.(interface{ Unwrap() []error }); ok {
        for _, child := range many.Unwrap() {
            yes, no := partition(child, target)
            matched, rest = append(matched, yes...), append(rest, no...)
        }
    } else if errors.Is(err, target) { matched = append(matched, err)
    } else { rest = append(rest, err) }
    return
}

func recoverOnly(err error, target error, recover func([]error) error) error {
    matching, rest := partition(err, target)
    recovery := recover(matching)
    return errors.Join(append(rest, recovery)...)
}

type Located struct { Err error; PCs []uintptr }
func (e Located) Error() string { return e.Err.Error() }
func (e Located) Unwrap() error { return e.Err }
func locate(err error) error {
    pcs := make([]uintptr, 32)
    n := runtime.Callers(2, pcs)
    return Located{err, pcs[:n]}
}

func cancellationRule(err error) error {
    if errors.Is(err, context.Canceled) { return err } // must precede ordinary fallback
    return nil
}
// fmt printing of a joined error gives text; the Located frames need a custom reporter.
// errors.Unwrap handles a single Unwrap() error, not the Unwrap() []error branch above.
// A naive `if errors.Is(err, missing) { return nil }` loses unrelated joined failures.
// Validation caps use len(bad) and an explicit omitted counter, as in the other peers.

func bounded(items []string, keep int, check func(string) error) error {
    var bad []error
    omitted := 0
    for i, item := range items {
        if err := check(item); err != nil {
            if len(bad) < keep { bad = append(bad, fmt.Errorf("row %d: invalid quantity", i+1))
            } else { omitted++ }
        }
    }
    if omitted > 0 { bad = append(bad, fmt.Errorf("%d additional failures omitted", omitted)) }
    return errors.Join(bad...)
}
