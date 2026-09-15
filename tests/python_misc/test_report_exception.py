"""Rejected interpretations carry diagnostics without laying out excerpts."""
import pickle
import traceback

from dewy.reporting import Error, Pointer, Report, Span, SrcFile
from dewy.semantic.errors import TypeCheckError


def test_report_exception_defers_rendering_and_preserves_output(monkeypatch):
    report = Error(SrcFile(None, 'let x = 1'), title='test diagnostic',
                   pointer_messages=[Pointer(Span(4, 5), 'binding')], use_color=False)
    expected = str(report)
    calls = []
    render = Report.__str__

    def observed(self):
        calls.append(self)
        return render(self)

    monkeypatch.setattr(Report, '__str__', observed)
    error = TypeCheckError(report)
    try:
        raise error
    except TypeCheckError as caught:
        assert caught.report is report
    assert calls == []
    assert str(error) == expected
    assert calls == [report]
    assert error._render_traceback_() == expected.splitlines()
    assert expected in ''.join(traceback.format_exception_only(error))
    # Structured diagnostics remain structured across worker boundaries.
    restored = pickle.loads(pickle.dumps(error))
    assert isinstance(restored, TypeCheckError)
    assert restored.report == report
    assert str(restored) == expected


def test_exception_uses_the_final_report_color_policy():
    report = Error(SrcFile(None, 'bad'), title='error',
                   pointer_messages=[Pointer(Span(0, 3), 'here')], use_color=True)
    error = TypeCheckError(report)
    report.use_color = False
    assert str(error) == str(report)
    assert '\x1b[' not in str(error)
