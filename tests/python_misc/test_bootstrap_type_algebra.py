"""Execute the Dewy type algebra and compare its normalization with hosted ty."""

import subprocess
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import ty
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def expressions():
    a, b, c = 'A', 'B', 'C'
    return [
        'any', 'never', a,
        ty.union(a, b), ty.intersect(a, b), ty.negate(a),
        ty.negate(ty.union(a, b)), ty.negate(ty.intersect(a, b)),
        ty.intersect(ty.union(a, b), ty.union(b, c)),
        ty.union(a, ty.union(b, a), 'never'),
        ty.intersect(a, ty.intersect(b, a), 'any'),
        ty.TypeNot(ty.TypeNot(a)),
        ty.TypeNot(ty.TypeOr([a, ty.TypeAnd([b, c])])),
        ty.ArrayType(ty.TypeNot(ty.TypeNot(a)), 3),
        ty.TypeNot(ty.ArrayType(a)),
        ty.TypeParameterize(a, [ty.TypeNot(ty.TypeNot(b))]),
        ty.sequence(a, ty.sequence(b, c)),
        ty.StringType(), ty.StringType(0), ty.StringLiteralType('hello'),
        ty.IntegerLiteralType(10**60 + 1000000001),
        ty.IntegerLiteralType(-(10**60 + 1000000001)),
        ty.IntegerLiteralType(0),
        ty.BinaryLiteralType(bytes([0, 128, 255])),
        ty.RationalLiteralType(-5, 7), ty.RationalLiteralType(0, 1),
        ty.DimensionType((('length', 1), ('time', -2))),
        ty.QuantityType(ty.TypeNot(ty.TypeNot('int64')), ty.DimensionType((('length', 1),))),
        ty.ObjectType((ty.ObjectField('x', ty.TypeNot(ty.TypeNot('int64')), default=17),), immutable=True),
        ty.PATH_TYPE, ty.PathLiteralType('src/main.dewy'),
    ]


def subtype_expressions():
    plain = ty.FunctionType([ty.PosOrKwArg('x', 'int64')], [], None, 'int64')
    wide = ty.FunctionType([ty.PosOrKwArg('x', 'int')], [], None, 'int64')
    return [
        'any', 'never', 'int', 'uint', 'int8', 'uint8', 'int64', 'bool',
        'string', 'grapheme', 'array', 'generator',
        ty.StringType(), ty.StringType(1), ty.StringLiteralType('hi'),
        ty.IntegerLiteralType(-129), ty.IntegerLiteralType(0), ty.IntegerLiteralType(255),
        ty.ArrayType('int64'), ty.ArrayType('int64', 2), ty.ArrayType('int8'),
        ty.union('int64', 'string'), ty.negate('int'),
        ty.TypeParameterize('generator', ['int64']),
        ty.sequence('int64', 'string'),
        'function', 'multifunction', plain, wide,
        ty.FunctionType([ty.PosOrKwArg(None, 'int64')], [], None, 'int'),
        ty.FunctionType([ty.PosOrKwArg('x', 'int64', required=False)], [], None, 'int64'),
        ty.FunctionType([ty.PosOrKwArg('x', 'int64', place=True)], [], None, 'int64'),
        ty.FunctionType([], [ty.KwOnlyArg('x', 'int64', required=True)], None, 'int64'),
        ty.FunctionType([], [ty.KwOnlyArg('x', 'int', required=False)], None, 'int64'),
        ty.FunctionType([], [], 'rest', 'int64'),
        ty.OverloadType([plain, wide]),
        'rational', 'number', ty.RationalLiteralType(2, 3), ty.RationalLiteralType(3, 2),
        ty.BinaryLiteralType(b'ab'), ty.BinaryLiteralType(b'ac'),
        ty.ArrayType('uint8'), ty.ArrayType('uint8', 2),
        ty.DimensionType(()), ty.DimensionType((('length', 1),)),
        ty.QuantityType('int64', ty.DimensionType((('length', 1),))),
        ty.QuantityType('int', ty.DimensionType((('length', 1),))),
        ty.QuantityType('int64', ty.DimensionType((('time', 1),))),
        'object', ty.ObjectType(()),
        ty.ObjectType((ty.ObjectField('x', 'int64'),)),
        ty.ObjectType((ty.ObjectField('x', 'int64', default=17),)),
        ty.ObjectType((ty.ObjectField('x', 'int64'),), immutable=True),
        ty.ObjectType((ty.ObjectField('x', 'int64', mutable=False),)),
        ty.ObjectType((ty.ObjectField('x', 'int'),)),
        ty.ObjectType((ty.ObjectField('y', 'int64'),)),
        ty.PATH_TYPE, ty.PathLiteralType('a'), ty.PathLiteralType('b'),
        ty.ObjectType((ty.ObjectField('path', ty.StringType()),)),
        ty.ModuleType((ty.ModuleField('x', 'int64', 1),)),
        ty.ModuleType((ty.ModuleField('x', 'int64', 2),)),
        ty.MetaType(ty.ObjectType(())),
        ty.RefinedType('int64', (ty.Proposition('self', '>=?', 0),)),
        ty.RefinedType('int64', (ty.Proposition('self', '>?', 0),)),
    ]


