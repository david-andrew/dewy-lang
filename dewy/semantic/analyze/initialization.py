"""Validate source-order binding initialization on checked HIR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from ...reporting import Error, Pointer, SrcFile
from .. import hir, ty
from ..bindings import BindingRegistry
from ..errors import NotImplementedYet, UserError
from ..hir_display import type_to_dewy


@dataclass(frozen=True)
class CallableEffect:
    """Concrete callable alternatives supplied for one function parameter."""

    targets: tuple[hir.FunctionLiteral, ...]


class _InitializationChecker:
    def __init__(
        self,
        root: hir.Block,
        registry: BindingRegistry,
        srcfile: SrcFile,
    ):
        self.root = root
        self.registry = registry
        self.srcfile = srcfile
        self.reassigned_callables: set[int] = set()
        self.reassigned_objects: set[int] = set()
        self.reassigned_members: set[tuple[int, tuple[str, ...]]] = set()
        self._collect_reassigned_callables(root)

    def _collect_reassigned_callables(self, node: hir.AST) -> None:
        if isinstance(node, hir.Assign):
            if (
                node.target.binding_id is not None
                and isinstance(node.target.type, (ty.FunctionType, ty.OverloadType))
            ):
                self.reassigned_callables.add(node.target.binding_id)
            if (
                node.target.binding_id is not None
                and isinstance(node.target.type, ty.ObjectType)
            ):
                self.reassigned_objects.add(node.target.binding_id)
            self._collect_reassigned_callables(node.value)
            return
        if isinstance(node, hir.Block):
            for item in node.items:
                self._collect_reassigned_callables(item)
            return
        if isinstance(node, hir.Declare):
            self._collect_reassigned_callables(node.expr)
            return
        if isinstance(node, hir.FunctionLiteral):
            self._collect_reassigned_callables(node.body)
            return
        if isinstance(node, hir.OverloadedFunction):
            for alternate in node.alternates:
                self._collect_reassigned_callables(alternate)
            return
        if isinstance(node, hir.FunctionCall):
            self._collect_reassigned_callables(node.func)
            for arg in node.pos_args:
                self._collect_reassigned_callables(arg)
            for arg in node.kw_args.values():
                self._collect_reassigned_callables(arg)
            return
        if isinstance(node, hir.Flow):
            for arm in node.arms:
                self._collect_reassigned_callables(arm.condition)
                self._collect_reassigned_callables(arm.body)
            if node.default is not None:
                self._collect_reassigned_callables(node.default)
            return
        if isinstance(node, hir.ShortCircuit):
            self._collect_reassigned_callables(node.left)
            self._collect_reassigned_callables(node.right)
            return
        if isinstance(node, hir.StringLength):
            self._collect_reassigned_callables(node.string)
            return
        if isinstance(node, hir.StringIndex):
            self._collect_reassigned_callables(node.string)
            self._collect_reassigned_callables(node.index)
            return
        if isinstance(node, hir.StringSlice):
            self._collect_reassigned_callables(node.string)
            self._collect_reassigned_callables(node.range)
            return
        if isinstance(node, hir.StringEqual):
            self._collect_reassigned_callables(node.left)
            self._collect_reassigned_callables(node.right)
            return
        if isinstance(node, hir.StringConcat):
            self._collect_reassigned_callables(node.left)
            self._collect_reassigned_callables(node.right)
            return
        if isinstance(node, hir.InterpolatedString):
            for part in node.parts:
                self._collect_reassigned_callables(part)
            return
        if isinstance(node, hir.Return) and node.item is not None:
            self._collect_reassigned_callables(node.item)
            return
        if isinstance(node, (hir.ValueCast, hir.RepresentationCast, hir.Transmute)):
            self._collect_reassigned_callables(node.expr)
            return
        if isinstance(node, hir.ObjectLiteral):
            for field in node.fields:
                self._collect_reassigned_callables(field.value)
            return
        if isinstance(node, hir.MemberAccess):
            self._collect_reassigned_callables(node.value)
            return
        if isinstance(node, hir.MemberAssign):
            key = self._member_key(node.target)
            if key is not None:
                self.reassigned_members.add(key)
            self._collect_reassigned_callables(node.target)
            self._collect_reassigned_callables(node.value)
            return

    @staticmethod
    def _member_key(
        node: hir.MemberAccess,
    ) -> tuple[int, tuple[str, ...]] | None:
        names = [node.name]
        root = node.value
        while isinstance(root, hir.MemberAccess):
            names.append(root.name)
            root = root.value
        if not isinstance(root, hir.ExpressedIdentifier) or root.binding_id is None:
            return None
        return root.binding_id, tuple(reversed(names))

    def _member_was_reassigned(self, node: hir.MemberAccess) -> bool:
        key = self._member_key(node)
        if key is None:
            return False
        binding_id, path = key
        if binding_id in self.reassigned_objects:
            return True
        return any(
            changed_binding == binding_id
            and path[:len(changed_path)] == changed_path
            for changed_binding, changed_path in self.reassigned_members
        )

    def check(self) -> None:
        initialized = self._check_block(self.root, set(), {}, set())
        main = next(
            (
                item
                for item in self.root.items
                if isinstance(item, hir.Declare) and item.name == 'main'
            ),
            None,
        )
        if main is None:
            return
        self._validate_main(main)
        assert isinstance(main.expr, hir.FunctionLiteral)
        self._check_function(main.expr, initialized, (), {}, {}, set())

    def _check_block(
        self,
        block: hir.Block,
        initialized: set[int],
        parameters: dict[int, CallableEffect],
        call_stack: set[int],
    ) -> set[int]:
        current = set(initialized) if block.scoped else initialized
        for item in block.items:
            if isinstance(item, hir.Declare):
                if isinstance(item.expr, hir.FunctionLiteral):
                    current = self._check_function_defaults(
                        item.expr,
                        current,
                        parameters,
                        call_stack,
                    )
                else:
                    current = self._check_eager(
                        item.expr,
                        current,
                        parameters,
                        call_stack,
                    )
                if item.binding_id is not None:
                    current.add(item.binding_id)
                continue
            current = self._check_eager(item, current, parameters, call_stack)
        return current

    def _check_eager(
        self,
        node: hir.AST,
        initialized: set[int],
        parameters: dict[int, CallableEffect],
        call_stack: set[int],
    ) -> set[int]:
        if isinstance(node, hir.ExpressedIdentifier):
            self._require_initialized(node, initialized)
            return initialized
        if isinstance(node, hir.Suppress):
            return self._check_eager(
                node.item,
                initialized,
                parameters,
                call_stack,
            )
        if isinstance(node, hir.FunctionLiteral):
            return self._check_function_defaults(
                node,
                initialized,
                parameters,
                call_stack,
            )
        if isinstance(node, hir.OverloadedFunction):
            current = initialized
            for alternate in node.alternates:
                current = self._check_eager(
                    alternate,
                    current,
                    parameters,
                    call_stack,
                )
            return current
        if isinstance(node, hir.Block):
            current = self._check_block(node, initialized, parameters, call_stack)
            return initialized if node.scoped else current
        if isinstance(node, hir.Declare):
            current = self._check_eager(node.expr, initialized, parameters, call_stack)
            if node.binding_id is not None:
                current.add(node.binding_id)
            return current
        if isinstance(node, hir.FunctionCall):
            current = self._check_eager(node.func, initialized, parameters, call_stack)
            for arg in node.pos_args:
                current = self._check_eager(arg, current, parameters, call_stack)
            for arg in node.kw_args.values():
                current = self._check_eager(arg, current, parameters, call_stack)
            targets = self._callable_targets(node.func, parameters, set())
            if targets is None:
                self._unknown_callable(node)
            for target in targets:
                self._check_function(
                    target,
                    current,
                    tuple(node.pos_args),
                    node.kw_args,
                    parameters,
                    call_stack,
                )
            return current
        if isinstance(node, hir.Return):
            return (
                self._check_eager(node.item, initialized, parameters, call_stack)
                if node.item is not None
                else initialized
            )
        if isinstance(node, hir.Flow):
            current = initialized
            reached_known_arm = False
            for arm in node.arms:
                if isinstance(
                    arm.condition,
                    (hir.IteratorExpression, hir.MultiIteratorExpression),
                ):
                    iterators = (
                        [arm.condition]
                        if isinstance(arm.condition, hir.IteratorExpression)
                        else arm.condition.iterators
                    )
                    for iterator in iterators:
                        current = self._check_eager(
                            iterator.iterable,
                            current,
                            parameters,
                            call_stack,
                        )
                    body_initialized = set(current)
                    for iterator in iterators:
                        if iterator.target.binding_id is not None:
                            body_initialized.add(iterator.target.binding_id)
                    self._check_eager(
                        arm.body,
                        body_initialized,
                        parameters,
                        call_stack,
                    )
                    continue
                current = self._check_eager(
                    arm.condition,
                    current,
                    parameters,
                    call_stack,
                )
                if isinstance(arm.condition, hir.Bool) and not arm.condition.value:
                    continue
                self._check_eager(
                    arm.body,
                    set(current),
                    parameters,
                    call_stack,
                )
                if isinstance(arm.condition, hir.Bool) and arm.condition.value:
                    reached_known_arm = True
                    break
            if node.default is not None and not reached_known_arm:
                self._check_eager(
                    node.default,
                    set(current),
                    parameters,
                    call_stack,
                )
            return current
        if isinstance(node, hir.ShortCircuit):
            current = self._check_eager(
                node.left,
                initialized,
                parameters,
                call_stack,
            )
            skip_right = isinstance(node.left, hir.Bool) and (
                node.op in {'and', 'nand'} and not node.left.value
                or node.op in {'or', 'nor'} and node.left.value
            )
            if not skip_right:
                self._check_eager(
                    node.right,
                    set(current),
                    parameters,
                    call_stack,
                )
            return current
        if isinstance(node, hir.ArrayLiteral):
            current = initialized
            for item in node.items:
                current = self._check_eager(
                    item,
                    current,
                    parameters,
                    call_stack,
                )
            return current
        if isinstance(node, hir.ArrayLength):
            return self._check_eager(
                node.array,
                initialized,
                parameters,
                call_stack,
            )
        if isinstance(node, hir.IteratorExpression):
            return self._check_eager(
                node.iterable,
                initialized,
                parameters,
                call_stack,
            )
        if isinstance(node, hir.MultiIteratorExpression):
            current = initialized
            for iterator in node.iterators:
                current = self._check_eager(
                    iterator.iterable,
                    current,
                    parameters,
                    call_stack,
                )
            return current
        if isinstance(node, hir.TypeTest):
            return self._check_eager(
                node.value,
                initialized,
                parameters,
                call_stack,
            )
        if isinstance(node, hir.Index):
            current = self._check_eager(
                node.array,
                initialized,
                parameters,
                call_stack,
            )
            return self._check_eager(
                node.index,
                current,
                parameters,
                call_stack,
            )
        if isinstance(node, hir.IndexAssign):
            current = self._check_eager(
                node.target,
                initialized,
                parameters,
                call_stack,
            )
            return self._check_eager(
                node.value,
                current,
                parameters,
                call_stack,
            )
        if isinstance(node, hir.StringLength):
            return self._check_eager(
                node.string,
                initialized,
                parameters,
                call_stack,
            )
        if isinstance(node, hir.StringIndex):
            current = self._check_eager(
                node.string,
                initialized,
                parameters,
                call_stack,
            )
            return self._check_eager(
                node.index,
                current,
                parameters,
                call_stack,
            )
        if isinstance(node, hir.StringSlice):
            current = self._check_eager(
                node.string,
                initialized,
                parameters,
                call_stack,
            )
            return self._check_eager(
                node.range,
                current,
                parameters,
                call_stack,
            )
        if isinstance(node, hir.StringEqual):
            current = self._check_eager(
                node.left,
                initialized,
                parameters,
                call_stack,
            )
            return self._check_eager(
                node.right,
                current,
                parameters,
                call_stack,
            )
        if isinstance(node, hir.StringConcat):
            current = self._check_eager(
                node.left,
                initialized,
                parameters,
                call_stack,
            )
            return self._check_eager(
                node.right,
                current,
                parameters,
                call_stack,
            )
        if isinstance(node, hir.Assign):
            current = self._check_eager(
                node.target,
                initialized,
                parameters,
                call_stack,
            )
            return self._check_eager(node.value, current, parameters, call_stack)
        if isinstance(node, (hir.ValueCast, hir.RepresentationCast, hir.Transmute)):
            return self._check_eager(node.expr, initialized, parameters, call_stack)
        if isinstance(node, hir.TypeBlock):
            current = initialized
            for item in node.items:
                current = self._check_eager(item, current, parameters, call_stack)
            return current
        if isinstance(node, hir.Range):
            current = initialized
            items = [
                *([] if node.step_pair is None else node.step_pair),
                *([] if node.left is None else [node.left]),
                *([] if node.right is None else [node.right]),
            ]
            seen: set[int] = set()
            for item in items:
                if id(item) in seen:
                    continue
                seen.add(id(item))
                current = self._check_eager(
                    item,
                    current,
                    parameters,
                    call_stack,
                )
            return current
        if isinstance(node, hir.InterpolatedString):
            current = initialized
            for part in node.parts:
                current = self._check_eager(
                    part,
                    current,
                    parameters,
                    call_stack,
                )
            return current
        if isinstance(node, hir.ObjectLiteral):
            current = set(initialized)
            for field in node.fields:
                current = self._check_eager(
                    field.value,
                    current,
                    parameters,
                    call_stack,
                )
                if field.binding_id is not None:
                    current.add(field.binding_id)
            return initialized
        if isinstance(node, hir.MemberAccess):
            return self._check_eager(
                node.value,
                initialized,
                parameters,
                call_stack,
            )
        if isinstance(node, hir.MemberAssign):
            current = self._check_eager(
                node.target,
                initialized,
                parameters,
                call_stack,
            )
            return self._check_eager(
                node.value,
                current,
                parameters,
                call_stack,
            )
        if isinstance(node, hir.TypeValue):
            return initialized
        return initialized

    def _check_function_defaults(
        self,
        function: hir.FunctionLiteral,
        initialized: set[int],
        parameters: dict[int, CallableEffect],
        call_stack: set[int],
    ) -> set[int]:
        current = initialized
        for param in [
            *function.pos_or_kw_args,
            *function.kw_only_args,
            *([function.rest_args] if function.rest_args is not None else []),
        ]:
            if isinstance(param, hir.BoundParam):
                current = self._check_eager(
                    param.value,
                    current,
                    parameters,
                    call_stack,
                )
        return current

    def _check_function(
        self,
        function: hir.FunctionLiteral,
        initialized: set[int],
        arguments: tuple[hir.AST, ...],
        keyword_arguments: dict[str, hir.AST],
        outer_parameters: dict[int, CallableEffect],
        call_stack: set[int],
    ) -> None:
        if id(function) in call_stack:
            return
        available = set(initialized)
        for binding_id, _name in function.object_fields:
            available.add(binding_id)
        parameter_effects: dict[int, CallableEffect] = {}
        for index, param in enumerate(function.pos_or_kw_args):
            if param.binding_id is not None:
                available.add(param.binding_id)
                if index < len(arguments):
                    targets = self._callable_targets(
                        arguments[index],
                        outer_parameters,
                        set(),
                    )
                    if targets is not None:
                        parameter_effects[param.binding_id] = CallableEffect(
                            tuple(targets)
                        )
                elif param.name in keyword_arguments:
                    targets = self._callable_targets(
                        keyword_arguments[param.name],
                        outer_parameters,
                        set(),
                    )
                    if targets is not None:
                        parameter_effects[param.binding_id] = CallableEffect(
                            tuple(targets)
                        )
                elif isinstance(param, hir.BoundParam):
                    targets = self._callable_targets(
                        param.value,
                        outer_parameters,
                        set(),
                    )
                    if targets is not None:
                        parameter_effects[param.binding_id] = CallableEffect(
                            tuple(targets)
                        )
        for param in function.kw_only_args:
            if param.binding_id is not None:
                available.add(param.binding_id)
                argument = keyword_arguments.get(param.name)
                if argument is None and isinstance(param, hir.BoundParam):
                    argument = param.value
                if argument is not None:
                    targets = self._callable_targets(
                        argument,
                        outer_parameters,
                        set(),
                    )
                    if targets is not None:
                        parameter_effects[param.binding_id] = CallableEffect(
                            tuple(targets)
                        )
        if function.rest_args is not None and function.rest_args.binding_id is not None:
            available.add(function.rest_args.binding_id)
        body = function.body
        stack = {*call_stack, id(function)}
        if isinstance(body, hir.Block):
            self._check_block(body, available, parameter_effects, stack)
        else:
            self._check_eager(body, available, parameter_effects, stack)

    def _callable_targets(
        self,
        node: hir.AST,
        parameters: dict[int, CallableEffect],
        seen: set[int],
    ) -> list[hir.FunctionLiteral] | None:
        while isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
            node = node.items[0]
        if isinstance(node, hir.FunctionLiteral):
            return [node]
        if isinstance(node, hir.OverloadedFunction):
            targets: list[hir.FunctionLiteral] = []
            for alternate in node.alternates:
                resolved = self._callable_targets(alternate, parameters, seen)
                if resolved is None:
                    return None
                targets.extend(resolved)
            return targets
        if isinstance(node, hir.ExpressedIdentifier):
            if node.binding_id is None:
                return []
            parameter = parameters.get(node.binding_id)
            if parameter is not None:
                return list(parameter.targets)
            if node.binding_id in seen:
                return []
            binding = self.registry.by_id[node.binding_id]
            if binding.kind == 'function' and binding.function is not None:
                return [binding.function]
            if binding.declaration is not None:
                if node.binding_id in self.reassigned_callables:
                    return None
                return self._callable_targets(
                    binding.declaration.expr,
                    parameters,
                    {*seen, node.binding_id},
                )
            return None
        if isinstance(node, hir.Block):
            values = [
                item
                for item in node.items
                if item.type not in (ty.VOID_TYPE, ty.BOTTOM_TYPE)
            ]
            if len(values) != 1:
                return None
            return self._callable_targets(values[0], parameters, seen)
        if isinstance(node, hir.Flow):
            targets: list[hir.FunctionLiteral] = []
            bodies = [arm.body for arm in node.arms]
            if node.default is not None:
                bodies.append(node.default)
            for body in bodies:
                resolved = self._callable_targets(body, parameters, seen)
                if resolved is None:
                    return None
                targets.extend(resolved)
            return targets
        if isinstance(node, hir.FunctionCall):
            producers = self._callable_targets(node.func, parameters, seen)
            if producers is None:
                return None
            targets: list[hir.FunctionLiteral] = []
            for producer in producers:
                for result in self._function_results(producer.body):
                    resolved = self._callable_targets(result, parameters, seen)
                    if resolved is None:
                        return None
                    targets.extend(resolved)
            return targets
        if isinstance(node, hir.Index):
            array = node.array
            if isinstance(array, hir.ExpressedIdentifier):
                if array.binding_id is None or array.binding_id in seen:
                    return None
                binding = self.registry.by_id.get(array.binding_id)
                if binding is None or binding.declaration is None:
                    return None
                array = binding.declaration.expr
                seen = {*seen, binding.id}
            if not isinstance(array, hir.ArrayLiteral):
                return None
            items = (
                [array.items[node.constant_index]]
                if node.constant_index is not None
                else array.items
            )
            targets: list[hir.FunctionLiteral] = []
            for item in items:
                resolved = self._callable_targets(item, parameters, seen)
                if resolved is None:
                    return None
                targets.extend(resolved)
            return targets
        if isinstance(node, hir.MemberAccess):
            if self._member_was_reassigned(node):
                return None
            field = self._object_field_value(node.value, node.name, parameters, seen)
            if field is not None:
                return self._callable_targets(field, parameters, seen)
            if isinstance(node.type, (ty.FunctionType, ty.OverloadType)):
                return None
            return None
        return None

    def _object_field_value(
        self,
        node: hir.AST,
        name: str,
        parameters: dict[int, CallableEffect],
        seen: set[int],
    ) -> hir.AST | None:
        while isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
            node = node.items[0]
        if isinstance(node, hir.ObjectLiteral):
            for field in node.fields:
                if field.name == name:
                    return field.value
            return None
        if isinstance(node, hir.ExpressedIdentifier):
            if node.binding_id is None or node.binding_id in seen:
                return None
            if node.binding_id in self.reassigned_objects:
                return None
            binding = self.registry.by_id.get(node.binding_id)
            if binding is None or binding.declaration is None:
                return None
            if node.binding_id in self.reassigned_callables:
                return None
            return self._object_field_value(
                binding.declaration.expr,
                name,
                parameters,
                {*seen, node.binding_id},
            )
        if isinstance(node, hir.FunctionCall):
            producers = self._callable_targets(node.func, parameters, seen)
            if producers is None:
                return None
            for producer in producers:
                for result in self._function_results(producer.body):
                    field = self._object_field_value(result, name, parameters, seen)
                    if field is not None:
                        return field
            return None
        return None

    def _function_results(self, node: hir.AST) -> list[hir.AST]:
        if isinstance(node, hir.Return):
            return [node.item] if node.item is not None else []
        if isinstance(node, hir.Block):
            returned: list[hir.AST] = []
            for item in node.items:
                returned.extend(self._function_results(item))
            if returned:
                return returned
            return [
                item
                for item in node.items
                if item.type not in (ty.VOID_TYPE, ty.BOTTOM_TYPE)
            ]
        if isinstance(node, hir.Flow):
            results: list[hir.AST] = []
            for arm in node.arms:
                results.extend(self._function_results(arm.body))
            if node.default is not None:
                results.extend(self._function_results(node.default))
            return results
        return [node] if node.type not in (ty.VOID_TYPE, ty.BOTTOM_TYPE) else []

    def _require_initialized(
        self,
        node: hir.ExpressedIdentifier,
        initialized: set[int],
    ) -> None:
        if node.binding_id is None or node.binding_id in initialized:
            return
        binding = self.registry.by_id[node.binding_id]
        pointers = [
            Pointer(
                span=node.loc,
                message=f'`{binding.name}` may be accessed here before it is initialized',
            ),
            Pointer(
                span=binding.loc,
                message=f'`{binding.name}` is initialized here',
            ),
        ]
        raise UserError(Error(
            srcfile=self.srcfile,
            title=f'`{binding.name}` used before initialization',
            pointer_messages=pointers,
            hint='move the declaration before the call that can reach this use',
        ))

    def _unknown_callable(self, node: hir.FunctionCall) -> NoReturn:
        raise NotImplementedYet(Error(
            srcfile=self.srcfile,
            title='callable initialization effect is not resolved',
            pointer_messages=[
                Pointer(
                    span=node.func.loc,
                    message='the possible callable values are not known here',
                )
            ],
        ))

    def _validate_main(self, declaration: hir.Declare) -> None:
        if not isinstance(declaration.expr, hir.FunctionLiteral):
            self._main_error(declaration, '`main` must be a function')
        function = declaration.expr
        if (
            function.pos_or_kw_args
            or function.kw_only_args
            or function.rest_args is not None
        ):
            self._main_error(
                declaration,
                '`main` must take no arguments',
                'the root entrypoint is invoked without arguments',
            )
        if not (
            function.rettype == ty.VOID_TYPE
            or isinstance(function.rettype, ty.IntegerLiteralType)
            or function.rettype in {
                'int',
                'uint',
                'uint8',
                'uint16',
                'uint32',
                'uint64',
                'int8',
                'int16',
                'int32',
                'int64',
            }
        ):
            self._main_error(
                declaration,
                '`main` must return an integer or `void`',
                f'`main` returns `{type_to_dewy(function.rettype)}`',
            )

    def _main_error(
        self,
        declaration: hir.Declare,
        title: str,
        message: str = 'automatic invocation requires this entrypoint shape',
    ) -> NoReturn:
        raise UserError(Error(
            srcfile=self.srcfile,
            title=title,
            pointer_messages=[Pointer(span=declaration.loc, message=message)],
        ))


def validate_initialization(
    root: hir.AST,
    registry: BindingRegistry,
    srcfile: SrcFile,
) -> None:
    """Validate module execution before target-specific lowering."""
    if not isinstance(root, hir.Block):
        raise TypeError(f'expected Block, got {type(root).__name__}')
    _InitializationChecker(root, registry, srcfile).check()
