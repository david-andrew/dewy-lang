"""
Exception classes and report helpers for the semantic phase.

All user-facing diagnostics are authored as reporting.Report objects (same machinery as
t1/t2/p0). The exception classes are a thin classification layer over ReportException:
which class carries a report is a control-flow concern of the semantic phase (namely
whether the Ambiguous handler may prune it), not a property of the message itself.

Internal errors (compiler bugs) stay plain exceptions with an 'INTERNAL ERROR:' prefix;
a traceback is more useful than a source pointer for those.
"""
from typing import NoReturn

from ..reporting import SrcFile, ReportException, Error, Pointer, Span
from . import ty


class TypeCheckError(ReportException):
    """this reading is ill-typed; prunes an Ambiguous candidate"""

class UserError(ReportException):
    """genuine user error; never pruned"""

class NotImplementedYet(ReportException):
    """construct not yet handled by the semantic phase"""


def type_error(srcfile: SrcFile, title: str, *pointers: Pointer, message: str | None = None, hint: str | None = None, dimmed: list[Span] | None = None) -> NoReturn:
    raise TypeCheckError(Error(srcfile=srcfile, title=title, message=message, pointer_messages=list(pointers), hint=hint, dimmed=dimmed or []))


def user_error(srcfile: SrcFile, title: str, *pointers: Pointer, message: str | None = None, hint: str | None = None, notes: list[str] | None = None, dimmed: list[Span] | None = None) -> NoReturn:
    raise UserError(Error(srcfile=srcfile, title=title, message=message, pointer_messages=list(pointers), hint=hint, notes=notes or [], dimmed=dimmed or []))


def not_implemented(srcfile: SrcFile, loc: Span, what: str) -> NoReturn:
    raise NotImplementedYet(Error(
        srcfile=srcfile,
        title='not implemented',
        pointer_messages=[Pointer(span=loc, message=f'{what} is not yet handled by the semantic phase')],
    ))


def require_valued(t: ty.Type, srcfile: SrcFile, loc: Span, what: str) -> ty.TypeExpr:
    """narrow Type -> TypeExpr at an algebra boundary, reporting when the expression expresses no value"""
    if t == ty.VOID_TYPE or t == ty.INFERRED_TYPE:
        type_error(
            srcfile,
            f'{what} expresses no value',
            Pointer(span=loc, message=f'this has type `{t}`, but a value is required here'),
        )
    return t
