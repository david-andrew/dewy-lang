// internal header shared by check.c and expr.c
#include "sloppy0.h"

typedef struct FnCtx {
  FnInst *inst;
  struct FnCtx *parent;
  Scope *scope;
  Type *ret;
  bool infer_ret;
  int loop_depth;
  Module *mod;
} FnCtx;

typedef struct {
  int ntp;          // total type params (explicit + implicit)
  int nexplicit;
  Type **params;    // patterns (may contain TY_PARAM)
  Type *ret;        // NULL if inferred
  uint32_t mutmask;
  bool generic;
  bool done;
} FnSig;

typedef struct { VEC(FnInst *) insts; FnSig sig; } FnDeclInfo;

extern Type *t_never;
extern Scope *universe, *prelude_scope;
extern VEC(Module *) modules;

Scope *scope_new(Scope *parent, int kind, FnCtx *fn);
Sym *scope_add(Scope *s, Str name, int kind, void *p, Node *decl);
Sym *scope_lookup(Scope *s, Str name);
Sym *scope_lookup_here(Scope *s, Str name);

Type *resolve_type(Node *tn, Scope *sc);
StructInfo *get_struct_inst(Node *decl, Type **targs, int n);
Type *subst(Type *t, Type **targs);
FnSig *fn_sig(Node *decl);
FnDeclInfo *decl_info(Node *decl);
FnInst *get_fn_inst(Node *decl, Type **targs, int ntargs, Pos use);
void ensure_ret(FnInst *f, Pos use);
Local *new_local(FnCtx *c, Str name, Type *t, Pos pos);
Local *capture_local(FnCtx *c, Local *l);
void ensure_global(Global *g, Pos use);
Type *check_block(FnCtx *c, Node *b, Type *expected, bool want_value);
void check_stmt(FnCtx *c, Node **ps);
bool stmt_terminates(Node *s);
FnInst *new_inst(int kind, Module *mod, const char *base);
Module *module_of_type(Type *t);
void check_struct_fields(StructInfo *si);

Type *check_expr(FnCtx *c, Node **pn, Type *expected);
void coerce(FnCtx *c, Node **pn, Type *target);
Type *check_expr_to(FnCtx *c, Node **pn, Type *target);
bool can_coerce(Node *n, Type *from, Type *to);
Type *join_types(FnCtx *c, Node **a, Node **b, Pos pos);
FnInst *resolve_by_types(FnCtx *c, Str name, Type **types, int n, Pos pos, bool required);
FnInst *runtime_fn(const char *name);
void check_place(FnCtx *c, Node *n, bool for_mut);
Node *mk_ident_local(Local *l, Pos pos);
Sym *lookup_value(FnCtx *c, Str name);
bool const_eval_bool(FnCtx *c, Node *e);
void zonk_tree(Node *n);
Node *get_build_option(const char *key);
