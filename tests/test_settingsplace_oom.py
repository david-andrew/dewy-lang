"""A refused policy-text allocation unwinds its frame and parent reference."""
import subprocess
import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('flags', [(), ('--release',)])
def test_policy_text_allocation_failure_releases_the_pending_frame(compiler, tmp_path, flags):
    # A fabricated string requests an impossible virtual allocation before any
    # payload is read. Its header is freed after the explicit failure is caught.
    (tmp_path / 'probe.jo').write_text("""exhaust = () -> bool:
    raw = __alloc(24) as *int
    raw[0] = 1 << 40
    raw[1] = 1 << 60
    raw[2] = 1 << 60
    saved = __settings_current()
    refs = saved.refs
    frame = __oom_frame()
    if __setjmp(frame) != 0:
        current = __settings_current()
        tracked = current != saved and current != null and current.parent == saved and current.value == ""
        __oom_caught()
        restored = __settings_current() == saved and saved.refs == refs
        __free(raw as *u8)
        return tracked and restored
    __settings_enter_policy(1, raw as str)
    __oom_release()
    __free(raw as *u8)
    false
""")
    source = tmp_path / 'app.dewy'
    source.write_text("$explicit_allocation_failure\n$runtime_checks\nimport p\"probe.jo\" as probe\nmain=()=>{\n $time.zone='UTC'\n printl(probe.exhaust)\n}\n")
    result = subprocess.run([compiler, 'run', source, *flags], capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'true\n'
