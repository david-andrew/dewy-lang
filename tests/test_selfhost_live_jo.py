"""New executable compiler Jo needs an explicit bridge contract through the execution cutover."""
from collections import Counter
from pathlib import Path
import re

from tools.compiler.build import FROZEN_TWINS

COMPILER = Path(__file__).resolve().parents[1] / "compiler"
# Keep overloads separately. A new body in an existing bridge file needs review too.
BRIDGES = {
    "ast": ("Supply the shared AST and child-list arenas to node operations.",
            "mk set_list set_list2 kid kid2 nkids nkids2 set_kid kid_c kid_d kids kids2 "
            "has_flag add_flag clear_flag clone dewy_note_member decl_has_rest"),
    "dewy_fmt": ("Read or restore the parser file and source through the bootstrap adapter.", "df_file df_file"),
    "dewy_nodes": ("Pass the node arena and token ordinal to bound construction.", "dw_singleton_bound"),
    "directives": ("Pass the shared per-module directive tables to their index.",
                   "dir_module_start dir_module_end dir_find dir_value dir_code_slot"),
    "fmt": ("Catch a lexer nonlocal exit in the frame that invokes the lexer.", "fmt_try_tokens"),
    "frontend": ("Bind the source reader to the available bootstrap frontend.", "source_force_body"),
    "main": ("Adapt the no-argument versioning callback and enter the Dewy CLI.", "driver_version main"),
    "member_replay": ("Expose a node kind's ABI ordinal without copying the node.", "member_kind_ordinal"),
    "nd_contracts": ("Forward calls with the shared contract tables and checker state.",
                     "fact_nd_call fact_nd_plain_store fact_nd_reads_only nd_mutable_call nd_mutable_entry "
                     "nd_mutable_check nd_mutable_handle nd_call_entry nd_contracts_reset"),
    "opt": ("Bind stable workspace addresses and expose value-only opcode table lookups.",
            "opt_bind_addresses o_pure o_defines kills_memory cse_arity o_operand_mask"),
    "par": ("Read an unaligned native word or use the C seed's bytewise fallback.", "pr"),
    "spirv": ("Pass float32 bits to the shared constant pool.", "sv_cf"),
    "string_domains": ("Pass shared arenas, a token ordinal and the mutable output to domain queries.",
                       "domain_leaf domain_literals"),
    "types": ("Provide shared type, substitution and type-argument tables to their operations.",
              "targ tkind telem has_var mk_type fn_type_pack prune is_int is_float is_numeric is_vec "
              "struct_targ type_eq align_up tsize talign is_union union_members"),
    "units": ("Read a type kind or pass the shared table to quantity-base lookup.", "is_quantity quantity_base"),
    "util": ("Supply intern and source-position storage to Dewy.",
             "intern intern_sub intern_new name_of name_known mkpos pos_file pos_off pos_in_lib"),
    "watch_sys": ("Install platform signal handling with the watch process ID's address.", "ws_test_signals"),
}


# A parameter may itself be a tuple or a function. Jo's top-level declaration
# begins in column zero, including when its parameters span several lines.
HEADER = re.compile(r"^(\w+)[ \t]*=[ \t]*\((?:[^\n]|\n[ \t]+)*?\s*\)[ \t]*(?:->[^:\n]+)?[ \t]*:", re.M)


def test_live_jo_bodies_have_a_bridge_contract():
    frozen = set(FROZEN_TWINS.values()) | {"dewy_reader_seed.jo"}
    actual = {}
    for path in COMPILER.glob("*.jo"):
        if path.name in frozen:
            continue
        functions = Counter(HEADER.findall(path.read_text()))
        if functions:
            actual[path.stem] = functions
    assert actual == {stem: Counter(names.split()) for stem, (_, names) in BRIDGES.items()}
