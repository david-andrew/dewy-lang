#include "check.h"
#include <dirent.h>
#include <unistd.h>

Program prog;
int g_target_wasm;
const char *g_lib_dir;
static Type T_never_s = {.kind = TY_VOID, .bits = 1, .laid_out = true};
Type *t_never = &T_never_s;
Scope *universe, *prelude_scope;
typeof(modules) modules;
static VEC(StructInfo *) struct_insts;
static int inst_counter;

// ---------------- scopes ----------------
static uint32_t shash(Str s) { uint32_t h = 2166136261u; for (int i = 0; i < s.len; i++) h = (h ^ (uint8_t)s.p[i]) * 16777619u; return h; }

typedef struct { Sym **ht; int cap, n; } SymHash;

Scope *scope_new(Scope *parent, int kind, FnCtx *fn) {
  Scope *s = arena_alloc(sizeof(Scope));
  s->parent = parent; s->kind = kind; s->fn = fn;
  return s;
}

static Sym *hash_find(Scope *s, Str name) {
  SymHash *h = (SymHash *)s->syms;
  if (!h || !h->cap) return NULL;
  uint32_t i = shash(name) & (h->cap - 1);
  while (h->ht[i]) { if (str_eq(h->ht[i]->name, name)) return h->ht[i]; i = (i + 1) & (h->cap - 1); }
  return NULL;
}
static void hash_put(Scope *s, Sym *sym) {
  SymHash *h = (SymHash *)s->syms;
  if (!h) { h = calloc(1, sizeof(SymHash)); s->syms = (Sym *)h; }
  if (h->n * 2 >= h->cap) {
    int nc = h->cap ? h->cap * 2 : 64;
    Sym **nt = calloc(nc, sizeof(Sym *));
    for (int i = 0; i < h->cap; i++) if (h->ht[i]) {
      uint32_t j = shash(h->ht[i]->name) & (nc - 1);
      while (nt[j]) j = (j + 1) & (nc - 1);
      nt[j] = h->ht[i];
    }
    free(h->ht); h->ht = nt; h->cap = nc;
  }
  uint32_t i = shash(sym->name) & (h->cap - 1);
  while (h->ht[i]) i = (i + 1) & (h->cap - 1);
  h->ht[i] = sym; h->n++;
}

Sym *scope_lookup_here(Scope *s, Str name) {
  if (s->kind == 0) return hash_find(s, name);
  for (int i = s->n - 1; i >= 0; i--) if (str_eq(s->syms[i].name, name)) return &s->syms[i];
  return NULL;
}

Sym *scope_add(Scope *s, Str name, int kind, void *p, Node *decl) {
  Sym *existing = scope_lookup_here(s, name);
  if (existing && s->kind == 0) {
    if (existing->kind == S_FNS && kind == S_FNS) {
      Sym *ns = arena_alloc(sizeof(Sym));
      ns->name = name; ns->kind = kind; ns->p = p; ns->decl = decl;
      Sym *e = existing; while (e->next_overload) e = e->next_overload;
      e->next_overload = ns;
      return existing;
    }
    if (decl && existing->decl) {
      fatal(decl->pos, "'%.*s' is already defined (at line %d)", name.len, name.p, existing->decl->pos.line);
    }
  }
  if (s->kind == 0) {
    Sym *ns = arena_alloc(sizeof(Sym));
    ns->name = name; ns->kind = kind; ns->p = p; ns->decl = decl;
    hash_put(s, ns);
    return ns;
  }
  if (s->n == s->cap) { s->cap = s->cap ? s->cap * 2 : 8; s->syms = realloc(s->syms, sizeof(Sym) * s->cap); }
  Sym *ns = &s->syms[s->n++];
  memset(ns, 0, sizeof *ns);
  ns->name = name; ns->kind = kind; ns->p = p; ns->decl = decl;
  return ns;
}

Sym *scope_lookup(Scope *s, Str name) {
  for (; s; s = s->parent) {
    Sym *r = scope_lookup_here(s, name);
    if (r) return r;
    for (int i = 0; i < s->nuses; i++) { r = scope_lookup_here(s->uses[i], name); if (r) return r; }
  }
  return NULL;
}

// ---------------- modules ----------------
static Module *find_module(const char *path) {
  for (int i = 0; i < modules.len; i++) if (strcmp(g_files.data[modules.data[i]->file].path, path) == 0) return modules.data[i];
  return NULL;
}

static Module *load_module(const char *path, bool is_prelude, Pos from);

static void register_decls(Module *m, NodeList *decls, NodeList *init_stmts);

static void eval_when_toplevel(Module *m, Node *w, NodeList *init_stmts) {
  FnCtx tmp = {0};
  tmp.scope = m->scope; tmp.mod = m;
  bool cond = const_eval_bool(&tmp, w->a);
  Node *blk = cond ? w->b : w->c;
  if (!blk) return;
  NodeList l = {0};
  for (int i = 0; i < blk->list.len; i++) vpush(l, blk->list.data[i]);
  register_decls(m, &l, init_stmts);
}

// `x = value` where no variable x exists yet is a declaration
// (m != NULL: at the top level of module m, where only that module's globals count)
static bool name_assignable(Scope *sc, Str name, Module *m) {
  Sym *s = m ? scope_lookup_here(m->scope, name) : scope_lookup(sc, name);
  if (!s) return false;
  return s->kind == S_GLOBAL || (!m && s->kind == S_LOCAL);
}
static bool assign_declares(Node *s, Scope *sc, Module *m) {
  if (s->kind != N_ASSIGN || s->op != TK_ASSIGN) return false;
  Node *lhs = s->a;
  if (lhs->kind == N_IDENT) return !name_assignable(sc, lhs->name, m);
  if (lhs->kind != N_TUPLE) return false;
  bool any = false;
  for (int i = 0; i < lhs->list.len; i++) {
    Node *e = lhs->list.data[i];
    if (e->kind == N_HOLE) continue;
    if (e->kind != N_IDENT || name_assignable(sc, e->name, m)) return false;
    any = true;
  }
  return any;
}
static void assign_to_decl(Node *s) {
  Node *lhs = s->a;
  s->kind = N_VARDECL;
  s->a = NULL;
  if (lhs->kind == N_IDENT) s->name = lhs->name;
  else s->list = lhs->list;
}

static void register_decls(Module *m, NodeList *decls, NodeList *init_stmts) {
  for (int i = 0; i < decls->len; i++) {
    Node *d = decls->data[i];
    d->mod = m;
    if (assign_declares(d, m->scope, m)) assign_to_decl(d);
    switch (d->kind) {
    case N_FN:
      scope_add(m->scope, d->name, S_FNS, NULL, d);
      break;
    case N_STRUCT: scope_add(m->scope, d->name, S_STRUCT, d, d); break;
    case N_ENUM: scope_add(m->scope, d->name, S_ENUM, d, d); break;
    case N_CONST: {
      Global *g = arena_alloc(sizeof(Global));
      g->name = d->name; g->decl = d; g->mod = m; g->is_const = true;
      scope_add(m->scope, d->name, S_CONST, g, d);
      break;
    }
    case N_IMPORT: {
      char path[1024];
      if (d->aux2) { // use 'file.jo': relative to the importing file
        if (d->sval.len && d->sval.p[0] == '/') snprintf(path, sizeof path, "%.*s", d->sval.len, d->sval.p);
        else snprintf(path, sizeof path, "%s/%.*s", m->dir, d->sval.len, d->sval.p);
        if (access(path, R_OK) != 0) fatal(d->pos, "cannot find '%.*s' (looked for %s)", d->sval.len, d->sval.p, path);
      } else {
        snprintf(path, sizeof path, "%s/%.*s.jo", m->dir, d->sval.len, d->sval.p);
        if (access(path, R_OK) != 0) snprintf(path, sizeof path, "%s/%.*s.jo", g_lib_dir, d->sval.len, d->sval.p);
        if (access(path, R_OK) != 0) fatal(d->pos, "cannot find module '%.*s'", d->sval.len, d->sval.p);
      }
      Module *im = load_module(path, false, d->pos);
      if (d->aux) {
        Scope *s = m->scope;
        s->uses = realloc(s->uses, sizeof(Scope *) * (s->nuses + 1));
        s->uses[s->nuses++] = im->scope;
      } else scope_add(m->scope, d->name, S_MODULE, im, d);
      break;
    }
    case N_WHEN:
      eval_when_toplevel(m, d, init_stmts);
      break;
    case N_BUILD:
      if (m->is_main) prog.build = d;
      break;
    case N_TEST:
      break;
    case N_VARDECL: {
      if (d->list.len) {
        for (int k = 0; k < d->list.len; k++) {
          Node *id = d->list.data[k];
          if (id->kind == N_HOLE) continue;
          Global *g = arena_alloc(sizeof(Global));
          g->name = id->name; g->decl = d; g->mod = m;
          g->sym = internc(fmt("g_%.*s_%d", id->name.len, id->name.p, inst_counter++));
          id->sym = g;
          id->flags |= NF_GLOBAL;
          scope_add(m->scope, id->name, S_GLOBAL, g, id);
          vpush(prog.globals, g);
        }
        d->aux = 1; // tuple global
      } else {
        Global *g = arena_alloc(sizeof(Global));
        g->name = d->name; g->decl = d; g->mod = m;
        g->sym = internc(fmt("g_%.*s_%d", d->name.len, d->name.p, inst_counter++));
        d->sym = g;
        scope_add(m->scope, d->name, S_GLOBAL, g, d);
        vpush(prog.globals, g);
      }
      d->flags |= NF_GLOBAL;
      if (!m->is_prelude) vpush(*init_stmts, d);
      break;
    }
    default:
      if (m->is_prelude) fatal(d->pos, "statements are not allowed at the top level of library modules");
      vpush(*init_stmts, d);
      break;
    }
  }
}

