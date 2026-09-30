import json

from audit_support import output_directory

from dewy.backend.udewy import lower
from dewy.reporting import Span, SrcFile
from dewy.semantic import hir, ty
from udewy.backend.x86_64 import X86_64Backend

HERE = output_directory()

loc = Span(0, 0)
empty = hir.Block(loc, ty.VOID_TYPE, [], True)
node = hir.Void(loc, ty.VOID_TYPE)
source = SrcFile(None, "")
original = {
    k: getattr(ty, k) for k in ("USER_BRAND_TYPES", "USER_BRAND_PARENTS", "USER_BRANDS")
}
root = ty.ObjectType((ty.ObjectField("x", "int64"),), brand="AuditRoot")
small = ty.ObjectType(root.fields, brand="AuditSmall")
large = ty.ObjectType(
    (*root.fields, *(ty.ObjectField(f"extra{i}", "int64") for i in range(128))),
    brand="AuditLarge",
)
plain = ty.ObjectType(root.fields)
out = {"layout": [], "generic_key": []}
try:
    for include_large in (False, True):
        ty.USER_BRAND_TYPES = {"AuditRoot": root, "AuditSmall": small}
        ty.USER_BRAND_PARENTS = {"AuditSmall": "AuditRoot"}
        if include_large:
            ty.USER_BRAND_TYPES["AuditLarge"] = large
            ty.USER_BRAND_PARENTS["AuditLarge"] = "AuditRoot"
        ty.USER_BRANDS = set(ty.USER_BRAND_TYPES)
        lowerer = lower._Lowerer(empty, source)
        out["layout"].append(
            {
                "large_child_present": include_large,
                "parent_size": lowerer._object_layout(root, node)[0],
                "small_size": lowerer._object_layout(small, node)[0],
                "unbranded_shape_size": lowerer._object_layout(plain, node)[0],
                "record_array_stride": lowerer._array_element_layout(plain, node)[0],
                "int64_array_stride": lowerer._array_element_layout("int64", node)[0],
            }
        )
finally:
    for k, v in original.items():
        setattr(ty, k, v)

value = ty.ObjectType((ty.ObjectField("n", "int64"),))
for depth in range(1, 11):
    children = ty.ArrayType(value)
    value = ty.ObjectType(
        (ty.ObjectField("left", children), ty.ObjectField("right", children))
    )
    if depth in (6, 8, 10):
        out["generic_key"].append(
            {
                "shared_graph_depth": depth,
                "distinct_record_and_array_nodes": depth * 2 + 1,
                "repr_bytes": len(repr(value).encode()),
                "record_storage_bytes": lower._Lowerer(empty, source)._object_layout(
                    value, node
                )[0],
            }
        )

backend = X86_64Backend()
backend.debug_info = False
label = backend.declare_function("audit_identity", 1)
backend.begin_function(label, "audit_identity", 1, False)
backend.load_param(0)
backend.emit_return()
backend.end_function()
asm = "\n".join(backend._function_code[0][1])
out["identity_assembly"] = asm
(HERE / "layout_and_codegen.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
