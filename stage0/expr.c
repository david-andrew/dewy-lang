#include "check.h"

void check_lambda_body(FnInst *f, FnCtx *parent, Node *lam, Type *ret_hint);

static Type *mk_typeval(Type *t) {
  Type *tv = arena_alloc(sizeof(Type));
  tv->kind = TY_TYPE; tv->elem = t; tv->laid_out = true;
  return tv;
}
static Type *mk_modval(Module *m) {
  Type *tv = arena_alloc(sizeof(Type));
  tv->kind = TY_MODULE; tv->mod = m; tv->laid_out = true;
  return tv;
}

Node *mk_ident_local(Local *l, Pos pos) {
  Node *n = new_node(N_IDENT, pos);
  n->name = l->name; n->sym = l; n->type = l->type; n->aux = S_LOCAL;
  n->flags |= NF_CHECKED;
  return n;
}

// ---------------- intrinsics ----------------
static struct { const char *name; int id; bool arr_domain; } intrinsics[] = {
  {"len", IN_LEN, true}, {"cap", IN_ARRCAP, true}, {"push", IN_PUSH, true}, {"pop", IN_POP, true},
  {"insert", IN_INSERT, true}, {"remove", IN_REMOVE, true}, {"clear", IN_CLEAR, true},
  {"reserve", IN_RESERVE, true}, {"resize", IN_RESIZE, true}, {"truncate", IN_TRUNCATE, true},
  {"data", IN_ARRDATA, true},
  {"syscall", IN_SYSCALL, false}, {"mem_copy", IN_MEMCPY, false}, {"mem_set", IN_MEMSET, false},
  {"size_of", IN_SIZEOF, false}, {"align_of", IN_ALIGNOF, false}, {"panic", IN_PANIC, false},
  {"assert", IN_ASSERT, false}, {"print", IN_PRINT, false}, {"embed", IN_EMBED, false},
  {"str_from_bytes", IN_FROM_BYTES, false}, {"bytes", IN_TO_BYTES, false}, {"__argv", IN_ARGV, false},
  {"unreachable", IN_UNREACHABLE, false}, {"sqrt", IN_SQRT, false}, {"__fmt_fields", IN_FMT_STRUCT, false}, {"__fmt_elem_value", IN_FMT_ELEM, false},
  {"__hash_value", IN_HASH, false}, {"__set_len", IN_SETLEN, false},
  {"__atomic_add", IN_ATOMIC_ADD, false}, {"__atomic_cas", IN_ATOMIC_CAS, false},
  {"__stack_ptr", IN_STACK_PTR, false}, {"fill", IN_FILL, false},
  {"__cpu_features", IN_CPU_FEATURES, false},
};

void register_intrinsics(Scope *s) {
  for (size_t i = 0; i < sizeof intrinsics / sizeof *intrinsics; i++)
    scope_add(s, internc(intrinsics[i].name), S_BUILTIN, (void *)(intptr_t)intrinsics[i].id, NULL);
}
static int intrinsic_id(Str name, bool *arr_domain) {
  for (size_t i = 0; i < sizeof intrinsics / sizeof *intrinsics; i++)
    if (str_eqc(name, intrinsics[i].name)) { if (arr_domain) *arr_domain = intrinsics[i].arr_domain; return intrinsics[i].id; }
  return 0;
}

// ---------------- lookup ----------------
Sym *lookup_value(FnCtx *c, Str name) { return scope_lookup(c->scope, name); }

static bool is_lit(Node *n) { return n->flags & NF_LITERAL; }

// a one-character string literal standing for its character code
static bool charlike(Node *n) { return n->kind == N_STR && (n->flags & NF_CHARLIKE); }
static void charlike_to_int(Node *n) {
  const unsigned char *s = (const unsigned char *)n->sval.p;
  int len = n->sval.len;
  int64_t v = s[0];
  if (len > 1) { v &= 0x3f >> (len - 1); for (int i = 1; i < len; i++) v = (v << 6) | (s[i] & 0x3f); }
  n->kind = N_INT; n->ival = v; n->aux = 1; n->type = NULL;
  n->flags = (n->flags & ~(NF_CHARLIKE | NF_CHECKED)) | NF_LITERAL;
}
static Type *lit_default(Node *n) { return n->kind == N_FLOAT ? t_float : t_int; }

static void wrap_conv(Node **pn, int cv, Type *to) {
  Node *c = new_node(N_CONV, (*pn)->pos);
  c->a = *pn; c->aux = cv; c->type = to;
  c->flags |= NF_CHECKED;
  *pn = c;
}

// ---------------- coercion ----------------
static bool int_widens(Type *f, Type *t) {
  if (f->sign == t->sign) return t->bits >= f->bits;
  if (!f->sign && t->sign) return t->bits > f->bits;
  return false;
}

bool can_coerce(Node *n, Type *from, Type *to) {
  from = prune(from); to = prune(to);
  if (type_eq(from, to)) return true;
  if (from == t_never) return true;
  if (from->has_var || to->has_var) {
    // trial: structural compatibility
    if (from->kind == TY_VAR || to->kind == TY_VAR) return true;
    if (from->kind == to->kind && from->kind == TY_ARRAY) return can_coerce(NULL, from->elem, to->elem) && (prune(from->elem)->kind == TY_VAR || prune(to->elem)->kind == TY_VAR || type_eq(from->elem, to->elem));
    if (from->kind == TY_OPT && to->kind == TY_OPT) return true;
  }
  if (n && is_lit(n)) {
    if (n->kind == N_INT && (to->kind == TY_INT || to->kind == TY_FLOAT)) return true;
    if (n->kind == N_FLOAT && to->kind == TY_FLOAT) return true;
  }
  if (from->kind == TY_INT && to->kind == TY_INT) return int_widens(from, to);
  if (from->kind == TY_INT && to->kind == TY_FLOAT) return true;
  if (from->kind == TY_FLOAT && to->kind == TY_FLOAT) return true;
  if (to->kind == TY_OPT) {
    if (from->kind == TY_NONE_LIT) return true;
    if (from->kind == TY_OPT) return type_eq(from->elem, to->elem) || (prune(from->elem)->kind == TY_VAR);
    return can_coerce(n, from, to->elem);
  }
  if (from->kind == TY_NULL && to->kind == TY_PTR) return true;
  if (from->kind == TY_PTR && to->kind == TY_PTR && (to == t_rawptr || from == t_rawptr)) return true;
  return false;
}

void coerce(FnCtx *c, Node **pn, Type *target) {
  (void)c;
  Node *n = *pn;
  Type *from = prune(n->type), *to = prune(target);
  if (!to) return;
  if (charlike(n) && to->kind == TY_INT) { charlike_to_int(n); n->type = t_int; from = t_int; }
  if (!from) fatal(n->pos, "internal: unchecked expression");
  if (from == t_never) return;
  if (is_lit(n)) {
    if (n->kind == N_INT && to->kind == TY_INT) {
      int64_t v = n->ival;
      if (to->bits < 64) {
        int64_t lo = to->sign ? -(1LL << (to->bits - 1)) : 0;
        int64_t hi = to->sign ? (1LL << (to->bits - 1)) - 1 : (int64_t)((1ULL << to->bits) - 1);
        if (v < lo || v > hi) fatal(n->pos, "value %lld does not fit in %s", (long long)v, type_str(to));
      }
      n->type = to; n->flags &= ~NF_LITERAL; return;
    }
    if (n->kind == N_INT && to->kind == TY_FLOAT) { n->kind = N_FLOAT; n->fval = (double)n->ival; n->type = to; n->flags &= ~NF_LITERAL; return; }
    if (n->kind == N_FLOAT && to->kind == TY_FLOAT) { n->type = to; n->flags &= ~NF_LITERAL; return; }
    if (to->kind == TY_OPT && (is_numeric(to->elem))) { coerce(c, pn, to->elem); wrap_conv(pn, CV_OPT, to); return; }
    if (to->kind == TY_VAR) { Type *d = lit_default(n); n->type = d; n->flags &= ~NF_LITERAL; unify(to, d); return; }
  }
  if (type_eq(from, to)) { n->flags &= ~NF_LITERAL; return; }
  if (from->has_var || to->has_var) {
    if (unify(from, to)) return;
    if (to->kind == TY_OPT && unify(from, prune(to)->elem)) { wrap_conv(pn, CV_OPT, to); return; }
  }
  if (from->kind == TY_INT && to->kind == TY_INT) {
    if (int_widens(from, to)) { wrap_conv(pn, CV_INT, to); return; }
    fatal(n->pos, "cannot implicitly convert %s to %s (use %s(x) to convert explicitly)", type_str(from), type_str(to), type_str(to));
  }
  if (from->kind == TY_INT && to->kind == TY_FLOAT) { wrap_conv(pn, CV_INT2FLOAT, to); return; }
  if (from->kind == TY_FLOAT && to->kind == TY_FLOAT) { wrap_conv(pn, CV_FLOAT, to); return; }
  if (to->kind == TY_OPT) {
    if (from->kind == TY_NONE_LIT) { n->type = to; return; }
    if (from->kind == TY_OPT) {
      if (prune(from->elem)->kind == TY_VAR) { unify(from->elem, to->elem); n->type = to; return; }
      fatal(n->pos, "type mismatch: expected %s, found %s", type_str(to), type_str(from));
    }
    coerce(c, pn, to->elem);
    wrap_conv(pn, CV_OPT, to);
    return;
  }
  if (from->kind == TY_NULL && to->kind == TY_PTR) { n->type = to; return; }
  if (from->kind == TY_PTR && to->kind == TY_PTR && (to == t_rawptr || from == t_rawptr)) { wrap_conv(pn, CV_PTR, to); return; }
  if (from->kind == TY_TYPE) fatal(n->pos, "expected a value of type %s, found a type name", type_str(to));
  fatal(n->pos, "type mismatch: expected %s, found %s", type_str(to), type_str(from));
}

Type *check_expr_to(FnCtx *c, Node **pn, Type *target) {
  check_expr(c, pn, target);
  coerce(c, pn, target);
  return target;
}

static Type *finalize_literal(FnCtx *c, Node **pn) {
  if (is_lit(*pn)) coerce(c, pn, lit_default(*pn));
  return (*pn)->type;
}

static Type *num_join(Type *a, Type *b) {
  a = prune(a); b = prune(b);
  if (type_eq(a, b)) return a;
  if (a->kind == TY_FLOAT && b->kind == TY_FLOAT) return a->bits >= b->bits ? a : b;
  if (a->kind == TY_FLOAT && b->kind == TY_INT) return a;
  if (b->kind == TY_FLOAT && a->kind == TY_INT) return b;
  if (a->kind == TY_INT && b->kind == TY_INT) {
    if (int_widens(a, b)) return b;
    if (int_widens(b, a)) return a;
    return NULL;
  }
  return NULL;
}

Type *join_types(FnCtx *c, Node **a, Node **b, Pos pos) {
  Type *ta = prune((*a)->type), *tb = prune((*b)->type);
  if (ta == t_never) { finalize_literal(c, b); return (*b)->type; }
  if (tb == t_never) { finalize_literal(c, a); return (*a)->type; }
  bool la = is_lit(*a), lb = is_lit(*b);
  if (la && !lb && can_coerce(*a, ta, tb)) { coerce(c, a, tb); return tb; }
  if (lb && !la && can_coerce(*b, tb, ta)) { coerce(c, b, ta); return ta; }
  if (la && lb) {
    Type *t = ((*a)->kind == N_FLOAT || (*b)->kind == N_FLOAT) ? t_float : t_int;
    coerce(c, a, t); coerce(c, b, t); return t;
  }
  if (is_numeric(ta) && is_numeric(tb)) {
    Type *j = num_join(ta, tb);
    if (!j) fatal(pos, "cannot mix %s and %s; convert one explicitly", type_str(ta), type_str(tb));
    coerce(c, a, j); coerce(c, b, j); return j;
  }
  if (ta->kind == TY_NONE_LIT || (ta->kind == TY_OPT && prune(ta->elem)->kind == TY_VAR)) {
    Type *t = tb->kind == TY_OPT ? tb : mk_opt(tb);
    coerce(c, a, t); coerce(c, b, t); return t;
  }
  if (tb->kind == TY_NONE_LIT || (tb->kind == TY_OPT && prune(tb->elem)->kind == TY_VAR)) {
    Type *t = ta->kind == TY_OPT ? ta : mk_opt(ta);
    coerce(c, a, t); coerce(c, b, t); return t;
  }
  if (ta->kind == TY_OPT && can_coerce(*b, tb, ta)) { coerce(c, b, ta); return ta; }
  if (tb->kind == TY_OPT && can_coerce(*a, ta, tb)) { coerce(c, a, tb); return tb; }
  coerce(c, b, ta);
  return ta;
}