def dispatch_cases():
    def method(args, result='int64', *, kw=(), rest=None, params=()):
        return ty.FunctionType([ty.PosOrKwArg(name, kind, required) for name, kind, required in args],
                               list(kw), rest, result, list(params))
    narrow = method([('x', 'int64', True)])
    wide = method([('x', 'int', True)], 'int')
    unsigned = method([('x', 'uint64', True)], 'uint64')
    optional = method([('x', 'int64', False)])
    named = method([], kw=[ty.KwOnlyArg('x', 'int64', True)])
    generic = method([('x', 'T', True)], 'T', params=[ty.GenericParam('T')])
    pair = method([('x', 'T', True), ('y', 'T', True)], 'T', params=[ty.GenericParam('T', 'number')])
    array = method([('x', ty.ArrayType('T'), True)], 'T', params=[ty.GenericParam('T')])
    binary = method([('x', 'int64', True), ('y', 'int64', True)])
    return [
        ([narrow, wide], ['int64'], {}, None),
        ([wide, narrow], ['int64'], {}, None),
        ([narrow, unsigned], [ty.IntegerLiteralType(1)], {}, None),
        ([narrow, unsigned], [ty.IntegerLiteralType(1)], {}, 'uint64'),
        ([narrow], ['bool'], {}, None),
        ([narrow, narrow], ['int64'], {}, None),
        ([optional], [], {}, None),
        ([narrow], [], {}, None),
        ([named], [], {'x': 'int64'}, None),
        ([named], [], {}, None),
        ([named], [], {'x': 'int64', 'extra': 'bool'}, None),
        ([narrow], ['int64'], {'x': 'int64'}, None),
        ([method([], rest='rest')], ['bool'], {'extra': 'int64'}, None),
        ([generic], ['string'], {}, None),
        ([pair], [ty.IntegerLiteralType(1), ty.IntegerLiteralType(2)], {}, None),
        ([pair], ['string', 'string'], {}, None),
        ([generic], ['int64'], {}, 'int'),
        ([generic], ['string'], {}, 'int'),
        ([array], [ty.ArrayType('int64', 2)], {}, None),
        ([binary], ['int16', 'uint16'], {}, None),
        ([generic], [ty.RefinedType('int64', (ty.Proposition('self', '>=?', 0),))], {}, None),
        ([method([('x', 'T', True), ('y', 'T', True)], 'T', params=[ty.GenericParam('T')])],
         [ty.BinaryLiteralType(b'ab'), ty.BinaryLiteralType(b'cd')], {}, None),
        ([method([('x', ty.ObjectType((ty.ObjectField('value', 'T'),)), True)], 'T', params=[ty.GenericParam('T')])],
         [ty.ObjectType((ty.ObjectField('value', 'int64'),))], {}, None),
    ]


def join_cases():
    positive = ty.RefinedType('int64', (ty.Proposition('self', '>?', 0),))
    nonnegative = ty.RefinedType('int64', (ty.Proposition('self', '>=?', 0),))
    return [[], ['never', 'int64'], ['int8', 'int'], ['int', 'int8'],
            [ty.StringLiteralType('x'), 'string'], [ty.ArrayType('int64', 2), ty.ArrayType('int64')],
            [positive, 'int64'], ['int64', positive], [positive, nonnegative],
            [ty.ArrayType(positive), ty.ArrayType('int64')],
            [ty.ObjectType((ty.ObjectField('x', positive),)), ty.ObjectType((ty.ObjectField('x', 'int64'),))],
            [ty.FunctionType([], [], None, 'int64'), ty.FunctionType([], [], None, 'int')]]


