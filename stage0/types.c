#include "sloppy0.h"

static Type mk_basic(int kind, int bits, int sign, int size) {
  Type t = {0};
  t.kind = kind; t.bits = bits; t.sign = sign; t.size = size; t.align = size ? size : 1; t.laid_out = true;
  return t;
}
static Type T_void, T_bool, T_int, T_i8, T_i16, T_i32, T_u8, T_u16, T_u32, T_u64, T_float, T_f32, T_str, T_null, T_none, T_range;
Type *t_void = &T_void, *t_bool = &T_bool, *t_int = &T_int, *t_i8 = &T_i8, *t_i16 = &T_i16, *t_i32 = &T_i32,
  *t_u8 = &T_u8, *t_u16 = &T_u16, *t_u32 = &T_u32, *t_u64 = &T_u64, *t_float = &T_float, *t_f32 = &T_f32,
  *t_str = &T_str, *t_null = &T_null, *t_range = &T_range, *t_none = &T_none, *t_rawptr;

__attribute__((constructor)) static void init_types(void) {
  T_void = mk_basic(TY_VOID, 0, 0, 0);
  T_bool = mk_basic(TY_BOOL, 8, 0, 1);
  T_int = mk_basic(TY_INT, 64, 1, 8);
  T_i8 = mk_basic(TY_INT, 8, 1, 1);
  T_i16 = mk_basic(TY_INT, 16, 1, 2);
  T_i32 = mk_basic(TY_INT, 32, 1, 4);
  T_u8 = mk_basic(TY_INT, 8, 0, 1);
  T_u16 = mk_basic(TY_INT, 16, 0, 2);
  T_u32 = mk_basic(TY_INT, 32, 0, 4);
  T_u64 = mk_basic(TY_INT, 64, 0, 8);
  T_float = mk_basic(TY_FLOAT, 64, 1, 8);
  T_f32 = mk_basic(TY_FLOAT, 32, 1, 4);
  T_str = mk_basic(TY_STR, 0, 0, 8); T_str.managed = true;
  T_null = mk_basic(TY_NULL, 0, 0, 8);
  T_none = mk_basic(TY_NONE_LIT, 0, 0, 0);
  T_range = mk_basic(TY_RANGE, 0, 0, 16); T_range.align = 8;
  t_rawptr = mk_ptr(t_u8);
}

// ---- interning ----
#define HT_SIZE 65536
static Type *ht[HT_SIZE];
static int next_var_id = 1;

static uint32_t thash(Type *t) {
  uint64_t h = t->kind * 31 + (uintptr_t)t->elem * 7 + (uintptr_t)t->st * 13 + t->bits + t->mutmask * 17;
  for (int i = 0; i < t->nargs; i++) h = h * 131 + (uintptr_t)t->args[i];
  return (uint32_t)(h ^ (h >> 29)) & (HT_SIZE - 1);
}
static bool tsame(Type *a, Type *b) {
  if (a->kind != b->kind || a->elem != b->elem || a->st != b->st || a->nargs != b->nargs || a->bits != b->bits || a->mutmask != b->mutmask) return false;
  for (int i = 0; i < a->nargs; i++) if (a->args[i] != b->args[i]) return false;
  return true;
}
static Type *intern_type(Type *t) {
  t->has_var = (t->elem && t->elem->has_var);
  for (int i = 0; i < t->nargs; i++) if (t->args[i]->has_var) t->has_var = true;
  if (t->kind == TY_VAR || t->kind == TY_PARAM) t->has_var = true;
  if (!t->has_var || t->kind == TY_PARAM) {
    uint32_t h = thash(t);
    for (Type *x = ht[h]; x; x = x->ref) ; // unused chain
    for (int i = 0; i < HT_SIZE; i++) {
      uint32_t j = (h + i) & (HT_SIZE - 1);
      if (!ht[j]) { Type *n = arena_alloc(sizeof(Type)); *n = *t; ht[j] = n; return n; }
      if (tsame(ht[j], t)) return ht[j];
    }
    fatal((Pos){-1, 0, 0}, "type table full");
  }
  Type *n = arena_alloc(sizeof(Type));
  *n = *t;
  return n;
}

Type *mk_array(Type *e) { Type t = {0}; t.kind = TY_ARRAY; t.elem = e; return intern_type(&t); }
Type *mk_ptr(Type *e) { Type t = {0}; t.kind = TY_PTR; t.elem = e; return intern_type(&t); }
Type *mk_opt(Type *e) { Type t = {0}; t.kind = TY_OPT; t.elem = e; return intern_type(&t); }
static Type **dup_types(Type **a, int n) { Type **r = arena_alloc(sizeof(Type *) * (n ? n : 1)); memcpy(r, a, sizeof(Type *) * n); return r; }
Type *mk_fn(Type **params, int n, Type *ret, uint32_t mutmask) {
  Type t = {0}; t.kind = TY_FN; t.args = dup_types(params, n); t.nargs = n; t.elem = ret; t.mutmask = mutmask;
  return intern_type(&t);
}
Type *mk_tuple(Type **elems, int n) { Type t = {0}; t.kind = TY_TUPLE; t.args = dup_types(elems, n); t.nargs = n; return intern_type(&t); }
Type *mk_var(void) { Type t = {0}; t.kind = TY_VAR; t.id = next_var_id++; return intern_type(&t); }
Type *mk_param(int idx) { Type t = {0}; t.kind = TY_PARAM; t.id = idx; t.bits = idx; return intern_type(&t); }

