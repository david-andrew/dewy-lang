"""Representation selection for arbitrary-precision integers.

Abstract ``int`` values lower to 64-bit words when the bounds analysis proves
they fit. Everything it could not prove — an arithmetic result with an
unknown or oversized interval, a narrowing it could not justify — is
rewritten here onto the prelude's ``BigInt`` object: the flagged operation
becomes a ``_bigint_*`` call, bindings that receive big values become
big-integer bindings, and the change propagates to every use. Integer
parameters and results keep their word representation (a big value cannot
cross such a boundary without a proof), which the report explains.

The decisions are recorded as ``RepresentationNote``s for the analysis
report (``dewy --analyze``).
"""

from __future__ import annotations

from dataclasses import dataclass, fields

from ...reporting import Pointer, Span, SrcFile
from .. import bindings as sb
from .. import hir, ty
from ..errors import user_error

_BINARY = {
    '__add__': '_bigint_add',
    '__sub__': '_bigint_sub',
    '__mul__': '_bigint_mul',
    '__floordiv__': '_bigint_floordiv',
    '__mod__': '_bigint_mod',
    '__eq__': '_bigint_eq',
    '__ne__': '_bigint_ne',
    '__lt__': '_bigint_lt',
    '__le__': '_bigint_le',
    '__gt__': '_bigint_gt',
    '__ge__': '_bigint_ge',
}
_COMPARISONS = {'__eq__', '__ne__', '__lt__', '__le__', '__gt__', '__ge__'}


@dataclass(frozen=True)
class RepresentationNote:
    """One decision the report shows: where a value became a big integer and why."""

    loc: Span
    message: str