// ---------------- places ----------------
void check_place(FnCtx *c, Node *n, bool for_mut) {
  (void)c;
  switch (n->kind) {
  case N_IDENT: {
    if (n->aux == S_LOCAL) {
      Local *l = n->sym;
      if ((l->flags & LF_PARAM) && !(l->flags & LF_MUTPARAM))
        fatal(n->pos, "cannot modify parameter '%.*s' (parameters are read-only; mark it `mut` or copy it with `let %.*s = %.*s`)", l->name.len, l->name.p, l->name.len, l->name.p, l->name.len, l->name.p);
      // (closures share the variables they capture; the bootstrap compiler only copies them)
      if (l->flags & (LF_CAPTURE | LF_CAPTURED)) fatal(n->pos, "the bootstrap compiler cannot modify '%.*s' after a closure captured it", l->name.len, l->name.p);
      if (l->flags & LF_BYREF) fatal(n->pos, "cannot modify loop variable '%.*s' (use `loop mut` to modify elements)", l->name.len, l->name.p);
      l->flags |= LF_ASSIGNED;
      return;
    }
    if (n->aux == S_GLOBAL) return;
    fatal(n->pos, "cannot assign to '%.*s'", n->name.len, n->name.p);
  }
  case N_FIELD: {
    Type *bt = prune(n->a->type);
    if (bt->kind == TY_PTR) return;
    check_place(c, n->a, for_mut);
    return;
  }
  case N_INDEX: {
    Type *bt = prune(n->a->type);
    if (bt->kind == TY_PTR) return;
    if (bt->kind == TY_STR) fatal(n->pos, "strings are immutable");
    if (bt->kind != TY_ARRAY) fatal(n->pos, "cannot assign to this index expression");
    if (n->b && prune(n->b->type)->kind == TY_RANGE) fatal(n->pos, "cannot assign to a slice");
    check_place(c, n->a, for_mut);
    return;
  }
  default:
    fatal(n->pos, for_mut ? "a `mut` argument must be a variable, field or element" : "cannot assign to this expression");
  }
}

// ---------------- type expressions written as expressions ----------------
static Type *expr_as_type(FnCtx *c, Node *e) {
  switch (e->kind) {
  case N_IDENT: {
    Node tn = {0}; tn.kind = N_TNAME; tn.name = e->name; tn.pos = e->pos;
    return resolve_type(&tn, c->scope);
  }
  case N_INDEX: {
    if (e->a->kind != N_IDENT) break;
    Node tn = {0}; tn.kind = N_TNAME; tn.name = e->a->name; tn.pos = e->pos;
    NodeList targs = {0};
    if (e->b) { vpush(targs, e->b); } else targs = e->list;
    for (int i = 0; i < targs.len; i++) {
      Node *tn2 = arena_alloc(sizeof(Node));
      Type *t = expr_as_type(c, targs.data[i]);
      tn2->kind = N_TNAME; tn2->pos = targs.data[i]->pos;
      // stash resolved type through a synthetic scope
      Scope *s = scope_new(c->scope, 2, NULL);
      Str nm = internc(fmt("__t%d", i));
      scope_add(s, nm, S_TYPE, t, NULL);
      tn2->name = nm;
      vpush(tn.list, tn2);
      c->scope = s;
    }
    Type *r = resolve_type(&tn, c->scope);
    return r;
  }
  case N_ARRAY:
    if (e->list.len == 1) return mk_array(expr_as_type(c, e->list.data[0]));
    break;
  default: break;
  }
  fatal(e->pos, "expected a type");
}

// ---------------- calls ----------------
typedef struct {
  Node *decl;       // N_FN (NULL for value calls)
  FnSig *sig;
  Type **ptypes;    // for value calls / struct ctors
  int np;
  uint32_t mutmask;
  Node *args[64];   // param index -> arg (NULL: default)
  Type *binds[16];
  int cost;
  bool ok;
} Cand;

static bool ctx_dependent(Node *a) {
  switch (a->kind) {
  case N_IDENT: return (a->flags & NF_GENERIC) != 0; // function name used as a value
  case N_LAMBDA: case N_DOTNAME: case N_NONE: case N_HOLE: return true;
  case N_ARRAY: return a->list.len == 0 && !a->b;
  case N_MAP: return a->list.len == 0;
  default: return false;
  }
}

static Node *unnamed(Node *a) { return a->kind == N_NAMEDARG ? a->a : a; }

// map call args to params; returns false on mismatch (with *err set)
static bool map_args(Node *decl, Str *pnames, int np, Node **defaults, Node **args, int nargs, Node **out, const char **err) {
  for (int i = 0; i < np; i++) out[i] = NULL;
  int pos = 0;
  for (int i = 0; i < nargs; i++) {
    Node *a = args[i];
    if (a->kind == N_NAMEDARG) {
      int k = -1;
      for (int j = 0; j < np; j++) if (str_eq(pnames[j], a->name)) k = j;
      if (k < 0) { *err = fmt("no parameter named '%.*s'", a->name.len, a->name.p); return false; }
      if (out[k]) { *err = fmt("parameter '%.*s' given twice", a->name.len, a->name.p); return false; }
      out[k] = a->a;
    } else {
      if (pos >= np) { *err = fmt("too many arguments (expected %d)", np); return false; }
      out[pos++] = a;
    }
  }
  for (int i = 0; i < np; i++) if (!out[i] && !(defaults && defaults[i])) {
    *err = fmt("missing argument '%.*s'", pnames[i].len, pnames[i].p);
    return false;
  }
  (void)decl;
  return true;
}

static int match_type(Type *pat, Type *a, Type **binds, int depth) {
  pat = prune(pat); a = prune(a);
  if (a == t_never) return 0;
  if (pat->kind == TY_PARAM) {
    if (!binds[pat->id]) { binds[pat->id] = a; return depth == 0 ? 3 : 0; }
    if (type_eq(binds[pat->id], a)) return 0;
    if (prune(binds[pat->id])->has_var && unify(binds[pat->id], a)) return 0;
    if (can_coerce(NULL, a, binds[pat->id])) return 1;
    return -1;
  }
  if (!pat->has_var) {
    if (type_eq(pat, a)) return 0;
    if (a->has_var) {
      if (a->kind == TY_VAR) return 0;
      if (a->kind == pat->kind && a->kind == TY_ARRAY && match_type(pat->elem, a->elem, binds, depth + 1) >= 0) return 0;
      if (a->kind == TY_OPT && pat->kind == TY_OPT) return 0;
    }
    if (a->kind == TY_NONE_LIT && pat->kind == TY_OPT) return 0;
    if (can_coerce(NULL, a, pat)) return (a->kind == TY_INT && pat->kind == TY_FLOAT) || pat->kind == TY_OPT ? 2 : 1;
    return -1;
  }
  if (a->kind == TY_VAR) return 0;
  if (pat->kind == TY_OPT && a->kind != TY_OPT) {
    if (a->kind == TY_NONE_LIT) return 0;
    int r = match_type(pat->elem, a, binds, depth + 1);
    return r < 0 ? -1 : r + 4;
  }
  if (pat->kind != a->kind) return -1;
  switch (pat->kind) {
  case TY_ARRAY: case TY_PTR: case TY_OPT: return match_type(pat->elem, a->elem, binds, depth + 1);
  case TY_FN: case TY_TUPLE: {
    if (pat->nargs != a->nargs) return -1;
    int cost = 0;
    for (int i = 0; i < pat->nargs; i++) { int r = match_type(pat->args[i], a->args[i], binds, depth + 1); if (r < 0) return -1; cost += r; }
    if (pat->kind == TY_FN) { int r = match_type(pat->elem, a->elem, binds, depth + 1); if (r < 0) return -1; cost += r; }
    return cost;
  }
  case TY_STRUCT: case TY_ENUM: {
    if (!a->st || pat->st->decl != a->st->decl) return -1;
    int cost = 0;
    for (int i = 0; i < pat->st->ntargs; i++) { int r = match_type(pat->st->targs[i], a->st->targs[i], binds, depth + 1); if (r < 0) return -1; cost += r; }
    return cost;
  }
  default: return -1;
  }
}

// substitute bound params; unbound params become fresh vars (recorded in binds)
static Type *subst_partial(Type *pat, Type **binds) {
  pat = prune(pat);
  if (!pat->has_var) return pat;
  switch (pat->kind) {
  case TY_PARAM:
    if (!binds[pat->id]) binds[pat->id] = mk_var();
    return binds[pat->id];
  case TY_ARRAY: return mk_array(subst_partial(pat->elem, binds));
  case TY_PTR: return mk_ptr(subst_partial(pat->elem, binds));
  case TY_OPT: return mk_opt(subst_partial(pat->elem, binds));
  case TY_FN: case TY_TUPLE: {
    Type *a[32];
    for (int i = 0; i < pat->nargs; i++) a[i] = subst_partial(pat->args[i], binds);
    return pat->kind == TY_FN ? mk_fn(a, pat->nargs, subst_partial(pat->elem, binds), pat->mutmask) : mk_tuple(a, pat->nargs);
  }
  case TY_STRUCT: case TY_ENUM: {
    Type *a[16];
    for (int i = 0; i < pat->st->ntargs; i++) a[i] = subst_partial(pat->st->targs[i], binds);
    return get_struct_inst(pat->st->decl, a, pat->st->ntargs)->type;
  }
  default: return pat;
  }
}

// cost of passing (unchecked or checked) arg to param pattern
static int arg_cost(Node *a, Type *pat, Type **binds) {
  Type *p = prune(pat);
  if (ctx_dependent(a)) {
    switch (a->kind) {
    case N_HOLE: return 0;
    case N_IDENT: return p->kind == TY_FN ? 0 : p->kind == TY_PARAM ? 3 : -1;
    case N_LAMBDA:
      if (p->kind == TY_PARAM) return a->list.len && a->list.data[0]->a ? 3 : -1;
      if (p->kind != TY_FN || p->nargs != a->list.len) return -1;
      return 0;
    case N_DOTNAME: {
      Type *e = p->kind == TY_OPT ? prune(p->elem) : p;
      if (e->kind != TY_ENUM) return -1;
      check_struct_fields(e->st);
      for (int i = 0; i < e->st->nvariants; i++) if (str_eq(e->st->variants[i].name, a->name)) return 0;
      return -1;
    }
    case N_NONE: return p->kind == TY_OPT ? 0 : p->kind == TY_PARAM ? 3 : -1;
    case N_ARRAY: return p->kind == TY_ARRAY ? 0 : p->kind == TY_PARAM ? 3 : -1;
    case N_MAP: return (p->kind == TY_STRUCT && str_eqc(p->st->decl->name, "Map")) ? 0 : -1;
    default: return -1;
    }
  }
  if (charlike(a) && p->kind == TY_INT) return 1;
  if (is_lit(a)) {
    if (p->kind == TY_PARAM) {
      Type *b = binds[p->id];
      if (!b) return 2; // bound later
      return can_coerce(a, a->type, b) ? 0 : -1;
    }
    if (p->kind == TY_INT) return a->kind == N_INT ? (p == t_int ? 0 : 1) : -1;
    if (p->kind == TY_FLOAT) return a->kind == N_INT ? 1 : (p == t_float ? 0 : 1);
    if (p->kind == TY_OPT && is_numeric(p->elem)) return 2;
    if (p->has_var) return -1;
    return -1;
  }
  return match_type(pat, a->type, binds, 0);
}

static Type *check_call(FnCtx *c, Node **pn, Type *expected);
static Type *check_intrinsic(FnCtx *c, Node **pn, int id, Node **args, int nargs, Type *expected);

static void check_args_untyped(FnCtx *c, Node **args, int nargs) {
  for (int i = 0; i < nargs; i++) {
    Node **pa = args[i]->kind == N_NAMEDARG ? &args[i]->a : &args[i];
    if ((*pa)->kind == N_IDENT && !((*pa)->flags & NF_CHECKED)) {
      Sym *s = lookup_value(c, (*pa)->name);
      if (s && s->kind == S_FNS) (*pa)->flags |= NF_GENERIC;
    }
    if (ctx_dependent(*pa)) continue;
    if ((*pa)->flags & NF_CHECKED) continue;
    check_expr(c, pa, NULL);
    (*pa)->flags |= NF_CHECKED;
  }
}

static void fn_param_info(Node *decl, Str *names, Node **defaults) {
  for (int i = 0; i < decl->list.len; i++) { names[i] = decl->list.data[i]->name; defaults[i] = decl->list.data[i]->b; }
}

