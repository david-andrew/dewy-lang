// Paper comparison idioms; ES2022 errors, ESNext explicit resource management; not run.
class Canceled extends Error {}
function joined(errors: unknown[]): unknown | undefined {
    if (!errors.length) return undefined;
    if (errors.length === 1) return errors[0];
    return new AggregateError(errors, "operation failures");
}
function withResource(resource: Disposable, body: () => void): void {
    using owned = resource;
    body(); // disposal failure + body failure become SuppressedError, not AggregateError
}
function validate(name: string, age: number): void {
    const bad: Error[] = [];
    if (!name.trim()) bad.push(new Error("name is required"));
    if (age < 18) bad.push(new Error("age must be at least 18"));
    if (bad.length) throw joined(bad);
}
function canceled(e: unknown): boolean {
    if (e instanceof Canceled) return true;
    if (e instanceof AggregateError) return e.errors.some(canceled);
    if (e instanceof SuppressedError) return canceled(e.error) || canceled(e.suppressed);
    if (e instanceof Error && e.cause !== undefined) return canceled(e.cause);
    return false;
}
async function batch(items: string[], read: (x: string) => Promise<string>): Promise<string[]> {
    const bad: unknown[] = [], good: string[] = [];
    for (const item of items) {
        try { good.push(await read(item)); }
        catch (e: unknown) {
            bad.push(new Error(`reading ${item}`, { cause: e }));
            if (canceled(e)) throw joined(bad);
        }
    }
    if (bad.length) throw joined(bad);
    return good;
}
async function parallel(calls: (() => Promise<string>)[]): Promise<string[]> {
    const results = await Promise.allSettled(calls.map(f => f()));
    const errors = results.flatMap(r => r.status === "rejected" ? [r.reason] : []);
    if (errors.length) throw joined(errors);
    return results.flatMap(r => r.status === "fulfilled" ? [r.value] : []);
}
function context(error: unknown): Error {
    return new Error("loading configuration", { cause: error }); // changes outer identity
}
function split(e: unknown, matches: (e: unknown) => boolean): [unknown[], unknown[]] {
    if (e instanceof AggregateError) {
        const yes: unknown[] = [], no: unknown[] = [];
        for (const child of e.errors) {
            const [a, b] = split(child, matches); yes.push(...a); no.push(...b);
        }
        const rebuild = (xs: unknown[]) => {
            if (!xs.length) return [];
            const value = new AggregateError(xs, e.message, { cause: e.cause });
            value.stack = e.stack;
            return [value];
        };
        return [rebuild(yes), rebuild(no)];
    }
    return matches(e) ? [[e], []] : [[], [e]];
}
async function retry(count: number, attempt: (n: number) => Promise<string>): Promise<string> {
    if (count < 1) throw new RangeError("count must be positive");
    const bad: unknown[] = [];
    for (let n = 1; n <= count; n++) {
        try { return await attempt(n); }
        catch (e: unknown) {
            bad.push(new Error(`attempt ${n}`, { cause: e }));
            if (canceled(e)) throw joined(bad);
        }
    }
    throw joined(bad);
}
function cancellationRule(e: unknown): void {
    if (canceled(e)) throw e; // ordinary catch/fallback does not enforce this for us
}
// A full reporter must traverse AggregateError, SuppressedError and Error.cause separately.
// Error.stack is customary but not the portable ECMAScript origin contract Dewy proposes.
// The split helper preserves standard fields, not arbitrary subclasses or custom properties.
// Bounded diagnostics use bad.length and an explicit omitted counter, as in other peers.
// Runtime abort conventions (DOMException, AbortSignal.reason, etc.) need an adapter to Canceled.
function bounded(items: string[], keep: number): void {
    const bad: Error[] = []; let omitted = 0;
    for (const [i, text] of items.entries()) {
        if (!/^[+-]?\d+$/.test(text)) {
            if (bad.length < keep) bad.push(new Error(`row ${i+1}: invalid quantity`));
            else omitted++;
        }
    }
    if (omitted) bad.push(new Error(`${omitted} additional failures omitted`));
    if (bad.length) throw joined(bad);
}