class _RepresentationPass:
    def __init__(
        self,
        registry: sb.BindingRegistry,
        srcfile: SrcFile,
        prelude: dict[str, sb.Binding],
        unfit: dict[int, tuple[hir.AST, object, str]],
    ) -> None:
        self.registry = registry
        self.srcfile = srcfile
        self.prelude = prelude
        self.unfit = unfit
        self.big_type = prelude['BigInt'].type_value
        assert isinstance(self.big_type, ty.ObjectType)
        self.big_bindings: set[int] = set()
        self.notes: list[RepresentationNote] = []

    # ------------------------------------------------------------ helpers
    def _prelude_call(self, name: str, args: list[hir.AST], loc: Span) -> hir.FunctionCall:
        binding = self.prelude[name]
        assert isinstance(binding.type, ty.FunctionType)
        func = hir.ExpressedIdentifier(loc, binding.type, binding.name, binding_id=binding.id)
        return hir.FunctionCall(loc, binding.type.ret, func, args, {})

    def _is_big(self, node: hir.AST) -> bool:
        return node.type == self.big_type

    def _to_big(self, node: hir.AST) -> hir.AST:
        """A word-typed integer value as a big integer (constants become exact limbs)."""
        if self._is_big(node):
            return node
        if isinstance(node, hir.Integer):
            return self._literal(node.value, node.loc)
        if isinstance(node.type, ty.IntegerLiteralType):
            return self._literal(node.type.value, node.loc)
        word = node if node.type == 'int64' else hir.ValueCast(node.loc, 'int64', node)
        return self._prelude_call('_bigint_from_int', [word], node.loc)

    def _literal(self, value: int, loc: Span) -> hir.AST:
        magnitude = abs(value)
        limbs: list[int] = []
        while magnitude:
            limbs.append(magnitude & 0xFFFFFFFF)
            magnitude >>= 32
        array = hir.ArrayLiteral(loc, ty.ArrayType('uint64', len(limbs)), [hir.Integer(loc, 'uint64', '0d', limb) for limb in limbs])
        return self._prelude_call('_bigint_from_limbs', [hir.Bool(loc, 'bool', value < 0), array], loc)

    def _note(self, loc: Span, message: str) -> None:
        self.notes.append(RepresentationNote(loc, message))

    @staticmethod
    def _describe(interval: object) -> str:
        lower = getattr(interval, 'lower', None)
        upper = getattr(interval, 'upper', None)
        if interval is None or (lower is None and upper is None):
            return 'its range is unknown'
        return f'its range is [{"-∞" if lower is None else lower}, {"∞" if upper is None else upper}]'

    # ------------------------------------------------------------ the pass
    def run(self, root: hir.Block) -> None:
        # bindings receiving big values become big; iterate to a fixed point
        # because a loop accumulator feeds itself
        changed = True
        while changed:
            changed = False
            self._rewrite(root)
            before = len(self.big_bindings)
            self._mark_bindings(root)
            changed = len(self.big_bindings) != before

    def _mark_bindings(self, node: object) -> None:
        if isinstance(node, hir.Declare) and node.binding_id is not None and self._is_big(node.expr) and node.binding_id not in self.big_bindings:
            binding = self.registry.by_id[node.binding_id]
            if binding.kind == 'value' and (binding.type in ('int', 'uint') or isinstance(binding.type, ty.IntegerLiteralType)):
                self.big_bindings.add(node.binding_id)
                binding.type = self.big_type
                node.annotation = self.big_type
                self._note(node.loc, f'`{node.name}` is a big integer: its initializer is one')
        if isinstance(node, hir.Assign) and node.op == '=':
            target = node.target
            if (
                isinstance(target, hir.ExpressedIdentifier)
                and target.binding_id is not None
                and self._is_big(node.value)
                and target.binding_id not in self.big_bindings
            ):
                binding = self.registry.by_id[target.binding_id]
                if binding.kind == 'value' and binding.type in ('int', 'uint'):
                    self.big_bindings.add(target.binding_id)
                    binding.type = self.big_type
                    if binding.declaration is not None:
                        binding.declaration.annotation = self.big_type
                    self._note(node.loc, f'`{target.name}` is a big integer: this assignment stores one')
        if isinstance(node, hir.AST):
            for field in fields(node):
                self._mark_bindings(getattr(node, field.name))
        elif isinstance(node, (list, tuple)):
            for item in node:
                self._mark_bindings(item)
        elif isinstance(node, hir.ObjectField):
            self._mark_bindings(node.value)

    def _rewrite(self, node: object) -> object:
        """Rewrite a subtree in place; returns the (possibly replaced) node."""
        if isinstance(node, (list, tuple)):
            items = [self._rewrite(item) for item in node]
            if isinstance(node, list):
                node[:] = items
                return node
            return tuple(items)
        if isinstance(node, hir.ObjectField):
            node.value = self._rewrite(node.value)
            return node
        if not isinstance(node, hir.AST):
            return node
        # children first
        for field in fields(node):
            if field.name in ('type', 'annotation'):
                continue
            value = getattr(node, field.name)
            rewritten = self._rewrite(value)
            if rewritten is not value:
                setattr(node, field.name, rewritten)
        return self._rewrite_node(node)

    def _rewrite_node(self, node: hir.AST) -> hir.AST:
        if isinstance(node, hir.Integer) and (isinstance(node.type, ty.IntegerLiteralType) or node.type in ('int', 'uint')):
            # an oversized literal has no word representation at all
            if not (-(1 << 63) <= node.value < (1 << 64)):
                self._note(node.loc, f'the literal `{node.value}` is a big integer: it does not fit a 64-bit word')
                return self._literal(node.value, node.loc)
            return node
        if isinstance(node, hir.ExpressedIdentifier):
            if node.binding_id in self.big_bindings:
                node.type = self.big_type
            return node
        if isinstance(node, hir.Declare):
            if node.binding_id in self.big_bindings:
                node.expr = self._to_big(node.expr)
                node.annotation = self.big_type
            return node
        if isinstance(node, hir.Assign):
            target = node.target
            if isinstance(target, hir.ExpressedIdentifier) and target.binding_id in self.big_bindings:
                if node.op != '=':
                    dunder = {'+=': '__add__', '-=': '__sub__'}[node.op]
                    node.value = self._prelude_call(_BINARY[dunder], [target, self._to_big(node.value)], node.loc)
                    node.op = '='
                else:
                    node.value = self._to_big(node.value)
            return node
        if isinstance(node, hir.FunctionCall) and isinstance(node.func, hir.ExpressedIdentifier):
            name = node.func.name
            if name == '_bigint_from_int' and len(node.pos_args) == 1:
                # the checker's word→big conversion of a value that is now big itself
                inner = node.pos_args[0]
                casts: list[hir.ValueCast] = []
                while isinstance(inner, hir.ValueCast):
                    casts.append(inner)
                    inner = inner.expr
                if self._is_big(inner):
                    for cast in casts:
                        self.unfit.pop(id(cast), None)
                    return inner
                return node
            flagged = id(node) in self.unfit
            big_operand = any(self._is_big(arg) for arg in node.pos_args)
            if name in _BINARY and len(node.pos_args) == 2 and (flagged or big_operand) and node.type in ('int', 'uint', 'bool'):
                if flagged:
                    _node, interval, word = self.unfit.pop(id(node))
                    self._note(node.loc, f'this `{node.func.name.strip("_")}` result is a big integer: {self._describe(interval)}, so it may not fit `{word}`')
                left, right = (self._to_big(arg) for arg in node.pos_args)
                call = self._prelude_call(_BINARY[name], [left, right], node.loc)
                return call
            if name == '__unary_sub__' and len(node.pos_args) == 1 and (flagged or big_operand):
                if flagged:
                    self.unfit.pop(id(node), None)
                return self._prelude_call('_bigint_neg', [self._to_big(node.pos_args[0])], node.loc)
            if name == '__pow__' and len(node.pos_args) == 2 and (flagged or big_operand):
                self.unfit.pop(id(node), None)
                base, exponent = node.pos_args
                return self._prelude_call('_bigint_pow', [self._to_big(base), hir.ValueCast(exponent.loc, 'int64', exponent) if exponent.type != 'int64' else exponent], node.loc)
            if isinstance(node.func.type, ty.OverloadType) and big_operand is False:
                # an interpolation/print of a value that became big: pick the big overload
                for position, arg in enumerate(node.pos_args):
                    if isinstance(arg, hir.ValueCast) and self._is_big(arg.expr):
                        for index, method in enumerate(node.func.type.methods):
                            if method.pos_or_kw and method.pos_or_kw[0].type == self.big_type:
                                node.pos_args[position] = arg.expr
                                node.selected_method_index = index
                                self.unfit.pop(id(arg), None)
                                break
            return node
        if isinstance(node, hir.FunctionLiteral) and node.rettype in ('int', 'uint'):
            # a word-typed result cannot carry a big value
            for item in _returns_of(node.body):
                if item.item is not None and self._is_big(item.item):
                    user_error(
                        self.srcfile,
                        'a big integer is returned from a word-sized function',
                        Pointer(span=item.loc, message='this value is a big integer, but the result type is `int`'),
                        hint='annotate the result as `bigint`, or prove the value fits with a comparison',
                    )
            return node
        if isinstance(node, hir.FunctionCall) and isinstance(node.func, hir.ExpressedIdentifier) and isinstance(node.func.type, ty.FunctionType):
            for arg, param in zip(node.pos_args, node.func.type.pos_or_kw):
                if self._is_big(arg) and param.type != self.big_type and not isinstance(arg, hir.Place):
                    user_error(
                        self.srcfile,
                        'a big integer is passed to a word-sized parameter',
                        Pointer(span=arg.loc, message=f'this value is a big integer, but `{param.name}` is `{param.type}`'),
                        hint='annotate the parameter as `bigint`, or prove the value fits with a comparison',
                    )
        # narrowings the analysis could not justify stay flagged; whatever is
        # still flagged when the pass ends is reported (see select_representations)
        return node