// Finalize an argument: check context-dependent args with expected type, coerce, handle mut.
static void finish_arg(FnCtx *c, Node **pa, Type *pt, bool is_mut) {
  Node *a = *pa;
  if (a->kind == N_HOLE) { a->type = pt; return; }
  if (!(a->flags & NF_CHECKED) && !a->type) { check_expr(c, pa, pt); a = *pa; a->flags |= NF_CHECKED; }
  if (is_mut) {
    check_place(c, a, true);
    if (!type_eq(a->type, pt) && !unify(a->type, pt)) fatal(a->pos, "`mut` argument must have type %s exactly, found %s", type_str(pt), type_str(a->type));
    a->flags |= NF_MUT;
    return;
  }
  coerce(c, pa, pt);
}

static Node *default_arg(FnCtx *c, Node *decl, int i, Type *pt) {
  Node *d = clone_node(decl->list.data[i]->b);
  FnCtx tmp = *c;
  tmp.scope = scope_new(decl->mod->scope, 2, c);
  check_expr(&tmp, &d, pt);
  coerce(&tmp, &d, pt);
  return d;
}

static Type *finish_partial(FnCtx *c, Node *n, Type **ptypes, int np, uint32_t mutmask, Type *ret) {
  // n: N_CALL with holes; becomes N_PARTIAL
  Type *hp[32]; uint32_t mm = 0; int nh = 0;
  for (int i = 0; i < np; i++) {
    Node *a = n->list.data[i];
    if (a->kind == N_HOLE) { if (mutmask & (1u << i)) mm |= 1u << nh; hp[nh++] = ptypes[i]; }
  }
  n->kind = N_PARTIAL;
  FnInst *th = new_inst(FK_PARTIAL, c->mod, "partial");
  th->np = nh;
  th->ptypes = arena_alloc(sizeof(Type *) * (nh + 1));
  memcpy(th->ptypes, hp, sizeof(Type *) * nh);
  th->ret = ret;
  th->has_env = true;
  th->partial = n;
  th->state = 2;
  vpush(prog.fns, th);
  n->type = mk_fn(hp, nh, ret, mm);
  n->sym = n->sym; // callee FnInst (or NULL for value)
  n->d = (Node *)th;
  return n->type;
}

static bool has_hole(Node **args, int n) {
  for (int i = 0; i < n; i++) if (unnamed(args[i])->kind == N_HOLE) return true;
  return false;
}

// Resolve a call against candidate function declarations.
static Type *resolve_fn_call(FnCtx *c, Node *n, Str name, Node **decls, int ndecls, Node **args, int nargs, Type *expected) {
  check_args_untyped(c, args, nargs);
  Cand *cands = calloc(ndecls, sizeof(Cand));
  const char *last_err = NULL;
  int best = -1;
  for (int k = 0; k < ndecls; k++) {
    Cand *cd = &cands[k];
    cd->decl = decls[k];
    cd->sig = fn_sig(decls[k]);
    int np = decls[k]->list.len;
    if (np > 64) fatal(n->pos, "too many parameters");
    Str names[64]; Node *defs[64];
    fn_param_info(decls[k], names, defs);
    const char *err = NULL;
    if (!map_args(decls[k], names, np, defs, args, nargs, cd->args, &err)) { last_err = err; continue; }
    int cost = 0; bool ok = true;
    // pass 1: typed non-literal args
    for (int pass = 0; pass < 3 && ok; pass++) {
      for (int i = 0; i < np; i++) {
        Node *a = cd->args[i];
        if (!a) continue;
        int cls = ctx_dependent(a) ? 2 : is_lit(a) ? 1 : 0;
        if (cls != pass) continue;
        if ((cd->sig->mutmask & (1u << i)) && !ctx_dependent(a)) {
          // mut params need an exact type
          int r = match_type(cd->sig->params[i], a->type, cd->binds, 0);
          Type *ptx = r >= 0 ? subst(cd->sig->params[i], cd->binds) : NULL;
          if (r < 0 || (ptx && !prune(ptx)->has_var && !prune(a->type)->has_var && !type_eq(ptx, a->type))) { ok = false; last_err = fmt("argument %d must have type %s (mut parameters need an exact match)", i + 1, type_str(subst(cd->sig->params[i], cd->binds))); break; }
          cost += r;
          continue;
        }
        int r = arg_cost(a, cd->sig->params[i], cd->binds);
        if (r < 0) {
          ok = false;
          Type *pt = subst(cd->sig->params[i], cd->binds);
          last_err = a->type ? fmt("argument '%.*s' expects %s, found %s", names[i].len, names[i].p, type_str(pt), type_str(a->type)) : fmt("argument '%.*s' has the wrong type (expects %s)", names[i].len, names[i].p, type_str(pt));
          break;
        }
        cost += r;
      }
    }
    if (!ok) continue;
    for (int i = 0; i < np; i++) if (!cd->args[i]) cost += 0;
    cd->ok = true; cd->cost = cost;
    if (best < 0 || cost < cands[best].cost) best = k;
    else if (cost == cands[best].cost) {
      // prefer non-generic
      if (cands[best].sig->generic && !cd->sig->generic) best = k;
      else if (cands[best].sig->generic == cd->sig->generic) {
        fatal(n->pos, "ambiguous call to '%.*s': candidates at lines %d and %d", name.len, name.p, cands[best].decl->pos.line, cd->decl->pos.line);
      }
    }
  }
  if (best < 0) {
    if (ndecls == 1) fatal(n->pos, "in call to '%.*s': %s", name.len, name.p, last_err ? last_err : "arguments do not match");
    char buf[2048]; int bl = 0;
    for (int i = 0; i < nargs && bl < 1800; i++) {
      Node *a = unnamed(args[i]);
      bl += snprintf(buf + bl, sizeof buf - bl, "%s%s", i ? ", " : "", a->type ? type_str(a->type) : "?");
    }
    fatal(n->pos, "no matching overload for '%.*s(%s)'%s%s", name.len, name.p, buf, last_err ? ": " : "", last_err ? last_err : "");
  }
  Cand *cd = &cands[best];
  Node *decl = cd->decl;
  int np = decl->list.len;
  // bind remaining type params from context-dependent args
  bool partial = has_hole(args, nargs);
  for (int i = 0; i < np; i++) {
    Node *a = cd->args[i];
    if (!a) continue;
    if (is_lit(a)) {
      Type *p = prune(cd->sig->params[i]);
      if (p->kind == TY_PARAM && !cd->binds[p->id]) cd->binds[p->id] = lit_default(a);
    }
  }
  for (int i = 0; i < np; i++) {
    Node *a = cd->args[i];
    if (!a || !ctx_dependent(a) || a->kind == N_HOLE) continue;
    Type *pt = subst_partial(cd->sig->params[i], cd->binds);
    Node **slot = NULL;
    for (int j = 0; j < nargs; j++) { if (args[j] == a) slot = &args[j]; else if (args[j]->kind == N_NAMEDARG && args[j]->a == a) slot = &args[j]->a; }
    check_expr(c, slot, pt);
    (*slot)->flags |= NF_CHECKED;
    cd->args[i] = *slot;
    match_type(cd->sig->params[i], (*slot)->type, cd->binds, 0);
  }
  // expected return type may bind remaining params
  if (expected && cd->sig->ret) {
    Type *rb[16]; memcpy(rb, cd->binds, sizeof rb);
    if (match_type(cd->sig->ret, expected, rb, 0) >= 0) memcpy(cd->binds, rb, sizeof rb);
  }
  for (int i = 0; i < cd->sig->ntp; i++) {
    if (!cd->binds[i] || prune(cd->binds[i])->kind == TY_VAR) {
      if (partial) {
        // a hole fixes nothing; try to find a param that's a hole
        fatal(n->pos, "cannot infer generic types for partial application of '%.*s'; annotate the arguments", name.len, name.p);
      }
      fatal(n->pos, "cannot infer type parameter %d of '%.*s'", i + 1, name.len, name.p);
    }
  }
  FnInst *f = get_fn_inst(decl, cd->binds, cd->sig->ntp, n->pos);
  // build final arg list
  NodeList fin = {0};
  for (int i = 0; i < np; i++) {
    Node *a = cd->args[i];
    bool is_mut = decl->list.data[i]->flags & NF_MUT;
    if (!a) { a = default_arg(c, decl, i, f->ptypes[i]); vpush(fin, a); continue; }
    Node **slot = NULL;
    for (int j = 0; j < nargs; j++) { if (args[j] == a) slot = &args[j]; else if (args[j]->kind == N_NAMEDARG && args[j]->a == a) slot = &args[j]->a; }
    finish_arg(c, slot, f->ptypes[i], is_mut);
    vpush(fin, *slot);
  }
  free(cands);
  n->list = fin;
  n->sym = f;
  n->aux = 0;
  n->kind = N_CALL;
  n->a = NULL;
  if (partial) {
    uint32_t mm = 0;
    for (int i = 0; i < np; i++) if (decl->list.data[i]->flags & NF_MUT) mm |= 1u << i;
    return finish_partial(c, n, f->ptypes, np, mm, f->ret);
  }
  n->type = f->ret;
  return f->ret;
}

// closure / function-value call
static Type *value_call(FnCtx *c, Node *n, Node *callee, Node **args, int nargs) {
  Type *ft = prune(callee->type);
  if (ft->kind != TY_FN) fatal(n->pos, "cannot call a value of type %s", type_str(ft));
  if (nargs != ft->nargs) fatal(n->pos, "function value expects %d argument(s), got %d", ft->nargs, nargs);
  NodeList fin = {0};
  for (int i = 0; i < nargs; i++) {
    if (args[i]->kind == N_NAMEDARG) fatal(args[i]->pos, "named arguments are not allowed when calling a function value");
    finish_arg(c, &args[i], ft->args[i], ft->mutmask & (1u << i));
    vpush(fin, args[i]);
  }
  n->list = fin;
  n->a = callee;
  n->sym = NULL;
  n->aux = 1; // value call
  if (has_hole(args, nargs)) return finish_partial(c, n, ft->args, ft->nargs, ft->mutmask, ft->elem);
  n->type = ft->elem;
  return ft->elem;
}

static Type *struct_ctor(FnCtx *c, Node *n, Type *st_type_or_null, Node *decl, Node **args, int nargs, Type *expected) {
  // generic inference
  Type *t = st_type_or_null;
  if (!t && !decl->list2.len) t = get_struct_inst(decl, NULL, 0)->type;
  if (!t) {
    int ntp = decl->list2.len;
    Type *binds[16] = {0};
    if (expected && prune(expected)->kind == TY_STRUCT && prune(expected)->st->decl == decl) t = prune(expected);
    else {
      // infer from field types
      Scope *sc = scope_new(decl->mod->scope, 2, NULL);
      for (int i = 0; i < ntp; i++) scope_add(sc, decl->list2.data[i]->name, S_TYPE, mk_param(i), NULL);
      check_args_untyped(c, args, nargs);
      Str names[64]; Node *defs[64]; Node *mapped[64];
      for (int i = 0; i < decl->list.len; i++) { names[i] = decl->list.data[i]->name; defs[i] = (Node *)1; }
      const char *err;
      if (!map_args(decl, names, decl->list.len, defs, args, nargs, mapped, &err)) fatal(n->pos, "%s", err);
      for (int i = 0; i < decl->list.len; i++) {
        if (!mapped[i] || ctx_dependent(mapped[i])) continue;
        Node *f = decl->list.data[i];
        if (!f->a) continue;
        Type *pat = resolve_type(f->a, sc);
        if (is_lit(mapped[i])) finalize_literal(c, &mapped[i]);
        match_type(pat, mapped[i]->type, binds, 0);
      }
      for (int i = 0; i < ntp; i++) if (!binds[i]) fatal(n->pos, "cannot infer type parameter '%.*s' of %.*s", decl->list2.data[i]->name.len, decl->list2.data[i]->name.p, decl->name.len, decl->name.p);
      t = get_struct_inst(decl, binds, ntp)->type;
    }
  }
  StructInfo *si = prune(t)->st;
  check_struct_fields(si);
  Str names[64]; Node *defs[64]; Node *mapped[64];
  if (si->nfields > 64) fatal(n->pos, "too many fields");
  for (int i = 0; i < si->nfields; i++) { names[i] = si->fields[i].name; defs[i] = (Node *)1; }
  const char *err;
  if (!map_args(decl, names, si->nfields, defs, args, nargs, mapped, &err)) fatal(n->pos, "in %.*s(...): %s", decl->name.len, decl->name.p, err);
  NodeList fin = {0};
  for (int i = 0; i < si->nfields; i++) {
    Node *a = mapped[i];
    if (!a) {
      if (si->fields[i].defval) {
        Node *d = clone_node(si->fields[i].defval);
        FnCtx tmp = *c;
        tmp.scope = scope_new(decl->mod->scope, 2, c);
        check_expr(&tmp, &d, si->fields[i].type);
        coerce(&tmp, &d, si->fields[i].type);
        vpush(fin, d);
      } else vpush(fin, NULL);
      continue;
    }
    Node **slot = NULL;
    for (int j = 0; j < nargs; j++) { if (args[j] == a) slot = &args[j]; else if (args[j]->kind == N_NAMEDARG && args[j]->a == a) slot = &args[j]->a; }
    if (unnamed(*slot)->kind == N_HOLE) fatal((*slot)->pos, "partial application of constructors is not supported");
    finish_arg(c, slot, si->fields[i].type, false);
    vpush(fin, *slot);
  }
  n->kind = N_CALL;
  n->aux = 2; // struct constructor
  n->list = fin;
  n->type = t;
  n->a = NULL;
  return t;
}