static NodeList module_inits[256];
static FnCtx *module_ctx[256];

static Module *load_module(const char *path, bool is_prelude, Pos from) {
  char *rp = realpath(path, NULL);
  if (!rp) fatal(from, "cannot open '%s'", path);
  Module *ex = find_module(rp);
  if (ex) return ex;
  int len;
  char *src = read_file(rp, &len);
  if (!src) fatal(from, "cannot read '%s'", rp);
  char *dir = strdup(rp);
  char *slash = strrchr(dir, '/'); if (slash) *slash = 0;
  SrcFile sf = {rp, dir, src, len};
  vpush(g_files, sf);
  Module *m = arena_alloc(sizeof(Module));
  m->file = g_files.len - 1;
  m->dir = dir;
  m->is_prelude = is_prelude;
  m->order = modules.len;
  const char *base = strrchr(rp, '/'); base = base ? base + 1 : rp;
  m->name = intern(base, strlen(base) - 3);
  m->scope = is_prelude ? prelude_scope : scope_new(prelude_scope, 0, NULL);
  vpush(modules, m);
  if (modules.len >= 256) fatal(from, "too many modules");
  parse_file(m->file, &m->decls);
  if (!is_prelude && modules.len > 0 && !prog.build) { /* main detection happens in check_program */ }
  return m;
}

// ---------------- types ----------------
static Sym *find_type_sym(Scope *sc, Str name) {
  Sym *s = scope_lookup(sc, name);
  return s;
}

Type *resolve_type(Node *tn, Scope *sc) {
  switch (tn->kind) {
  case N_TNAME: {
    Scope *look = sc;
    if (tn->sval.len) {
      Sym *ms = scope_lookup(sc, tn->sval);
      if (!ms || ms->kind != S_MODULE) fatal(tn->pos, "unknown module '%.*s'", tn->sval.len, tn->sval.p);
      look = ((Module *)ms->p)->scope;
    }
    Sym *s = find_type_sym(look, tn->name);
    if (!s) fatal(tn->pos, "unknown type '%.*s'", tn->name.len, tn->name.p);
    if (s->kind == S_TYPE) {
      if (tn->list.len) fatal(tn->pos, "type '%.*s' takes no type arguments", tn->name.len, tn->name.p);
      return s->p;
    }
    if (s->kind == S_STRUCT || s->kind == S_ENUM) {
      Node *d = s->p;
      int ntp = d->list2.len;
      if (tn->list.len != ntp) fatal(tn->pos, "type '%.*s' expects %d type argument(s), got %d", tn->name.len, tn->name.p, ntp, tn->list.len);
      Type *targs[16];
      for (int i = 0; i < ntp; i++) targs[i] = resolve_type(tn->list.data[i], sc);
      return get_struct_inst(d, targs, ntp)->type;
    }
    fatal(tn->pos, "'%.*s' is not a type", tn->name.len, tn->name.p);
  }
  case N_TARRAY:
    if (tn->b) fatal(tn->pos, "fixed-size arrays are not supported yet");
    return mk_array(resolve_type(tn->a, sc));
  case N_TMAP: {
    Sym *s = scope_lookup(prelude_scope, S("Map"));
    if (!s) fatal(tn->pos, "Map type is not available");
    Type *targs[2] = {resolve_type(tn->a, sc), resolve_type(tn->b, sc)};
    return get_struct_inst(s->p, targs, 2)->type;
  }
  case N_TTUPLE: {
    Type *el[32];
    if (tn->list.len > 32) fatal(tn->pos, "tuple too large");
    for (int i = 0; i < tn->list.len; i++) el[i] = resolve_type(tn->list.data[i], sc);
    if (tn->list.len == 0) return t_void;
    return mk_tuple(el, tn->list.len);
  }
  case N_TOPT: return mk_opt(resolve_type(tn->a, sc));
  case N_TPTR: return mk_ptr(resolve_type(tn->a, sc));
  case N_TFN: {
    Type *ps[32]; uint32_t mm = 0;
    for (int i = 0; i < tn->list.len; i++) {
      ps[i] = resolve_type(tn->list.data[i], sc);
      if (tn->list.data[i]->flags & NF_MUT) mm |= 1u << i;
    }
    return mk_fn(ps, tn->list.len, tn->a ? resolve_type(tn->a, sc) : t_void, mm);
  }
  default:
    fatal(tn->pos, "invalid type");
  }
}

Type *subst(Type *t, Type **targs) {
  t = prune(t);
  if (!t || !t->has_var) return t;
  if (t->kind == TY_PARAM) return targs[t->id] ? targs[t->id] : t;
  if (t->kind == TY_VAR) return t;
  switch (t->kind) {
  case TY_ARRAY: return mk_array(subst(t->elem, targs));
  case TY_PTR: return mk_ptr(subst(t->elem, targs));
  case TY_OPT: return mk_opt(subst(t->elem, targs));
  case TY_FN: case TY_TUPLE: {
    Type *a[32];
    for (int i = 0; i < t->nargs; i++) a[i] = subst(t->args[i], targs);
    return t->kind == TY_FN ? mk_fn(a, t->nargs, subst(t->elem, targs), t->mutmask) : mk_tuple(a, t->nargs);
  }
  case TY_STRUCT: case TY_ENUM: {
    Type *a[16];
    for (int i = 0; i < t->st->ntargs; i++) a[i] = subst(t->st->targs[i], targs);
    return get_struct_inst(t->st->decl, a, t->st->ntargs)->type;
  }
  default: return t;
  }
}

static Scope *type_param_scope(Node *decl, Type **targs, int n, Scope *parent) {
  Scope *s = scope_new(parent, 2, NULL);
  for (int i = 0; i < n && i < decl->list2.len; i++) scope_add(s, decl->list2.data[i]->name, S_TYPE, targs[i], NULL);
  return s;
}

StructInfo *get_struct_inst(Node *decl, Type **targs, int n) {
  for (int i = 0; i < struct_insts.len; i++) {
    StructInfo *si = struct_insts.data[i];
    if (si->decl != decl || si->ntargs != n) continue;
    bool same = true;
    for (int k = 0; k < n; k++) if (!type_eq(si->targs[k], targs[k])) { same = false; break; }
    if (same) return si;
  }
  StructInfo *si = arena_alloc(sizeof(StructInfo));
  si->decl = decl;
  si->ntargs = n;
  si->targs = arena_alloc(sizeof(Type *) * (n ? n : 1));
  bool hv = false;
  for (int k = 0; k < n; k++) { si->targs[k] = targs[k]; if (prune(targs[k])->has_var) hv = true; }
  Type t = {0};
  t.kind = decl->kind == N_STRUCT ? TY_STRUCT : TY_ENUM;
  t.st = si;
  Type *nt = arena_alloc(sizeof(Type));
  *nt = t;
  nt->has_var = hv;
  si->type = nt;
  si->mangled = internc(fmt("%.*s_%d", decl->name.len, decl->name.p, struct_insts.len));
  vpush(struct_insts, si);
  return si;
}

