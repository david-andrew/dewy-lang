"""A zone set from a run-time value names the zone for calls inside its scope: no warning there."""
import subprocess

from tests.support import compiler  # noqa: F401

SOURCE = '''office = (z:Zone):>void => {
    $time.zone = z
    let text:string = "2026-10-26T09:00"
    let local = zoned(text)
    if local is? ZonedDateTime printl(local)
}
elsewhere = ():>void => {
    let text:string = "2026-10-26T09:00"
    printl(zoned(text) is? ZonedDateTime)
}
main = () => {
    office(zone"Europe/Berlin")
    elsewhere()
}
'''


def test_computed_zone_scope_names_the_zone(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'zones.dewy'
    source.write_text(SOURCE)
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=120)
    assert checked.returncode == 0, checked.stderr
    warnings = [line for line in checked.stderr.splitlines() if 'has no time zone here' in line]
    # (only the call outside the scope, line 9, can read no zone)
    assert len(warnings) == 1 and ':9:' in warnings[0], checked.stderr