static int find_variant(StructInfo *si, Str name) {
  check_struct_fields(si);
  for (int i = 0; i < si->nvariants; i++) if (str_eq(si->variants[i].name, name)) return i;
  return -1;
}

static Type *variant_ctor(FnCtx *c, Node *n, Type *et, int vi, Node **args, int nargs) {
  StructInfo *si = prune(et)->st;
  Variant *v = &si->variants[vi];
  Str names[64]; Node *mapped[64];
  for (int i = 0; i < v->nfields; i++) names[i] = v->fields[i].name;
  const char *err;
  if (!map_args(NULL, names, v->nfields, NULL, args, nargs, mapped, &err)) fatal(n->pos, "in %.*s(...): %s", v->name.len, v->name.p, err);
  NodeList fin = {0};
  for (int i = 0; i < v->nfields; i++) {
    Node **slot = NULL;
    for (int j = 0; j < nargs; j++) { if (args[j] == mapped[i]) slot = &args[j]; else if (args[j]->kind == N_NAMEDARG && args[j]->a == mapped[i]) slot = &args[j]->a; }
    finish_arg(c, slot, v->fields[i].type, false);
    vpush(fin, *slot);
  }
  n->kind = N_CALL;
  n->aux = 3; // variant constructor
  n->aux2 = vi;
  n->list = fin;
  n->type = et;
  n->a = NULL;
  return et;
}

static Type *conversion(FnCtx *c, Node **pn, Type *to, Node **args, int nargs) {
  Node *n = *pn;
  if (nargs != 1 || args[0]->kind == N_NAMEDARG) fatal(n->pos, "%s(...) takes one argument", type_str(to));
  to = prune(to);
  if (to->kind == TY_STR) {
    // str(x) -> interpolation
    Node *s = new_node(N_STR, n->pos);
    Node *part = new_node(N_PAIR, n->pos);
    part->a = args[0];
    vpush(s->list, part);
    s->aux = 1;
    *pn = s;
    return check_expr(c, pn, NULL);
  }
  if (charlike(args[0]) && to->kind == TY_INT) charlike_to_int(args[0]);
  Node *a = args[0];
  Type *ft = check_expr(c, &args[0], NULL);
  a = args[0];
  ft = prune(ft);
  if (is_lit(a) && a->kind == N_FLOAT && to->kind == TY_INT) { a->kind = N_INT; a->ival = (int64_t)a->fval; }
  if (is_lit(a) && is_numeric(to)) { coerce(c, &args[0], to); *pn = args[0]; return to; }
  int cv = -1;
  if (to->kind == TY_INT) {
    if (ft->kind == TY_INT) cv = CV_INT;
    else if (ft->kind == TY_FLOAT) cv = CV_FLOAT2INT;
    else if (ft->kind == TY_BOOL) cv = CV_INT;
    else if (ft->kind == TY_ENUM && (layout(ft), ft->st->simple_enum)) cv = CV_INT;
    else if (ft->kind == TY_PTR) cv = CV_PTR;
  } else if (to->kind == TY_FLOAT) {
    if (ft->kind == TY_INT) cv = CV_INT2FLOAT;
    else if (ft->kind == TY_FLOAT) cv = CV_FLOAT;
  } else if (to->kind == TY_BOOL) {
    if (ft->kind == TY_BOOL) cv = CV_NONE;
  }
  if (cv < 0) fatal(n->pos, "cannot convert %s to %s", type_str(ft), type_str(to));
  if (type_eq(ft, to)) { *pn = args[0]; return to; }
  Node *cn = new_node(N_CONV, n->pos);
  cn->a = args[0]; cn->aux = cv; cn->type = to; cn->flags |= NF_CHECKED;
  *pn = cn;
  return to;
}

static void collect_here(Scope *s, Str name, Node **out, int *n, int max) {
  Sym *sym = scope_lookup_here(s, name);
  if (!sym || sym->kind != S_FNS) return;
  for (Sym *o = sym; o; o = o->next_overload) {
    bool dup = false;
    for (int i = 0; i < *n; i++) if (out[i] == o->decl) dup = true;
    if (!dup && *n < max) out[(*n)++] = o->decl;
  }
}
static void collect_fns(Scope *s, Str name, Node **out, int *n, int max) {
  for (; s; s = s->parent) {
    collect_here(s, name, out, n, max);
    for (int i = 0; i < s->nuses; i++) collect_here(s->uses[i], name, out, n, max);
  }
}

static Type *call_by_name(FnCtx *c, Node **pn, Scope *sc, Str name, Node **args, int nargs, Type *expected, bool ufcs) {
  Node *n = *pn;
  // array/str intrinsics
  bool arr_dom = false;
  int iid = intrinsic_id(name, &arr_dom);
  if (iid && arr_dom && nargs > 0) {
    Node **a0 = &args[0];
    if (!((*a0)->flags & NF_CHECKED)) { check_expr(c, a0, NULL); (*a0)->flags |= NF_CHECKED; }
    Type *t0 = prune((*a0)->type);
    if (t0->kind == TY_ARRAY || t0->kind == TY_STR) return check_intrinsic(c, pn, iid, args, nargs, expected);
  }
  Node *decls[64]; int nd = 0;
  // look up innermost symbol for value calls
  if (!ufcs) {
    for (Scope *s = sc; s; s = s->parent) {
      Sym *sym = scope_lookup_here(s, name);
      for (int ui = 0; !sym && ui < s->nuses; ui++) sym = scope_lookup_here(s->uses[ui], name);
      if (!sym) continue;
      if (sym->kind == S_LOCAL || sym->kind == S_GLOBAL) {
        Type *vt = sym->kind == S_LOCAL ? ((Local *)sym->p)->type : (ensure_global(sym->p, n->pos), ((Global *)sym->p)->type);
        if (prune(vt)->kind == TY_FN) {
          Node *callee = new_node(N_IDENT, n->pos);
          callee->name = name;
          check_expr(c, &callee, NULL);
          return value_call(c, n, callee, args, nargs);
        }
        continue;
      }
      if (sym->kind == S_STRUCT) return struct_ctor(c, n, NULL, sym->p, args, nargs, expected);
      if (sym->kind == S_ENUM) fatal(n->pos, "use %.*s.variant(...) to construct an enum", name.len, name.p);
      if (sym->kind == S_TYPE) return conversion(c, pn, sym->p, args, nargs);
      if (sym->kind == S_CONST || sym->kind == S_MODULE) fatal(n->pos, "'%.*s' is not a function", name.len, name.p);
      if (sym->kind == S_BUILTIN) {
        collect_fns(sc, name, decls, &nd, 64);
        if (nd == 0) return check_intrinsic(c, pn, (int)(intptr_t)sym->p, args, nargs, expected);
      }
      break;
    }
  }
  collect_fns(sc, name, decls, &nd, 64);
  if (ufcs && nargs > 0) {
    Module *tm = module_of_type(args[0]->type);
    if (tm) collect_fns(tm->scope, name, decls, &nd, 64);
  }
  if (nd == 0) {
    if (iid && !arr_dom) return check_intrinsic(c, pn, iid, args, nargs, expected);
    if (iid && arr_dom && nargs > 0) fatal(n->pos, "'%.*s' expects an array or string, found %s", name.len, name.p, type_str(args[0]->type));
    if (ufcs) fatal(n->pos, "no field or function '%.*s' for type %s", name.len, name.p, type_str(args[0]->type));
    fatal(n->pos, "unknown function '%.*s'", name.len, name.p);
  }
  return resolve_fn_call(c, n, name, decls, nd, args, nargs, expected);
}

static Type *check_call(FnCtx *c, Node **pn, Type *expected) {
  Node *n = *pn;
  Node *callee = n->a;
  Node **args = n->list.data;
  int nargs = n->list.len;
  if (callee->kind == N_IDENT) return call_by_name(c, pn, c->scope, callee->name, args, nargs, expected, false);
  if (callee->kind == N_DOTNAME) {
    Type *et = expected ? prune(expected) : NULL;
    if (et && et->kind == TY_OPT) et = prune(et->elem);
    if (!et || et->kind != TY_ENUM) fatal(callee->pos, "cannot infer the enum type for '.%.*s'", callee->name.len, callee->name.p);
    int vi = find_variant(et->st, callee->name);
    if (vi < 0) fatal(callee->pos, "%s has no variant '%.*s'", type_str(et), callee->name.len, callee->name.p);
    return variant_ctor(c, n, et, vi, args, nargs);
  }
  if (callee->kind == N_FIELD) {
    Node **recv = &callee->a;
    Type *rt = prune(check_expr(c, recv, NULL));
    if (rt->kind == TY_MODULE) return call_by_name(c, pn, rt->mod->scope, callee->name, args, nargs, expected, false);
    if (rt->kind == TY_TYPE) {
      Type *tt = prune(rt->elem);
      if (tt->kind == TY_ENUM) {
        int vi = find_variant(tt->st, callee->name);
        if (vi < 0) fatal(callee->pos, "%s has no variant '%.*s'", type_str(tt), callee->name.len, callee->name.p);
        return variant_ctor(c, n, tt, vi, args, nargs);
      }
      fatal(callee->pos, "type %s has no member '%.*s'", type_str(tt), callee->name.len, callee->name.p);
    }
    // field holding a function value?
    Type *st = rt->kind == TY_PTR ? prune(rt->elem) : rt;
    if (st->kind == TY_STRUCT) {
      check_struct_fields(st->st);
      for (int i = 0; i < st->st->nfields; i++) if (str_eq(st->st->fields[i].name, callee->name) && prune(st->st->fields[i].type)->kind == TY_FN) {
        check_expr(c, &n->a, NULL);
        return value_call(c, n, n->a, args, nargs);
      }
    }
    // UFCS
    (*recv)->flags |= NF_CHECKED;
    NodeList nl = {0};
    vpush(nl, *recv);
    for (int i = 0; i < nargs; i++) vpush(nl, args[i]);
    n->list = nl;
    return call_by_name(c, pn, c->scope, callee->name, n->list.data, n->list.len, expected, true);
  }
  if (callee->kind == N_INDEX && callee->a->kind == N_IDENT) {
    Sym *s = scope_lookup(c->scope, callee->a->name);
    if (s && (s->kind == S_STRUCT)) {
      Type *t = expr_as_type(c, callee);
      return struct_ctor(c, n, t, s->p, args, nargs, expected);
    }
  }
  check_expr(c, &n->a, NULL);
  return value_call(c, n, n->a, args, nargs);
}

FnInst *resolve_by_types(FnCtx *c, Str name, Type **types, int n, Pos pos, bool required) {
  Node *decls[64]; int nd = 0;
  collect_fns(c ? c->scope : prelude_scope, name, decls, &nd, 64);
  collect_fns(prelude_scope, name, decls, &nd, 64);
  if (n > 0) { Module *tm = module_of_type(types[n - 1]); if (tm) collect_fns(tm->scope, name, decls, &nd, 64); }
  int best = -1, bestcost = 1 << 30;
  Type *bestb[16];
  for (int k = 0; k < nd; k++) {
    FnSig *sig = fn_sig(decls[k]);
    if (decls[k]->list.len != n) continue;
    Type *binds[16] = {0};
    int cost = 0; bool ok = true;
    for (int i = 0; i < n; i++) {
      int r = match_type(sig->params[i], types[i], binds, 0);
      if (r < 0 || ((sig->mutmask & (1u << i)) && r == 1)) { ok = false; break; }
      cost += r;
    }
    if (!ok) continue;
    if (cost < bestcost) { best = k; bestcost = cost; memcpy(bestb, binds, sizeof bestb); }
  }
  if (best < 0) {
    if (!required) return NULL;
    fatal(pos, "no function '%.*s' accepting %s", name.len, name.p, n ? type_str(types[n - 1]) : "()");
  }
  return get_fn_inst(decls[best], bestb, fn_sig(decls[best])->ntp, pos);
}

