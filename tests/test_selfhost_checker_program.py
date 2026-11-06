"""Program checking preserves discovery, initialization and phase order."""
import re
import pytest
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import compare
from tests.selfhost_expr_double import jo_doubles
from tests.test_selfhost_checker_values import DRIVER as BASE, JO as BASE_JO, DOUBLES as BASE_DOUBLES
JO = dict(BASE_JO)
DOUBLES = dict(BASE_DOUBLES)
EXTRA = {'check.jo': {'FK_INIT': 'const FK_INIT = 4',
              'add_universe': 'add_universe = (): events.push("add_universe"); return',
              'bind_from_imports': 'bind_from_imports = (start: int = 0): events.push("bind_from_imports"); '
                                   'return',
              'calls_named': 'calls_named = (n: int, name: str) -> bool: events.push("calls_named"); false',
              'check_all': 'check_all = false',
              'check_build_block': 'check_build_block = (): events.push("check_build_block"); return',
              'check_pending_functions': 'check_pending_functions = (start: int) -> int: '
                                         'events.push("check_pending_functions"); 0',
              'check_pushers_first': 'check_pushers_first = (): events.push("check_pushers_first"); return',
              'cx': 'cx = -1',
              'dewy_main_result': 'dewy_main_result = (decl: int, rt: int): events.push("dewy_main_result"); '
                                  'return',
              'draw_fn': 'draw_fn = 0',
              'export_decls': 'export_decls: int[]',
              'export_fns': 'export_fns: int[]',
              'find_module': 'find_module = (path: str) -> int: events.push("find_module"); 0',
              'float_int_demanded': 'float_int_demanded = false',
              'game_fn': 'game_fn = (m: int, name: str) -> int?: events.push("game_fn"); none',
              'global_ids': 'global_ids: int[]',
              'init_fns': 'init_fns: int[]',
              'late_module_imports': 'late_module_imports = false',
              'lib_dir': 'lib_dir = ""',
              'load_module': 'load_module = (path: str, is_prelude: bool, from: int) -> int: '
                             'events.push("load_module"); 0',
              'load_prelude': 'load_prelude = (): events.push("load_prelude"); return',
              'main_fn': 'main_fn = 0',
              'module_ctx': 'module_ctx: int[]',
              'module_frames': 'module_frames: FnCtx[]',
              'modules': 'modules: Module[]',
              'names_known': 'names_known = (probes: str[]) -> bool: events.push("names_known"); false',
              'new_inst': 'new_inst = (kind: int, m: int, base: str) -> int: events.push("new_inst"); 0',
              'open_globals': 'open_globals: int[]',
              'optional_runtime': 'optional_runtime = ["__requirement_fail", "__panic_narrow", '
                                  '"__mac_syscall"]',
              'prelude': 'prelude: {int: int} = {}',
              'prelude_named': 'prelude_named = (probes: str[], families: bool = false) -> bool: '
                               'events.push("prelude_named"); false',
              'program_callback_checks': 'program_callback_checks = (mainm: int, has_upd: bool, has_drw: '
                                         'bool): events.push("program_callback_checks"); return',
              'program_game': 'program_game = (mainm: int, has_upd: bool, has_drw: bool): '
                              'events.push("program_game"); return',
              'program_main_error0': 'program_main_error0 = (st: int, s: int): '
                                     'events.push("program_main_error0"); return',
              'program_main_error1': 'program_main_error1 = (s: int, rt: int): '
                                     'events.push("program_main_error1"); return',
              'program_name_default': 'program_name_default = (main_path: str): '
                                      'events.push("program_name_default"); return',
              'program_setting_errors': 'program_setting_errors = (mainm: int): '
                                        'events.push("program_setting_errors"); return',
              'program_tests': 'program_tests = (mainm: int, main_path: str): events.push("program_tests"); '
                               'return',
              'program_unused_warnings': 'program_unused_warnings = (mainm: int, main_path: str, runs: '
                                         'bool): events.push("program_unused_warnings"); return',
              'register_module': 'register_module = (m: int): events.push("register_module"); return',
              'runtime_demand': 'runtime_demand = (name: str): events.push("runtime_demand"); return',
              'runtime_ffi_demand': 'runtime_ffi_demand = () -> bool: events.push("runtime_ffi_demand"); '
                                    'false',
              'runtime_fn': 'runtime_fn = (name: str) -> int: events.push("runtime_fn"); 0',
              'runtime_memeq': 'runtime_memeq = -1',
              'runtime_names': 'runtime_names: str[]',
              'runtime_streq': 'runtime_streq = -1',
              'settle_open_globals': 'settle_open_globals = (): events.push("settle_open_globals"); return',
              'setup_module_contexts': 'setup_module_contexts = (prelude_init: int): '
                                       'events.push("setup_module_contexts"); return',
              'skip_main': 'skip_main = false',
              'synth_call': 'synth_call = (name: str, args: int[], pos: int) -> int: '
                            'events.push("synth_call"); 0',
              'target_macos': 'target_macos = false',
              'target_wasm': 'target_wasm = false',
              'test_mode': 'test_mode = false',
              'update_fn': 'update_fn = 0',
              'want_cpu_flag': 'want_cpu_flag = false',
              'want_loop_watch': 'want_loop_watch = false',
              'zonk_tree': 'zonk_tree = (root: int): events.push("zonk_tree"); return'},
 'icount.jo': {'IC_CHECK': 'const IC_CHECK = 1',
               'IC_EFFECTS': 'const IC_EFFECTS = 3',
               'IC_FACTS': 'const IC_FACTS = 2',
               'IC_LIB': 'const IC_LIB = 2',
               'IC_LOAD': 'const IC_LOAD = 0',
               'IC_OWNERSHIP': 'const IC_OWNERSHIP = 4',
               'IC_ROOT': 'const IC_ROOT = 1',
               'IC_SHARED': 'const IC_SHARED = 0',
               'ic_mod': 'ic_mod = (phase: int, m: int) -> int: events.push("ic_mod"); 0',
               'ic_restore': 'ic_restore = (bucket: int): events.push("ic_restore"); return',
               'ic_switch': 'ic_switch = (phase: int, side: int) -> int: events.push("ic_switch"); 0'},
 'ast.jo': {'NF_EXTERN': 'const NF_EXTERN = 4'},
 'types.jo': {'layout': 'layout = (t: int): events.push("layout"); return', 'ts_dewy': 'ts_dewy = false'},
 'arena.jo': {'arena_reset': 'arena_reset = (): events.push("arena_reset"); return',
              'runtime_switch': 'runtime_switch = (): events.push("runtime_switch"); return',
              'runtime_switch_on': 'runtime_switch_on = (name: str): events.push("runtime_switch_on"); '
                                   'return',
              'runtime_switches': 'runtime_switches: str[]'},
 'check_constant.jo': {'cc_reset': 'cc_reset = (): events.push("cc_reset"); return'},
 'concurrency.jo': {'concurrency_claims_finalize': 'concurrency_claims_finalize = (): '
                                                   'events.push("concurrency_claims_finalize"); return',
                    'concurrency_finalize': 'concurrency_finalize = (): events.push("concurrency_finalize"); '
                                            'return',
                    'concurrency_protocol_module': 'concurrency_protocol_module = -1'},
 'expr.jo': {'console_type_id': 'console_type_id = -1'},
 'lazy_bodies.jo': {'dc_force_all': 'dc_force_all = (): events.push("dc_force_all"); return'},
 'deadlock.jo': {'deadlock_finalize': 'deadlock_finalize = (): events.push("deadlock_finalize"); return'},
 'decimals.jo': {'decimal_writers_first': 'decimal_writers_first = (): events.push("decimal_writers_first"); '
                                          'return'},
 'dewy_methods.jo': {'dewy_infer_methods': 'dewy_infer_methods = (): events.push("dewy_infer_methods"); '
                                           'return',
                     'dewy_methods': 'dewy_methods: DewyMethod[]',
                     'dewy_resolve_inherited': 'dewy_resolve_inherited = (): '
                                               'events.push("dewy_resolve_inherited"); return'},
 'prelude.jo': {'dewy_prelude_file': 'dewy_prelude_file = (file: str) -> int: '
                                     'events.push("dewy_prelude_file"); 0',
                'dewy_prelude_module': 'dewy_prelude_module = (name: int) -> int: '
                                       'events.push("dewy_prelude_module"); 0',
                'order_prelude_globals': 'order_prelude_globals = (decls: mut int[]): '
                                         'events.push("order_prelude_globals"); return'},
 'definite.jo': {'dg_check_program': 'dg_check_program = (inits: int[], main: int, later: int[]): '
                                     'events.push("dg_check_program"); return',
                 'dg_globals': 'dg_globals: int[]'},
 'directives.jo': {'directives_reset': 'directives_reset = (): events.push("directives_reset"); return'},
 'effects.jo': {'effects_finalize': 'effects_finalize = (): events.push("effects_finalize"); return',
                'effects_reset': 'effects_reset = (): events.push("effects_reset"); return'},
 'util.jo': {'errors_only': 'errors_only = false',
             'intern': 'intern = (s: str) -> int: events.push("intern"); 0',
             'pos_in_lib': 'pos_in_lib = (p: int) -> bool: events.push("pos_in_lib"); false'},
 'exact.jo': {'exact_prepare': 'exact_prepare = (): events.push("exact_prepare"); return'},
 'facts.jo': {'facts_reset': 'facts_reset = (): events.push("facts_reset"); return'},
 'floats.jo': {'float_keys_reset': 'float_keys_reset = (): events.push("float_keys_reset"); return',
               'floats_notes_reset': 'floats_notes_reset = (): events.push("floats_notes_reset"); return'},
 'ide.jo': {'ide_doc': 'ide_doc = ""',
            'ide_find_file': 'ide_find_file = (path: str) -> int: events.push("ide_find_file"); 0',
            'ide_force': 'ide_force = -1'},
 'import_cycles.jo': {'init_module_order': 'init_module_order = (mainm: int) -> int[]: '
                                           'events.push("init_module_order"); []',
                      'merge_cycle_inits': 'merge_cycle_inits = (order: int[]): '
                                           'events.push("merge_cycle_inits"); return'},
 'string_domains.jo': {'int_domains_finish': 'int_domains_finish = (): events.push("int_domains_finish"); '
                                             'return',
                       'string_domains_finish': 'string_domains_finish = (): '
                                                'events.push("string_domains_finish"); return',
                       'string_domains_materialize': 'string_domains_materialize = (): '
                                                     'events.push("string_domains_materialize"); return'},
 'member_replay.jo': {'member_reset': 'member_reset = (): events.push("member_reset"); return'},
 'ownership.jo': {'ownership_finalize': 'ownership_finalize = (): events.push("ownership_finalize"); return',
                  'ownership_reset': 'ownership_reset = (): events.push("ownership_reset"); return'},
 'pcheck.jo': {'pc_finish': 'pc_finish = (): events.push("pc_finish"); return'},
 'poly_closure.jo': {'poly_families': 'poly_families: PolyFamily[] = [PolyFamily()]',
                     'poly_finish_warnings': 'poly_finish_warnings = (): '
                                             'events.push("poly_finish_warnings"); return'},
 'errors.jo': {'prepare_nominals': 'prepare_nominals = (): events.push("prepare_nominals"); return'},
 'proofs.jo': {'proof_reset': 'proof_reset = (): events.push("proof_reset"); return'},
 'refine.jo': {'refine_reset': 'refine_reset = (): events.push("refine_reset"); return'},
 'parse.jo': {'stop_after': 'stop_after = ""'},
 'safe_paths.jo': {'ut_reset': 'ut_reset = (): events.push("ut_reset"); return',
                   'ut_run': 'ut_run = (): events.push("ut_run"); return'},
 'warn_if.jo': {'wi_reset': 'wi_reset = (): events.push("wi_reset"); return'}}