static Type *resolve_type_any(Node *tn, Scope *sc);

void check_struct_fields(StructInfo *si) {
  if (si->resolved) return;
  si->resolved = true;
  Node *d = si->decl;
  Scope *sc = type_param_scope(d, si->targs, si->ntargs, d->mod->scope);
  if (d->kind == N_STRUCT) {
    si->nfields = d->list.len;
    si->fields = arena_alloc(sizeof(Field) * (si->nfields ? si->nfields : 1));
    for (int i = 0; i < d->list.len; i++) {
      Node *f = d->list.data[i];
      si->fields[i].name = f->name;
      si->fields[i].defval = f->b;
      if (f->a) si->fields[i].type = resolve_type(f->a, sc);
      else if (f->b) {
        // infer from default expression
        FnCtx tmp = {0};
        tmp.scope = sc; tmp.mod = d->mod;
        tmp.inst = new_inst(FK_INIT, d->mod, "__fielddef");
        Node *cl = clone_node(f->b);
        Type *t = check_expr(&tmp, &cl, NULL);
        if (cl->flags & NF_LITERAL) t = cl->kind == N_FLOAT ? t_float : t_int;
        si->fields[i].type = zonk(t);
      } else fatal(f->pos, "field needs a type");
      for (int k = 0; k < i; k++) if (str_eq(si->fields[k].name, f->name)) fatal(f->pos, "duplicate field '%.*s'", f->name.len, f->name.p);
    }
  } else {
    si->nvariants = d->list.len;
    si->variants = arena_alloc(sizeof(Variant) * (si->nvariants ? si->nvariants : 1));
    int64_t next_val = 0;
    for (int v = 0; v < d->list.len; v++) {
      Node *vn = d->list.data[v];
      Variant *var = &si->variants[v];
      var->name = vn->name;
      var->tag = v;
      if (vn->a) {
        if (vn->a->kind != N_INT) fatal(vn->a->pos, "enum value must be an integer literal");
        next_val = vn->a->ival;
      }
      var->value = next_val++;
      var->nfields = vn->list.len;
      var->fields = arena_alloc(sizeof(Field) * (var->nfields ? var->nfields : 1));
      for (int i = 0; i < vn->list.len; i++) {
        var->fields[i].name = vn->list.data[i]->name;
        var->fields[i].type = resolve_type(vn->list.data[i]->a, sc);
      }
      for (int k = 0; k < v; k++) if (str_eq(si->variants[k].name, vn->name)) fatal(vn->pos, "duplicate variant '%.*s'", vn->name.len, vn->name.p);
    }
  }
  (void)resolve_type_any;
}
static Type *resolve_type_any(Node *tn, Scope *sc) { return resolve_type(tn, sc); }

Module *module_of_type(Type *t) {
  t = prune(t);
  if ((t->kind == TY_STRUCT || t->kind == TY_ENUM) && t->st) return t->st->decl->mod;
  return NULL;
}

// ---------------- functions ----------------
FnDeclInfo *decl_info(Node *decl) {
  if (!decl->sym) decl->sym = calloc(1, sizeof(FnDeclInfo));
  return decl->sym;
}

FnSig *fn_sig(Node *decl) {
  FnDeclInfo *di = decl_info(decl);
  FnSig *s = &di->sig;
  if (s->done) return s;
  s->done = true;
  s->nexplicit = decl->list2.len;
  Scope *sc = scope_new(decl->mod->scope, 2, NULL);
  for (int i = 0; i < decl->list2.len; i++) scope_add(sc, decl->list2.data[i]->name, S_TYPE, mk_param(i), NULL);
  int ntp = decl->list2.len;
  s->params = arena_alloc(sizeof(Type *) * (decl->list.len + 1));
  for (int i = 0; i < decl->list.len; i++) {
    Node *p = decl->list.data[i];
    if (p->a) s->params[i] = resolve_type(p->a, sc);
    else s->params[i] = mk_param(ntp++);
    if (p->flags & NF_MUT) s->mutmask |= 1u << i;
  }
  s->ntp = ntp;
  s->generic = ntp > 0;
  s->ret = decl->a ? resolve_type(decl->a, sc) : NULL;
  return s;
}

FnInst *new_inst(int kind, Module *mod, const char *base) {
  FnInst *f = arena_alloc(sizeof(FnInst));
  f->kind = kind; f->mod = mod;
  f->sym = internc(fmt("f_%s_%d", base, inst_counter++));
  return f;
}

static const char *mangle_base(Str name) {
  char *b = arena_alloc(name.len + 8);
  int j = 0;
  for (int i = 0; i < name.len && j < 40; i++) {
    char c = name.p[i];
    if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_') b[j++] = c;
    else b[j++] = 'X';
  }
  b[j] = 0;
  return b;
}

// true if the body clearly returns nothing: no `return value` anywhere and the last
// statement cannot produce a value
static bool has_value_return(Node *n) {
  if (!n) return false;
  if (n->kind == N_RETURN) return n->a != NULL;
  if (n->kind == N_LAMBDA) return false;
  if (has_value_return(n->a) || has_value_return(n->b) || (n->kind != N_FOR && has_value_return(n->c))) return true;
  for (int i = 0; i < n->list.len; i++) if (has_value_return(n->list.data[i])) return true;
  return false;
}
static bool syntactic_void(Node *body) {
  if (!body || !body->list.len) return true;
  if (has_value_return(body)) return false;
  Node *last = body->list.data[body->list.len - 1];
  switch (last->kind) {
  case N_EXPRSTMT: return false;
  case N_IF: case N_IFLET: return last->c == NULL;
  default: return true;
  }
}

FnInst *get_fn_inst(Node *decl, Type **targs, int ntargs, Pos use) {
  FnDeclInfo *di = decl_info(decl);
  FnSig *sig = fn_sig(decl);
  for (int i = 0; i < di->insts.len; i++) {
    FnInst *f = di->insts.data[i];
    bool same = true;
    for (int k = 0; k < ntargs; k++) if (!type_eq(f->targs[k], targs[k])) { same = false; break; }
    if (same) { ensure_ret(f, use); return f; }
  }
  FnInst *f = new_inst(FK_NORMAL, decl->mod, mangle_base(decl->name));
  f->decl = decl;
  f->ntargs = ntargs;
  f->targs = arena_alloc(sizeof(Type *) * (ntargs ? ntargs : 1));
  for (int k = 0; k < ntargs; k++) {
    f->targs[k] = zonk(targs[k]);
    if (prune(f->targs[k])->has_var) fatal(use, "cannot infer the type of an argument to '%.*s' (%s); add a type annotation", decl->name.len, decl->name.p, type_str(f->targs[k]));
  }
  f->np = decl->list.len;
  f->ptypes = arena_alloc(sizeof(Type *) * (f->np + 1));
  for (int i = 0; i < f->np; i++) f->ptypes[i] = subst(sig->params[i], f->targs);
  f->ret = sig->ret ? subst(sig->ret, f->targs) : NULL;
  if (!f->ret && decl->b && syntactic_void(decl->b)) f->ret = t_void;
  f->body = sig->generic ? clone_node(decl->b) : decl->b;
  if (decl->flags & NF_EXTERN) f->ret = f->ret ? f->ret : t_void;
  vpush(di->insts, f);
  vpush(prog.fns, f);
  ensure_ret(f, use);
  return f;
}

static bool has_value_return(Node *n);
static void check_fn_body(FnInst *f);
void ensure_ret(FnInst *f, Pos use) {
  if (f->ret) return;
  if (f->state == 1 && f->decl && !has_value_return(f->decl->b)) { f->ret = t_void; f->aux_void = true; return; }
  if (f->state == 1) fatal(use, "recursive function '%.*s' needs an explicit return type (add `-> Type`)", f->decl->name.len, f->decl->name.p);
  check_fn_body(f);
}

Local *new_local(FnCtx *c, Str name, Type *t, Pos pos) {
  Local *l = arena_alloc(sizeof(Local));
  l->name = name; l->type = t; l->fn = c->inst; l->pos = pos;
  vpush(c->inst->locals, l);
  if (name.len && !(name.len == 1 && name.p[0] == '_')) scope_add(c->scope, name, S_LOCAL, l, NULL);
  return l;
}