// ---------------- intrinsics ----------------
static Type *arg_type(FnCtx *c, Node **args, int i, Type *expected) {
  if (args[i]->kind == N_NAMEDARG) fatal(args[i]->pos, "named arguments are not supported here");
  if (!(args[i]->flags & NF_CHECKED) || !args[i]->type) { check_expr(c, &args[i], expected); args[i]->flags |= NF_CHECKED; }
  if (expected) coerce(c, &args[i], expected);
  return prune(args[i]->type);
}
static void nargs_check(Node *n, int nargs, int lo, int hi, const char *name) {
  if (nargs < lo || nargs > hi) {
    if (lo == hi) fatal(n->pos, "%s expects %d argument(s), got %d", name, lo, nargs);
    fatal(n->pos, "%s expects %d to %d arguments, got %d", name, lo, hi, nargs);
  }
}

static void fmt_part(FnCtx *c, Node *part, Pos pos) {
  Type *t = prune(part->a->type);
  if (t->kind == TY_VOID) fatal(part->a->pos, "cannot format a value of type void");
  Type *bt = mk_array(t_u8);
  if (part->sval.len) {
    Type *ts[3] = {bt, t, t_str};
    part->sym = resolve_by_types(c, S("__fmt_spec"), ts, 3, pos, true);
  } else {
    Type *ts[2] = {bt, t};
    part->sym = resolve_by_types(c, S("__fmt"), ts, 2, pos, true);
  }
}

static Type *check_intrinsic(FnCtx *c, Node **pn, int id, Node **args, int nargs, Type *expected) {
  Node *n = *pn;
  n->kind = N_INTRINSIC;
  n->aux = id;
  NodeList al = {0};
  for (int i = 0; i < nargs; i++) vpush(al, args[i]);
  n->list = al;
  args = n->list.data;
  n->a = NULL;
  Type *r = t_void;
  switch (id) {
  case IN_FMT_ELEM: { // __fmt_elem_value(buf, x): __fmt(buf, x) (no unions here)
    nargs_check(n, nargs, 2, 2, "__fmt_elem_value");
    Node *callee = new_node(N_IDENT, n->pos);
    callee->name = S("__fmt");
    n->kind = N_CALL;
    n->a = callee;
    n->aux = 0;
    return check_expr(c, pn, expected);
  }
  case IN_FILL: { // fill(x, n): an array of n copies of x
    nargs_check(n, nargs, 2, 2, "fill");
    n->kind = N_ARRAY;
    n->aux = 0;
    n->b = args[1];
    n->list.len = 1;
    return check_expr(c, pn, expected);
  }
  case IN_LEN: case IN_ARRCAP: {
    nargs_check(n, nargs, 1, 1, "len");
    Type *t = arg_type(c, args, 0, NULL);
    if (t->kind != TY_ARRAY && t->kind != TY_STR) fatal(n->pos, "len() expects an array or string, found %s", type_str(t));
    r = t_int;
    break;
  }
  case IN_PUSH: {
    nargs_check(n, nargs, 2, 2, "push");
    Type *t = arg_type(c, args, 0, NULL);
    if (t->kind != TY_ARRAY) fatal(n->pos, "push() needs an array, found %s", type_str(t));
    check_place(c, args[0], true);
    arg_type(c, args, 1, t->elem);
    break;
  }
  case IN_POP: {
    nargs_check(n, nargs, 1, 1, "pop");
    Type *t = arg_type(c, args, 0, NULL);
    if (t->kind != TY_ARRAY) fatal(n->pos, "pop() needs an array");
    check_place(c, args[0], true);
    r = t->elem;
    break;
  }
  case IN_INSERT: {
    nargs_check(n, nargs, 3, 3, "insert");
    Type *t = arg_type(c, args, 0, NULL);
    if (t->kind != TY_ARRAY) fatal(n->pos, "insert() needs an array");
    check_place(c, args[0], true);
    arg_type(c, args, 1, t_int);
    arg_type(c, args, 2, t->elem);
    break;
  }
  case IN_REMOVE: {
    nargs_check(n, nargs, 2, 2, "remove");
    Type *t = arg_type(c, args, 0, NULL);
    if (t->kind != TY_ARRAY) fatal(n->pos, "remove() needs an array");
    check_place(c, args[0], true);
    arg_type(c, args, 1, t_int);
    r = t->elem;
    break;
  }
  case IN_CLEAR: {
    nargs_check(n, nargs, 1, 1, "clear");
    Type *t = arg_type(c, args, 0, NULL);
    if (t->kind != TY_ARRAY) fatal(n->pos, "clear() needs an array");
    check_place(c, args[0], true);
    break;
  }
  case IN_RESERVE: case IN_RESIZE: case IN_TRUNCATE: case IN_SETLEN: {
    nargs_check(n, nargs, 2, 2, "reserve/resize/truncate");
    Type *t = arg_type(c, args, 0, NULL);
    if (t->kind != TY_ARRAY) fatal(n->pos, "this operation needs an array");
    check_place(c, args[0], true);
    arg_type(c, args, 1, t_int);
    break;
  }
  case IN_ARRDATA: {
    nargs_check(n, nargs, 1, 1, "data");
    Type *t = arg_type(c, args, 0, NULL);
    if (t->kind == TY_STR) r = t_rawptr;
    else if (t->kind == TY_ARRAY) r = mk_ptr(t->elem);
    else fatal(n->pos, "data() needs an array or string");
    break;
  }
  case IN_SYSCALL: {
    if (nargs < 1 || nargs > 7) fatal(n->pos, "syscall takes 1 to 7 arguments");
    for (int i = 0; i < nargs; i++) {
      Type *t = arg_type(c, args, i, NULL);
      if (is_lit(args[i])) coerce(c, &args[i], t_int);
      else if (t->kind == TY_PTR || t->kind == TY_NULL) { if (t->kind == TY_NULL) args[i]->type = t_rawptr; }
      else if (t->kind == TY_INT) { if (t != t_int) coerce(c, &args[i], t_int); }
      else if (t->kind == TY_BOOL) {}
      else fatal(args[i]->pos, "syscall arguments must be integers or pointers");
    }
    r = t_int;
    break;
  }
  case IN_ATOMIC_ADD: case IN_ATOMIC_CAS: {
    int na = id == IN_ATOMIC_ADD ? 2 : 3;
    nargs_check(n, nargs, na, na, id == IN_ATOMIC_ADD ? "__atomic_add" : "__atomic_cas");
    Type *t0 = arg_type(c, args, 0, NULL);
    if (t0->kind != TY_PTR) fatal(args[0]->pos, "expected a pointer");
    for (int i = 1; i < na; i++) arg_type(c, args, i, t_int);
    r = t_int;
    break;
  }
  case IN_STACK_PTR:
    nargs_check(n, nargs, 0, 0, "__stack_ptr");
    r = t_rawptr;
    break;
  case IN_CPU_FEATURES:
    nargs_check(n, nargs, 0, 0, "__cpu_features");
    r = t_int;
    break;
  case IN_MEMCPY: case IN_MEMSET: {
    nargs_check(n, nargs, 3, 3, id == IN_MEMCPY ? "mem_copy" : "mem_set");
    Type *t0 = arg_type(c, args, 0, NULL);
    if (t0->kind != TY_PTR) fatal(args[0]->pos, "expected a pointer");
    if (id == IN_MEMCPY) { Type *t1 = arg_type(c, args, 1, NULL); if (t1->kind != TY_PTR) fatal(args[1]->pos, "expected a pointer"); }
    else arg_type(c, args, 1, t_int);
    arg_type(c, args, 2, t_int);
    break;
  }
  case IN_SIZEOF: case IN_ALIGNOF: {
    nargs_check(n, nargs, 1, 1, "size_of");
    Type *t = expr_as_type(c, args[0]);
    layout(t);
    n->ival = id == IN_SIZEOF ? prune(t)->size : prune(t)->align;
    n->kind = N_INT; n->type = t_int; n->flags |= NF_LITERAL;
    n->list.len = 0;
    return t_int;
  }
  case IN_PANIC: {
    nargs_check(n, nargs, 0, 1, "panic");
    if (nargs) arg_type(c, args, 0, t_str);
    r = t_never;
    break;
  }
  case IN_UNREACHABLE: r = t_never; break;
  case IN_ASSERT: {
    nargs_check(n, nargs, 1, 2, "assert");
    arg_type(c, args, 0, t_bool);
    if (nargs == 2) arg_type(c, args, 1, t_str);
    break;
  }
  case IN_PRINT: {
    // print(a, b, c) -> __print_str("{a} {b} {c}")
    Node *s = new_node(N_STR, n->pos);
    s->aux = 1;
    for (int i = 0; i < nargs; i++) {
      if (args[i]->kind == N_NAMEDARG) fatal(args[i]->pos, "print() does not take named arguments");
      if (i) { Node *sp = new_node(N_STR, n->pos); sp->sval = S(" "); vpush(s->list, sp); }
      Node *part = new_node(N_PAIR, n->pos);
      part->a = args[i];
      vpush(s->list, part);
    }
    if (nargs == 1 && args[0]->kind == N_STR && !args[0]->aux) { s = args[0]; }
    check_expr(c, &s, NULL);
    n->kind = N_CALL;
    n->aux = 0;
    n->list.len = 0;
    vpush(n->list, s);
    n->sym = runtime_fn("__print_str");
    n->type = t_void;
    return t_void;
  }
  case IN_EMBED: {
    nargs_check(n, nargs, 1, 1, "embed");
    if (args[0]->kind != N_STR || args[0]->aux) fatal(n->pos, "embed() needs a string literal path");
    char path[2048];
    const char *dir = g_files.data[n->pos.file].dir;
    if (args[0]->sval.p[0] == '/') snprintf(path, sizeof path, "%.*s", args[0]->sval.len, args[0]->sval.p);
    else snprintf(path, sizeof path, "%s/%.*s", dir, args[0]->sval.len, args[0]->sval.p);
    int len;
    char *data = read_file(path, &len);
    if (!data) fatal(n->pos, "embed: cannot read '%s'", path);
    n->sval = (Str){data, len};
    r = mk_array(t_u8);
    break;
  }
  case IN_FROM_BYTES: {
    nargs_check(n, nargs, 1, 1, "str_from_bytes");
    arg_type(c, args, 0, mk_array(t_u8));
    n->kind = N_CALL; n->aux = 0; n->sym = runtime_fn("__str_from_bytes"); n->type = t_str;
    return t_str;
  }
  case IN_TO_BYTES: {
    nargs_check(n, nargs, 1, 1, "bytes");
    arg_type(c, args, 0, t_str);
    r = mk_array(t_u8);
    break;
  }
  case IN_ARGV: r = t_rawptr; break;
  case IN_SQRT: {
    nargs_check(n, nargs, 1, 1, "sqrt");
    Type *t = arg_type(c, args, 0, NULL);
    if (is_lit(args[0])) { coerce(c, &args[0], t_float); t = t_float; }
    if (t->kind == TY_INT) { coerce(c, &args[0], t_float); t = t_float; }
    if (t->kind != TY_FLOAT) fatal(n->pos, "sqrt() needs a float");
    r = t;
    break;
  }
  case IN_FMT_STRUCT: {
    nargs_check(n, nargs, 2, 2, "__fmt_fields");
    arg_type(c, args, 0, NULL);
    Type *t = arg_type(c, args, 1, NULL);
    // resolve formatting for each field
    Type *bt = mk_array(t_u8);
    NodeList fl = {0};
    Type *fts[256]; int nf = 0;
    if (t->kind == TY_STRUCT) { check_struct_fields(t->st); for (int i = 0; i < t->st->nfields; i++) fts[nf++] = t->st->fields[i].type; }
    else if (t->kind == TY_TUPLE) { for (int i = 0; i < t->nargs; i++) fts[nf++] = t->args[i]; }
    else if (t->kind == TY_ENUM) { check_struct_fields(t->st); for (int v = 0; v < t->st->nvariants; v++) for (int i = 0; i < t->st->variants[v].nfields; i++) fts[nf++] = t->st->variants[v].fields[i].type; }
    else if (t->kind == TY_FN) {}
    else fatal(n->pos, "cannot format a value of type %s", type_str(t));
    for (int i = 0; i < nf; i++) {
      Type *ts[2] = {bt, fts[i]};
      Node *ref = new_node(N_FNREF, n->pos);
      ref->sym = resolve_by_types(c, S("__fmt_elem"), ts, 2, n->pos, true);
      vpush(fl, ref);
    }
    n->list2 = fl;
    break;
  }
  case IN_HASH: {
    nargs_check(n, nargs, 1, 1, "__hash_value");
    arg_type(c, args, 0, NULL);
    r = t_u64;
    break;
  }
  default:
    fatal(n->pos, "unsupported intrinsic");
  }
  (void)expected;
  n->type = r;
  return r;
}