EXTRA['check.jo']['Module'] = '''struct Module:
    file: i32
    is_prelude: bool
    is_main: bool
    init_fn: i32
    decls: int[]
    names: {int: int}
    inits: int[]
'''
EXTRA['dewy_methods.jo']['dewy_methods'] = 'dewy_methods: int[]'
EXTRA['poly_closure.jo']['poly_families'] = 'poly_families: int[]'
EXTRA['check.jo'].update({
    'load_module': 'load_module = (path: str, prelude: bool, from: int) -> int: events.push("load:" + path); 1',
    'new_inst': 'new_inst = (kind: int, m: int, base: str) -> int: f = fns.len(); fns.push(FnInst(kind=i32(kind))); f',
    'register_module': '''register_module = (m: int):
    events.push("register:{m}")
    if pg_grow and m == 1: modules.push(Module(init_fn=12))
''',
    'check_pending_functions': '''check_pending_functions = (start: int) -> int:
    events.push("pending:{start}")
    loop k in [start..fns.len()): fns[k].state = 2
    fns.len()
''',
    'runtime_fn': 'runtime_fn = (name: str) -> int: events.push("runtime:" + name); 3',
    'runtime_demand': 'runtime_demand = (name: str): events.push("demand:" + name)',
    'runtime_ffi_demand': '''runtime_ffi_demand = () -> bool:
    events.push("ffi")
    if pg_ffi: pg_ffi = false; fns.push(FnInst()); return true
    false
''',
    'program_setting_errors': 'program_setting_errors = (mainm: int): if pg_error: print("program-setting-error"); exit(45)',
    'program_unused_warnings': 'program_unused_warnings = (m: int, path: str, runs: bool): events.push("unused:{runs}")',
})
EXTRA['import_cycles.jo']['init_module_order'] = '''init_module_order = (mainm: int) -> int[]:
    events.push("init-order")
    out: int[]
    loop i in [0..modules.len()): out.push(i)
    out
'''
EXTRA['import_cycles.jo']['merge_cycle_inits'] = 'merge_cycle_inits = (order: int[]): events.push("merge:{order}")'
EXTRA['prelude.jo']['order_prelude_globals'] = 'order_prelude_globals = (decls: mut int[]): events.push("order-globals"); decls.reverse()'
EXTRA['util.jo']['intern'] = 'intern = (s: str) -> int: if s == "main": 1 else: 2'
EXTRA['icount.jo']['ic_switch'] = 'ic_switch = (phase: int, side: int) -> int: events.push("phase:{phase}:{side}"); phase'
EXTRA['check.jo']['synth_call'] = 'synth_call = (name: str, args: int[], pos: int) -> int: events.push("synth:" + name); mk(.call, pos)'
for module, text in jo_doubles(EXTRA).items():
    JO[module] = JO.get(module, '') + text