Local *capture_local(FnCtx *c, Local *l) {
  if (l->fn == c->inst || !c->parent) return l;
  Local *outer = capture_local(c->parent, l);
  for (int i = 0; i < c->inst->caps.len; i++) if (c->inst->caps.data[i].outer == outer) return c->inst->caps.data[i].inner;
  Local *in = arena_alloc(sizeof(Local));
  in->name = l->name; in->type = l->type; in->fn = c->inst; in->flags = LF_CAPTURE; in->pos = l->pos;
  l->flags |= LF_CAPTURED;
  Capture cap = {outer, in};
  vpush(c->inst->caps, cap);
  vpush(c->inst->locals, in);
  return in;
}

void ensure_global(Global *g, Pos use) {
  if (g->state == 2) return;
  if (g->state == 1) fatal(use, "global '%.*s' is used in its own initializer", g->name.len, g->name.p);
  g->state = 1;
  FnCtx *ctx = module_ctx[g->mod->order];
  Scope *saved = ctx->scope;
  ctx->scope = g->mod->scope;
  Node *d = g->decl;
  if (g->is_const) {
    Type *t = NULL;
    if (d->a) t = resolve_type(d->a, g->mod->scope);
    Node *cl = clone_node(d->b);
    Type *et = check_expr(ctx, &cl, t);
    if (t) coerce(ctx, &cl, t);
    else if ((cl->flags & NF_LITERAL)) t = cl->kind == N_FLOAT ? t_float : t_int;
    else t = et;
    g->type = zonk(t);
    g->init = cl;
  } else if (d->list.len) {
    // tuple global: check initializer once
    if (!(d->flags & NF_CHECKED)) {
      Type *t = check_expr(ctx, &d->b, NULL);
      t = prune(t);
      if (t->kind != TY_TUPLE || t->nargs != d->list.len) fatal(d->pos, "expected a tuple with %d elements, found %s", d->list.len, type_str(t));
      for (int k = 0; k < d->list.len; k++) {
        Node *id = d->list.data[k];
        if (id->kind == N_HOLE) continue;
        Global *gg = id->sym;
        gg->type = zonk(t->args[k]);
        gg->state = 2;
      }
      d->flags |= NF_CHECKED;
      d->type = t;
    }
  } else {
    Type *t = d->a ? resolve_type(d->a, g->mod->scope) : NULL;
    if (d->b) {
      Type *et = check_expr(ctx, &d->b, t);
      if (t) coerce(ctx, &d->b, t);
      else {
        t = et;
        if (d->b->flags & NF_LITERAL) { t = d->b->kind == N_FLOAT ? t_float : t_int; coerce(ctx, &d->b, t); }
      }
    }
    t = zonk(t);
    if (prune(t)->has_var) fatal(d->pos, "cannot infer the type of '%.*s'; add a type annotation", g->name.len, g->name.p);
    if (prune(t)->kind == TY_VOID) fatal(d->pos, "cannot assign a value of type void");
    g->type = t;
    d->flags |= NF_CHECKED;
  }
  g->state = 2;
  ctx->scope = saved;
}

// ---------------- statements ----------------
bool stmt_terminates(Node *s) {
  if (!s) return false;
  switch (s->kind) {
  case N_RETURN: case N_BREAK: case N_CONTINUE: return true;
  case N_BLOCK: return s->list.len && stmt_terminates(s->list.data[s->list.len - 1]);
  case N_IF: return s->c && stmt_terminates(s->b) && stmt_terminates(s->c);
  case N_EXPRSTMT: {
    Node *e = s->a;
    if (e->type == t_never) return true;
    if (e->kind == N_MATCH) {
      bool all = true, wild = false;
      for (int i = 0; i < e->list.len; i++) {
        Node *arm = e->list.data[i];
        if (!stmt_terminates(arm->b)) all = false;
        for (int k = 0; k < arm->list.len; k++) if (arm->list.data[k]->kind == N_PWILD) wild = true;
      }
      return all && (wild || e->aux2);
    }
    if (e->kind == N_IF) return e->c && stmt_terminates(e->b) && stmt_terminates(e->c);
    return false;
  }
  case N_WHILE: return s->a->kind == N_BOOL && s->a->ival && !s->aux2;
  default: return false;
  }
}

static bool value_capable(Node *s) {
  if (s->kind == N_EXPRSTMT) return true;
  if (s->kind == N_IF && s->c) return true;
  return false;
}

static void expand_when(FnCtx *c, NodeList *out, Node *s) {
  if (s->kind != N_WHEN) { vpush(*out, s); return; }
  Node *blk = const_eval_bool(c, s->a) ? s->b : s->c;
  if (!blk) return;
  for (int i = 0; i < blk->list.len; i++) expand_when(c, out, blk->list.data[i]);
}

Type *check_block(FnCtx *c, Node *b, Type *expected, bool want_value) {
  bool has_when = false;
  for (int i = 0; i < b->list.len; i++) if (b->list.data[i]->kind == N_WHEN) has_when = true;
  if (has_when) {
    NodeList nl = {0};
    for (int i = 0; i < b->list.len; i++) expand_when(c, &nl, b->list.data[i]);
    b->list = nl;
  }
  Scope *saved = c->scope;
  c->scope = scope_new(c->scope, 2, c);
  Type *result = t_void;
  b->aux = 0;
  for (int i = 0; i < b->list.len; i++) {
    bool last = i == b->list.len - 1;
    Node **ps = &b->list.data[i];
    if (last && want_value && value_capable(*ps)) {
      if ((*ps)->kind == N_IF) {
        Node *es = new_node(N_EXPRSTMT, (*ps)->pos);
        es->a = *ps;
        (*ps)->flags &= ~NF_STMT;
        *ps = es;
      }
      Node *es = *ps;
      if (es->a->kind == N_MATCH) es->a->flags &= ~NF_STMT;
      result = check_expr(c, &es->a, expected);
      if (prune(result)->kind != TY_VOID) b->aux = 1;
      if (result == t_never) b->aux = 0;
      es->flags |= NF_CHECKED;
      continue;
    }
    check_stmt(c, ps);
  }
  if (want_value && !b->aux && b->list.len && stmt_terminates(b->list.data[b->list.len - 1])) result = t_never;
  b->type = result;
  c->scope = saved;
  return result;
}

static Node *loop_index_ident(Local *l, Pos pos) { return mk_ident_local(l, pos); }