// ---------------- operators ----------------
static Type *op_overload(FnCtx *c, Node **pn, const char *opname) {
  Node *n = *pn;
  Node *decls[64]; int nd = 0;
  Str nm = internc(opname);
  collect_fns(c->scope, nm, decls, &nd, 64);
  Module *tm = module_of_type(n->a->type); if (tm) collect_fns(tm->scope, nm, decls, &nd, 64);
  if (n->b) { tm = module_of_type(n->b->type); if (tm) collect_fns(tm->scope, nm, decls, &nd, 64); }
  if (!nd) return NULL;
  Node *args[2] = {n->a, n->b};
  n->a->flags |= NF_CHECKED;
  if (n->b) n->b->flags |= NF_CHECKED;
  Node *call = new_node(N_CALL, n->pos);
  NodeList l = {0};
  vpush(l, n->a);
  if (n->b) vpush(l, n->b);
  call->list = l;
  (void)args;
  *pn = call;
  return resolve_fn_call(c, call, nm, decls, nd, call->list.data, call->list.len, NULL);
}

static bool is_struct_like(Type *t) {
  t = prune(t);
  return t->kind == TY_STRUCT || t->kind == TY_TUPLE || (t->kind == TY_ENUM && (layout(t), !t->st->simple_enum));
}

static Type *check_binary(FnCtx *c, Node **pn, Type *expected) {
  Node *n = *pn;
  int op = n->op;
  if (op == TK_XOR) {
    // logical on bools (a != b), bitwise on integers
    Type *ta = prune(check_expr(c, &n->a, NULL));
    n->a->flags |= NF_CHECKED;
    n->op = ta->kind == TY_BOOL ? TK_NE : TK_CARET;
    return check_binary(c, pn, expected);
  }
  // 'a' == c: the literal is a character code when the other side is an integer
  if (charlike(n->a) && !charlike(n->b) && op != TK_PLUS) {
    Type *tb = prune(check_expr(c, &n->b, NULL));
    n->b->flags |= NF_CHECKED;
    if (is_int(tb) || is_lit(n->b)) charlike_to_int(n->a);
  }
  if (op == TK_IN) {
    // a in b  ->  contains(b, a)
    Node *call = new_node(N_CALL, n->pos);
    Node *callee = new_node(N_FIELD, n->pos);
    callee->a = n->b; callee->name = S("contains");
    call->a = callee;
    vpush(call->list, n->a);
    *pn = call;
    return check_expr(c, pn, NULL);
  }
  bool is_cmp = op == TK_EQ || op == TK_NE || op == TK_LT || op == TK_LE || op == TK_GT || op == TK_GE;
  bool is_shift = op == TK_SHL || op == TK_SHR;
  Type *hint = (!is_cmp && expected && is_numeric(expected)) ? expected : NULL;
  Type *ta = prune(check_expr(c, &n->a, is_shift ? hint : hint));
  Type *tb;
  if (n->b->kind == N_NONE || n->b->kind == N_NULL || n->b->kind == N_DOTNAME) tb = prune(check_expr(c, &n->b, ta));
  else tb = prune(check_expr(c, &n->b, (is_lit(n->a) || is_shift) ? NULL : (is_numeric(ta) ? ta : NULL)));
  if (ta->kind == TY_TYPE || tb->kind == TY_TYPE) fatal(n->pos, "a type name cannot be used as a value here");
  // operator overloading for user types
  if (is_struct_like(ta) || is_struct_like(tb)) {
    const char *opn = tok_name(op);
    Type *r = op_overload(c, pn, opn);
    if (r) return r;
    if (op == TK_NE) {
      Node *saved = *pn;
      (void)saved;
      // try == and negate
      Node *eq = n;
      eq->op = TK_EQ;
      Node *tmp = eq;
      Type *r2 = op_overload(c, &tmp, "==");
      if (r2) { Node *nn = new_node(N_NOT, n->pos); nn->a = tmp; nn->type = t_bool; *pn = nn; return t_bool; }
      eq->op = TK_NE;
    }
    if (op == TK_EQ || op == TK_NE) {
      if (!type_eq(ta, tb)) fatal(n->pos, "cannot compare %s with %s", type_str(ta), type_str(tb));
      n->aux = 1; n->type = t_bool; return t_bool;
    }
    fatal(n->pos, "operator %s is not defined for %s and %s", opn, type_str(ta), type_str(tb));
  }
  if (is_shift) {
    finalize_literal(c, &n->a); finalize_literal(c, &n->b);
    ta = prune(n->a->type); tb = prune(n->b->type);
    if (!is_int(ta) || !is_int(tb)) fatal(n->pos, "shift operands must be integers");
    n->type = ta;
    return ta;
  }
  if (op == TK_PLUS && ta->kind == TY_STR) {
    coerce(c, &n->b, t_str);
    n->aux = 2; n->type = t_str; return t_str;
  }
  if (op == TK_PLUS && ta->kind == TY_ARRAY) {
    coerce(c, &n->b, ta);
    n->aux = 3; n->type = ta; return ta;
  }
  if (ta->kind == TY_PTR && (op == TK_PLUS || op == TK_MINUS) && (is_int(tb) || is_lit(n->b))) {
    coerce(c, &n->b, t_int);
    n->aux = 4; n->type = ta; return ta;
  }
  if (ta->kind == TY_PTR && tb->kind == TY_PTR && op == TK_MINUS) { n->aux = 5; n->type = t_int; return t_int; }
  if (is_cmp) {
    if (ta->kind == TY_STR || tb->kind == TY_STR) {
      if (!type_eq(ta, tb)) fatal(n->pos, "cannot compare %s with %s", type_str(ta), type_str(tb));
      n->aux = 2; n->type = t_bool; return t_bool;
    }
    if (ta->kind == TY_OPT || tb->kind == TY_OPT || ta->kind == TY_NONE_LIT || tb->kind == TY_NONE_LIT) {
      if (op != TK_EQ && op != TK_NE) fatal(n->pos, "optionals can only be compared with == and !=");
      if (n->b->kind == N_NONE || n->a->kind == N_NONE) {
        if (n->a->kind == N_NONE) { Node *t = n->a; n->a = n->b; n->b = t; }
        if (prune(n->a->type)->kind != TY_OPT) fatal(n->pos, "only optionals can be compared with none");
        n->aux = 6; n->type = t_bool; return t_bool; // test for none
      }
      Type *j = join_types(c, &n->a, &n->b, n->pos);
      (void)j;
      n->aux = 1; n->type = t_bool; return t_bool;
    }
    if (ta->kind == TY_ARRAY || tb->kind == TY_ARRAY) {
      if (op != TK_EQ && op != TK_NE) fatal(n->pos, "arrays can only be compared with == and !=");
      if (!can_coerce(n->b, tb, ta)) fatal(n->pos, "cannot compare %s with %s", type_str(ta), type_str(tb));
      coerce(c, &n->b, ta);
      n->aux = 1; n->type = t_bool; return t_bool;
    }
    if (ta->kind == TY_BOOL || ta->kind == TY_ENUM || ta->kind == TY_PTR || ta->kind == TY_NULL || ta->kind == TY_FN) {
      if (ta->kind == TY_NULL) { Node *t = n->a; n->a = n->b; n->b = t; Type *tt = ta; ta = tb; tb = tt; }
      if (!can_coerce(n->b, tb, ta) && !type_eq(ta, tb)) fatal(n->pos, "cannot compare %s with %s", type_str(ta), type_str(tb));
      if (ta->kind == TY_FN) fatal(n->pos, "functions cannot be compared");
      coerce(c, &n->b, ta);
      n->type = t_bool; return t_bool;
    }
  }
  if (op == TK_AMP || op == TK_PIPE || op == TK_CARET) {
    if (ta->kind == TY_BOOL && tb->kind == TY_BOOL) { n->type = t_bool; return t_bool; }
  }
  if (!is_numeric(ta) || !is_numeric(tb)) {
    if (ta->kind == TY_OPT && is_numeric(ta->elem)) fatal(n->pos, "operator %s on an optional value: unwrap it first with `x!` or `x ?? default`", tok_name(op));
    fatal(n->pos, "operator %s is not defined for %s and %s", tok_name(op), type_str(ta), type_str(tb));
  }
  Type *j = join_types(c, &n->a, &n->b, n->pos);
  if ((op == TK_AMP || op == TK_PIPE || op == TK_CARET || op == TK_PERCENT) && !is_int(j) && op != TK_PERCENT) fatal(n->pos, "bitwise operators need integers");
  n->type = is_cmp ? t_bool : j;
  if (!is_cmp && is_lit(n->a) && is_lit(n->b)) {
    // fold integer literals
    if (n->a->kind == N_INT && n->b->kind == N_INT) {
      int64_t x = n->a->ival, y = n->b->ival, v = 0; bool ok = true;
      switch (op) {
      case TK_PLUS: v = x + y; break; case TK_MINUS: v = x - y; break; case TK_STAR: v = x * y; break;
      case TK_SLASH: if (!y) ok = false; else v = x / y; break; case TK_PERCENT: if (!y) ok = false; else v = x % y; break;
      case TK_AMP: v = x & y; break; case TK_PIPE: v = x | y; break; case TK_CARET: v = x ^ y; break;
      default: ok = false;
      }
      if (ok) { n->kind = N_INT; n->ival = v; n->flags |= NF_LITERAL; n->type = t_int; }
    }
  }
  return n->type;
}

// ---------------- match ----------------
static Type *check_match(FnCtx *c, Node **pn, Type *expected) {
  Node *m = *pn;
  bool is_stmt = m->flags & NF_STMT;
  Type *st = prune(check_expr(c, &m->a, NULL));
  finalize_literal(c, &m->a);
  st = prune(m->a->type);
  Scope *saved = c->scope;
  c->scope = scope_new(c->scope, 2, c);
  Local *hidden = new_local(c, (Str){0}, st, m->pos);
  m->sym = hidden;
  Type *result = NULL;
  Node *first_val = NULL;
  bool has_wild = false;
  bool seen[256] = {0};
  for (int i = 0; i < m->list.len; i++) {
    Node *arm = m->list.data[i];
    Scope *as = c->scope;
    c->scope = scope_new(c->scope, 2, c);
    for (int k = 0; k < arm->list.len; k++) {
      Node **pp = &arm->list.data[k];
      Node *p = *pp;
      if (p->kind == N_PWILD) { has_wild = true; continue; }
      if (p->kind == N_PVARIANT && st->kind == TY_ENUM) {
        int vi = find_variant(st->st, p->name);
        if (vi < 0) fatal(p->pos, "%s has no variant '%.*s'", type_str(st), p->name.len, p->name.p);
        p->aux2 = vi;
        if (vi < 256) seen[vi] = true;
        Variant *v = &st->st->variants[vi];
        if (p->list.len) {
          if (p->list.len != v->nfields) fatal(p->pos, "variant '%.*s' has %d field(s), pattern binds %d", v->name.len, v->name.p, v->nfields, p->list.len);
          if (arm->list.len > 1) fatal(p->pos, "patterns with bindings cannot be combined with other patterns");
          for (int f = 0; f < p->list.len; f++) {
            Node *b = p->list.data[f];
            if (b->name.len == 1 && b->name.p[0] == '_') continue;
            Local *l = new_local(c, b->name, v->fields[f].type, b->pos);
            l->flags |= LF_ALIAS;
            // alias: payload field of hidden local
            Node *fa = new_node(N_FIELD, b->pos);
            fa->a = mk_ident_local(hidden, b->pos);
            fa->aux = -3; fa->aux2 = vi; fa->ival = f;
            fa->type = v->fields[f].type;
            fa->flags |= NF_CHECKED;
            l->alias = fa;
            b->sym = l;
          }
        }
        continue;
      }
      if (p->kind == N_PVARIANT) {
        // bare identifier in a non-enum match: a constant
        if (p->aux) fatal(p->pos, "variant patterns need an enum value");
        Node *id = new_node(N_IDENT, p->pos); id->name = p->name;
        Node *lit = new_node(N_PLIT, p->pos); lit->a = id;
        *pp = p = lit;
      }
      if (p->kind == N_PLIT) {
        check_expr(c, &p->a, st);
        coerce(c, &p->a, st);
        if (st->kind == TY_ENUM && p->a->kind == N_DOTNAME) { if (p->a->aux < 256) seen[p->a->aux] = true; }
        continue;
      }
      if (p->kind == N_PRANGE) {
        if (!is_int(st)) fatal(p->pos, "range patterns need an integer value");
        check_expr(c, &p->a, st); coerce(c, &p->a, st);
        check_expr(c, &p->b, st); coerce(c, &p->b, st);
        continue;
      }
      fatal(p->pos, "invalid pattern");
    }
    if (is_stmt) check_block(c, arm->b, NULL, false);
    else {
      Type *t = check_block(c, arm->b, result ? result : expected, true);
      if (t != t_never) {
        if (!arm->b->aux && prune(t)->kind == TY_VOID) {
          if (result && prune(result)->kind != TY_VOID && expected) fatal(arm->pos, "match arm has no value");
          result = t_void;
        } else if (!result) { result = t; first_val = arm->b; }
        else {
          Node **vp = &arm->b->list.data[arm->b->list.len - 1]->a;
          if (expected) coerce(c, vp, expected);
          else if (first_val) {
            Node **fp = &first_val->list.data[first_val->list.len - 1]->a;
            result = join_types(c, fp, vp, arm->pos);
          } else coerce(c, vp, result);
        }
      }
    }
    c->scope = as;
  }
  c->scope = saved;
  bool exhaustive = has_wild;
  if (!exhaustive && st->kind == TY_ENUM) {
    exhaustive = true;
    for (int v = 0; v < st->st->nvariants && v < 256; v++) if (!seen[v]) exhaustive = false;
  }
  if (!exhaustive && st->kind == TY_BOOL) exhaustive = false;
  m->aux2 = exhaustive;
  if (is_stmt) { m->type = t_void; return t_void; }
  if (!exhaustive) fatal(m->pos, "match expression is not exhaustive (add a `_:` arm)");
  if (!result) result = t_never;
  if (expected && result != t_never) {
    for (int i = 0; i < m->list.len; i++) {
      Node *b = m->list.data[i]->b;
      if (b->aux) coerce(c, &b->list.data[b->list.len - 1]->a, expected);
    }
    result = expected;
  } else {
    for (int i = 0; i < m->list.len; i++) {
      Node *b = m->list.data[i]->b;
      if (b->aux) { Node **vp = &b->list.data[b->list.len - 1]->a; finalize_literal(c, vp); coerce(c, vp, result); }
    }
  }
  m->type = result;
  return result;
}