# Every mock service accesses the same arenas; explicit imports do not re-export them.
for module in EXTRA:
    if module != 'check.jo':
        JO[module] = "use 'check.jo'\nuse 'ast.jo'\n" + JO[module]
DOUBLES['module_paths'] = {
    'dewy': 'path_norm=(p:string):>string=>p\n',
    'jo': 'path_norm = (p: str) -> str: p\n',
}
JO['arena_ops.dewy'] = r'''from p"arena.jo" import (arena_reset as reset_double runtime_switch as switch_double runtime_switch_on as on_double)
arena_reset=():>void=>reset_double()
runtime_switch=():>void=>switch_double()
runtime_switch_on=(name:string):>void=>on_double(name)
'''
JO['deadlock_graph.dewy'] = 'from p"deadlock.jo" import (deadlock_finalize as finalize_double)\ndeadlock_finalize=():>void=>finalize_double()\n'
JO['deadlock_graph.jo'] = "use 'deadlock.jo'\n"
JO['definite_walk.dewy'] = 'from p"definite.jo" import (dg_check_program as check_double)\ndg_check_program=(inits:array<int64> main:int64 later:array<int64>):>void=>check_double(inits main later)\n'
JO['definite_walk.jo'] = "use 'definite.jo'\n"
JO['arena_ops.jo'] = "use 'arena.jo'\n"