static void check_for(FnCtx *c, Node *s) {
  Scope *saved = c->scope;
  c->scope = scope_new(c->scope, 2, c);
  Node *it = s->a;
  bool is_mut = s->flags & NF_MUT;
  int nv = s->list.len;
  Str n1 = s->list.data[0]->name, n2 = nv > 1 ? s->list.data[1]->name : (Str){0};
  if (it->kind == N_RANGE) {
    if (!it->a || !it->b) fatal(it->pos, "for loop range needs both bounds");
    Type *t = check_expr(c, &it->a, NULL);
    Type *t2 = check_expr(c, &it->b, NULL);
    (void)t2;
    if ((it->a->flags & NF_LITERAL) && !(it->b->flags & NF_LITERAL)) t = it->b->type;
    if (it->a->flags & NF_LITERAL && it->b->flags & NF_LITERAL) t = t_int;
    if (!is_int(t)) fatal(it->pos, "range bounds must be integers, found %s", type_str(t));
    coerce(c, &it->a, t); coerce(c, &it->b, t);
    if (nv != 1) fatal(s->pos, "a range loop has one loop variable");
    if (is_mut) fatal(s->pos, "'loop mut' needs an array");
    Local *l = new_local(c, n1, t, s->pos);
    s->sym = l;
    s->aux = 0; // range loop
  } else {
    Type *t = check_expr(c, &s->a, NULL);
    t = prune(t);
    it = s->a;
    if (t->kind == TY_RANGE) {
      Local *l = new_local(c, n1, t_int, s->pos);
      s->sym = l; s->aux = 4;
    } else if (t->kind == TY_ARRAY || t->kind == TY_STR) {
      Type *et = t->kind == TY_ARRAY ? t->elem : t_u8;
      Local *idx = new_local(c, nv == 2 ? n1 : (Str){0}, t_int, s->pos);
      Local *snap = new_local(c, (Str){0}, t, s->pos);
      Local *el;
      if (is_mut) {
        if (t->kind == TY_STR) fatal(s->pos, "strings are immutable; 'loop mut' needs an array");
        check_place(c, it, true);
        el = new_local(c, nv == 2 ? n2 : n1, et, s->pos);
        el->flags |= LF_ALIAS;
        Node *ix = new_node(N_INDEX, s->pos);
        ix->a = clone_node(it);
        check_expr(c, &ix->a, NULL);
        ix->b = loop_index_ident(idx, s->pos);
        ix->b->type = t_int;
        ix->type = et;
        ix->flags |= NF_CHECKED;
        el->alias = ix;
        s->aux = 2;
      } else {
        el = new_local(c, nv == 2 ? n2 : n1, et, s->pos);
        el->flags |= LF_BYREF;
        s->aux = 1;
      }
      s->sym = el;
      s->c = (Node *)idx; // stash
      s->d = (Node *)snap;
    } else if ((t->kind == TY_STRUCT) && t->st->nfields >= 2 && str_eqc(t->st->decl->name, "Map")) {
      check_struct_fields(t->st);
      Type *kt = t->st->fields[0].type, *vt = t->st->fields[1].type;
      Local *idx = new_local(c, (Str){0}, t_int, s->pos);
      Local *snap = new_local(c, (Str){0}, t, s->pos);
      Local *kl = new_local(c, n1, kt, s->pos);
      kl->flags |= LF_BYREF;
      Local *vl = NULL;
      if (nv == 2) {
        if (is_mut) {
          check_place(c, it, true);
          vl = new_local(c, n2, prune(vt)->elem, s->pos);
          vl->flags |= LF_ALIAS;
          // alias: it.vals[idx]
          Node *f = new_node(N_FIELD, s->pos); f->a = clone_node(it); f->name = S("vals");
          Node *ix = new_node(N_INDEX, s->pos); ix->a = f; ix->b = loop_index_ident(idx, s->pos);
          check_expr(c, &ix, NULL);
          vl->alias = ix;
        } else {
          vl = new_local(c, n2, prune(vt)->elem, s->pos);
          vl->flags |= LF_BYREF;
        }
      } else if (is_mut) fatal(s->pos, "'loop mut' over a map needs key and value variables");
      kl->type = prune(kt)->elem;
      s->aux = 3;
      s->sym = kl;
      s->c = (Node *)idx; s->d = (Node *)snap;
      s->list2.len = 0;
      Node *holder = new_node(N_BLOCK, s->pos); holder->sym = vl;
      vpush(s->list2, holder);
    } else fatal(it->pos, "cannot iterate over a value of type %s", type_str(t));
  }
  c->loop_depth++;
  check_block(c, s->b, NULL, false);
  c->loop_depth--;
  c->scope = saved;
}

static void check_assign(FnCtx *c, Node **ps) {
  Node *s = *ps;
  if (s->a->kind == N_TUPLE) {
    if (s->op != TK_ASSIGN) fatal(s->pos, "compound assignment to a tuple");
    Type *t = check_expr(c, &s->b, NULL);
    t = prune(t);
    if (t->kind != TY_TUPLE || t->nargs != s->a->list.len) fatal(s->pos, "expected a tuple with %d elements, found %s", s->a->list.len, type_str(t));
    for (int i = 0; i < s->a->list.len; i++) {
      Node **tp = &s->a->list.data[i];
      if ((*tp)->kind == N_HOLE) continue;
      Type *tt = check_expr(c, tp, NULL);
      check_place(c, *tp, false);
      if (!can_coerce(NULL, t->args[i], tt) && !type_eq(t->args[i], tt)) fatal((*tp)->pos, "cannot assign %s to %s", type_str(t->args[i]), type_str(tt));
    }
    s->aux = 1;
    return;
  }
  // indexing a struct: m[k] = v  ->  `[]=`(mut m, k, v)
  if (s->a->kind == N_INDEX) {
    Node *ix = s->a;
    Type *bt = check_expr(c, &ix->a, NULL);
    bt = prune(bt);
    if (bt->kind == TY_STRUCT) {
      Node *call = new_node(N_CALL, s->pos);
      Node *callee = new_node(N_IDENT, s->pos);
      callee->name = S("[]=");
      call->a = callee;
      Node *recv = ix->a; recv->flags |= NF_MUT;
      vpush(call->list, recv);
      vpush(call->list, ix->b);
      Node *val = s->b;
      if (s->op != TK_ASSIGN) {
        Node *get = new_node(N_INDEX, s->pos);
        get->a = clone_node(ix->a); get->a->flags &= ~NF_MUT; get->a->type = NULL;
        get->b = clone_node(ix->b);
        Node *bin = new_node(N_BINARY, s->pos);
        int map[][2] = {{TK_PLUSEQ, TK_PLUS}, {TK_MINUSEQ, TK_MINUS}, {TK_STAREQ, TK_STAR}, {TK_SLASHEQ, TK_SLASH}, {TK_PERCENTEQ, TK_PERCENT}, {TK_AMPEQ, TK_AMP}, {TK_PIPEEQ, TK_PIPE}, {TK_CARETEQ, TK_CARET}, {TK_SHLEQ, TK_SHL}, {TK_SHREQ, TK_SHR}};
        for (int i = 0; i < 10; i++) if (map[i][0] == s->op) bin->op = map[i][1];
        bin->a = get; bin->b = val;
        val = bin;
      }
      vpush(call->list, val);
      Node *es = new_node(N_EXPRSTMT, s->pos);
      es->a = call;
      // the receiver was already checked; the call checker re-checks args, so reset
      recv->flags &= ~NF_CHECKED;
      *ps = es;
      check_expr(c, &es->a, NULL);
      return;
    }
  }
  Type *lt = check_expr(c, &s->a, NULL);
  check_place(c, s->a, false);
  if (s->op == TK_ASSIGN) {
    check_expr(c, &s->b, lt);
    coerce(c, &s->b, lt);
  } else {
    // compound: x op= y
    Type *l = prune(lt);
    if (l->kind == TY_STR && s->op == TK_PLUSEQ) {
      check_expr(c, &s->b, t_str);
      coerce(c, &s->b, t_str);
      s->aux = 2; // string append
      return;
    }
    Node *bin = new_node(N_BINARY, s->pos);
    int map[][2] = {{TK_PLUSEQ, TK_PLUS}, {TK_MINUSEQ, TK_MINUS}, {TK_STAREQ, TK_STAR}, {TK_SLASHEQ, TK_SLASH}, {TK_PERCENTEQ, TK_PERCENT}, {TK_AMPEQ, TK_AMP}, {TK_PIPEEQ, TK_PIPE}, {TK_CARETEQ, TK_CARET}, {TK_SHLEQ, TK_SHL}, {TK_SHREQ, TK_SHR}};
    for (int i = 0; i < 10; i++) if (map[i][0] == s->op) bin->op = map[i][1];
    if (l->kind == TY_PTR) {
      check_expr(c, &s->b, t_int); coerce(c, &s->b, t_int);
      s->aux = 3;
      return;
    }
    if (!is_numeric(l) && l->kind != TY_BOOL) {
      // operator overload: x = x op y
      bin->a = clone_node(s->a); bin->b = s->b;
      check_expr(c, &bin, NULL);
      coerce(c, &bin, lt);
      s->b = bin; s->op = TK_ASSIGN;
      return;
    }
    Type *rt = check_expr(c, &s->b, is_int(l) && (bin->op == TK_SHL || bin->op == TK_SHR) ? NULL : l);
    if (bin->op == TK_SHL || bin->op == TK_SHR) { if (!is_int(rt)) fatal(s->b->pos, "shift amount must be an integer"); coerce(c, &s->b, is_int(rt) ? rt : t_int); }
    else {
      if (is_int(l) && is_float(rt)) fatal(s->pos, "cannot apply %s to %s and %s (use int(...) to convert)", tok_name(s->op), type_str(l), type_str(rt));
      coerce(c, &s->b, l);
    }
  }
}