// ---------------- lambda ----------------
static Type *check_lambda(FnCtx *c, Node **pn, Type *expected) {
  Node *lam = *pn;
  Type *et = expected ? prune(expected) : NULL;
  if (et && et->kind != TY_FN) et = NULL;
  int np = lam->list.len;
  if (et && et->nargs != np) fatal(lam->pos, "lambda has %d parameter(s) but %d are expected", np, et->nargs);
  FnInst *f = new_inst(FK_LAMBDA, c->mod, "lambda");
  f->decl = lam;
  f->np = np;
  f->ptypes = arena_alloc(sizeof(Type *) * (np + 1));
  f->has_env = true;
  f->body = lam->b;
  uint32_t mm = 0;
  for (int i = 0; i < np; i++) {
    Node *p = lam->list.data[i];
    if (p->a) {
      f->ptypes[i] = resolve_type(p->a, c->scope);
      if (et && !unify(f->ptypes[i], et->args[i])) fatal(p->pos, "parameter type %s does not match expected %s", type_str(f->ptypes[i]), type_str(et->args[i]));
    } else if (et && !prune(et->args[i])->has_var) f->ptypes[i] = et->args[i];
    else if (et) f->ptypes[i] = et->args[i];
    else fatal(p->pos, "cannot infer the type of parameter '%.*s'; add a type annotation", p->name.len, p->name.p);
    if (p->flags & NF_MUT) mm |= 1u << i;
    if (et && (et->mutmask & (1u << i))) { mm |= 1u << i; p->flags |= NF_MUT; }
  }
  vpush(prog.fns, f);
  check_lambda_body(f, c, lam, et ? et->elem : NULL);
  for (int i = 0; i < np; i++) f->ptypes[i] = zonk(f->ptypes[i]);
  f->ret = zonk(f->ret);
  zonk_tree(f->body);
  for (int i = 0; i < f->locals.len; i++) f->locals.data[i]->type = zonk(f->locals.data[i]->type);
  lam->sym = f;
  lam->type = mk_fn(f->ptypes, np, f->ret, mm);
  f->fntype = lam->type;
  return lam->type;
}

// function name used as a value
static Type *fn_value(FnCtx *c, Node **pn, Sym *sym, Type *expected) {
  Node *n = *pn;
  Node *decls[64]; int nd = 0;
  collect_fns(c->scope, n->name, decls, &nd, 64);
  Type *et = expected ? prune(expected) : NULL;
  FnInst *f = NULL;
  for (int k = 0; k < nd; k++) {
    FnSig *sig = fn_sig(decls[k]);
    if (et && et->kind == TY_FN) {
      if (et->nargs != decls[k]->list.len) continue;
      Type *binds[16] = {0}; bool ok = true;
      for (int i = 0; i < et->nargs; i++) if (match_type(sig->params[i], et->args[i], binds, 0) < 0 || (match_type(sig->params[i], et->args[i], binds, 0) == 1)) { ok = false; break; }
      if (!ok) continue;
      for (int i = 0; i < sig->ntp; i++) if (!binds[i]) ok = false;
      if (!ok) continue;
      f = get_fn_inst(decls[k], binds, sig->ntp, n->pos);
      break;
    } else if (!sig->generic && nd == 1) {
      f = get_fn_inst(decls[k], NULL, 0, n->pos);
    }
  }
  (void)sym;
  if (!f) {
    if (et && et->kind == TY_FN) fatal(n->pos, "no version of '%.*s' matches %s", n->name.len, n->name.p, type_str(et));
    fatal(n->pos, "cannot use overloaded or generic function '%.*s' as a value without a known type", n->name.len, n->name.p);
  }
  uint32_t mm = 0;
  for (int i = 0; i < f->np; i++) if (f->decl->list.data[i]->flags & NF_MUT) mm |= 1u << i;
  n->kind = N_FNREF;
  n->sym = f;
  n->type = mk_fn(f->ptypes, f->np, f->ret, mm);
  return n->type;
}

