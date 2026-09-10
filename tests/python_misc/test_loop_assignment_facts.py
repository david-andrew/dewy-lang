"""A loop body does not describe every way execution can leave the loop."""
from test_aggregate_ownership import run


def test_iterator_assignment_facts_do_not_escape_continue_or_empty_paths(tmp_path):
    source = '''
let selected=(values:array<int64>):>int64=>{
    let result:int64?=none
    loop value in values {
        if value =? 1 {result=value continue}
        result=none
    }
    return if result is? none 0 else result
}
let until_match=(values:array<int64>):>int64=>{
    let result:int64?=7
    loop value in values {
        if value =? 1 break
        result=none
    }
    return if result is? none 0 else result
}
let main=():>int64=>{
    printl(selected([]))
    printl(selected([1]))
    printl(selected([2 1]))
    printl(selected([1 2]))
    printl(until_match([]))
    printl(until_match([1]))
    printl(until_match([2 1]))
    return 0
}
'''
    assert run(source, tmp_path).splitlines() == ['0', '1', '1', '0', '7', '7', '0']