static void check_vardecl(FnCtx *c, Node *s) {
  if (s->list.len) { // tuple destructuring
    if (s->flags & NF_GLOBAL) { // global tuple
      for (int i = 0; i < s->list.len; i++) if (s->list.data[i]->kind != N_HOLE) { ensure_global(s->list.data[i]->sym, s->pos); break; }
      return;
    }
    Type *t = check_expr(c, &s->b, NULL);
    t = prune(t);
    if (t->kind != TY_TUPLE || t->nargs != s->list.len) fatal(s->pos, "expected a tuple with %d elements, found %s", s->list.len, type_str(t));
    for (int i = 0; i < s->list.len; i++) {
      Node *id = s->list.data[i];
      if (id->kind == N_HOLE) continue;
      Local *l = new_local(c, id->name, t->args[i], id->pos);
      id->sym = l;
    }
    s->type = t;
    return;
  }
  if (s->flags & NF_GLOBAL) { // global declaration at module top level
    ensure_global(s->sym, s->pos);
    return;
  }
  Type *t = s->a ? resolve_type(s->a, c->scope) : NULL;
  if (s->b) {
    if (s->b->kind == N_LAMBDA && !t) {
      // local function: allow recursion? no — bind after
    }
    Type *et = check_expr(c, &s->b, t);
    if (t) coerce(c, &s->b, t);
    else {
      t = et;
      if (s->b->flags & NF_LITERAL) { t = s->b->kind == N_FLOAT ? t_float : t_int; coerce(c, &s->b, t); }
      if (prune(t)->kind == TY_NONE_LIT) fatal(s->pos, "cannot infer the type of '%.*s' from 'none'; add a type: %.*s: T? = none", s->name.len, s->name.p, s->name.len, s->name.p);
    }
  }
  if (!t) fatal(s->pos, "variable needs a type or a value");
  if (prune(t)->kind == TY_VOID) fatal(s->pos, "cannot assign a value with no type (void) to '%.*s'", s->name.len, s->name.p);
  if (prune(t)->kind == TY_TYPE || prune(t)->kind == TY_MODULE) fatal(s->pos, "'%.*s' cannot hold a type or module", s->name.len, s->name.p);
  Local *l = new_local(c, s->name, t, s->pos);
  s->sym = l;
}

void check_stmt(FnCtx *c, Node **ps) {
  Node *s = *ps;
  switch (s->kind) {
  case N_VARDECL: check_vardecl(c, s); break;
  case N_CONST: {
    Global *g = arena_alloc(sizeof(Global));
    g->name = s->name; g->decl = s; g->mod = c->mod; g->is_const = true;
    Type *t = s->a ? resolve_type(s->a, c->scope) : NULL;
    Node *cl = clone_node(s->b);
    Type *et = check_expr(c, &cl, t);
    if (t) coerce(c, &cl, t); else if (cl->flags & NF_LITERAL) t = cl->kind == N_FLOAT ? t_float : t_int; else t = et;
    g->type = t; g->init = cl; g->state = 2;
    scope_add(c->scope, s->name, S_CONST, g, NULL);
    s->kind = N_BLOCK; s->list.len = 0; // becomes a no-op
    break;
  }
  case N_ASSIGN:
    if (assign_declares(s, c->scope, NULL)) { assign_to_decl(s); check_vardecl(c, s); }
    else check_assign(c, ps);
    break;
  case N_EXPRSTMT: {
    if (s->flags & NF_CHECKED) break;
    if (s->a->kind == N_MATCH) s->a->flags |= NF_STMT;
    check_expr(c, &s->a, NULL);
    break;
  }
  case N_IF: {
    s->flags |= NF_STMT;
    check_expr(c, ps, NULL);
    break;
  }
  case N_IFLET: {
    s->flags |= NF_STMT;
    check_expr(c, ps, NULL);
    break;
  }
  case N_WHILE: {
    Scope *saved = c->scope;
    c->scope = scope_new(c->scope, 2, c);
    if (s->aux == 1) { // while v := opt
      Type *t = check_expr(c, &s->a, NULL);
      t = prune(t);
      if (t->kind != TY_OPT) fatal(s->a->pos, "'loop let x = value' needs an optional value, found %s", type_str(t));
      Local *l = new_local(c, s->name, t->elem, s->pos);
      s->sym = l;
    } else {
      check_expr(c, &s->a, t_bool);
      coerce(c, &s->a, t_bool);
    }
    c->loop_depth++;
    check_block(c, s->b, NULL, false);
    c->loop_depth--;
    c->scope = saved;
    // detect break for termination analysis
    break;
  }
  case N_FOR: check_for(c, s); break;
  case N_RETURN: {
    if (c->inst->kind == FK_INIT && !c->parent) fatal(s->pos, "'return' outside of a function");
    if (s->a) {
      if (c->infer_ret && prune(c->ret)->kind == TY_VAR) {
        Type *t = check_expr(c, &s->a, NULL);
        if (s->a->flags & NF_LITERAL) { t = s->a->kind == N_FLOAT ? t_float : t_int; coerce(c, &s->a, t); }
        unify(c->ret, t);
      } else {
        Type *rt = prune(c->ret);
        if (rt->kind == TY_VOID) fatal(s->pos, "this function does not return a value");
        check_expr(c, &s->a, rt);
        coerce(c, &s->a, rt);
      }
    } else {
      Type *rt = prune(c->ret);
      if (rt->kind == TY_VAR) unify(rt, t_void);
      else if (rt->kind != TY_VOID) fatal(s->pos, "missing return value (function returns %s)", type_str(rt));
    }
    break;
  }
  case N_BREAK: case N_CONTINUE:
    if (!c->loop_depth) fatal(s->pos, "'%s' outside of a loop", s->kind == N_BREAK ? "break" : "continue");
    break;
  case N_DEFER: {
    if (s->a->kind == N_BLOCK) check_block(c, s->a, NULL, false);
    else check_stmt(c, &s->a);
    break;
  }
  case N_WHEN: {
    bool cond = const_eval_bool(c, s->a);
    Node *blk = cond ? s->b : s->c;
    if (!blk) { s->kind = N_BLOCK; s->list.len = 0; break; }
    // statements of the chosen branch are checked in the current scope (declarations stay visible)
    for (int i = 0; i < blk->list.len; i++) check_stmt(c, &blk->list.data[i]);
    s->kind = N_BLOCK; s->list = blk->list; s->aux = 5; // inline block (no new scope at codegen)
    break;
  }
  case N_BLOCK:
    check_block(c, s, NULL, false);
    break;
  case N_FN: case N_STRUCT: case N_ENUM: case N_IMPORT:
    fatal(s->pos, "declarations are only allowed at the top level");
  case N_TEST: case N_BUILD: break;
  default:
    fatal(s->pos, "invalid statement");
  }
}

static void check_fn_body(FnInst *f) {
  if (f->state != 0) return;
  f->state = 1;
  Node *decl = f->decl;
  FnCtx ctx = {0};
  ctx.inst = f;
  ctx.mod = f->mod;
  Scope *ps = decl ? decl->mod->scope : f->mod->scope;
  if (decl && decl->kind == N_FN) ps = type_param_scope(decl, f->targs, f->ntargs, ps);
  ctx.scope = scope_new(ps, 1, &ctx);
  if (decl && decl->kind == N_FN) {
    // implicit type params get no names
    f->params = arena_alloc(sizeof(Local *) * (f->np + 1));
    for (int i = 0; i < f->np; i++) {
      Node *p = decl->list.data[i];
      Local *l = new_local(&ctx, p->name, f->ptypes[i], p->pos);
      l->flags |= LF_PARAM;
      if (p->flags & NF_MUT) l->flags |= LF_MUTPARAM;
      f->params[i] = l;
    }
  }
  if (decl && (decl->flags & NF_EXTERN)) { f->state = 2; return; }
  if (f->ret) { ctx.ret = f->ret; }
  else { ctx.ret = mk_var(); ctx.infer_ret = true; }
  Node *body = f->body;
  if (f->kind == FK_INIT) {
    for (int i = 0; i < body->list.len; i++) check_stmt(&ctx, &body->list.data[i]);
    f->ret = t_void;
  } else {
    bool want = !ctx.infer_ret ? prune(ctx.ret)->kind != TY_VOID : true;
    Type *bt = check_block(&ctx, body, ctx.infer_ret ? NULL : ctx.ret, want);
    Type *r = prune(ctx.ret);
    if (ctx.infer_ret) {
      if (r->kind == TY_VAR) {
        if (body->aux) {
          if (body->list.data[body->list.len - 1]->a->flags & NF_LITERAL) {
            Node **vp = &body->list.data[body->list.len - 1]->a;
            bt = (*vp)->kind == N_FLOAT ? t_float : t_int;
            coerce(&ctx, vp, bt);
          }
          unify(r, bt);
        } else unify(r, t_void);
      } else if (r->kind == TY_VOID) {
        body->aux = 0;
      } else if (body->aux) {
        coerce(&ctx, &body->list.data[body->list.len - 1]->a, r);
      } else if (bt != t_never && !stmt_terminates(body->list.len ? body->list.data[body->list.len - 1] : NULL)) {
        fatal(decl ? decl->pos : body->pos, "function must return a value of type %s on all paths", type_str(r));
      }
      f->ret = zonk(ctx.ret);
      if (f->aux_void && prune(f->ret)->kind != TY_VOID) fatal(decl->pos, "recursive function '%.*s' returns a value; add an explicit return type (`-> Type`)", decl->name.len, decl->name.p);
    } else if (want) {
      if (body->aux) coerce(&ctx, &body->list.data[body->list.len - 1]->a, r);
      else if (bt != t_never && !(body->list.len && stmt_terminates(body->list.data[body->list.len - 1])))
        fatal(decl ? decl->pos : body->pos, "missing return value: function returns %s", type_str(r));
    }
  }
  zonk_tree(body);
  for (int i = 0; i < f->locals.len; i++) {
    f->locals.data[i]->type = zonk(f->locals.data[i]->type);
    if (prune(f->locals.data[i]->type)->has_var) fatal(f->locals.data[i]->pos, "cannot infer the type of '%.*s' (%s); add a type annotation", f->locals.data[i]->name.len, f->locals.data[i]->name.p, type_str(f->locals.data[i]->type));
  }
  f->state = 2;
}