def _returns_of(node: object) -> list[hir.Return]:
    """Return statements of a body, not descending into nested functions."""
    found: list[hir.Return] = []
    if isinstance(node, hir.Return):
        found.append(node)
    if isinstance(node, hir.FunctionLiteral):
        return found
    if isinstance(node, hir.AST):
        for field in fields(node):
            found.extend(_returns_of(getattr(node, field.name)))
    elif isinstance(node, (list, tuple)):
        for item in node:
            found.extend(_returns_of(item))
    elif isinstance(node, hir.ObjectField):
        found.extend(_returns_of(node.value))
    return found


last_notes: list[RepresentationNote] = []
"""Notes from the most recent compilation, for the analysis report."""


def select_representations(
    root: hir.Block,
    registry: sb.BindingRegistry,
    srcfile: SrcFile,
    prelude: dict[str, sb.Binding],
    unfit: dict[int, tuple[hir.AST, object, str]],
) -> list[RepresentationNote]:
    """Rewrite unproven abstract integers onto `BigInt`; returns the report notes."""
    if 'BigInt' not in prelude or prelude['BigInt'].type_value is None:
        return []
    pass_ = _RepresentationPass(registry, srcfile, prelude, unfit)
    pass_.run(root)
    last_notes.extend(pass_.notes)
    if unfit:
        # anything still flagged is a narrowing of a word value we could not
        # bound (for example an `int` parameter into `int64`)
        for node, interval, word in list(unfit.values()):
            lower = getattr(interval, 'lower', None)
            upper = getattr(interval, 'upper', None)
            refuted = (
                lower is not None and upper is not None and lower == upper
                and not ty.integer_literal_fits(lower, word)
            )
            big_value = isinstance(node, hir.ValueCast) and pass_._is_big(node.expr)
            user_error(
                srcfile,
                f'this integer does not fit `{word}`' if refuted else f'cannot prove this integer fits `{word}`',
                Pointer(
                    span=node.loc,
                    message=(
                        ('this value is a big integer; ' if big_value else '')
                        + pass_._describe(interval)
                        + ('' if refuted else ', so it may not fit (neither proven nor refuted)')
                    ),
                ),
                hint=(
                    'keep it a big integer (`bigint`), or prove its range with a comparison'
                    if big_value
                    else 'annotate a fixed width such as `int64`, narrow the value with a comparison, or use `bigint`'
                ),
            )
    pass_.notes.sort(key=lambda note: note.loc.start)
    return pass_.notes