Type *prune(Type *t) {
  while (t && t->kind == TY_VAR && t->ref) t = t->ref;
  return t;
}

bool is_int(Type *t) { t = prune(t); return t && t->kind == TY_INT; }
bool is_float(Type *t) { t = prune(t); return t && t->kind == TY_FLOAT; }
bool is_numeric(Type *t) { return is_int(t) || is_float(t); }

static bool occurs(Type *v, Type *t) {
  t = prune(t);
  if (t == v) return true;
  if (!t->has_var) return false;
  if (t->elem && occurs(v, t->elem)) return true;
  for (int i = 0; i < t->nargs; i++) if (occurs(v, t->args[i])) return true;
  return false;
}

Type *zonk(Type *t) {
  t = prune(t);
  if (!t || !t->has_var || t->kind == TY_VAR || t->kind == TY_PARAM) return t;
  Type c = *t;
  if (c.elem) c.elem = zonk(c.elem);
  if (c.nargs) {
    c.args = arena_alloc(sizeof(Type *) * c.nargs);
    for (int i = 0; i < c.nargs; i++) c.args[i] = zonk(t->args[i]);
  }
  c.laid_out = false;
  if (c.kind == TY_STRUCT || c.kind == TY_ENUM) return t; // struct instances are created with concrete args
  return intern_type(&c);
}

bool type_eq(Type *a, Type *b) {
  a = prune(a); b = prune(b);
  if (a == b) return true;
  if (!a || !b) return false;
  if (!a->has_var && !b->has_var) return false;
  if (a->kind != b->kind || a->nargs != b->nargs || a->bits != b->bits) return false;
  if (a->kind == TY_VAR) return false;
  if (a->st != b->st) return false;
  if ((a->elem || b->elem) && !type_eq(a->elem, b->elem)) return false;
  for (int i = 0; i < a->nargs; i++) if (!type_eq(a->args[i], b->args[i])) return false;
  return true;
}

bool unify(Type *a, Type *b) {
  a = prune(a); b = prune(b);
  if (a == b) return true;
  if (a->kind == TY_VAR) { if (occurs(a, b)) return false; a->ref = b; return true; }
  if (b->kind == TY_VAR) { if (occurs(b, a)) return false; b->ref = a; return true; }
  if (a->kind != b->kind || a->nargs != b->nargs || a->bits != b->bits || a->sign != b->sign) return false;
  if (a->kind == TY_STRUCT || a->kind == TY_ENUM) {
    if (a->st == b->st) return true;
    if (!a->st || !b->st || a->st->decl != b->st->decl) return false;
    for (int i = 0; i < a->st->ntargs; i++) if (!unify(a->st->targs[i], b->st->targs[i])) return false;
    return true;
  }
  if (a->elem || b->elem) { if (!a->elem || !b->elem || !unify(a->elem, b->elem)) return false; }
  for (int i = 0; i < a->nargs; i++) if (!unify(a->args[i], b->args[i])) return false;
  if (a->kind == TY_FN && a->mutmask != b->mutmask) return false;
  return true;
}

bool is_managed(Type *t) {
  t = prune(t);
  switch (t->kind) {
  case TY_STR: case TY_ARRAY: case TY_FN: return true;
  case TY_STRUCT: case TY_ENUM: case TY_TUPLE: case TY_OPT: layout(t); return t->managed;
  default: return false;
  }
}

bool is_aggregate(Type *t) {
  t = prune(t);
  switch (t->kind) {
  case TY_STRUCT: case TY_TUPLE: case TY_OPT: case TY_FN: case TY_RANGE: return true;
  case TY_ENUM: layout(t); return !t->st->simple_enum;
  default: return false;
  }
}

static int align_up(int x, int a) { return (x + a - 1) & ~(a - 1); }
void check_struct_fields(StructInfo *si); // check.c