// ---------------- main expression checker ----------------
Type *check_expr(FnCtx *c, Node **pn, Type *expected) {
  Node *n = *pn;
  if (n->type && (n->flags & NF_CHECKED)) return n->type;
  Type *t = NULL;
  Type *ex = expected ? prune(expected) : NULL;
  switch (n->kind) {
  case N_INT:
    if (ex && ex->kind == TY_INT) { coerce_lit_int:;
      n->type = t_int; coerce(c, pn, ex); t = ex; break; }
    if (ex && ex->kind == TY_FLOAT) { n->type = t_int; coerce(c, pn, ex); t = ex; break; }
    if (ex && ex->kind == TY_OPT && is_numeric(ex->elem)) { ex = prune(ex->elem); goto coerce_lit_int; }
    t = n->type = t_int;
    n->flags |= NF_LITERAL;
    break;
  case N_FLOAT:
    if (ex && ex->kind == TY_FLOAT) { n->type = ex; n->flags &= ~NF_LITERAL; t = ex; break; }
    if (ex && ex->kind == TY_OPT && is_float(ex->elem)) { n->type = prune(ex->elem); n->flags &= ~NF_LITERAL; t = n->type; break; }
    t = n->type = t_float;
    n->flags |= NF_LITERAL;
    break;
  case N_STR:
    if (charlike(n) && ex && ex->kind == TY_INT) { charlike_to_int(n); return check_expr(c, pn, expected); }
    if (n->aux) {
      for (int i = 0; i < n->list.len; i++) {
        Node *part = n->list.data[i];
        if (part->kind != N_PAIR) continue;
        check_expr(c, &part->a, NULL);
        finalize_literal(c, &part->a);
        fmt_part(c, part, part->pos);
      }
    }
    t = t_str;
    break;
  case N_BOOL: t = t_bool; break;
  case N_NONE:
    if (ex && ex->kind == TY_OPT) t = ex;
    else t = mk_opt(mk_var());
    break;
  case N_NULL:
    t = (ex && ex->kind == TY_PTR) ? ex : t_null;
    break;
  case N_IDENT: {
    Sym *s = lookup_value(c, n->name);
    if (!s) fatal(n->pos, "unknown name '%.*s'", n->name.len, n->name.p);
    n->aux = s->kind;
    switch (s->kind) {
    case S_LOCAL: {
      Local *l = capture_local(c, s->p);
      n->sym = l;
      t = l->type;
      break;
    }
    case S_GLOBAL: {
      Global *g = s->p;
      ensure_global(g, n->pos);
      n->sym = g;
      t = g->type;
      break;
    }
    case S_CONST: {
      Global *g = s->p;
      if (g->decl) ensure_global(g, n->pos);
      Node *v = clone_node(g->init);
      v->pos = n->pos;
      *pn = v;
      Type *vt = check_expr(c, pn, expected);
      if (!is_lit(*pn) && g->type && g->decl && g->decl->a && !(prune(g->type)->has_var)) coerce(c, pn, g->type);
      return vt;
    }
    case S_FNS: return fn_value(c, pn, s, expected);
    case S_STRUCT: case S_ENUM: {
      Node *d = s->p;
      if (d->list2.len) { t = mk_typeval(NULL); t->args = (Type **)d; break; }
      t = mk_typeval(get_struct_inst(d, NULL, 0)->type);
      break;
    }
    case S_TYPE: t = mk_typeval(s->p); break;
    case S_MODULE: t = mk_modval(s->p); break;
    case S_BUILTIN: fatal(n->pos, "'%.*s' must be called", n->name.len, n->name.p);
    default: fatal(n->pos, "invalid use of '%.*s'", n->name.len, n->name.p);
    }
    break;
  }
  case N_FIELD: {
    Type *bt = prune(check_expr(c, &n->a, NULL));
    if (bt->kind == TY_MODULE) {
      Sym *s = scope_lookup_here(bt->mod->scope, n->name);
      if (!s) fatal(n->pos, "module '%.*s' has no member '%.*s'", bt->mod->name.len, bt->mod->name.p, n->name.len, n->name.p);
      Node *id = new_node(N_IDENT, n->pos);
      id->name = n->name;
      FnCtx tmp = *c;
      tmp.scope = bt->mod->scope;
      *pn = id;
      return check_expr(&tmp, pn, expected);
    }
    if (bt->kind == TY_TYPE) {
      Type *tt = prune(bt->elem);
      if (tt && tt->kind == TY_ENUM) {
        int vi = find_variant(tt->st, n->name);
        if (vi < 0) fatal(n->pos, "%s has no variant '%.*s'", type_str(tt), n->name.len, n->name.p);
        if (tt->st->variants[vi].nfields) fatal(n->pos, "variant '%.*s' needs arguments", n->name.len, n->name.p);
        n->kind = N_DOTNAME; n->aux = vi; n->a = NULL;
        t = tt;
        break;
      }
      fatal(n->pos, "type has no member '%.*s'", n->name.len, n->name.p);
    }
    if (n->aux == -2) { // tuple index
      if (bt->kind != TY_TUPLE) fatal(n->pos, "'.%lld' needs a tuple, found %s", (long long)n->ival, type_str(bt));
      if (n->ival < 0 || n->ival >= bt->nargs) fatal(n->pos, "tuple index out of range");
      t = bt->args[n->ival];
      break;
    }
    Type *st = bt->kind == TY_PTR ? prune(bt->elem) : bt;
    if (st->kind == TY_STRUCT) {
      check_struct_fields(st->st);
      int fi = -1;
      for (int i = 0; i < st->st->nfields; i++) if (str_eq(st->st->fields[i].name, n->name)) fi = i;
      if (fi >= 0) { n->aux = fi; t = st->st->fields[fi].type; break; }
    }
    fatal(n->pos, "%s has no field '%.*s'", type_str(bt), n->name.len, n->name.p);
  }
  case N_DOTNAME: {
    Type *et = ex;
    if (et && et->kind == TY_OPT) et = prune(et->elem);
    if (!et || et->kind != TY_ENUM) fatal(n->pos, "cannot infer the enum type for '.%.*s'", n->name.len, n->name.p);
    int vi = find_variant(et->st, n->name);
    if (vi < 0) fatal(n->pos, "%s has no variant '%.*s'", type_str(et), n->name.len, n->name.p);
    if (et->st->variants[vi].nfields) fatal(n->pos, "variant '%.*s' needs arguments", n->name.len, n->name.p);
    n->aux = vi;
    t = et;
    break;
  }
  case N_CALL:
    t = check_call(c, pn, expected);
    n = *pn;
    break;
  case N_INDEX: {
    Type *bt = prune(check_expr(c, &n->a, NULL));
    if (bt->kind == TY_TYPE) { t = mk_typeval(expr_as_type(c, n)); break; }
    if (n->b && n->b->kind == N_RANGE) {
      Node *r = n->b;
      if (r->a) check_expr_to(c, &r->a, t_int);
      if (r->b) check_expr_to(c, &r->b, t_int);
      r->type = t_range;
      if (bt->kind != TY_ARRAY && bt->kind != TY_STR) fatal(n->pos, "cannot slice %s", type_str(bt));
      n->aux = 1; // slice
      t = bt;
      break;
    }
    if (!n->b) fatal(n->pos, "invalid index");
    if (bt->kind == TY_ARRAY) { check_expr_to(c, &n->b, t_int); t = bt->elem; break; }
    if (bt->kind == TY_STR) { check_expr_to(c, &n->b, t_int); t = t_u8; break; }
    if (bt->kind == TY_PTR) { check_expr_to(c, &n->b, t_int); t = bt->elem; break; }
    if (bt->kind == TY_STRUCT) {
      Node *call = new_node(N_CALL, n->pos);
      Node *callee = new_node(N_IDENT, n->pos); callee->name = S("[]");
      call->a = callee;
      n->a->flags |= NF_CHECKED;
      vpush(call->list, n->a);
      vpush(call->list, n->b);
      *pn = call;
      return check_expr(c, pn, expected);
    }
    fatal(n->pos, "cannot index a value of type %s", type_str(bt));
  }
  case N_UNARY: {
    Type *at = prune(check_expr(c, &n->a, ex && is_numeric(ex) ? ex : NULL));
    if (n->op == TK_MINUS) {
      if (is_struct_like(at)) { Type *r = op_overload(c, pn, "-"); if (r) return r; }
      if (!is_numeric(at)) fatal(n->pos, "cannot negate %s", type_str(at));
      if (is_lit(n->a)) { n->flags |= NF_LITERAL; }
    } else if (n->op == TK_TILDE) {
      if (!is_int(at)) fatal(n->pos, "'~' needs an integer");
    }
    t = at;
    break;
  }
  case N_BINARY:
    t = check_binary(c, pn, expected);
    n = *pn;
    break;
  case N_AND: case N_OR: case N_NOT: {
    // logical on bools, bitwise on integers
    Type *ta = prune(check_expr(c, &n->a, ex && is_int(ex) ? ex : NULL));
    if (is_int(ta) || (is_lit(n->a) && n->a->kind == N_INT)) {
      n->a->flags |= NF_CHECKED;
      if (n->kind == N_NOT) { n->kind = N_UNARY; n->op = TK_TILDE; }
      else { n->op = n->kind == N_AND ? TK_AMP : TK_PIPE; n->kind = N_BINARY; }
      return check_expr(c, pn, expected);
    }
    coerce(c, &n->a, t_bool);
    if (n->b) check_expr_to(c, &n->b, t_bool);
    t = t_bool;
    break;
  }
  case N_COALESCE: {
    Type *at = prune(check_expr(c, &n->a, ex ? (ex->kind == TY_OPT ? ex : mk_opt(ex)) : NULL));
    if (at->kind != TY_OPT) fatal(n->pos, "'?\?' needs an optional on the left, found %s", type_str(at));
    Type *inner = at->elem;
    Type *btt = prune(check_expr(c, &n->b, ex ? ex : inner));
    if (btt->kind == TY_OPT) { coerce(c, &n->b, at); t = at; n->aux = 1; }
    else { coerce(c, &n->b, inner); t = inner; }
    break;
  }
  case N_UNWRAP: {
    Type *at = prune(check_expr(c, &n->a, ex ? mk_opt(ex) : NULL));
    if (at->kind != TY_OPT) fatal(n->pos, "'!' needs an optional value, found %s", type_str(at));
    t = at->elem;
    break;
  }
  case N_LAMBDA: t = check_lambda(c, pn, expected); break;
  case N_ARRAY: {
    Type *et = ex && ex->kind == TY_ARRAY ? ex->elem : NULL;
    if (n->b) { // [v; n]
      Type *vt = check_expr(c, &n->list.data[0], et);
      if (et) coerce(c, &n->list.data[0], et); else vt = finalize_literal(c, &n->list.data[0]);
      check_expr_to(c, &n->b, t_int);
      t = mk_array(et ? et : vt);
      n->aux = 1;
      break;
    }
    if (n->list.len == 0) { t = (ex && ex->kind == TY_ARRAY) ? ex : mk_array(mk_var()); break; }
    if (et) {
      for (int i = 0; i < n->list.len; i++) check_expr_to(c, &n->list.data[i], et);
      t = ex;
      break;
    }
    Type *elt = NULL; bool anyfloat = false, allchar = true;
    for (int i = 0; i < n->list.len; i++) {
      Node *e = n->list.data[i];
      Type *it = check_expr(c, &n->list.data[i], elt);
      if (!charlike(e)) allchar = false;
      if (is_lit(e)) { if (e->kind == N_FLOAT) anyfloat = true; }
      else if (!elt && !charlike(e)) elt = it;
    }
    if (!elt) elt = allchar ? t_str : anyfloat ? t_float : t_int;
    for (int i = 0; i < n->list.len; i++) coerce(c, &n->list.data[i], elt);
    t = mk_array(elt);
    break;
  }
  case N_MAP: {
    Sym *ms = scope_lookup(prelude_scope, S("Map"));
    if (!ms) fatal(n->pos, "Map is not available");
    Type *kt = NULL, *vt = NULL;
    if (ex && ex->kind == TY_STRUCT && ex->st->decl == ms->p) { kt = ex->st->targs[0]; vt = ex->st->targs[1]; }
    if (!kt) {
      if (!n->list.len) fatal(n->pos, "cannot infer the type of an empty map; add a type annotation: `m: {K: V} = {}`");
      Node *p0 = n->list.data[0];
      check_expr(c, &p0->a, NULL); kt = finalize_literal(c, &p0->a);
      check_expr(c, &p0->b, NULL); vt = finalize_literal(c, &p0->b);
    }
    for (int i = 0; i < n->list.len; i++) {
      Node *p = n->list.data[i];
      check_expr_to(c, &p->a, kt);
      check_expr_to(c, &p->b, vt);
    }
    Type *targs[2] = {kt, vt};
    t = get_struct_inst(ms->p, targs, 2)->type;
    if (n->list.len) {
      Type *ts[3] = {t, kt, vt};
      n->sym = resolve_by_types(c, S("[]="), ts, 3, n->pos, true);
    }
    break;
  }
  case N_TUPLE: {
    if (n->list.len == 0) { t = t_void; break; }
    Type *el[32];
    if (n->list.len > 32) fatal(n->pos, "tuple too large");
    for (int i = 0; i < n->list.len; i++) {
      Type *e = (ex && ex->kind == TY_TUPLE && ex->nargs == n->list.len) ? ex->args[i] : NULL;
      check_expr(c, &n->list.data[i], e);
      if (e) coerce(c, &n->list.data[i], e); else finalize_literal(c, &n->list.data[i]);
      el[i] = n->list.data[i]->type;
    }
    t = mk_tuple(el, n->list.len);
    break;
  }
  case N_IF: {
    bool is_stmt = n->flags & NF_STMT;
    check_expr_to(c, &n->a, t_bool);
    if (is_stmt) {
      check_block(c, n->b, NULL, false);
      if (n->c) check_block(c, n->c, NULL, false);
      t = t_void;
      break;
    }
    if (!n->c) fatal(n->pos, "an if expression needs an else branch");
    Type *t1 = check_block(c, n->b, ex, true);
    Type *t2 = check_block(c, n->c, ex, true);
    if (t1 == t_never && t2 == t_never) { t = t_never; break; }
    if (t1 != t_never && !n->b->aux && prune(t1)->kind == TY_VOID) { t = t_void; break; }
    if (t2 != t_never && !n->c->aux && prune(t2)->kind == TY_VOID && !ex) { t = t_void; break; }
    if (t1 == t_never) { if (ex) coerce(c, &n->c->list.data[n->c->list.len - 1]->a, ex); else finalize_literal(c, &n->c->list.data[n->c->list.len - 1]->a); t = n->c->list.data[n->c->list.len - 1]->a->type; break; }
    if (t2 == t_never) { if (ex) coerce(c, &n->b->list.data[n->b->list.len - 1]->a, ex); else finalize_literal(c, &n->b->list.data[n->b->list.len - 1]->a); t = n->b->list.data[n->b->list.len - 1]->a->type; break; }
    if (!n->b->aux || !n->c->aux) fatal(n->pos, "both branches of an if expression need a value");
    Node **va = &n->b->list.data[n->b->list.len - 1]->a;
    Node **vb = &n->c->list.data[n->c->list.len - 1]->a;
    if (ex) { coerce(c, va, ex); coerce(c, vb, ex); t = ex; }
    else t = join_types(c, va, vb, n->pos);
    break;
  }
  case N_IFLET: {
    bool is_stmt = n->flags & NF_STMT;
    Type *ot = prune(check_expr(c, &n->a, NULL));
    if (ot->kind != TY_OPT) fatal(n->a->pos, "'if let x = value' needs an optional value, found %s", type_str(ot));
    Scope *saved = c->scope;
    c->scope = scope_new(c->scope, 2, c);
    Local *l = new_local(c, n->name, ot->elem, n->pos);
    n->sym = l;
    Type *t1 = check_block(c, n->b, is_stmt ? NULL : ex, !is_stmt);
    c->scope = saved;
    Type *t2 = t_void;
    if (n->c) t2 = check_block(c, n->c, is_stmt ? NULL : (ex ? ex : t1), !is_stmt);
    if (is_stmt) { t = t_void; break; }
    if (!n->c) fatal(n->pos, "an if expression needs an else branch");
    if (t1 == t_never) t = t2; else if (t2 == t_never) t = t1;
    else {
      Node **va = &n->b->list.data[n->b->list.len - 1]->a;
      Node **vb = &n->c->list.data[n->c->list.len - 1]->a;
      t = ex ? (coerce(c, va, ex), coerce(c, vb, ex), ex) : join_types(c, va, vb, n->pos);
    }
    break;
  }
  case N_MATCH: t = check_match(c, pn, expected); break;
  case N_CAST: {
    Type *ft = prune(check_expr(c, &n->a, NULL));
    finalize_literal(c, &n->a);
    ft = prune(n->a->type);
    Type *tt = prune(resolve_type(n->b, c->scope));
    if (ft->has_var && unify(ft, tt)) { *pn = n->a; return tt; }
    if (type_eq(ft, tt)) { *pn = n->a; return tt; }
    bool ok = false;
    int fk = ft->kind, tk = tt->kind;
    if ((fk == TY_PTR || fk == TY_INT || fk == TY_NULL) && (tk == TY_PTR || tk == TY_INT)) ok = true;
    if ((fk == TY_INT || fk == TY_FLOAT) && (tk == TY_INT || tk == TY_FLOAT)) { layout(ft); layout(tt); ok = ft->size == tt->size || (fk == TY_INT && tk == TY_INT); }
    if (fk == TY_ENUM && tk == TY_INT) ok = true;
    if (fk == TY_INT && tk == TY_ENUM) ok = true;
    if (fk == TY_BOOL && tk == TY_INT) ok = true;
    if (fk == TY_STR && tk == TY_PTR) ok = true;
    if (fk == TY_ARRAY && tk == TY_PTR) ok = true;
    if (fk == TY_PTR && (tk == TY_STR || tk == TY_ARRAY)) ok = true;
    if (!ok) fatal(n->pos, "cannot cast %s to %s", type_str(ft), type_str(tt));
    t = tt;
    break;
  }
  case N_RANGE:
    if (n->a) check_expr_to(c, &n->a, t_int);
    if (n->b) check_expr_to(c, &n->b, t_int);
    t = t_range;
    break;
  case N_ADDR: {
    Type *at = check_expr(c, &n->a, NULL);
    if (n->a->kind != N_IDENT && n->a->kind != N_FIELD && n->a->kind != N_INDEX) fatal(n->pos, "can only take the address of a variable, field or element");
    if (n->a->kind == N_IDENT && n->a->aux == S_LOCAL) {
      Local *l = n->a->sym;
      if (l->flags & LF_CAPTURE) fatal(n->pos, "cannot take the address of a captured variable");
    }
    t = mk_ptr(at);
    break;
  }
  case N_HOLE: fatal(n->pos, "'_' can only be used as a function argument (partial application)");
  case N_NAMEDARG: fatal(n->pos, "named arguments are only allowed in calls");
  case N_FNREF: t = n->type; break;
  case N_CONV: t = n->type; break;
  case N_BLOCK: t = check_block(c, n, expected, true); break;
  default:
    fatal(n->pos, "invalid expression");
  }
  n = *pn;
  n->type = t;
  n->flags |= NF_CHECKED;
  return t;
}
