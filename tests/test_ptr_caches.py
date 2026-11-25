from tools.compiler.check_ptr_caches import COMPILER, check


def test_compiler_table_views():
    assert not (issues := list(check(COMPILER))), '\n'.join(issues)


def test_table_specific_effects_and_control_flow(tmp_path):
    (tmp_path / 'rows.jo').write_text('append_node = (): nodes.push(0)\n')
    (tmp_path / 'read.dewy').write_text('use=(x:int32)=>{}\n')
    (tmp_path / 'sample.dewy').write_text('''
indirect=()=>{append_node()}
visit=(again:bool)=>$unsafe {
    let rows=nodes.ptr
    let item=rows + 1
    let children=lists.ptr
    indirect()
    rows=nodes.ptr
    use(rows[0])
    use(children[0])
    use(item[0])
    if again {indirect(); rows=nodes.ptr}
    use(rows[0])
    if again {indirect()}
    use(rows[0])
    rows=nodes.ptr
    loop again {
        use(rows[0])
        indirect()
        continue
    }
}
''')
    issues = list(check(tmp_path))
    assert [int(s.split(':')[-3]) for s in issues] == [11, 15, 18]


def test_reserve_callbacks_and_multiline_calls(tmp_path):
    (tmp_path / 'fixture.dewy').write_text('''
fill=<T>(@rows:array<T>)=>{rows.reserve(16)}
visit=(again:bool)=>$unsafe {
    let p=types.ptr
    if again { fill<int32>(@lists) } else { p=types.ptr }
    let first=p[0]
    p=types.ptr
    if again { host[0].lookup() }
    let second=p[0]
    p=types.ptr
    mystery(
        again)
    let third=p[0]
    p=types.ptr
    p[0]=mystery()
}
''')
    issues = list(check(tmp_path))
    assert [int(s.split(':')[-3]) for s in issues] == [6, 9, 13, 15]


def test_local_lifetimes_and_retained_globals(tmp_path):
    (tmp_path / 'fixture.dewy').write_text('''
let retained:ptr<Row>=$unsafe nodes.ptr
visit=(again:bool)=>$unsafe {
    let p=nodes.ptr
    loop again {
        nodes.reserve(128)
        if again {break}
        p=nodes.ptr
    }
    let last=p[0]
}
''')
    issues = list(check(tmp_path))
    assert len(issues) == 2
    assert 'local variables' in issues[0]
    assert 'old nodes address after reserve' in issues[1]


def test_rereading_a_table_clears_the_diagnostic(tmp_path):
    fixture = tmp_path / 'sample.dewy'
    lines = ['append=()=>{nodes.push(0)}', 'read=()=>$unsafe {', '    let view=nodes.ptr',
             '    append()', '    view=nodes.ptr', '    return view[0]', '}']
    fixture.write_text('\n'.join(lines))
    assert not list(check(tmp_path))
    del lines[4]
    fixture.write_text('\n'.join(lines))
    assert list(check(tmp_path)) == [f'{fixture}:5: read: view may use an old nodes address after append']


def test_free_array_mutator_and_jo_mutable_parameter(tmp_path):
    (tmp_path / 'helpers.jo').write_text('grow = (rows: mut Node[]): reserve(rows, 12)\n')
    (tmp_path / 'read.dewy').write_text('''
read=()=>$unsafe {
    let n=nodes.ptr
    let l=lists.ptr
    grow(@nodes)
    let a=n[0]
    let b=l[0]
    push(@lists 0)
    let c=l[0]
}
''')
    assert [int(s.split(':')[-3]) for s in check(tmp_path)] == [6, 9]


def test_pointer_arguments_remain_live_through_later_arguments(tmp_path):
    path = tmp_path / 'sample.dewy'
    path.write_text('''
consume=(p:ptr<Row> n:int64)=>{}
append=()=>{nodes.push(0)}
visit=()=>$unsafe {
    let p=
        nodes.ptr
    consume(p
            append())
}
''')
    assert list(check(tmp_path)) == [f'{path}:7: visit: p may use an old nodes address after append']