void layout(Type *t) {
  t = prune(t);
  if (t->laid_out) return;
  switch (t->kind) {
  case TY_ARRAY: t->size = t->align = 8; t->managed = true; break;
  case TY_PTR: case TY_NULL: t->size = t->align = 8; break;
  case TY_FN: t->size = 16; t->align = 8; t->managed = true; break;
  case TY_OPT: {
    Type *e = prune(t->elem);
    layout(e);
    t->align = e->align ? e->align : 1;
    t->size = align_up(e->size + 1, t->align);
    t->managed = is_managed(e);
    break;
  }
  case TY_TUPLE: {
    int off = 0, al = 1; bool m = false;
    for (int i = 0; i < t->nargs; i++) {
      Type *e = prune(t->args[i]); layout(e);
      off = align_up(off, e->align ? e->align : 1);
      off += e->size;
      if (e->align > al) al = e->align;
      if (is_managed(e)) m = true;
    }
    t->size = align_up(off, al); t->align = al; t->managed = m;
    break;
  }
  case TY_STRUCT: {
    StructInfo *si = t->st;
    check_struct_fields(si);
    if (si->resolving) fatal(si->decl->pos, "struct '%.*s' contains itself (use an array or optional... recursive types need indirection via [T])", si->decl->name.len, si->decl->name.p);
    si->resolving = true;
    int off = 0, al = 1; bool m = false;
    for (int i = 0; i < si->nfields; i++) {
      Type *e = prune(si->fields[i].type); layout(e);
      off = align_up(off, e->align ? e->align : 1);
      si->fields[i].offset = off;
      off += e->size;
      if (e->align > al) al = e->align;
      if (is_managed(e)) m = true;
    }
    si->resolving = false;
    t->size = align_up(off, al); t->align = al; t->managed = m;
    break;
  }
  case TY_ENUM: {
    StructInfo *si = t->st;
    check_struct_fields(si);
    if (si->resolving) fatal(si->decl->pos, "enum '%.*s' contains itself", si->decl->name.len, si->decl->name.p);
    si->resolving = true;
    int psize = 0, pal = 4; bool m = false;
    for (int v = 0; v < si->nvariants; v++) {
      Variant *var = &si->variants[v];
      int off = 0;
      for (int i = 0; i < var->nfields; i++) {
        Type *e = prune(var->fields[i].type); layout(e);
        off = align_up(off, e->align ? e->align : 1);
        var->fields[i].offset = off;
        off += e->size;
        if (e->align > pal) pal = e->align;
        if (is_managed(e)) m = true;
      }
      if (off > psize) psize = off;
    }
    si->resolving = false;
    si->simple_enum = psize == 0;
    si->payload_off = align_up(4, pal);
    for (int v = 0; v < si->nvariants; v++)
      for (int i = 0; i < si->variants[v].nfields; i++) si->variants[v].fields[i].offset += si->payload_off;
    if (si->simple_enum) { t->size = 4; t->align = 4; }
    else { t->size = align_up(si->payload_off + psize, pal); t->align = pal; }
    t->managed = m;
    break;
  }
  default: break;
  }
  t->laid_out = true;
}

static void tstr(char *buf, int *n, int cap, Type *t) {
#define P(...) (*n += snprintf(buf + *n, cap - *n > 0 ? cap - *n : 0, __VA_ARGS__))
  t = prune(t);
  if (!t) { P("?"); return; }
  switch (t->kind) {
  case TY_VOID: P("void"); break;
  case TY_BOOL: P("bool"); break;
  case TY_INT:
    if (t == t_int) P("int"); else P("%c%d", t->sign ? 'i' : 'u', t->bits);
    break;
  case TY_FLOAT: if (t->bits == 64) P("f64"); else P("f32"); break;
  case TY_STR: P("str"); break;
  case TY_ARRAY: case TY_OPT: { // T[] T? (function types need parentheses)
    bool fn = prune(t->elem)->kind == TY_FN;
    if (fn) P("(");
    tstr(buf, n, cap, t->elem);
    if (fn) P(")");
    P(t->kind == TY_ARRAY ? "[]" : "?");
    break;
  }
  case TY_PTR: P("*"); tstr(buf, n, cap, t->elem); break;
  case TY_NULL: P("null"); break;
  case TY_RANGE: P("range"); break;
  case TY_NONE_LIT: P("none"); break;
  case TY_VAR: P("?T%d", t->id); break;
  case TY_PARAM: P("$%d", t->id); break;
  case TY_MODULE: P("module"); break;
  case TY_TYPE: P("type"); break;
  case TY_FN:
    P("(");
    for (int i = 0; i < t->nargs; i++) { if (i) P(", "); if (t->mutmask & (1u << i)) P("mut "); tstr(buf, n, cap, t->args[i]); }
    P(") -> ");
    tstr(buf, n, cap, t->elem);
    break;
  case TY_TUPLE:
    P("(");
    for (int i = 0; i < t->nargs; i++) { if (i) P(", "); tstr(buf, n, cap, t->args[i]); }
    P(")");
    break;
  case TY_STRUCT: case TY_ENUM: {
    Str nm = t->st->decl->name;
    if (str_eqc(nm, "Map") && t->st->ntargs == 2) {
      P("{"); tstr(buf, n, cap, t->st->targs[0]); P(": "); tstr(buf, n, cap, t->st->targs[1]); P("}");
      break;
    }
    P("%.*s", nm.len, nm.p);
    if (t->st->ntargs) {
      P("[");
      for (int i = 0; i < t->st->ntargs; i++) { if (i) P(", "); tstr(buf, n, cap, t->st->targs[i]); }
      P("]");
    }
    break;
  }
  }
#undef P
}
const char *type_str(Type *t) {
  char buf[512]; int n = 0;
  tstr(buf, &n, sizeof buf, t);
  return xstrndup(buf, n < (int)sizeof buf ? n : (int)sizeof buf - 1);
}