def dispatch_spelling(result):
    return '|'.join([str(result.method_index), spelling(result.method.ret),
                     ','.join(spelling(p.type) for p in result.method.pos_or_kw),
                     ','.join('none' if p is None else spelling(p) for p in result.promote_pos)])


def spelling(node):
    if isinstance(node, str):
        return node
    if isinstance(node, ty.TypeNot):
        return f'~({spelling(node.type)})'
    if isinstance(node, (ty.TypeAnd, ty.TypeOr, ty.SequenceType)):
        separator = ' & ' if isinstance(node, ty.TypeAnd) else ' | ' if isinstance(node, ty.TypeOr) else ' '
        return '(' + separator.join(map(spelling, node.items)) + ')'
    if isinstance(node, ty.ArrayType):
        length = '' if node.length is None else f' length={node.length}'
        return f'array<{spelling(node.element)}{length}>'
    if isinstance(node, ty.StringType):
        return 'string' if node.length is None else f'string<length={node.length}>'
    if isinstance(node, ty.StringLiteralType):
        return '"' + node.value + '"'
    if isinstance(node, ty.IntegerLiteralType):
        return str(node.value)
    if isinstance(node, ty.BinaryLiteralType):
        return 'bytes[' + ','.join(map(str, node.value)) + ']'
    if isinstance(node, ty.RationalLiteralType):
        return f'{node.numerator}/{node.denominator}'
    if isinstance(node, ty.DimensionType):
        return 'dimension[' + ' '.join(f'{name}^{exponent}' for name, exponent in node.powers) + ']'
    if isinstance(node, ty.QuantityType):
        return f'quantity<{spelling(node.number)} {spelling(node.dimension)}>'
    if isinstance(node, ty.PathLiteralType):
        return f'path("{node.value}")'
    if isinstance(node, ty.PathType):
        return 'path'
    if isinstance(node, ty.ObjectType):
        fields = ' '.join(('' if f.mutable else 'const ') + f'{f.name}:{spelling(f.type)}' for f in node.fields)
        brand = '' if node.brand is None else node.brand + ' '
        return brand + ('const ' if node.immutable else '') + f'[{fields}]'
    if isinstance(node, ty.TypeParameterize):
        return f'{spelling(node.t)}<{" ".join(map(spelling, node.args))}>'
    raise AssertionError(node)


def render_dnf(node):
    return '|'.join('[' + ','.join(f'{str(positive).lower()}:{spelling(atom)}' for positive, atom in clause) + ']'
                    for clause in ty.normalize(node))


