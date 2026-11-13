"""Paper comparison idioms, standard library only; not an executed workload suite."""
import asyncio
import traceback


def joined(errors):
    if not errors:
        return None
    if len(errors) == 1:
        return errors[0]
    return BaseExceptionGroup("operation failures", errors)


def cleanup(body, close):
    primary = None
    try:
        body()
    except BaseException as error:
        primary = error
    try:
        close()
    except BaseException as error:
        raise joined(([primary] if primary is not None else []) + [error])
    if primary is not None:
        raise primary


def validate(name, age_text):
    errors = []
    if not name.strip():
        errors.append(ValueError("name is required"))
    try:
        age = int(age_text)
        if not 18 <= age <= 130:
            errors.append(ValueError("age must be in 18..130"))
    except ValueError as error:
        error.add_note("age field")
        errors.append(error)
    if errors:
        raise joined(errors)
    return name.strip(), age


def batch(items, read):
    errors, good = [], []
    for item in items:
        try:
            good.append(read(item))
        except BaseException as error:
            error.add_note(f"reading {item}")
            errors.append(error)
            if not isinstance(error, Exception):
                raise joined(errors)
    if errors:
        raise joined(errors)
    return good


async def all_items(calls):
    # Caller cancellation still interrupts gather; this is not a cancellation-proof report.
    outcomes = await asyncio.gather(*(f() for f in calls), return_exceptions=True)
    errors = [x for x in outcomes if isinstance(x, BaseException)]
    if errors:
        raise joined(errors)
    return outcomes


def contextual(error):
    error.add_note("loading configuration")  # same identity, but mutates aliases too
    return error


def translate(read):
    try:
        return read()
    except Exception as error:
        raise RuntimeError("cannot load configuration") from error


def report(error):
    traceback.print_exception(error)         # group, cause and raise-site traceback


def retry(attempt, count):
    errors = []
    for number in range(1, count + 1):
        try:
            return attempt(number)
        except BaseException as error:
            error.add_note(f"attempt {number}")
            errors.append(error)
            if not isinstance(error, Exception):
                raise joined(errors)
    if errors:
        raise joined(errors)
    raise ValueError("count must be positive")


def selective(operation, recover):
    try:
        operation()
    except* FileNotFoundError as matching:
        recover(matching)                   # unmatched leaves propagate automatically


def origins():
    first = ValueError("same")
    second = ValueError("same")
    return first.__traceback__, second.__traceback__  # both None until raised


def bounded(lines, keep):
    errors, omitted = [], 0
    for number, text in enumerate(lines, 1):
        try:
            int(text)
        except ValueError:
            if len(errors) < keep:
                errors.append(ValueError(f"row {number}: invalid integer"))
            else:
                omitted += 1
    if omitted:
        errors.append(ValueError(f"{omitted} more invalid rows omitted"))
    if errors:
        raise joined(errors)


def parallel_cpu(items, check):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(check, item) for item in items]
        errors, good = [], []
        for future in futures:
            try:
                good.append(future.result())
            except Exception as error:
                errors.append(error)
        if errors:
            raise joined(errors)
        return good
