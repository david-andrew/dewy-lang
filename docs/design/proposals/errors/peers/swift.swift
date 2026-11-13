// Paper comparison idioms; standard Error/Result/task groups; not a compiled workload suite.
struct Failures: Error { let errors: [any Error] }
struct Context: Error { let message: String; let cause: any Error }
struct Invalid: Error { let message: String }
func joined(_ errors: [any Error]) -> (any Error)? {
    if errors.isEmpty { return nil }
    if errors.count == 1 { return errors[0] }
    return Failures(errors: errors)
}
func cleanup(body: () throws -> Void, close: () throws -> Void) throws {
    var errors: [any Error] = []
    do { try body() } catch { errors.append(error) }
    do { try close() } catch { errors.append(error) }
    if let failure = joined(errors) { throw failure }
}
func validate(name: String, age: Int) throws {
    var errors: [any Error] = []
    if name.isEmpty { errors.append(Invalid(message: "name is required")) }
    if age < 18 { errors.append(Invalid(message: "age must be at least 18")) }
    if let failure = joined(errors) { throw failure }
}
func canceled(_ e: any Error) -> Bool {
    if e is CancellationError { return true }
    if let group = e as? Failures { return group.errors.contains(where: canceled) }
    if let context = e as? Context { return canceled(context.cause) }
    return false
}
func batch(_ items: [String], read: (String) throws -> String) throws -> [String] {
    var errors: [any Error] = [], good: [String] = []
    for item in items {
        do { good.append(try read(item)) }
        catch {
            errors.append(Context(message: "reading \(item)", cause: error))
            if canceled(error), let failure = joined(errors) { throw failure }
        }
    }
    if let failure = joined(errors) { throw failure }
    return good
}
func parallel(_ items: [String], parse: @escaping @Sendable (String) throws -> String)
    async throws -> [String] {
    let results = await withTaskGroup(of: (Int, Result<String, any Error>).self) { group in
        for (i, text) in items.enumerated() {
            group.addTask { (i, Result { try parse(text) }) }
        }
        var results: [(Int, Result<String, any Error>)] = []
        for await item in group { results.append(item) }
        return results.sorted { $0.0 < $1.0 }
    }
    var errors: [any Error] = [], good: [String] = []
    for (_, result) in results {
        switch result { case .success(let v): good.append(v); case .failure(let e): errors.append(e) }
    }
    if let failure = joined(errors) { throw failure }
    return good
}
func split(_ e: any Error, matches: (any Error) -> Bool) -> ([any Error], [any Error]) {
    if let group = e as? Failures {
        var yes: [any Error] = [], no: [any Error] = []
        for child in group.errors {
            let (a,b) = split(child, matches: matches); yes += a; no += b
        }
        return (yes, no)
    }
    return matches(e) ? ([e], []) : ([], [e])
}
struct Located: Error {
    let error: any Error
    let file: StaticString
    let line: UInt
}
func locate(_ error: any Error, file: StaticString = #fileID, line: UInt = #line) -> Located {
    Located(error: error, file: file, line: line)
}
func retry(count: Int, attempt: (Int) throws -> String) throws -> String {
    guard count > 0 else { throw Invalid(message: "count must be positive") }
    var errors: [any Error] = []
    for n in 1...count {
        do { return try attempt(n) }
        catch {
            errors.append(Context(message: "attempt \(n)", cause: error))
            if canceled(error), let failure = joined(errors) { throw failure }
        }
    }
    throw Failures(errors: errors)
}
// Errors in arrays are explicit values. Ordinary catch also catches CancellationError.
// Standard Error conformance does not itself expose this custom tree to a generic reporter.
// Typed throws can retain a domain error enum; it does not supply an automatic many-error tree.
// Bounded diagnostic counts reuse an array limit plus an explicit omission summary.
func bounded(_ items: [String], keep: Int) throws {
    var errors: [any Error] = []; var omitted = 0
    for (i, text) in items.enumerated() {
        if Int(text) == nil {
            if errors.count < keep { errors.append(Invalid(message: "row \(i+1): invalid quantity")) }
            else { omitted += 1 }
        }
    }
    if omitted > 0 { errors.append(Invalid(message: "\(omitted) additional failures omitted")) }
    if let failure = joined(errors) { throw failure }
}