DRIVER = ''.join(f"use '{m}'\n" for m in EXTRA) + BASE + r'''
pg_grow = true
pg_ffi = true
pg_error = false
pg_prepare = ():
    prepare(); events = []
    modules = [Module(is_prelude=true), Module(init_fn=11)]
    d = cr_decl([]); nodes[d].mod = 1
    s = syms.len(); syms.push(Sym(kind=.fns, decl=i32(d), ref=i32(d)))
    modules[1].names[1] = s; modules[1].decls = [d]
    prelude[2] = s
    # A used library discovers an export after the initial pending-body sweep.
    libd = cr_decl([]); nodes[libd].mod = 0
    fns.push(FnInst(decl=i32(libd), state=2)); export_decls = [libd]
    runtime_names = ["needed"]; optional_runtime = ["optional", "__mac_syscall"]
    late_module_imports = true
    global_ids = []; pg_grow = true; pg_ffi = true
'''
MAIN = r'''main = ():
    pg_prepare()
    check_program("example.dewy")
    assert(modules.len() == 3 and modules[1].is_main)
    assert(modules[1].inits.len() == 1 and nodes[modules[1].inits[0]].kind == .call)
    assert(events.contains("register:2") and events.contains("runtime:needed"))
    assert(events.contains("demand:optional") and not events.contains("demand:__mac_syscall"))
    assert(events.contains("merge:[0, 1, 2]") and init_fns.len() == 3)
    assert(export_fns.len() == 1 and not pg_ffi)
    assert(events.contains("exact_prepare") and events.contains("ownership_finalize") and events.contains("effects_finalize"))
    print(events)
    # Errors-only checking still finishes domains and initializers, but no analyses.
    pg_prepare(); errors_only = true; test_mode = true; target_macos = true
    check_program("tests.dewy")
    assert(not events.contains("exact_prepare") and not events.contains("effects_finalize"))
    assert(events.contains("runtime:__test_run_begin") and events.contains("demand:__mac_syscall"))
    assert(init_fns.len() == 4 and events.contains("string_domains_materialize"))
    print(events)
    print("ok")
'''
STEMS = ('checker_program', 'checker_call_cost', 'checker_call_convert')

@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_program_twins(compiler, tmp_path, release):
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=STEMS, doubles=DOUBLES, jo_doubles=JO).endswith(b'ok\n')

@pytest.mark.parametrize('case,status,message', [
    ('pg_error = true', 45, b'program-setting-error'),
    ('stop_after = "parse"', 0, b'load:example.dewy'),
])
def test_checker_program_early_exit(compiler, tmp_path, case, status, message):
    driver = DRIVER + 'main = ():\n    pg_prepare()\n    ' + case + '\n    check_program("example.dewy")\n    print("unreachable")\n'
    output = compare(compiler, tmp_path, False, driver,
                     status=status, extra_stems=STEMS, doubles=DOUBLES, jo_doubles=JO)
    if status:
        assert message in output
    assert b'unreachable' not in output

JO['checker_hooks.dewy'] = 'from p"check.jo" import check_pending_functions\nrun_pending_functions=(start:int64):>int64=>check_pending_functions(start)\n'
JO['checker_hooks.jo'] = "use 'check.jo'\nrun_pending_functions = (start: int) -> int: check_pending_functions(start)\n"