@pytest.fixture(scope='module')
def algebra_program(tmp_path_factory):
    work = tmp_path_factory.mktemp('type-algebra')
    lines = [f'import p"{ROOT / "dewy/bootstrap/semantic/ty.dewy"}" as types',
             f'import p"{ROOT / "dewy/bootstrap/semantic/subtyping.dewy"}" as subtyping',
             f'import p"{ROOT / "dewy/bootstrap/semantic/propositions.dewy"}" as facts',
             f'import p"{ROOT / "dewy/bootstrap/semantic/dispatch.dewy"}" as dispatch', '''
render = (clauses:array<types.Clause> nodes:array<types.Type>):>string => {
    let parts:array<string> = []
    loop clause in clauses {
        let literals:array<string> = []
        loop literal in clause.literals {
            literals.push("{literal.positive}:{types.describe(literal.item nodes)}")
        }
        parts.push("[{literals.join(',')}]")
    }
    return parts.join('|')
}
render_dispatch = (result:dispatch.DispatchResult | dispatch.DispatchError nodes:array<types.Type>):>string => {
    if result is? dispatch.DispatchError {
        if result.message.startswith('ambiguous') return 'ambiguous'
        return 'no overload'
    }
    let method = dispatch.method_at(nodes result.method)
    let params:array<string> = []
    loop p in method.pos_or_kw { params.push(types.describe(p.value_type nodes)) }
    let promotions:array<string> = []
    loop p in result.promote_pos { promotions.push(if p is? none 'none' else types.describe(p nodes)) }
    return "{result.method_index}|{types.describe(method.ret nodes)}|{params.join(',')}|{promotions.join(',')}"
}
main = ():>int64 => {
    let nodes:array<types.Type> = []
''']
    counter = 0

    def build(node):
        nonlocal counter
        if isinstance(node, str):
            call = f'types.primitive("{node}" @nodes)'
        elif isinstance(node, (ty.TypeAnd, ty.TypeOr, ty.SequenceType)):
            children = [build(child) for child in node.items]
            function = 'intersect' if isinstance(node, ty.TypeAnd) else 'union' if isinstance(node, ty.TypeOr) else 'sequence'
            call = f'types.{function}([{" ".join(children)}] @nodes)'
        elif isinstance(node, ty.TypeNot):
            call = f'types.negate({build(node.type)} @nodes)'
        elif isinstance(node, ty.ArrayType):
            call = f'types.array_type({build(node.element)} {"none" if node.length is None else node.length} @nodes)'
        elif isinstance(node, ty.StringType):
            call = f'types.string_type({"none" if node.length is None else node.length} @nodes)'
        elif isinstance(node, ty.StringLiteralType):
            call = f'types.string_literal("{node.value}" @nodes)'
        elif isinstance(node, ty.IntegerLiteralType):
            call = f'types.integer_literal({node.value} @nodes)'
        elif isinstance(node, ty.BinaryLiteralType):
            call = f'types.binary_literal([{" ".join(map(str, node.value))}] @nodes)'
        elif isinstance(node, ty.RationalLiteralType):
            call = f'types.rational_literal(({node.numerator}) ({node.denominator}) @nodes)'
        elif isinstance(node, ty.DimensionType):
            powers = ' '.join(f'types.DimensionPower["{name}" ({exponent})]' for name, exponent in node.powers)
            call = f'types.dimension([{powers}] @nodes)'
        elif isinstance(node, ty.QuantityType):
            call = f'types.quantity_type({build(node.number)} {build(node.dimension)} @nodes)'
        elif isinstance(node, ty.PathType):
            value = f'"{node.value}"' if isinstance(node, ty.PathLiteralType) else 'none'
            call = f'types.path_type({value} [] @nodes)'
        elif isinstance(node, ty.ObjectType):
            fields = ' '.join(f'types.ObjectField[name="{f.name}" value_type={build(f.type)} mutable={str(f.mutable).lower()} default={"none" if f.default is None else f.default}]'
                              for f in node.fields)
            brand = 'none' if node.brand is None else f'"{node.brand}"'
            call = f'types.object_type([{fields}] {brand} {str(node.immutable).lower()} [] [] @nodes)'
        elif isinstance(node, ty.ModuleType):
            fields = []
            for f in node.fields:
                value = 'none' if f.type_value is None else build(f.type_value)
                fields.append(f'types.ModuleField["{f.name}" {build(f.type)} {f.binding_id} {value}]')
            call = f'types.module_type([{" ".join(fields)}] @nodes)'
        elif isinstance(node, ty.MetaType):
            call = f'types.meta_type({build(node.family)} @nodes)'
        elif isinstance(node, ty.RefinedType):
            props = ' '.join(f'facts.Proposition[subject="{p.subject}" op="{p.op}" value=({p.value})]' for p in node.propositions)
            call = f'types.refined_type({build(node.base)} [{props}] @nodes)'
        elif isinstance(node, ty.TypeParameterize):
            head = build(node.t)
            args = [build(arg) for arg in node.args]
            call = f'types.parameterize({head} [{" ".join(args)}] @nodes)'
        elif isinstance(node, ty.TypeVariable):
            call = f'types.type_variable("{node.name}" {build(node.bound)} @nodes)'
        elif isinstance(node, ty.FunctionType):
            def slot(p, kind):
                name = 'none' if p.name is None else f'"{p.name}"'
                return f'types.{kind}[name={name} value_type={build(p.type)} required={str(p.required).lower()} place={str(p.place).lower()}]'
            pos = ' '.join(slot(p, 'PosOrKwArg') for p in node.pos_or_kw)
            kw = ' '.join(slot(p, 'KwOnlyArg') for p in node.kw_only)
            rest = 'none' if node.rest is None else f'"{node.rest}"'
            params = ' '.join(f'types.GenericParam["{p.name}" {build(p.bound)}]' for p in node.type_params)
            call = f'types.function_type([{pos}] [{kw}] {rest} {build(node.ret)} [{params}] @nodes)'
        elif isinstance(node, ty.OverloadType):
            methods = [build(method) for method in node.methods]
            call = f'types.overload_type([{" ".join(methods)}] @nodes)'
        else:
            raise TypeError(node)
        name = f't{counter}'
        counter += 1
        lines.append(f'    let {name} = {call}')
        return name

    for expression in expressions():
        name = build(expression)
        lines.append(f'    let clauses{counter} = types.normalize({name} @nodes)')
        lines.append(f'    printl(render(clauses{counter} nodes))')
    matrix = [build(expr) for expr in subtype_expressions()]
    lines.append(f'    let matrix:array<addr> = [{" ".join(matrix)}]')
    lines.extend(['''
    printl("--subtypes--")
    loop a in matrix {
        let row:array<string> = []
        loop b in matrix {
            let fits = subtyping.is_subtype(a b subtyping.default_links @nodes)
            row.push("{fits}")
        }
        printl(row.join(','))
    }
'''])
    lines.extend(['    printl("--dispatch--")',
                  '    let system = dispatch.System[links=subtyping.default_links promotions=[["int16" "uint16" "int64"]]]'])
    for methods, pos, kw, expected in dispatch_cases():
        methods_text = ' '.join(build(m) for m in methods)
        pos_text = ' '.join(build(p) for p in pos)
        kw_text = ' '.join(f'"{name}" -> {build(p)}' for name, p in kw.items())
        expected_text = 'none' if expected is None else build(expected)
        lines.append(f'    let choice{counter} = dispatch.match_best_function([{methods_text}] [{pos_text}] [{kw_text}] {expected_text} system @nodes)')
        lines.append(f'    printl(render_dispatch(choice{counter} nodes))')
    lines.append('    printl("--joins--")')
    system = ty.TypeSystem()
    for values in join_cases():
        members = ' '.join(build(value) for value in values)
        expected = build(system.join(*values))
        lines.append(f'    printl(types.same_type(subtyping.join([{members}] subtyping.default_links @nodes) {expected} nodes))')
    lines.extend(['''
    printl('--dimensions--')
    let length = types.dimension([["length" 1]] @nodes)
    let time = types.dimension([["time" 1]] @nodes)
    let time_squared = types.power_dimension(time 2 @nodes)
    let acceleration = types.divide_dimensions(length time_squared @nodes)
    printl(types.describe(acceleration nodes))
    printl(types.describe(types.multiply_dimensions(acceleration time_squared @nodes) nodes))
    let cancelled = types.dimension([["z" 2] ["a" 3] ["z" (-2)] ["a" (-1)]] @nodes)
    printl(types.describe(cancelled nodes))
    printl(types.describe(types.power_dimension(cancelled 0 @nodes) nodes))
    printl(types.describe(types.rational_literal((-10) (-14) @nodes) nodes))
    printl('--metadata--')
    let int = types.primitive('int64' @nodes)
    let generic = types.primitive('T' @nodes)
    let plain = types.object_type([types.ObjectField['x' int]] none false [] [] @nodes)
    let first = types.object_type([types.ObjectField[name='x' value_type=int default=17]] none false [] [] @nodes)
    let second = types.object_type([types.ObjectField[name='x' value_type=int default=23]] none false [] [] @nodes)
    printl(first not=? second and types.same_type(first second nodes))
    let second_node = types.node_at(nodes second)
    $runtime_assert second_node is? types.ObjectType and second_node.fields.length =? 1
    printl(second_node.fields[0].default =? 23)
    let first_array = types.array_type(first none @nodes)
    let second_array = types.array_type(second none @nodes)
    printl(types.same_type(first_array second_array nodes))
    let positive = facts.Proposition[subject='self' op='>?' value=0]
    let method = types.MethodSpec[name='get' literal=51 binding_id=52 owner='Record']
    let source = types.object_type([types.ObjectField[name='x' value_type=generic default=17 refinement=[positive]]] none true [method] [53] @nodes)
    let replaced = types.substitute(source ['T' -> int] @nodes)
    let normalized = types.to_nnf(replaced @nodes)
    let record = types.node_at(nodes normalized)
    $runtime_assert record is? types.ObjectType and record.fields.length =? 1 and record.methods.length =? 1 and record.constructors.length =? 1
    printl(record.immutable and record.fields[0].default =? 17 and record.methods[0].binding_id =? 52 and record.constructors[0] =? 53)
    printl(types.same_type(record.fields[0].value_type int nodes))
    let invariants = types.object_invariants(record)
    printl(invariants.length =? 1 and invariants[0].subject =? '.x')
    let p = facts.Proposition[subject='self' op='<?' term='xs' term_id=11]
    let q = facts.Proposition[subject='self' op='<?' term='xs' term_id=22]
    let rp = types.refined_type(int [p] @nodes)
    let rq = types.refined_type(int [q] @nodes)
    printl(rp not=? rq and types.same_type(rp rq nodes))
    let q_node = types.node_at(nodes rq)
    $runtime_assert q_node is? types.RefinedType and q_node.propositions.length =? 1
    printl(q_node.propositions[0].term_id =? 22)
    let named = types.named_type('Node' 71 @nodes)
    let optional = types.union([named types.primitive('none' @nodes)] @nodes)
    let recursive = types.object_type([types.ObjectField['next' optional]] none false [] [] @nodes)
    types.resolve_alias(named recursive @nodes)
    printl(types.same_type(types.unfold(named nodes) recursive nodes))
    printl(subtyping.is_subtype(named recursive subtyping.default_links @nodes))
    let parent = types.object_type([types.ObjectField['x' int]] 'Parent' false [] [] @nodes minted=true parent=plain abstract=true)
    let child = types.object_type([types.ObjectField['x' int] types.ObjectField['y' int]] 'Child' false [] [] @nodes minted=true parent=parent)
    printl(subtyping.is_subtype(child parent subtyping.default_links @nodes))
    printl(subtyping.is_subtype(child plain subtyping.default_links @nodes))
    printl(subtyping.is_subtype(types.meta_type(child @nodes) types.meta_type(parent @nodes) subtyping.default_links @nodes))
    return 0
}'''])
    source = work / 'algebra.dewy'
    source.write_text('\n'.join(lines))
    output = work / 'algebra.udewy'
    output.write_text(codegen(SrcFile.from_path(source)))
    return work, output