// public for lambdas (expr.c)
void check_lambda_body(FnInst *f, FnCtx *parent, Node *lam, Type *ret_hint);
void check_lambda_body(FnInst *f, FnCtx *parent, Node *lam, Type *ret_hint) {
  f->state = 1;
  FnCtx ctx = {0};
  ctx.inst = f; ctx.parent = parent; ctx.mod = parent->mod;
  ctx.scope = scope_new(parent->scope, 1, &ctx);
  f->params = arena_alloc(sizeof(Local *) * (f->np + 1));
  for (int i = 0; i < f->np; i++) {
    Node *p = lam->list.data[i];
    Local *l = new_local(&ctx, p->name, f->ptypes[i], p->pos);
    l->flags |= LF_PARAM;
    if (p->flags & NF_MUT) l->flags |= LF_MUTPARAM;
    f->params[i] = l;
  }
  Type *declared = lam->a ? resolve_type(lam->a, parent->scope) : NULL;
  if (declared) { ctx.ret = declared; }
  else if (ret_hint && !prune(ret_hint)->has_var) { ctx.ret = ret_hint; }
  else { ctx.ret = ret_hint ? ret_hint : mk_var(); ctx.infer_ret = true; }
  Node *body = f->body;
  bool want = ctx.infer_ret || prune(ctx.ret)->kind != TY_VOID;
  Type *bt = check_block(&ctx, body, ctx.infer_ret ? NULL : ctx.ret, want);
  Type *r = prune(ctx.ret);
  if (ctx.infer_ret) {
    if (r->kind == TY_VAR) {
      if (body->aux) {
        Node **vp = &body->list.data[body->list.len - 1]->a;
        if ((*vp)->flags & NF_LITERAL) { bt = (*vp)->kind == N_FLOAT ? t_float : t_int; coerce(&ctx, vp, bt); }
        if (!unify(r, bt)) fatal(body->pos, "lambda returns %s, expected %s", type_str(bt), type_str(r));
      } else unify(r, bt == t_never ? t_void : t_void);
    } else if (r->kind == TY_VOID) body->aux = 0;
    else if (body->aux) coerce(&ctx, &body->list.data[body->list.len - 1]->a, r);
    else if (bt != t_never) fatal(body->pos, "lambda must return a value of type %s", type_str(r));
  } else if (want) {
    if (body->aux) coerce(&ctx, &body->list.data[body->list.len - 1]->a, r);
    else if (bt != t_never) fatal(body->pos, "lambda must return a value of type %s", type_str(r));
  } else body->aux = 0;
  f->ret = ctx.ret;
  f->state = 2;
}

void zonk_tree(Node *n) {
  if (!n) return;
  if (n->type) n->type = zonk(n->type);
  if (n->kind == N_LAMBDA) return; // lambda bodies are zonked separately
  zonk_tree(n->a); zonk_tree(n->b);
  if (n->kind != N_FOR) zonk_tree(n->c);
  if (n->kind != N_FOR && n->kind != N_PARTIAL) zonk_tree(n->d);
  for (int i = 0; i < n->list.len; i++) zonk_tree(n->list.data[i]);
  for (int i = 0; i < n->list2.len; i++) zonk_tree(n->list2.data[i]);
}

// ---------------- const evaluation (for `when`) ----------------
typedef struct { int kind; int64_t i; Str s; } CVal; // kind 0 int/bool, 1 str
static CVal ceval(FnCtx *c, Node *e) {
  switch (e->kind) {
  case N_BOOL: case N_INT: return (CVal){0, e->ival, {0}};
  case N_STR: return (CVal){1, 0, e->sval};
  case N_IDENT: {
    Sym *s = scope_lookup(c->scope, e->name);
    if (!s || s->kind != S_CONST) fatal(e->pos, "'%.*s' is not a compile-time constant", e->name.len, e->name.p);
    Global *g = s->p;
    if (g->init && !g->decl) return ceval(c, g->init);
    return ceval(c, g->decl->b);
  }
  case N_NOT: { CVal v = ceval(c, e->a); return (CVal){0, !v.i, {0}}; }
  case N_AND: { CVal a = ceval(c, e->a); if (!a.i) return a; return ceval(c, e->b); }
  case N_OR: { CVal a = ceval(c, e->a); if (a.i) return a; return ceval(c, e->b); }
  case N_BINARY: {
    CVal a = ceval(c, e->a), b = ceval(c, e->b);
    if (a.kind == 1 || b.kind == 1) {
      bool eq = a.kind == b.kind && str_eq(a.s, b.s);
      if (e->op == TK_EQ) return (CVal){0, eq, {0}};
      if (e->op == TK_NE) return (CVal){0, !eq, {0}};
      fatal(e->pos, "invalid operator on strings in compile-time expression");
    }
    switch (e->op) {
    case TK_EQ: return (CVal){0, a.i == b.i, {0}};
    case TK_NE: return (CVal){0, a.i != b.i, {0}};
    case TK_LT: return (CVal){0, a.i < b.i, {0}};
    case TK_LE: return (CVal){0, a.i <= b.i, {0}};
    case TK_GT: return (CVal){0, a.i > b.i, {0}};
    case TK_GE: return (CVal){0, a.i >= b.i, {0}};
    case TK_PLUS: return (CVal){0, a.i + b.i, {0}};
    case TK_MINUS: return (CVal){0, a.i - b.i, {0}};
    default: break;
    }
    break;
  }
  default: break;
  }
  fatal(e->pos, "expression is not a compile-time constant");
}
bool const_eval_bool(FnCtx *c, Node *e) { return ceval(c, e).i != 0; }

Node *get_build_option(const char *key) {
  if (!prog.build) return NULL;
  Node *b = prog.build->b;
  for (int i = 0; i < b->list.len; i++) {
    Node *s = b->list.data[i];
    if (s->kind == N_ASSIGN && s->a->kind == N_IDENT && str_eqc(s->a->name, key)) return s->b;
  }
  return NULL;
}

// ---------------- program ----------------
static const char *runtime_names[] = {
  "__alloc", "__free", "__panic", "__panic_bounds", "__panic_unwrap", "__free_obj", "__arr_clone", "__arr_push_slot",
  "__arr_reserve", "__arr_insert_slot", "__arr_remove_slot", "__arr_slice", "__arr_concat", "__str_concat", "__str_eq",
  "__str_cmp", "__str_slice", "__str_append", "__buf_finish", "__buf_append_str", "__arr_resize", "__arr_repeat",
  "__print_str", "__str_from_bytes", "__assert_fail", "__hash_bytes", "__str_hash", "__div_zero", NULL
};
static FnInst *runtime_insts[64];

