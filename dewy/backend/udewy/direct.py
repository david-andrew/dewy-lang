"""Compile legalized HIR through the existing µDewy backend protocol.

This internal bridge avoids the whole-program source/token round trip. The
µDewy parser still handles uncommon expression and static initializer forms.
Conditions and integer operations use the same backend primitives as its
parser, without printing and tokenizing expressions already checked by Dewy.
Debugger builds continue to use the source route.
"""
from udewy import p0, t1
from udewy.backend import Backend
from udewy.compilation import compiler_allocation_scope

from ...semantic import builtins, hir, ty
from . import emit, lower


_KINDS = dict(t1.SYMBOL_TOKENS)
_KINDS.update({name: kind for name, (_value, kind) in t1.KEYWORD_TOKENS.items()})
_KINDS['not=?'] = t1.Kind.TK_NOT_EQ
_TYPED_OPERATIONS = set(emit.UDEWY_BINOP_DUNDERS) | set(emit.UDEWY_PREFIX_DUNDERS)


class _DirectEmitter:
    def __init__(self, program: lower.LoweredProgram, root: hir.Block, backend: Backend):
        if backend.debug_info:
            raise ValueError('the HIR backend bridge requires debugger metadata to be disabled')
        self.backend = backend
        self.functions = emit.module_functions(program, root)
        self.state = p0.begin_parse(backend)
        self.ctx = emit.EmitContext(
            set(self.functions) | set(builtins.builtin_types),
            {declaration.name for declaration in program.globals},
            debug_locations=False,
        )
        self.program = program
        self.expression_handlers = dict(self._expression_handlers)
        # Intrinsic support/arity is fixed for this backend instance. Keep
        # target-specific answers here, never across compiler invocations.
        self.intrinsic_metadata = {}

    def fragment(self, text, parser):
        previous = self.state.src
        self.state.src = text
        try:
            tokens = t1.tokenize(text)
            result = parser(tokens, self.state)
            if isinstance(result, tuple):
                result = result[0]
            if result is not None and result != len(tokens):
                raise ValueError('unconsumed legalized HIR fragment')
        finally:
            self.state.src = previous

    def expression_fragment(self, node, *, condition=False):
        # Keep µDewy's condition-only short circuiting in its own parser.
        # Value expressions, including every argument, use its eager mode.
        parser = p0.parse_condition_expr if condition else p0.parse_expr
        self.fragment(emit.emit_ast(node, self.ctx),
                      lambda tokens, state: parser(tokens, 0, state, 0))

    def condition(self, node):
        # Lowering has already moved value-position lazy operations into
        # control flow. Only an explicit condition retains ShortCircuit;
        # ordinary expressions and call arguments stay in eager value mode.
        if isinstance(node, hir.ShortCircuit):
            if node.op not in ('and', 'or'):
                self.expression_fragment(node, condition=True)
                return
            self.condition(node.left)
            backend = self.backend
            split = backend.cond_and_split if node.op == 'and' else backend.cond_or_split
            join = backend.cond_and_join if node.op == 'and' else backend.cond_or_join
            label = split()
            self.condition(node.right)
            join(label)
        else:
            self.expression(node)

    def body(self, node):
        p0.push_parse_scope(self.state)
        previous = self.ctx
        self.ctx = previous.child(set(previous.local_names))
        try:
            if isinstance(node, hir.Block):
                self.statements(node.items)
            else:
                self.statement(node)
        finally:
            self.ctx = previous
            p0.pop_parse_scope(self.state)

    def statements(self, items):
        for item in items:
            self.statement(item)
            if emit._leaves_block(item):
                break

    def statement(self, node):
        backend = self.backend
        if isinstance(node, hir.Block):
            if node.scoped:
                self.body(node)
            else:
                self.statements(node.items)
        elif isinstance(node, hir.Return):
            if node.item is None:
                backend.push_void()
            else:
                self.expression(node.item)
            backend.emit_return()
        elif isinstance(node, (hir.Break, hir.Continue)):
            emit.emit_loop_exit(node, 'break' if isinstance(node, hir.Break) else 'continue')
            if self.state.ctx.loop_depth == 0:
                raise ValueError('lowered loop exit outside a loop')
            (backend.emit_break if isinstance(node, hir.Break) else backend.emit_continue)()
        elif isinstance(node, hir.Declare):
            if node.decltype == 'const':
                # Stable local values participate in static intrinsic arguments.
                self.fragment(emit.emit_declare(node, self.ctx),
                              lambda tokens, state: p0.parse_var_decl(tokens, 0, state))
            else:
                self.expression(node.expr)
                slot = backend.alloc_local()
                p0.var_declare(self.state.scope_stack, node.name,
                               p0.LocalEntry(slot, False), '', 0)
                backend.store_local(slot)
            self.ctx.local_names.add(node.name)
        elif isinstance(node, hir.Assign) and node.op == '=' and isinstance(node.target, hir.ExpressedIdentifier):
            self.expression(node.value)
            local = p0.var_lookup(self.state.scope_stack, node.target.name)
            if local is not None:
                if local.is_const:
                    raise ValueError('assignment to a lowered constant')
                backend.store_local(local.slot)
            else:
                global_ = self.state.global_table[node.target.name]
                if global_.is_const or global_.label_id is None:
                    raise ValueError('assignment to a lowered constant')
                backend.store_global(global_.label_id)
        elif isinstance(node, hir.Assign):
            self.fragment(emit.emit_ast(node, self.ctx),
                          lambda tokens, state: p0.parse_assign_or_expr(tokens, 0, state))
        elif isinstance(node, hir.Flow):
            if node.arms and all(isinstance(arm, hir.IfArm) for arm in node.arms):
                for index, arm in enumerate(node.arms):
                    if index:
                        backend.begin_else()
                    self.condition(arm.condition)
                    backend.begin_if()
                    self.body(arm.body)
                if node.default is not None:
                    backend.begin_else()
                    self.body(node.default)
                for _ in node.arms:
                    backend.end_if()
            elif len(node.arms) == 1 and isinstance(node.arms[0], hir.LoopArm) and node.default is None:
                arm = node.arms[0]
                backend.begin_loop()
                self.condition(arm.condition)
                backend.begin_loop_body()
                self.state.ctx.loop_depth += 1
                self.body(arm.body)
                self.state.ctx.loop_depth -= 1
                backend.end_loop()
            else:
                self.fragment(emit.emit_flow(node, self.ctx),
                              lambda tokens, state: p0.parse_statement(tokens, 0, state))
        else:
            self.expression(node)
            backend.pop_value()

    def identifier(self, name):
        backend, state = self.backend, self.state
        local = p0.var_lookup(state.scope_stack, name)
        if local is not None:
            backend.load_local(local.slot)
            return
        global_ = state.global_table.get(name)
        if global_ is not None:
            if global_.label_id is not None:
                backend.load_global(global_.label_id)
            else:
                p0.note_stable_value_use(state, global_.const_value)
                p0.push_stable_value(backend, global_.const_value)
            return
        value = state.ctx.builtin_consts.get(name)
        if value is not None:
            backend.push_const_i64(value)
            return
        entry = p0.note_function_reference(backend, state.fn_table, name, None, 0, '')
        p0.note_fn_use(state, entry.label_id)
        backend.push_fn_ref(entry.label_id)

    def expression(self, node):
        cls = type(node)
        handler = self.expression_handlers.get(cls)
        if handler is None:
            handler = next((handler for base, handler in self._expression_handlers.items()
                            if issubclass(cls, base)), _DirectEmitter.expression_fragment)
            self.expression_handlers[cls] = handler
        handler(self, node)

    def _integer(self, node):
        self.backend.push_const_i64(node.value)

    def _bool(self, node):
        self.backend.push_const_i64(t1.TRUE_VALUE if node.value else t1.FALSE_VALUE)

    def _void(self, node):
        self.backend.push_void()

    def _string(self, node):
        self.backend.push_string_ref(self.backend.intern_string(node.content.encode('utf-8')))

    def _bytes(self, node):
        self.backend.push_string_ref(self.backend.intern_string(node.content))

    def _identifier(self, node):
        self.identifier(node.name)

    def _cast(self, node):
        self.expression(node.expr)

    def _block(self, node):
        if not node.scoped and len(node.items) == 1:
            self.expression(node.items[0])
        else:
            self.expression_fragment(node)

    def _intrinsic_metadata(self, name):
        found = self.intrinsic_metadata.get(name)
        if found is None:
            supported = self.backend.is_intrinsic(name)
            found = (supported, self.backend.intrinsic_arity(name) if supported else None,
                     self.backend.intrinsic_static_arg_indices(name) if supported else ())
            self.intrinsic_metadata[name] = found
        return found

    def call(self, node):
        if node.kw_args:
            raise ValueError('keyword arguments survived lowering')
        backend, state = self.backend, self.state
        name = node.func.name if isinstance(node.func, hir.ExpressedIdentifier) else None
        count = len(node.pos_args)
        operand_type = emit._selected_first_parameter(node) if name in _TYPED_OPERATIONS else None
        intrinsic = None
        if name in emit.UNSIGNED_DUNDER_INTRINSICS and operand_type in emit.UNSIGNED_FIXED_INTS:
            intrinsic = emit.UNSIGNED_DUNDER_INTRINSICS[name]
        elif name == '__rshift__':
            if operand_type in emit.SIGNED_FIXED_INTS:
                intrinsic = '__signed_shr__'
            elif operand_type not in emit.UNSIGNED_FIXED_INTS:
                # Retain the source emitter's diagnostic for an unsupported
                # width rather than guessing a signedness.
                self.expression_fragment(node)
                return
        if intrinsic is not None and count == 2:
            self.intrinsic(intrinsic, node.pos_args)
            return
        binary = emit.UDEWY_BINOP_DUNDERS.get(name) if count == 2 else None
        raw = emit.LOWERED_RAW_SHIFT_DUNDERS.get(name)
        if binary is not None or raw is not None:
            symbol = binary if binary is not None else raw
            left, right = node.pos_args
            symbol = emit.DERIVED_BITWISE_DUNDERS.get(name, symbol)
            self.expression(left)
            if isinstance(right, hir.Integer):
                backend.binary_immediate(_KINDS[symbol], right.value)
            else:
                backend.save_value()
                self.expression(right)
                backend.binary_op(_KINDS[symbol])
            if name in emit.DERIVED_BITWISE_DUNDERS:
                backend.unary_op(t1.Kind.TK_NOT)
            if name in emit.NARROW_WRAPPING_DUNDERS:
                self.wrap_integer(operand_type)
            return
        prefix = emit.UDEWY_PREFIX_DUNDERS.get(name) if count == 1 else None
        if prefix is not None:
            symbol, value = prefix, node.pos_args[0]
            if symbol == '-' and isinstance(value, hir.Integer):
                backend.push_const_i64(-value.value)
            else:
                self.expression(value)
                backend.unary_op(_KINDS[symbol])
            self.wrap_integer(operand_type)
            return
        direct = name is not None and name not in self.ctx.local_names and (
            name in self.ctx.direct_function_names or name in emit.UDEWY_INTRINSICS)
        supported, arity, static_indices = self._intrinsic_metadata(name) if direct else (False, None, ())
        if direct and (name in ('__static_alloca__', '__static_words__')
                       or static_indices):
            self.expression_fragment(node)
            return
        if direct and supported:
            if arity is None or count != arity:
                p0.validate_intrinsic_arity(backend, name, count, 0, '')
            self.intrinsic(name, node.pos_args)
            return
        if not direct:
            self.expression(node.func)
            backend.save_value()
        for argument in node.pos_args:
            self.expression(argument)
            backend.save_value()
        if direct:
            p0.validate_call_arity(backend, count, 0, '')
            entry = p0.note_function_reference(backend, state.fn_table, name, count, 0, '')
            p0.note_fn_use(state, entry.label_id)
            backend.call_direct(entry.label_id, count)
        else:
            p0.validate_call_arity(backend, count, 0, '')
            backend.call_indirect(count)

    # Preserve the reference chain's order for any inherited HIR classes.
    # Only classification is reused; every occurrence still emits/evaluates.
    _expression_handlers = {
        hir.Integer: _integer,
        hir.Bool: _bool,
        hir.Void: _void,
        hir.String: _string,
        hir.BasedString: _bytes,
        hir.ExpressedIdentifier: _identifier,
        hir.ValueCast: _cast,
        hir.Transmute: _cast,
        hir.Block: _block,
        hir.FunctionCall: call,
    }

    def intrinsic(self, name, arguments):
        # The intrinsic backend contract consumes earlier arguments from
        # saved values and the final argument directly from the current value.
        for index, argument in enumerate(arguments):
            if index:
                self.backend.save_value()
            self.expression(argument)
        self.backend.emit_intrinsic(name, len(arguments), None)

    def wrap_integer(self, operand_type):
        """The word reduction used by emit._wrap_fixed_integer, without text."""
        if not isinstance(operand_type, str) or operand_type not in emit.NARROW_FIXED_INTS:
            return
        backend = self.backend
        width = emit.FIXED_INTEGER_WIDTHS[operand_type]
        backend.save_value()
        if operand_type in emit.UNSIGNED_FIXED_INTS:
            backend.push_const_i64((1 << width) - 1)
            backend.binary_op(t1.Kind.TK_AND)
        else:
            shift = 64 - width
            backend.push_const_i64(shift)
            backend.binary_op(t1.Kind.TK_LEFT_SHIFT)
            backend.save_value()
            backend.push_const_i64(shift)
            backend.signed_shr()

    def function(self, name, literal):
        backend, state = self.backend, self.state
        if literal.kw_only_args or literal.rest_args is not None:
            raise ValueError('non-positional signature survived lowering')
        count = len(literal.pos_or_kw_args)
        entry = p0.note_function_reference(backend, state.fn_table, name, count, 0, '')
        if entry.is_defined:
            raise ValueError('duplicate lowered function')
        entry.is_defined = True
        backend.begin_function(entry.label_id, name, count, name == 'main')
        state.current_fn_label_id = entry.label_id
        p0.push_parse_scope(state)
        previous = self.ctx
        self.ctx = emit.EmitContext(previous.direct_function_names,
                                    {param.name for param in literal.pos_or_kw_args},
                                    debug_locations=False)
        for index, parameter in enumerate(literal.pos_or_kw_args):
            slot = backend.alloc_local()
            backend.load_param(index)
            backend.store_local(slot)
            p0.var_declare(state.scope_stack, parameter.name, p0.LocalEntry(slot, False), '', 0)
        body = literal.body
        if emit._contains_return(body):
            self.statement(body)
        elif literal.rettype in (ty.VOID_TYPE, ty.BOTTOM_TYPE):
            self.statements(body.items if isinstance(body, hir.Block) else [body])
            backend.push_void()
            backend.emit_return()
        else:
            self.expression(body)
            backend.emit_return()
        backend.end_function()
        state.current_fn_label_id = None
        p0.pop_parse_scope(state)
        self.ctx = previous

    def stable_word(self, node):
        """Inspect a lowered word without allocating data or recording uses.

        Leave unfamiliar forms to the source parser. In particular, probing
        one static initializer must not emit half its data before falling
        back to that parser for an unsupported operand.
        """
        while isinstance(node, hir.ValueCast):
            node = node.expr
        if isinstance(node, hir.Integer):
            return p0.StableValue('int', node.value)
        if isinstance(node, hir.Bool):
            return p0.StableValue('int', t1.TRUE_VALUE if node.value else t1.FALSE_VALUE)
        if isinstance(node, hir.ExpressedIdentifier):
            return p0.lookup_stable_value(self.state.scope_stack, self.state.global_table,
                                          node.name, self.state.ctx.builtin_consts)
        return None

    def global_declaration(self, declaration):
        """Emit the literal data produced by lowering, sharing µDewy relocations."""
        backend, state = self.backend, self.state
        p0.check_top_level_value_name(state, declaration.name, 0)
        value = declaration.expr
        while isinstance(value, hir.ValueCast):
            value = value.expr
        stable = self.stable_word(value)
        if isinstance(value, (hir.String, hir.BasedString)):
            data = value.content.encode('utf-8') if isinstance(value, hir.String) else value.content
            stable = p0.StableValue('string', backend.intern_string(data))
        elif (isinstance(value, hir.FunctionCall)
              and isinstance(value.func, hir.ExpressedIdentifier)
              and not value.kw_args):
            name = value.func.name
            if name in ('__static_words__', '__static_alloca__') and name not in self.ctx.local_names:
                words = [self.stable_word(argument) for argument in value.pos_args]
                if (name == '__static_words__' and words
                        and all(word is not None and not p0.is_extern_function_value(state, word)
                                for word in words)):
                    for word in words:
                        p0.note_stable_value_use(state, word)
                        if word.kind == 'function':
                            state.static_word_fn_locs.setdefault(word.value, 0)
                    stable = p0.StableValue('static', backend.intern_words([
                        p0.stable_value_to_directive(backend, word) for word in words]))
                elif (name == '__static_alloca__' and len(words) == 1
                      and words[0] is not None and words[0].kind == 'int' and words[0].value >= 0):
                    stable = p0.StableValue('static', backend.intern_static(words[0].value))
        if stable is None:
            self.fragment(emit.emit_declare(declaration, self.ctx), p0.parse_program)
            return
        p0.note_stable_value_use(state, stable)
        label = backend.define_global(None, p0.stable_value_to_directive(backend, stable))
        is_const = declaration.decltype == 'const'
        p0.global_declare(state.global_table, declaration.name,
                          p0.GlobalEntry(label, is_const, stable if is_const else None), '', 0)

    def compile(self):
        # Includes have already been decoded in the lowered HIR. Definitions
        # still follow source order, including references in static words.
        for declaration in self.program.globals:
            self.global_declaration(declaration)
        for name, function in self.functions.items():
            self.function(name, function)
        return p0.finish_parse(self.state)


@compiler_allocation_scope()
def compile_program(program: lower.LoweredProgram, root: hir.Block, backend: Backend) -> str:
    return _DirectEmitter(program, root, backend).compile()
