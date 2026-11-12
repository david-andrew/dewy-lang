"""Reached prelude clock operations acquire only their required providers."""

import subprocess

from tests.support import compiler  # noqa: F401


def test_reached_clock_providers(compiler, tmp_path):
    programs = {
        "pure": ('printl(instant"2026-01-01T00:00:00Z")\n', False, False),
        "now": ("let r=now\nprintl(r-r)\n", True, True),
        "monotonic": ("let p=monotonic\nprintl(p-p)\n", False, True),
        "today": ("printl(today('UTC'))\n", True, False),
        "age_on": ('printl(age(date"2000-01-01" on=date"2026-01-01"))\n', False, False),
        "age_today": ('printl(age(date"2000-01-01" scope="UTC"))\n', True, False),
        "sleep": ('sleep(0ms)\n', False, True),
        "within": ('printl(within(1s @answer))\nanswer=()=>42\n', False, True),
        "channel_only": ('let c=channel<int64>(1)\nprintl(c.try_receive is? Empty)\n', False, False),
        "channel_timeout": ('let c=channel<int64>(1)\nprintl(c.receive(timeout=0s) is? Timeout)\n', False, True),
        "select_timeout": ('let c=channel<int64>(1)\nprintl(select(@c.receive timeout=0s) is? Timeout)\n', False, True),
        "select": ('let c=channel<int64>(1)\nc.send(7)\nprintl(select(@c.receive))\n', False, True),
        "ticker": ('let t=ticker(1ms)\nprintl(t.next is? Tick)\n', False, True),
    }
    wall = b"wall clock provider unavailable at entry"
    mono = b"suspend-inclusive monotonic clock unavailable at entry"
    for name, (source, wants_wall, wants_mono) in programs.items():
        path = tmp_path / f"{name}.dewy"
        binary = tmp_path / name
        path.write_text(source)
        built = subprocess.run([compiler, "build", path, "-o", binary],
                               capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, (name, built.stderr)
        linked = binary.read_bytes()
        assert (wall in linked) == wants_wall, name
        assert (mono in linked) == wants_mono, name