FnInst *runtime_fn(const char *name) {
  for (int i = 0; runtime_names[i]; i++) if (strcmp(runtime_names[i], name) == 0) {
    if (!runtime_insts[i]) {
      Sym *s = scope_lookup_here(prelude_scope, internc(name));
      if (!s || s->kind != S_FNS) { fprintf(stderr, "sloppy0: missing runtime function %s\n", name); exit(1); }
      runtime_insts[i] = get_fn_inst(s->decl, NULL, 0, s->decl->pos);
    }
    return runtime_insts[i];
  }
  fprintf(stderr, "sloppy0: unknown runtime function %s\n", name);
  exit(1);
}

static void add_universe(void) {
  universe = scope_new(NULL, 0, NULL);
  struct { const char *n; Type *t; } tys[] = {
    {"int", t_int}, {"i8", t_i8}, {"i16", t_i16}, {"i32", t_i32}, {"i64", t_int}, {"u8", t_u8}, {"byte", t_u8},
    {"u16", t_u16}, {"u32", t_u32}, {"u64", t_u64}, {"float", t_float}, {"f64", t_float}, {"f32", t_f32},
    {"bool", t_bool}, {"str", t_str}, {"void", t_void},
  };
  for (size_t i = 0; i < sizeof tys / sizeof *tys; i++) scope_add(universe, internc(tys[i].n), S_TYPE, tys[i].t, NULL);
  // compile-time constants
  struct { const char *n; Node *v; } cs[4];
  Node *tv = new_node(N_STR, (Pos){0}); tv->sval = internc(g_target_wasm ? "wasm" : "linux");
  Node *dv = new_node(N_BOOL, (Pos){0}); dv->ival = 1;
  Node *bv = new_node(N_BOOL, (Pos){0}); bv->ival = 1;
  Node *wv = new_node(N_BOOL, (Pos){0}); wv->ival = 0;
  cs[0].n = "TARGET"; cs[0].v = tv; cs[1].n = "DEBUG"; cs[1].v = dv; cs[2].n = "BOOTSTRAP"; cs[2].v = bv;
  cs[3].n = "WATCH"; cs[3].v = wv;
  for (int i = 0; i < 4; i++) {
    Global *g = arena_alloc(sizeof(Global));
    g->name = internc(cs[i].n); g->is_const = true; g->init = cs[i].v; g->state = 2;
    g->type = cs[i].v->kind == N_STR ? t_str : t_bool;
    scope_add(universe, g->name, S_CONST, g, NULL);
  }
}

void register_intrinsics(Scope *s); // expr.c

static void load_prelude(void) {
  prelude_scope = scope_new(universe, 0, NULL);
  register_intrinsics(universe);
  char dirpath[1024];
  snprintf(dirpath, sizeof dirpath, "%s/core", g_lib_dir);
  DIR *d = opendir(dirpath);
  if (!d) { fprintf(stderr, "sloppy0: cannot open library directory %s\n", dirpath); exit(1); }
  struct dirent *e;
  char *names[256]; int n = 0;
  while ((e = readdir(d))) {
    int l = strlen(e->d_name);
    if (l > 3 && strcmp(e->d_name + l - 3, ".jo") == 0 && n < 256) names[n++] = strdup(e->d_name);
  }
  closedir(d);
  // deterministic order
  for (int i = 0; i < n; i++) for (int j = i + 1; j < n; j++) if (strcmp(names[i], names[j]) > 0) { char *t = names[i]; names[i] = names[j]; names[j] = t; }
  for (int i = 0; i < n; i++) {
    char p[2048]; snprintf(p, sizeof p, "%s/%s", dirpath, names[i]);
    load_module(p, true, (Pos){-1, 0, 0});
  }
}

typedef VEC(Module *) ModVec;
static int dfs_state[256];
static void order_modules(Module *m, ModVec *out) {
  if (dfs_state[m->order]) return;
  dfs_state[m->order] = 1;
  for (int i = 0; i < m->decls.len; i++) {
    Node *d = m->decls.data[i];
    if (d->kind == N_IMPORT) {
      Sym *s = scope_lookup_here(m->scope, d->name);
      if (s && s->kind == S_MODULE) order_modules(s->p, out);
      if (d->aux) for (int k = 0; k < m->scope->nuses; k++) {
        for (int j = 0; j < modules.len; j++) if (modules.data[j]->scope == m->scope->uses[k]) order_modules(modules.data[j], out);
      }
    }
  }
  vpush(*out, m);
}

void check_program(const char *main_path) {
  add_universe();
  load_prelude();
  int nprelude = modules.len;
  Module *mainm = load_module(main_path, false, (Pos){-1, 0, 0});
  mainm->is_main = true;
  // register declarations of all modules (imports load more modules as we go)
  for (int i = 0; i < modules.len; i++) {
    Module *m = modules.data[i];
    register_decls(m, &m->decls, &module_inits[m->order]);
  }
  // module init contexts
  FnInst *prelude_init = new_inst(FK_INIT, modules.data[0], "init_prelude");
  prelude_init->body = new_node(N_BLOCK, (Pos){0});
  prelude_init->ret = t_void;
  prelude_init->state = 2;
  for (int i = 0; i < modules.len; i++) {
    Module *m = modules.data[i];
    FnCtx *ctx = calloc(1, sizeof(FnCtx));
    if (m->is_prelude) ctx->inst = prelude_init;
    else {
      ctx->inst = new_inst(FK_INIT, m, fmt("init_%.*s", m->name.len, m->name.p));
      ctx->inst->body = new_node(N_BLOCK, (Pos){m->file, 1, 1});
      ctx->inst->body->list = module_inits[m->order];
    }
    ctx->scope = m->scope;
    ctx->mod = m;
    ctx->ret = t_void;
    module_ctx[m->order] = ctx;
  }
  // entry points
  ModVec order = {0};
  order_modules(mainm, &order);
  VEC(FnInst *) inits = {0};
  vpush(inits, prelude_init);
  for (int i = 0; i < order.len; i++) {
    FnInst *f = module_ctx[order.data[i]->order]->inst;
    vpush(inits, f);
  }
  for (int i = 1; i < inits.len; i++) vpush(prog.fns, inits.data[i]);
  Sym *ms;
  if ((ms = scope_lookup_here(mainm->scope, S("main"))) && ms->kind == S_FNS) prog.main_fn = get_fn_inst(ms->decl, NULL, 0, ms->decl->pos);
  if ((ms = scope_lookup_here(mainm->scope, S("update"))) && ms->kind == S_FNS) prog.update_fn = get_fn_inst(ms->decl, NULL, 0, ms->decl->pos);
  if ((ms = scope_lookup_here(mainm->scope, S("draw"))) && ms->kind == S_FNS) prog.draw_fn = get_fn_inst(ms->decl, NULL, 0, ms->decl->pos);
  for (int i = 0; runtime_names[i]; i++) runtime_fn(runtime_names[i]);
  // worklist
  for (int i = 0; i < prog.fns.len; i++) {
    FnInst *f = prog.fns.data[i];
    if (f->state == 0 && (f->kind == FK_NORMAL || f->kind == FK_INIT)) {
      FnCtx *saved_ctx = NULL; (void)saved_ctx;
      if (f->kind == FK_INIT) {
        // module init: use the persistent module context
        FnCtx *ctx = module_ctx[f->mod->order];
        f->state = 1;
        ctx->scope = f->mod->scope;
        Scope *body_scope = scope_new(f->mod->scope, 2, ctx);
        // top-level statements share the module scope for globals; locals go in body scope
        ctx->scope = body_scope;
        for (int k = 0; k < f->body->list.len; k++) check_stmt(ctx, &f->body->list.data[k]);
        ctx->scope = f->mod->scope;
        zonk_tree(f->body);
        for (int k = 0; k < f->locals.len; k++) f->locals.data[k]->type = zonk(f->locals.data[k]->type);
        f->ret = t_void;
        f->state = 2;
      } else check_fn_body(f);
    }
  }
  // prelude init: referenced prelude globals in declaration order
  for (int i = 0; i < prog.globals.len; i++) {
    Global *g = prog.globals.data[i];
    if (g->mod->is_prelude && g->state == 2) vpush(prelude_init->body->list, g->decl);
  }
  zonk_tree(prelude_init->body);
  // record init order for codegen
  prog.init_stmts.len = 0;
  for (int i = 0; i < inits.len; i++) {
    Node *ref = new_node(N_FNREF, (Pos){0});
    ref->sym = inits.data[i];
    vpush(prog.init_stmts, ref);
  }
  vpush(prog.fns, prelude_init);
  (void)nprelude;
}