def test_native_type_algebra_matches_hosted_normalization(algebra_program):
    _work, source = algebra_program
    assert entry_point(source, [], EntryPointOptions(compile_only=True)) == 0
    executable = cache_artifact(source).resolve()
    # The 4,356-pair matrix takes about 24 seconds alone. Leave room for
    # contention with the other native compiler tests in the parallel suite.
    result = subprocess.run([executable], check=True, capture_output=True, text=True, timeout=90)
    normalized, rest = result.stdout.split('--subtypes--\n')
    matrix, dispatch_output = rest.split('--dispatch--\n')
    dispatch_output, rest = dispatch_output.split('--joins--\n')
    joins, dimensions = rest.split('--dimensions--\n')
    dimensions, metadata = dimensions.split('--metadata--\n')
    assert normalized.splitlines() == [render_dnf(expr) for expr in expressions()]
    system = ty.TypeSystem()
    assert matrix.splitlines() == [','.join(str(system.is_subtype(a, b)).lower() for b in subtype_expressions())
                                   for a in subtype_expressions()]
    system.add_promote_rule('int16', 'uint16', 'int64')
    expected_dispatch = []
    for methods, pos, kw, expected in dispatch_cases():
        try:
            expected_dispatch.append(dispatch_spelling(system.match_best_function(methods, pos, kw, expected)))
        except ty.DispatchError as error:
            expected_dispatch.append('ambiguous' if str(error).startswith('ambiguous') else 'no overload')
    assert dispatch_output.splitlines() == expected_dispatch
    assert joins.splitlines() == ['true'] * len(join_cases())
    assert dimensions.splitlines() == ['dimension[length^1 time^-2]', 'dimension[length^1]',
                                       'dimension[a^2]', 'dimension[]', '5/7']
    assert metadata.splitlines() == ['true'] * 13
