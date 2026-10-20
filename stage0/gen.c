// x86-64 code generator for sloppy0: emits GNU assembler (Intel syntax).
// Calling convention (internal): arguments are pushed left to right (hidden sret pointer
// first, then closure env, then user args), callee reads arg k of n at [rbp+16+8*(n-1-k)].
// Scalars return in rax/xmm0; aggregates are written through the sret pointer.
// All registers except rbp/rsp are caller-saved.
#include "check.h"
#include <math.h>

// ---------------- output buffers ----------------
typedef struct { char *p; int len, cap; } Buf;
static Buf *bufstack[256];
static int nbuf;
static FILE *OUT;

static void bput(Buf *b, const char *s, int n) {
  if (b->len + n + 1 > b->cap) { b->cap = (b->len + n + 1) * 2 + 256; b->p = realloc(b->p, b->cap); }
  memcpy(b->p + b->len, s, n);
  b->len += n;
}
static void E(const char *f, ...) {
  char tmp[4096];
  va_list ap; va_start(ap, f);
  int n = vsnprintf(tmp, sizeof tmp, f, ap);
  va_end(ap);
  Buf *b = bufstack[nbuf - 1];
  bput(b, "  ", 2);
  bput(b, tmp, n);
  bput(b, "\n", 1);
}
static void L(const char *f, ...) { // label / raw line
  char tmp[4096];
  va_list ap; va_start(ap, f);
  int n = vsnprintf(tmp, sizeof tmp, f, ap);
  va_end(ap);
  Buf *b = bufstack[nbuf - 1];
  bput(b, tmp, n);
  bput(b, "\n", 1);
}
static Buf *push_buf(void) { Buf *b = calloc(1, sizeof(Buf)); bufstack[nbuf++] = b; return b; }
static Buf *pop_buf(void) { return bufstack[--nbuf]; }
static void append_buf(Buf *b) { if (b->len) bput(bufstack[nbuf - 1], b->p, b->len); free(b->p); free(b); }

static int label_n;
static int newlabel(void) { return ++label_n; }

// ---------------- data ----------------
static Buf rodata, databuf;
typedef struct { Str s; int id; } StrLit;
static VEC(StrLit) strlits;

static void rd(Buf *b, const char *f, ...) {
  char tmp[4096];
  va_list ap; va_start(ap, f);
  int n = vsnprintf(tmp, sizeof tmp, f, ap);
  va_end(ap);
  bput(b, tmp, n);
  bput(b, "\n", 1);
}

static void emit_bytes(Buf *b, const char *p, int n) {
  for (int i = 0; i < n; i += 32) {
    char line[256]; int k = 0;
    k += sprintf(line + k, "  .byte ");
    for (int j = i; j < n && j < i + 32; j++) k += sprintf(line + k, "%s%u", j > i ? "," : "", (unsigned char)p[j]);
    bput(b, line, k); bput(b, "\n", 1);
  }
}

static int str_label(Str s) {
  for (int i = 0; i < strlits.len; i++) if (strlits.data[i].s.len == s.len && memcmp(strlits.data[i].s.p, s.p, s.len) == 0) return strlits.data[i].id;
  int id = newlabel();
  StrLit sl = {s, id};
  vpush(strlits, sl);
  rd(&rodata, "  .balign 8\n.Ls%d:\n  .quad -1, %d, %d", id, s.len, s.len + 1);
  emit_bytes(&rodata, s.p, s.len);
  rd(&rodata, "  .byte 0");
  return id;
}
static int loc_label(Pos p) {
  const char *path = p.file >= 0 && p.file < g_files.len ? g_files.data[p.file].path : "?";
  const char *base = strrchr(path, '/'); base = base ? base + 1 : path;
  char *s = fmt("%s:%d", base, p.line);
  return str_label((Str){s, (int)strlen(s)});
}
static int f64_label(double d) {
  int id = newlabel();
  uint64_t bits; memcpy(&bits, &d, 8);
  rd(&rodata, "  .balign 8\n.Lf%d: .quad %llu", id, (unsigned long long)bits);
  return id;
}
static int f32_label(float f) {
  int id = newlabel();
  uint32_t bits; memcpy(&bits, &f, 4);
  rd(&rodata, "  .balign 4\n.Lf%d: .long %u", id, bits);
  return id;
}

// ---------------- types ----------------
enum { VC_VOID, VC_INT, VC_FLT, VC_AGG };
static int vclass(Type *t) {
  t = prune(t);
  if (t->kind == TY_VOID) return VC_VOID;
  if (t->kind == TY_FLOAT) return VC_FLT;
  if (t->kind == TY_TYPE || t->kind == TY_MODULE) return VC_VOID;
  return is_aggregate(t) ? VC_AGG : VC_INT;
}
static int tsize(Type *t) { t = prune(t); layout(t); return t->size; }
static int talign(Type *t) { t = prune(t); layout(t); return t->align ? t->align : 1; }
static bool is_f32(Type *t) { t = prune(t); return t->kind == TY_FLOAT && t->bits == 32; }

static const char *fn_sym(FnInst *f) { return f->sym.p; }

// ---------------- helper functions (per type) ----------------
enum { H_DROP, H_COPY, H_ARRREL, H_ARRUNIQ, H_EQ, H_HASH, H_THUNK, H_ENVDROP, H_RELPLAIN };
typedef struct { int kind; Type *t; void *p; char *sym; } Helper;
static VEC(Helper) helpers;
static int helpers_done;

static const char *helper(int kind, Type *t, void *p) {
  t = t ? prune(t) : NULL;
  for (int i = 0; i < helpers.len; i++) if (helpers.data[i].kind == kind && helpers.data[i].p == p && (helpers.data[i].t == t || (t && helpers.data[i].t && type_eq(helpers.data[i].t, t)))) return helpers.data[i].sym;
  static const char *names[] = {"drop", "copy", "arrrel", "arruniq", "eq", "hash", "thunk", "envdrop", "relplain"};
  Helper h = {kind, t, p, fmt("h_%s_%d", names[kind], helpers.len)};
  vpush(helpers, h);
  return h.sym;
}

// ---------------- function state ----------------
typedef struct GScope {
  VEC(Local *) locals;
  VEC(Node *) defers;
} GScope;
typedef struct { int brk, cont, depth; } Loop;
typedef struct { int off; Type *t; } Temp;
typedef struct { VEC(Temp) temps; } TempList;

static FnInst *curfn;
static int frame;
static GScope scopes[256]; static int nscopes;
static Loop loops[64]; static int nloops;
static TempList tlists[256]; static int ntlists;
static int env_off_slot;   // rbp offset of env pointer (args)
static int sret_off_slot;  // rbp offset of sret pointer
static int ret_label;
static int ret_slot;       // slot for scalar return values
static int pushdepth;

typedef struct { bool owned; int slot; } Val; // slot: temp offset of owned aggregate (0 if none)
static Val V(bool owned) { return (Val){owned, 0}; }

static int alloc_slot(int size, int align) {
  if (align < 8) align = 8;
  if (size <= 0) size = 8;
  frame = (frame + size + align - 1) & ~(align - 1);
  return -frame;
}

static Val gen_expr(Node *e);
static void gen_addr(Node *e, bool write);
static void gen_stmt(Node *s);
static void gen_block_stmts(Node *b);

static void push_rax(void) { E("push rax"); pushdepth++; }
static void pop_reg(const char *r) { E("pop %s", r); pushdepth--; }
static void push_val(int vc) { if (vc == VC_FLT) E("movq rax, xmm0"); push_rax(); }

// load value of type t from address in rax
static void load_rax(Type *t) {
  t = prune(t);
  switch (vclass(t)) {
  case VC_FLT: if (is_f32(t)) E("movss xmm0, dword ptr [rax]"); else E("movsd xmm0, qword ptr [rax]"); return;
  case VC_AGG: case VC_VOID: return;
  }
  int sz = tsize(t);
  bool sign = t->kind == TY_INT ? t->sign : false;
  switch (sz) {
  case 1: E(sign ? "movsx rax, byte ptr [rax]" : "movzx eax, byte ptr [rax]"); break;
  case 2: E(sign ? "movsx rax, word ptr [rax]" : "movzx eax, word ptr [rax]"); break;
  case 4: E(sign ? "movsxd rax, dword ptr [rax]" : "mov eax, dword ptr [rax]"); break;
  default: E("mov rax, qword ptr [rax]"); break;
  }
}

static void copy_bytes(int size) { // copy size bytes from [rax] to [rdi]; clobbers rcx, rsi
  if (size <= 64 && size % 8 == 0) {
    for (int i = 0; i < size; i += 8) { E("mov rcx, qword ptr [rax+%d]", i); E("mov qword ptr [rdi+%d], rcx", i); }
    return;
  }
  int i = 0;
  if (size <= 64) {
    for (; i + 8 <= size; i += 8) { E("mov rcx, qword ptr [rax+%d]", i); E("mov qword ptr [rdi+%d], rcx", i); }
    for (; i + 4 <= size; i += 4) { E("mov ecx, dword ptr [rax+%d]", i); E("mov dword ptr [rdi+%d], ecx", i); }
    for (; i < size; i++) { E("mov cl, byte ptr [rax+%d]", i); E("mov byte ptr [rdi+%d], cl", i); }
    return;
  }
  E("mov rsi, rax"); E("mov rcx, %d", size); E("rep movsb");
}

// store rax/xmm0 (or aggregate at [rax]) into [rdi]
static void store_rdi(Type *t) {
  t = prune(t);
  switch (vclass(t)) {
  case VC_FLT: if (is_f32(t)) E("movss dword ptr [rdi], xmm0"); else E("movsd qword ptr [rdi], xmm0"); return;
  case VC_AGG: copy_bytes(tsize(t)); return;
  case VC_VOID: return;
  }
  switch (tsize(t)) {
  case 1: E("mov byte ptr [rdi], al"); break;
  case 2: E("mov word ptr [rdi], ax"); break;
  case 4: E("mov dword ptr [rdi], eax"); break;
  default: E("mov qword ptr [rdi], rax"); break;
  }
}

static void zero_slot(int off, int size) {
  size = (size + 7) & ~7;
  if (size <= 64) { for (int i = 0; i < size; i += 8) E("mov qword ptr [rbp%+d], 0", off + i); return; }
  E("lea rdi, [rbp%+d]", off); E("mov rcx, %d", size / 8); E("xor eax, eax"); E("rep stosq");
}

static void norm(Type *t) {
  t = prune(t);
  if (t->kind == TY_BOOL) { E("movzx eax, al"); return; }
  if (t->kind != TY_INT && t->kind != TY_ENUM) return;
  int sz = tsize(t);
  bool s = t->kind == TY_INT && t->sign;
  if (sz == 1) E(s ? "movsx rax, al" : "movzx eax, al");
  else if (sz == 2) E(s ? "movsx rax, ax" : "movzx eax, ax");
  else if (sz == 4) E(s ? "movsxd rax, eax" : "mov eax, eax");
}

// ---- refcounting ----
static void retain_rax(void) {
  E("test rax, rax"); E("jz 1f"); E("cmp qword ptr [rax], 0"); E("jle 1f"); E("inc qword ptr [rax]"); L("1:");
}
// release managed scalar value (str/array) in rax
static void release_scalar(Type *t) {
  t = prune(t);
  if (t->kind == TY_ARRAY && is_managed(t->elem)) { push_rax(); E("call %s", helper(H_ARRREL, t, NULL)); E("add rsp, 8"); pushdepth--; return; }
  push_rax(); E("call %s", helper(H_RELPLAIN, NULL, NULL)); E("add rsp, 8"); pushdepth--;
}
// drop the value stored at address rax
static void drop_at_rax(Type *t) {
  t = prune(t);
  if (!is_managed(t)) return;
  if (vclass(t) == VC_INT) { E("mov rax, qword ptr [rax]"); release_scalar(t); return; }
  push_rax(); E("call %s", helper(H_DROP, t, NULL)); E("add rsp, 8"); pushdepth--;
}
// retain the managed parts of the aggregate at address rax (preserves rax)
static void copy_at_rax(Type *t) {
  t = prune(t);
  if (!is_managed(t)) return;
  push_rax(); E("call %s", helper(H_COPY, t, NULL)); pop_reg("rax");
}

// ---- temps ----
static int new_temp(Type *t) { return alloc_slot(tsize(t), talign(t)); }
static void reg_temp(int off, Type *t) {
  if (!is_managed(t)) return;
  if (!ntlists) return;
  Temp tp = {off, t};
  vpush(tlists[ntlists - 1].temps, tp);
}
// make the value owned by the current statement (released at its end); value stays in rax/xmm0
static void borrow(Val v, Type *t) {
  if (!v.owned || !is_managed(t)) return;
  if (vclass(t) == VC_AGG) {
    if (!v.slot) { fprintf(stderr, "sloppy0: internal: owned aggregate without slot\n"); exit(1); }
    reg_temp(v.slot, t);
  } else {
    int off = new_temp(t);
    E("mov qword ptr [rbp%+d], rax", off);
    reg_temp(off, t);
  }
}
// produce an owned copy of the value (aggregates: rax = temp slot address)
static Val own(Val v, Type *t) {
  if (v.owned) return v;
  if (!is_managed(t)) {
    if (vclass(t) == VC_AGG) {
      int off = new_temp(t);
      E("lea rdi, [rbp%+d]", off);
      copy_bytes(tsize(t));
      E("lea rax, [rbp%+d]", off);
      return (Val){true, off};
    }
    return V(true);
  }
  if (vclass(t) == VC_AGG) {
    int off = new_temp(t);
    E("lea rdi, [rbp%+d]", off);
    copy_bytes(tsize(t));
    E("lea rax, [rbp%+d]", off);
    copy_at_rax(t);
    return (Val){true, off};
  }
  retain_rax();
  return V(true);
}
static Val gen_owned(Node *e) { Val v = gen_expr(e); return own(v, e->type); }
static Val gen_borrowed(Node *e) { Val v = gen_expr(e); borrow(v, e->type); v.owned = false; return v; }

static void stmt_begin(void) { push_buf(); tlists[ntlists++].temps.len = 0; }
static void stmt_end(void) {
  Buf *b = pop_buf();
  TempList *tl = &tlists[--ntlists];
  for (int i = 0; i < tl->temps.len; i++) zero_slot(tl->temps.data[i].off, tsize(tl->temps.data[i].t));
  append_buf(b);
  for (int i = tl->temps.len - 1; i >= 0; i--) {
    E("lea rax, [rbp%+d]", tl->temps.data[i].off);
    drop_at_rax(tl->temps.data[i].t);
  }
  tl->temps.len = 0;
}

// ---- locals ----
static bool param_indirect(Local *l) { return (l->flags & LF_MUTPARAM) || (vclass(l->type) == VC_AGG); }

static void local_addr(Local *l, bool write) {
  if (l->flags & LF_ALIAS) { gen_addr(l->alias, write); return; }
  if (l->flags & LF_CAPTURE) { E("mov rax, qword ptr [rbp%+d]", env_off_slot); E("add rax, %d", l->env_off); return; }
  if (l->flags & LF_PARAM) {
    if (param_indirect(l)) E("mov rax, qword ptr [rbp%+d]", l->offset);
    else E("lea rax, [rbp%+d]", l->offset);
    return;
  }
  if (l->flags & LF_BYREF) { E("mov rax, qword ptr [rbp%+d]", l->offset); return; }
  E("lea rax, [rbp%+d]", l->offset);
}

static void scope_push(void) { GScope *s = &scopes[nscopes++]; s->locals.len = 0; s->defers.len = 0; }
static void scope_add_local(Local *l) {
  if (!nscopes) return;
  if (!is_managed(l->type) || (l->flags & (LF_PARAM | LF_CAPTURE | LF_ALIAS | LF_BYREF))) return;
  vpush(scopes[nscopes - 1].locals, l);
}
// emit releases for scope i (defers first, reverse order)
static void emit_scope_exit(int i) {
  GScope *s = &scopes[i];
  for (int k = s->defers.len - 1; k >= 0; k--) {
    Node *d = s->defers.data[k];
    // defers run in a fresh scope context
    int saved_n = s->defers.len;
    s->defers.len = k; // prevent recursion into itself
    if (d->kind == N_BLOCK) { scope_push(); gen_block_stmts(d); emit_scope_exit(nscopes - 1); nscopes--; }
    else gen_stmt(d);
    s->defers.len = saved_n;
  }
  for (int k = s->locals.len - 1; k >= 0; k--) {
    Local *l = s->locals.data[k];
    E("lea rax, [rbp%+d]", l->offset);
    drop_at_rax(l->type);
    zero_slot(l->offset, tsize(l->type));
  }
}
static void scope_pop(void) { emit_scope_exit(nscopes - 1); nscopes--; }

// ---------------- addresses ----------------
static void bounds_check(Pos pos) {
  // rax = array object (may be null), rcx = index; leaves rax intact
  E("xor edx, edx"); E("test rax, rax"); E("jz 2f"); E("mov rdx, qword ptr [rax+8]"); L("2:");
  E("cmp rcx, rdx"); E("jb 1f");
  E("push rcx"); E("push rdx"); E("lea rax, [rip+.Ls%d]", loc_label(pos)); E("push rax");
  E("call %s", fn_sym(runtime_fn("__panic_bounds")));
  L("1:");
}

static void arr_unique(Type *at) {
  // rax = address of array slot
  push_rax(); E("call %s", helper(H_ARRUNIQ, at, NULL)); pop_reg("rax");
}

static void gen_addr(Node *e, bool write) {
  switch (e->kind) {
  case N_IDENT:
    if (e->aux == S_LOCAL) { local_addr(e->sym, write); return; }
    if (e->aux == S_GLOBAL) { E("lea rax, [rip+%s]", ((Global *)e->sym)->sym.p); return; }
    break;
  case N_FIELD: {
    Type *bt = prune(e->a->type);
    if (e->aux == -3) { // enum payload field (match binding)
      gen_addr(e->a, write);
      StructInfo *si = bt->st; layout(bt);
      E("add rax, %d", si->variants[e->aux2].fields[e->ival].offset);
      return;
    }
    if (bt->kind == TY_PTR) { Val v = gen_expr(e->a); (void)v; bt = prune(bt->elem); }
    else gen_addr(e->a, write);
    layout(bt);
    int off;
    if (bt->kind == TY_TUPLE) {
      off = 0;
      for (int i = 0; i <= e->ival; i++) { Type *el = prune(bt->args[i]); layout(el); off = (off + talign(el) - 1) & ~(talign(el) - 1); if (i < e->ival) off += el->size; }
    } else off = bt->st->fields[e->aux].offset;
    if (off) E("add rax, %d", off);
    return;
  }
  case N_INDEX: {
    Type *bt = prune(e->a->type);
    if (bt->kind == TY_PTR) {
      gen_expr(e->a); push_rax();
      gen_expr(e->b); E("mov rcx, rax"); pop_reg("rax");
      int sz = tsize(bt->elem);
      E("imul rcx, rcx, %d", sz); E("add rax, rcx");
      return;
    }
    if (bt->kind == TY_ARRAY) {
      if (write) {
        gen_addr(e->a, true);
        arr_unique(bt);
        push_rax();
        gen_expr(e->b); E("mov rcx, rax");
        pop_reg("rax");
        E("mov rax, qword ptr [rax]");
      } else {
        Val v = gen_borrowed(e->a); (void)v;
        push_rax();
        gen_expr(e->b); E("mov rcx, rax");
        pop_reg("rax");
      }
      bounds_check(e->pos);
      int sz = tsize(bt->elem);
      if (sz == 1 || sz == 2 || sz == 4 || sz == 8) E("lea rax, [rax+rcx*%d+24]", sz);
      else { E("imul rcx, rcx, %d", sz); E("lea rax, [rax+rcx+24]"); }
      return;
    }
    if (bt->kind == TY_STR) {
      gen_borrowed(e->a); push_rax();
      gen_expr(e->b); E("mov rcx, rax"); pop_reg("rax");
      bounds_check(e->pos);
      E("lea rax, [rax+rcx+24]");
      return;
    }
    break;
  }
  case N_UNWRAP: {
    Type *ot = prune(e->a->type);
    gen_addr(e->a, write);
    int inner = tsize(ot->elem);
    E("cmp byte ptr [rax+%d], 0", inner); E("jnz 1f");
    E("lea rax, [rip+.Ls%d]", loc_label(e->pos)); E("push rax"); E("call %s", fn_sym(runtime_fn("__panic_unwrap")));
    L("1:");
    return;
  }
  default: break;
  }
  // not a place: evaluate into a temporary
  Val v = gen_expr(e);
  if (vclass(e->type) == VC_AGG) { borrow(v, e->type); return; }
  int off = new_temp(e->type);
  if (vclass(e->type) == VC_FLT) { E("lea rdi, [rbp%+d]", off); store_rdi(e->type); }
  else E("mov qword ptr [rbp%+d], rax", off);
  if (v.owned) reg_temp(off, e->type);
  E("lea rax, [rbp%+d]", off);
}

// ---------------- calls ----------------
static int retslot_for(Type *t) { return vclass(t) == VC_AGG ? new_temp(t) : 0; }

// push arguments for FnInst-style params. mutmask: which params are mut.
static int push_args(Node **args, int n, Type **ptypes, uint32_t mutmask) {
  bool any_mut = mutmask != 0;
  for (int i = 0; i < n; i++) {
    Node *a = args[i];
    if (mutmask & (1u << i)) { gen_addr(a, true); push_rax(); continue; }
    Type *pt = ptypes ? ptypes[i] : a->type;
    Val v = gen_expr(a);
    if (any_mut && !v.owned && is_managed(pt)) v = own(v, pt);
    borrow(v, pt);
    push_val(vclass(pt));
  }
  return n;
}

static Val finish_call(Type *ret, int rslot) {
  int vc = vclass(ret);
  if (vc == VC_AGG) { E("lea rax, [rbp%+d]", rslot); return (Val){true, rslot}; }
  if (vc == VC_INT) norm(ret);
  return V(true);
}

static Val gen_direct_call(FnInst *f, Node **args, int n) {
  Type *ret = f->ret;
  int rslot = retslot_for(ret);
  int pushes = 0;
  if (rslot) { E("lea rax, [rbp%+d]", rslot); push_rax(); pushes++; }
  uint32_t mm = 0;
  if (f->decl && f->decl->kind == N_FN) for (int i = 0; i < f->np; i++) if (f->decl->list.data[i]->flags & NF_MUT) mm |= 1u << i;
  pushes += push_args(args, n, f->ptypes, mm);
  E("call %s", fn_sym(f));
  if (pushes) { E("add rsp, %d", pushes * 8); pushdepth -= pushes; }
  return finish_call(ret, rslot);
}

static Val gen_closure_call(Node *callee, Node **args, int n) {
  Type *ft = prune(callee->type);
  Type *ret = ft->elem;
  Val cv = gen_borrowed(callee);
  (void)cv;
  int fslot = alloc_slot(16, 8);
  E("mov rcx, qword ptr [rax]"); E("mov qword ptr [rbp%+d], rcx", fslot);
  E("mov rcx, qword ptr [rax+8]"); E("mov qword ptr [rbp%+d], rcx", fslot + 8);
  int rslot = retslot_for(ret);
  int pushes = 0;
  if (rslot) { E("lea rax, [rbp%+d]", rslot); push_rax(); pushes++; }
  E("mov rax, qword ptr [rbp%+d]", fslot + 8); push_rax(); pushes++;
  pushes += push_args(args, n, ft->args, ft->mutmask);
  E("mov rax, qword ptr [rbp%+d]", fslot);
  E("call rax");
  E("add rsp, %d", pushes * 8); pushdepth -= pushes;
  return finish_call(ret, rslot);
}

// call a runtime function with already-computed values pushed by caller
static void call_rt(const char *name, int nargs) {
  E("call %s", fn_sym(runtime_fn(name)));
  if (nargs) { E("add rsp, %d", nargs * 8); pushdepth -= nargs; }
}

// ---------------- closures ----------------
static void env_layout(FnInst *f) {
  if (f->env_size) return;
  int off = 16;
  for (int i = 0; i < f->caps.len; i++) {
    Local *in = f->caps.data[i].inner;
    int al = talign(in->type); if (al < 8) al = 8;
    off = (off + al - 1) & ~(al - 1);
    in->env_off = off;
    off += tsize(in->type);
  }
  f->env_size = (off + 7) & ~7;
}

static Val gen_lambda(Node *e) {
  FnInst *f = e->sym;
  env_layout(f);
  int slot = alloc_slot(16, 8);
  E("lea rax, [rip+%s]", fn_sym(f)); E("mov qword ptr [rbp%+d], rax", slot);
  E("mov qword ptr [rbp%+d], 0", slot + 8);
  if (f->caps.len) {
    E("push %d", f->env_size); pushdepth++;
    call_rt("__alloc", 1);
    E("mov qword ptr [rbp%+d], rax", slot + 8);
    E("mov qword ptr [rax], 1");
    E("lea rcx, [rip+%s]", helper(H_ENVDROP, NULL, f)); E("mov qword ptr [rax+8], rcx");
    for (int i = 0; i < f->caps.len; i++) {
      Local *outer = f->caps.data[i].outer, *in = f->caps.data[i].inner;
      Node *id = mk_ident_local(outer, e->pos);
      Val v = gen_expr(id);
      v = own(v, outer->type);
      E("mov rdi, qword ptr [rbp%+d]", slot + 8);
      E("add rdi, %d", in->env_off);
      store_rdi(outer->type);
    }
  }
  E("lea rax, [rbp%+d]", slot);
  return (Val){true, slot};
}

static Val gen_fnref(Node *e) {
  FnInst *f = e->sym;
  int slot = alloc_slot(16, 8);
  E("lea rax, [rip+%s]", helper(H_THUNK, NULL, f)); E("mov qword ptr [rbp%+d], rax", slot);
  E("mov qword ptr [rbp%+d], 0", slot + 8);
  E("lea rax, [rbp%+d]", slot);
  return (Val){true, slot};
}

// partial application: env = [hdr][callee closure if value call][args...]
static int partial_layout(Node *e, int *offs) {
  int off = 16;
  if (e->aux == 1) off += 16;
  for (int i = 0; i < e->list.len; i++) {
    Node *a = e->list.data[i];
    if (a->kind == N_HOLE) { offs[i] = -1; continue; }
    int al = talign(a->type); if (al < 8) al = 8;
    off = (off + al - 1) & ~(al - 1);
    offs[i] = off;
    off += tsize(a->type);
  }
  return (off + 7) & ~7;
}

static Val gen_partial(Node *e) {
  FnInst *th = (FnInst *)e->d;
  int offs[64];
  int size = partial_layout(e, offs);
  th->env_size = size;
  int slot = alloc_slot(16, 8);
  E("lea rax, [rip+%s]", fn_sym(th)); E("mov qword ptr [rbp%+d], rax", slot);
  E("push %d", size); pushdepth++;
  call_rt("__alloc", 1);
  E("mov qword ptr [rbp%+d], rax", slot + 8);
  E("mov qword ptr [rax], 1");
  E("lea rcx, [rip+%s]", helper(H_ENVDROP, NULL, th)); E("mov qword ptr [rax+8], rcx");
  if (e->aux == 1) {
    Val v = gen_owned(e->a); (void)v;
    E("mov rdi, qword ptr [rbp%+d]", slot + 8); E("add rdi, 16");
    store_rdi(e->a->type);
  }
  FnInst *target = e->sym;
  for (int i = 0; i < e->list.len; i++) {
    Node *a = e->list.data[i];
    if (a->kind == N_HOLE) continue;
    if (target && target->decl && (target->decl->list.data[i]->flags & NF_MUT)) fatal(a->pos, "cannot partially apply a `mut` argument; use `_` for it");
    if (!target && (prune(e->a->type)->mutmask & (1u << i))) fatal(a->pos, "cannot partially apply a `mut` argument; use `_` for it");
    gen_owned(a);
    E("mov rdi, qword ptr [rbp%+d]", slot + 8); E("add rdi, %d", offs[i]);
    store_rdi(a->type);
  }
  E("lea rax, [rbp%+d]", slot);
  return (Val){true, slot};
}

// ---------------- intrinsics ----------------
static Val gen_intrinsic(Node *e) {
  Node **a = e->list.data;
  switch (e->aux) {
  case IN_LEN: case IN_ARRCAP:
    gen_borrowed(a[0]);
    E("test rax, rax"); E("jz 1f"); E("mov rax, qword ptr [rax+%d]", e->aux == IN_LEN ? 8 : 16); L("1:");
    return V(false);
  case IN_PUSH: {
    Type *at = prune(a[0]->type);
    Val v = gen_owned(a[1]);
    (void)v;
    int vslot = 0;
    if (vclass(at->elem) == VC_AGG) { vslot = 1; push_rax(); }
    else push_val(vclass(at->elem));
    gen_addr(a[0], true);
    arr_unique(at);
    push_rax(); E("push %d", tsize(at->elem)); pushdepth++;
    call_rt("__arr_push_slot", 2);
    E("mov rdi, rax");
    pop_reg("rax");
    if (vclass(at->elem) == VC_FLT) E("movq xmm0, rax");
    store_rdi(at->elem);
    (void)vslot;
    return V(false);
  }
  case IN_POP: {
    Type *at = prune(a[0]->type);
    Type *et = at->elem;
    gen_addr(a[0], true);
    arr_unique(at);
    E("mov rcx, qword ptr [rax]");
    E("test rcx, rcx"); E("jz 3f"); E("cmp qword ptr [rcx+8], 0"); E("jnz 4f");
    L("3:"); E("lea rax, [rip+.Ls%d]", str_label(S("pop() from an empty array"))); E("push rax"); E("call %s", fn_sym(runtime_fn("__panic")));
    L("4:");
    E("mov rdx, qword ptr [rcx+8]"); E("dec rdx"); E("mov qword ptr [rcx+8], rdx");
    int sz = tsize(et);
    E("imul rdx, rdx, %d", sz); E("lea rax, [rcx+rdx+24]");
    // move element out
    if (vclass(et) == VC_AGG) {
      int off = new_temp(et);
      E("lea rdi, [rbp%+d]", off); E("push rax"); pushdepth++;
      copy_bytes(sz);
      pop_reg("rdi"); E("xor eax, eax"); E("mov rcx, %d", sz); E("rep stosb");
      E("lea rax, [rbp%+d]", off);
      return (Val){true, off};
    }
    E("mov rdi, rax");
    load_rax(et);
    if (sz == 8) E("mov qword ptr [rdi], 0"); else if (sz == 4) E("mov dword ptr [rdi], 0"); else if (sz == 2) E("mov word ptr [rdi], 0"); else E("mov byte ptr [rdi], 0");
    return V(true);
  }
  case IN_INSERT: {
    Type *at = prune(a[0]->type);
    Val v = gen_owned(a[2]); (void)v;
    push_val(vclass(at->elem));
    gen_expr(a[1]); push_rax();
    gen_addr(a[0], true);
    arr_unique(at);
    pop_reg("rcx");
    push_rax(); E("push %d", tsize(at->elem)); pushdepth++; E("push rcx"); pushdepth++;
    call_rt("__arr_insert_slot", 3);
    E("mov rdi, rax");
    pop_reg("rax");
    if (vclass(at->elem) == VC_FLT) E("movq xmm0, rax");
    store_rdi(at->elem);
    return V(false);
  }
  case IN_REMOVE: {
    Type *at = prune(a[0]->type);
    Type *et = at->elem;
    int sz = tsize(et);
    gen_expr(a[1]); push_rax();
    gen_addr(a[0], true);
    arr_unique(at);
    int sl = new_temp(t_int);
    E("mov qword ptr [rbp%+d], rax", sl);
    E("mov rax, qword ptr [rax]");
    pop_reg("rcx");
    E("push rcx"); pushdepth++;
    bounds_check(e->pos);
    pop_reg("rcx");
    E("imul rdx, rcx, %d", sz); E("lea rax, [rax+rdx+24]");
    int off = new_temp(et);
    E("push rcx"); pushdepth++;
    E("lea rdi, [rbp%+d]", off);
    copy_bytes(sz);
    pop_reg("rcx");
    E("push qword ptr [rbp%+d]", sl); pushdepth++; E("push %d", sz); pushdepth++; E("push rcx"); pushdepth++;
    call_rt("__arr_remove_slot", 3);
    E("lea rax, [rbp%+d]", off);
    if (vclass(et) == VC_AGG) return (Val){true, off};
    load_rax(et);
    return V(true);
  }
  case IN_CLEAR: {
    Type *at = prune(a[0]->type);
    gen_addr(a[0], true);
    E("push rax"); pushdepth++;
    E("mov rax, qword ptr [rax]");
    release_scalar(at);
    pop_reg("rax");
    E("mov qword ptr [rax], 0");
    return V(false);
  }
  case IN_RESERVE: {
    Type *at = prune(a[0]->type);
    gen_expr(a[1]); push_rax();
    gen_addr(a[0], true);
    arr_unique(at);
    pop_reg("rcx");
    push_rax(); E("push %d", tsize(at->elem)); pushdepth++; E("push rcx"); pushdepth++;
    call_rt("__arr_reserve", 3);
    return V(false);
  }
  case IN_RESIZE: case IN_TRUNCATE: case IN_SETLEN: {
    Type *at = prune(a[0]->type);
    gen_expr(a[1]); push_rax();
    gen_addr(a[0], true);
    arr_unique(at);
    pop_reg("rcx");
    if (e->aux == IN_SETLEN) {
      E("mov rax, qword ptr [rax]"); E("mov qword ptr [rax+8], rcx");
      return V(false);
    }
    if (is_managed(at->elem)) {
      // drop elements beyond the new length
      int sl = new_temp(t_int), nl = new_temp(t_int);
      E("mov qword ptr [rbp%+d], rax", sl); E("mov qword ptr [rbp%+d], rcx", nl);
      int lp = newlabel(), done = newlabel();
      L(".L%d:", lp);
      E("mov rax, qword ptr [rbp%+d]", sl); E("mov rax, qword ptr [rax]"); E("test rax, rax"); E("jz .L%d", done);
      E("mov rdx, qword ptr [rax+8]"); E("cmp rdx, qword ptr [rbp%+d]", nl); E("jle .L%d", done);
      E("dec rdx"); E("mov qword ptr [rax+8], rdx");
      E("imul rdx, rdx, %d", tsize(at->elem)); E("lea rax, [rax+rdx+24]");
      E("push rax"); pushdepth++;
      drop_at_rax(at->elem);
      pop_reg("rdi"); E("xor eax, eax"); E("mov rcx, %d", tsize(at->elem)); E("rep stosb");
      E("jmp .L%d", lp);
      L(".L%d:", done);
      E("mov rax, qword ptr [rbp%+d]", sl); E("mov rcx, qword ptr [rbp%+d]", nl);
    }
    if (e->aux == IN_TRUNCATE) {
      E("mov rdx, qword ptr [rax]"); E("test rdx, rdx"); E("jz 1f");
      E("cmp rcx, qword ptr [rdx+8]"); E("jge 1f"); E("mov qword ptr [rdx+8], rcx"); L("1:");
      return V(false);
    }
    push_rax(); E("push %d", tsize(at->elem)); pushdepth++; E("push rcx"); pushdepth++;
    call_rt("__arr_resize", 3);
    return V(false);
  }
  case IN_ARRDATA:
    gen_borrowed(a[0]);
    E("test rax, rax"); E("jz 1f"); E("add rax, 24"); L("1:");
    return V(false);
  case IN_SYSCALL: {
    static const char *regs[] = {"rax", "rdi", "rsi", "rdx", "r10", "r8", "r9"};
    for (int i = 0; i < e->list.len; i++) { gen_expr(a[i]); push_rax(); }
    for (int i = e->list.len - 1; i >= 0; i--) pop_reg(regs[i]);
    E("syscall");
    return V(false);
  }
  case IN_ATOMIC_ADD:
    gen_expr(a[0]); push_rax(); gen_expr(a[1]);
    pop_reg("rcx"); E("lock xadd qword ptr [rcx], rax");
    return V(false);
  case IN_ATOMIC_CAS:
    gen_expr(a[0]); push_rax(); gen_expr(a[1]); push_rax(); gen_expr(a[2]);
    E("mov rdx, rax"); pop_reg("rax"); pop_reg("rcx"); E("lock cmpxchg qword ptr [rcx], rdx");
    return V(false);
  case IN_STACK_PTR:
    E("mov rax, rsp");
    return V(false);
  case IN_CPU_FEATURES:
    // (the bootstrap compiler's programs never use what this reports)
    E("xor eax, eax");
    return V(false);
  case IN_MEMCPY:
    gen_expr(a[0]); push_rax(); gen_expr(a[1]); push_rax(); gen_expr(a[2]);
    E("mov rcx, rax"); pop_reg("rsi"); pop_reg("rdi"); E("rep movsb");
    return V(false);
  case IN_MEMSET:
    gen_expr(a[0]); push_rax(); gen_expr(a[1]); push_rax(); gen_expr(a[2]);
    E("mov rcx, rax"); pop_reg("rax"); pop_reg("rdi"); E("rep stosb");
    return V(false);
  case IN_PANIC:
    if (e->list.len) gen_borrowed(a[0]); else E("lea rax, [rip+.Ls%d]", str_label(S("panic")));
    push_rax();
    call_rt("__panic", 1);
    return V(false);
  case IN_UNREACHABLE:
    E("lea rax, [rip+.Ls%d]", str_label(S("unreachable code reached"))); push_rax(); call_rt("__panic", 1);
    return V(false);
  case IN_ASSERT: {
    gen_expr(a[0]);
    int ok = newlabel();
    E("test al, al"); E("jnz .L%d", ok);
    if (e->list.len > 1) gen_borrowed(a[1]); else E("lea rax, [rip+.Ls%d]", str_label(S("assertion failed")));
    push_rax();
    E("lea rax, [rip+.Ls%d]", loc_label(e->pos)); push_rax();
    call_rt("__assert_fail", 2);
    L(".L%d:", ok);
    return V(false);
  }
  case IN_EMBED: {
    int id = newlabel();
    rd(&rodata, "  .balign 8\n.Le%d:\n  .quad -1, %d, %d", id, e->sval.len, e->sval.len + 1);
    emit_bytes(&rodata, e->sval.p, e->sval.len);
    rd(&rodata, "  .byte 0");
    E("lea rax, [rip+.Le%d]", id);
    return V(false);
  }
  case IN_TO_BYTES:
    gen_expr(a[0]);
    return V(false); // borrowed reinterpretation (shares object, COW protects the string)
  case IN_ARGV:
    E("mov rax, qword ptr [rip+__sloppy_sp0]");
    return V(false);
  case IN_SQRT:
    gen_expr(a[0]);
    if (is_f32(a[0]->type)) E("sqrtss xmm0, xmm0"); else E("sqrtsd xmm0, xmm0");
    return V(false);
  case IN_HASH: {
    Type *t = prune(a[0]->type);
    gen_addr(a[0], false);
    push_rax();
    E("call %s", helper(H_HASH, t, NULL)); E("add rsp, 8"); pushdepth--;
    return V(false);
  }
  case IN_FMT_STRUCT: {
    // a[0]: mut buf param (address), a[1]: value
    Type *t = prune(a[1]->type);
    int bslot = new_temp(t_int), vslot = new_temp(t_int);
    gen_addr(a[0], true); E("mov qword ptr [rbp%+d], rax", bslot);
    gen_addr(a[1], false); E("mov qword ptr [rbp%+d], rax", vslot);
    #define APPEND_LIT(s) do { E("push qword ptr [rbp%+d]", bslot); pushdepth++; E("lea rax, [rip+.Ls%d]", str_label(internc(s))); push_rax(); call_rt("__buf_append_str", 2); } while (0)
    #define CALL_FMT(fi, ftype, off) do { \
      E("push qword ptr [rbp%+d]", bslot); pushdepth++; \
      E("mov rax, qword ptr [rbp%+d]", vslot); if (off) E("add rax, %d", off); \
      load_rax(ftype); push_val(vclass(ftype)); \
      E("call %s", fn_sym(fi)); E("add rsp, 16"); pushdepth -= 2; } while (0)
    int fi = 0;
    if (t->kind == TY_STRUCT) {
      StructInfo *si = t->st; layout(t);
      APPEND_LIT(fmt("%.*s(", si->decl->name.len, si->decl->name.p));
      for (int i = 0; i < si->nfields; i++) {
        APPEND_LIT(fmt("%s%.*s=", i ? ", " : "", si->fields[i].name.len, si->fields[i].name.p));
        CALL_FMT((FnInst *)e->list2.data[fi]->sym, si->fields[i].type, si->fields[i].offset);
        fi++;
      }
      APPEND_LIT(")");
    } else if (t->kind == TY_TUPLE) {
      APPEND_LIT("(");
      int off = 0;
      for (int i = 0; i < t->nargs; i++) {
        Type *el = prune(t->args[i]); off = (off + talign(el) - 1) & ~(talign(el) - 1);
        if (i) APPEND_LIT(", ");
        CALL_FMT((FnInst *)e->list2.data[fi]->sym, el, off);
        off += tsize(el); fi++;
      }
      APPEND_LIT(")");
    } else if (t->kind == TY_ENUM) {
      StructInfo *si = t->st; layout(t);
      int end = newlabel();
      for (int v = 0; v < si->nvariants; v++) {
        Variant *var = &si->variants[v];
        int next = newlabel();
        E("mov rax, qword ptr [rbp%+d]", vslot);
        if (si->simple_enum) E("cmp dword ptr [rax], %lld", (long long)var->value); else E("cmp dword ptr [rax], %d", v);
        E("jne .L%d", next);
        APPEND_LIT(fmt("%.*s", var->name.len, var->name.p));
        if (var->nfields) {
          APPEND_LIT("(");
          for (int k = 0; k < var->nfields; k++) {
            if (k) APPEND_LIT(", ");
            CALL_FMT((FnInst *)e->list2.data[fi]->sym, var->fields[k].type, var->fields[k].offset);
            fi++;
          }
          APPEND_LIT(")");
        }
        E("jmp .L%d", end);
        L(".L%d:", next);
      }
      L(".L%d:", end);
    } else APPEND_LIT("<fn>");
    #undef APPEND_LIT
    #undef CALL_FMT
    return V(false);
  }
  default:
    fatal(e->pos, "sloppy0: intrinsic not supported in codegen");
  }
}

// ---------------- string interpolation ----------------
static Val gen_interp(Node *e) {
  int bslot = new_temp(t_int);
  E("mov qword ptr [rbp%+d], 0", bslot);
  for (int i = 0; i < e->list.len; i++) {
    Node *p = e->list.data[i];
    if (p->kind == N_STR) {
      if (!p->sval.len) continue;
      E("lea rax, [rbp%+d]", bslot); push_rax();
      E("lea rax, [rip+.Ls%d]", str_label(p->sval)); push_rax();
      call_rt("__buf_append_str", 2);
      continue;
    }
    FnInst *f = p->sym;
    E("lea rax, [rbp%+d]", bslot); push_rax();
    Val v = gen_expr(p->a);
    borrow(v, p->a->type);
    push_val(vclass(p->a->type));
    int n = 2;
    if (p->sval.len) { E("lea rax, [rip+.Ls%d]", str_label(p->sval)); push_rax(); n = 3; }
    E("call %s", fn_sym(f));
    E("add rsp, %d", n * 8); pushdepth -= n;
  }
  E("push qword ptr [rbp%+d]", bslot); pushdepth++;
  call_rt("__buf_finish", 1);
  return V(true);
}

// ---------------- value blocks ----------------
// Generate block; if it yields a value, store owned value into result slot `rs` (type rt).
static void gen_value_block(Node *b, int rs, Type *rt) {
  scope_push();
  for (int i = 0; i < b->list.len; i++) {
    Node *s = b->list.data[i];
    if (i == b->list.len - 1 && b->aux && rs) {
      stmt_begin();
      Val v = gen_owned(s->a);
      (void)v;
      E("lea rdi, [rbp%+d]", rs);
      store_rdi(rt);
      stmt_end();
      continue;
    }
    gen_stmt(s);
  }
  scope_pop();
}

static Val result_from_slot(int rs, Type *t) {
  E("lea rax, [rbp%+d]", rs);
  if (vclass(t) == VC_AGG) return (Val){true, rs};
  load_rax(t);
  return V(true);
}

// ---------------- match ----------------
static void gen_match_test(Node *p, Type *st, int hidden_off, int fail_label) {
  st = prune(st);
  switch (p->kind) {
  case N_PWILD: return;
  case N_PVARIANT: {
    layout(st);
    StructInfo *si = st->st;
    E("lea rax, [rbp%+d]", hidden_off);
    if (si->simple_enum) E("cmp dword ptr [rax], %lld", (long long)si->variants[p->aux2].value);
    else E("cmp dword ptr [rax], %d", p->aux2);
    E("jne .L%d", fail_label);
    return;
  }
  case N_PLIT: {
    if (st->kind == TY_STR) {
      E("lea rax, [rbp%+d]", hidden_off); E("push qword ptr [rax]"); pushdepth++;
      gen_borrowed(p->a); push_rax();
      call_rt("__str_eq", 2);
      E("test al, al"); E("jz .L%d", fail_label);
      return;
    }
    if (st->kind == TY_OPT) {
      if (p->a->kind == N_NONE) { E("cmp byte ptr [rbp%+d], 0", hidden_off + tsize(st->elem)); E("jne .L%d", fail_label); return; }
      fatal(p->pos, "only `none` and `_` patterns are supported for optionals; use `if let v = x`");
    }
    if (vclass(st) == VC_FLT) fatal(p->pos, "cannot match on floats");
    if (vclass(st) == VC_AGG) fatal(p->pos, "unsupported pattern for this type");
    gen_expr(p->a);
    E("mov rcx, rax");
    E("lea rax, [rbp%+d]", hidden_off); load_rax(st);
    E("cmp rax, rcx"); E("jne .L%d", fail_label);
    return;
  }
  case N_PRANGE: {
    bool sign = st->kind == TY_INT && st->sign;
    gen_expr(p->a); E("mov rcx, rax");
    E("lea rax, [rbp%+d]", hidden_off); load_rax(st);
    E("cmp rax, rcx"); E("%s .L%d", sign ? "jl" : "jb", fail_label);
    push_rax();
    gen_expr(p->b); E("mov rcx, rax");
    pop_reg("rax");
    E("cmp rax, rcx"); E("%s .L%d", (p->flags & NF_INCLUSIVE) ? (sign ? "jg" : "ja") : (sign ? "jge" : "jae"), fail_label);
    return;
  }
  default: fatal(p->pos, "invalid pattern");
  }
}

static Val gen_match(Node *m, bool want) {
  Local *hidden = m->sym;
  Type *st = m->a->type;
  Type *rt = m->type;
  int rs = 0;
  bool val = want && vclass(rt) != VC_VOID && prune(rt) != t_never;
  if (val) { rs = new_temp(rt); zero_slot(rs, tsize(rt)); }
  scope_push();
  stmt_begin();
  Val v = gen_owned(m->a); (void)v;
  E("lea rdi, [rbp%+d]", hidden->offset);
  store_rdi(st);
  stmt_end();
  scope_add_local(hidden);
  int end = newlabel();
  for (int i = 0; i < m->list.len; i++) {
    Node *arm = m->list.data[i];
    int body = newlabel(), next = newlabel();
    for (int k = 0; k < arm->list.len; k++) {
      int fail = k == arm->list.len - 1 ? next : newlabel();
      gen_match_test(arm->list.data[k], st, hidden->offset, fail);
      E("jmp .L%d", body);
      if (fail != next) L(".L%d:", fail);
    }
    L(".L%d:", body);
    if (val) gen_value_block(arm->b, rs, rt);
    else { scope_push(); gen_block_stmts(arm->b); scope_pop(); }
    E("jmp .L%d", end);
    L(".L%d:", next);
  }
  if (val) { E("lea rax, [rip+.Ls%d]", str_label(S("no match arm matched"))); push_rax(); call_rt("__panic", 1); }
  L(".L%d:", end);
  scope_pop();
  if (val) return result_from_slot(rs, rt);
  return V(false);
}

// ---------------- binary ----------------
static void gen_eq_call(Type *t) {
  // two addresses pushed: a, b
  E("call %s", helper(H_EQ, t, NULL)); E("add rsp, 16"); pushdepth -= 2;
}

static Val gen_binary(Node *e) {
  Type *lt = prune(e->a->type);
  int op = e->op;
  bool cmp = op == TK_EQ || op == TK_NE || op == TK_LT || op == TK_LE || op == TK_GT || op == TK_GE;
  if (e->aux == 1) { // structural equality
    gen_addr(e->a, false); push_rax();
    gen_addr(e->b, false); push_rax();
    gen_eq_call(lt);
    if (op == TK_NE) E("xor eax, 1");
    return V(false);
  }
  if (e->aux == 6) { // opt == none
    gen_addr(e->a, false);
    E("movzx eax, byte ptr [rax+%d]", tsize(lt->elem));
    if (op == TK_EQ) E("xor eax, 1");
    return V(false);
  }
  if (e->aux == 2) { // strings
    gen_borrowed(e->a); push_rax();
    gen_borrowed(e->b); push_rax();
    if (op == TK_PLUS) { call_rt("__str_concat", 2); return V(true); }
    if (op == TK_EQ || op == TK_NE) { call_rt("__str_eq", 2); if (op == TK_NE) E("xor eax, 1"); return V(false); }
    call_rt("__str_cmp", 2);
    E("cmp rax, 0");
    const char *cc = op == TK_LT ? "setl" : op == TK_LE ? "setle" : op == TK_GT ? "setg" : "setge";
    E("%s al", cc); E("movzx eax, al");
    return V(false);
  }
  if (e->aux == 3) { // array concat
    gen_borrowed(e->a); push_rax();
    gen_borrowed(e->b); push_rax();
    E("push %d", tsize(lt->elem)); pushdepth++;
    call_rt("__arr_concat", 3);
    if (is_managed(lt->elem)) {
      // retain all elements of the result
      int sl = new_temp(t_int);
      E("mov qword ptr [rbp%+d], rax", sl);
      int lp = newlabel(), done = newlabel(), idx = new_temp(t_int);
      E("mov qword ptr [rbp%+d], 0", idx);
      L(".L%d:", lp);
      E("mov rax, qword ptr [rbp%+d]", sl); E("test rax, rax"); E("jz .L%d", done);
      E("mov rcx, qword ptr [rbp%+d]", idx); E("cmp rcx, qword ptr [rax+8]"); E("jge .L%d", done);
      E("imul rcx, rcx, %d", tsize(lt->elem)); E("lea rax, [rax+rcx+24]");
      copy_at_rax(lt->elem);
      E("inc qword ptr [rbp%+d]", idx); E("jmp .L%d", lp);
      L(".L%d:", done);
      E("mov rax, qword ptr [rbp%+d]", sl);
    }
    return V(true);
  }
  if (e->aux == 4) { // ptr +/- int
    gen_expr(e->a); push_rax(); gen_expr(e->b);
    E("imul rcx, rax, %d", tsize(lt->elem)); pop_reg("rax");
    E(op == TK_PLUS ? "add rax, rcx" : "sub rax, rcx");
    return V(false);
  }
  if (e->aux == 5) { // ptr - ptr
    gen_expr(e->a); push_rax(); gen_expr(e->b); E("mov rcx, rax"); pop_reg("rax");
    E("sub rax, rcx");
    int sz = tsize(lt->elem);
    if (sz > 1) { E("cqo"); E("mov rcx, %d", sz); E("idiv rcx"); }
    return V(false);
  }
  Type *ot = cmp ? prune(e->a->type) : prune(e->type);
  if (vclass(ot) == VC_FLT || (cmp && vclass(lt) == VC_FLT)) {
    bool f32 = is_f32(lt);
    gen_expr(e->a); E("movq rax, xmm0"); push_rax();
    gen_expr(e->b); E("movaps xmm1, xmm0"); pop_reg("rax"); E("movq xmm0, rax");
    const char *sfx = f32 ? "ss" : "sd";
    switch (op) {
    case TK_PLUS: E("add%s xmm0, xmm1", sfx); return V(false);
    case TK_MINUS: E("sub%s xmm0, xmm1", sfx); return V(false);
    case TK_STAR: E("mul%s xmm0, xmm1", sfx); return V(false);
    case TK_SLASH: E("div%s xmm0, xmm1", sfx); return V(false);
    case TK_PERCENT: {
      // fmod: a - trunc(a/b)*b
      E("movaps xmm2, xmm0"); E("div%s xmm2, xmm1", sfx);
      E("roundsd xmm2, xmm2, 3");
      if (f32) { E("cvtss2sd xmm2, xmm2"); }
      E("mul%s xmm2, xmm1", sfx); E("sub%s xmm0, xmm2", sfx);
      return V(false);
    }
    case TK_EQ: E("ucomi%s xmm0, xmm1", sfx); E("sete al"); E("setnp cl"); E("and al, cl"); E("movzx eax, al"); return V(false);
    case TK_NE: E("ucomi%s xmm0, xmm1", sfx); E("setne al"); E("setp cl"); E("or al, cl"); E("movzx eax, al"); return V(false);
    case TK_LT: E("ucomi%s xmm1, xmm0", sfx); E("seta al"); E("movzx eax, al"); return V(false);
    case TK_LE: E("ucomi%s xmm1, xmm0", sfx); E("setae al"); E("movzx eax, al"); return V(false);
    case TK_GT: E("ucomi%s xmm0, xmm1", sfx); E("seta al"); E("movzx eax, al"); return V(false);
    case TK_GE: E("ucomi%s xmm0, xmm1", sfx); E("setae al"); E("movzx eax, al"); return V(false);
    default: fatal(e->pos, "invalid float operator");
    }
  }
  gen_expr(e->a); push_rax();
  gen_expr(e->b); E("mov rcx, rax"); pop_reg("rax");
  bool sign = (lt->kind == TY_INT && lt->sign) || lt->kind == TY_ENUM;
  switch (op) {
  case TK_PLUS: E("add rax, rcx"); break;
  case TK_MINUS: E("sub rax, rcx"); break;
  case TK_STAR: E("imul rax, rcx"); break;
  case TK_SLASH: case TK_PERCENT:
    E("test rcx, rcx"); E("jnz 1f"); E("lea rax, [rip+.Ls%d]", loc_label(e->pos)); E("push rax"); E("call %s", fn_sym(runtime_fn("__div_zero"))); L("1:");
    if (sign) { E("cqo"); E("idiv rcx"); } else { E("xor edx, edx"); E("div rcx"); }
    if (op == TK_PERCENT) E("mov rax, rdx");
    break;
  case TK_AMP: E("and rax, rcx"); break;
  case TK_PIPE: E("or rax, rcx"); break;
  case TK_CARET: E("xor rax, rcx"); break;
  case TK_SHL: E("shl rax, cl"); break;
  case TK_SHR: if (sign) E("sar rax, cl"); else E("shr rax, cl"); break;
  case TK_EQ: case TK_NE: case TK_LT: case TK_LE: case TK_GT: case TK_GE: {
    E("cmp rax, rcx");
    const char *cc;
    switch (op) {
    case TK_EQ: cc = "sete"; break; case TK_NE: cc = "setne"; break;
    case TK_LT: cc = sign ? "setl" : "setb"; break; case TK_LE: cc = sign ? "setle" : "setbe"; break;
    case TK_GT: cc = sign ? "setg" : "seta"; break; default: cc = sign ? "setge" : "setae"; break;
    }
    E("%s al", cc); E("movzx eax, al");
    return V(false);
  }
  default: fatal(e->pos, "invalid operator");
  }
  norm(e->type);
  return V(false);
}

// ---------------- conversions ----------------
static Val gen_conv(Node *e) {
  Type *to = prune(e->type), *from = prune(e->a->type);
  switch (e->aux) {
  case CV_NONE: case CV_PTR: { Val v = gen_expr(e->a); return v; }
  case CV_INT: gen_expr(e->a); norm(to); return V(false);
  case CV_INT2FLOAT:
    gen_expr(e->a);
    if (from->kind == TY_INT && !from->sign && from->bits == 64) {
      // unsigned 64 -> float
      E("test rax, rax"); E("js 1f");
      E(is_f32(to) ? "cvtsi2ss xmm0, rax" : "cvtsi2sd xmm0, rax"); E("jmp 2f");
      L("1:"); E("mov rcx, rax"); E("shr rcx, 1"); E("and eax, 1"); E("or rcx, rax");
      E(is_f32(to) ? "cvtsi2ss xmm0, rcx" : "cvtsi2sd xmm0, rcx");
      E(is_f32(to) ? "addss xmm0, xmm0" : "addsd xmm0, xmm0");
      L("2:");
    } else E(is_f32(to) ? "cvtsi2ss xmm0, rax" : "cvtsi2sd xmm0, rax");
    return V(false);
  case CV_FLOAT2INT:
    gen_expr(e->a);
    E(is_f32(from) ? "cvttss2si rax, xmm0" : "cvttsd2si rax, xmm0");
    norm(to);
    return V(false);
  case CV_FLOAT:
    gen_expr(e->a);
    if (is_f32(from) && !is_f32(to)) E("cvtss2sd xmm0, xmm0");
    else if (!is_f32(from) && is_f32(to)) E("cvtsd2ss xmm0, xmm0");
    return V(false);
  case CV_OPT: {
    Type *inner = to->elem;
    int slot = new_temp(to);
    zero_slot(slot, tsize(to));
    Val v = gen_owned(e->a); (void)v;
    E("lea rdi, [rbp%+d]", slot);
    store_rdi(inner);
    E("mov byte ptr [rbp%+d], 1", slot + tsize(inner));
    E("lea rax, [rbp%+d]", slot);
    return (Val){true, slot};
  }
  default: fatal(e->pos, "invalid conversion");
  }
}

// ---------------- expressions ----------------
static Val gen_expr(Node *e) {
  Type *t = e->type ? prune(e->type) : t_void;
  switch (e->kind) {
  case N_INT:
    if (vclass(t) == VC_FLT) { e->fval = (double)e->ival; goto flt; }
    if (e->ival >= INT32_MIN && e->ival <= INT32_MAX) E("mov rax, %lld", (long long)e->ival);
    else E("movabs rax, %lld", (long long)e->ival);
    return V(false);
  case N_FLOAT: flt:
    if (is_f32(t)) E("movss xmm0, dword ptr [rip+.Lf%d]", f32_label((float)e->fval));
    else E("movsd xmm0, qword ptr [rip+.Lf%d]", f64_label(e->fval));
    return V(false);
  case N_BOOL: E("mov eax, %d", (int)e->ival); return V(false);
  case N_NULL: E("xor eax, eax"); return V(false);
  case N_NONE: {
    if (vclass(t) != VC_AGG) { E("xor eax, eax"); return V(false); }
    int slot = new_temp(t); zero_slot(slot, tsize(t)); E("lea rax, [rbp%+d]", slot);
    return (Val){true, slot};
  }
  case N_STR:
    if (e->aux) return gen_interp(e);
    E("lea rax, [rip+.Ls%d]", str_label(e->sval));
    return V(false);
  case N_IDENT: {
    if (e->aux == S_LOCAL || e->aux == S_GLOBAL) {
      gen_addr(e, false);
      load_rax(t);
      return V(false);
    }
    fatal(e->pos, "sloppy0: cannot generate identifier");
  }
  case N_FIELD:
    if (e->aux != -3 && prune(e->a->type)->kind != TY_PTR && vclass(e->a->type) == VC_AGG && e->a->kind != N_IDENT) {
      // field of an rvalue aggregate
      gen_addr(e, false);
      load_rax(t);
      return V(false);
    }
    gen_addr(e, false);
    load_rax(t);
    return V(false);
  case N_DOTNAME: {
    StructInfo *si = t->st; layout(t);
    if (si->simple_enum) { E("mov eax, %lld", (long long)si->variants[e->aux].value); return V(false); }
    int slot = new_temp(t); zero_slot(slot, tsize(t));
    E("mov dword ptr [rbp%+d], %d", slot, e->aux);
    E("lea rax, [rbp%+d]", slot);
    return (Val){true, slot};
  }
  case N_INDEX:
    if (e->aux == 1) { // slice
      Type *bt = prune(e->a->type);
      Node *r = e->b;
      gen_borrowed(e->a); push_rax();
      if (r->a) gen_expr(r->a); else E("xor eax, eax");
      push_rax();
      if (r->b) { gen_expr(r->b); if (r->flags & NF_INCLUSIVE) E("inc rax"); }
      else { E("mov rax, qword ptr [rsp+8]"); E("test rax, rax"); E("jz 1f"); E("mov rax, qword ptr [rax+8]"); L("1:"); }
      push_rax();
      if (bt->kind == TY_STR) { call_rt("__str_slice", 3); return V(true); }
      E("push %d", tsize(bt->elem)); pushdepth++;
      call_rt("__arr_slice", 4);
      if (is_managed(bt->elem)) {
        int sl = new_temp(t_int), idx = new_temp(t_int);
        E("mov qword ptr [rbp%+d], rax", sl); E("mov qword ptr [rbp%+d], 0", idx);
        int lp = newlabel(), done = newlabel();
        L(".L%d:", lp);
        E("mov rax, qword ptr [rbp%+d]", sl); E("test rax, rax"); E("jz .L%d", done);
        E("mov rcx, qword ptr [rbp%+d]", idx); E("cmp rcx, qword ptr [rax+8]"); E("jge .L%d", done);
        E("imul rcx, rcx, %d", tsize(bt->elem)); E("lea rax, [rax+rcx+24]");
        copy_at_rax(bt->elem);
        E("inc qword ptr [rbp%+d]", idx); E("jmp .L%d", lp);
        L(".L%d:", done);
        E("mov rax, qword ptr [rbp%+d]", sl);
      }
      return V(true);
    }
    gen_addr(e, false);
    load_rax(t);
    return V(false);
  case N_UNWRAP:
    gen_addr(e, false);
    load_rax(t);
    return V(false);
  case N_CALL: {
    Val v;
    if (e->aux == 0) {
      v = gen_direct_call(e->sym, e->list.data, e->list.len);
      if (vclass(t) == VC_VOID) return V(false);
      return v;
    }
    if (e->aux == 1) { v = gen_closure_call(e->a, e->list.data, e->list.len); if (vclass(t) == VC_VOID) return V(false); return v; }
    if (e->aux == 2) { // struct constructor
      StructInfo *si = t->st; layout(t);
      int slot = new_temp(t);
      zero_slot(slot, tsize(t));
      for (int i = 0; i < si->nfields; i++) {
        Node *a = e->list.data[i];
        if (!a) continue;
        gen_owned(a);
        E("lea rdi, [rbp%+d]", slot + si->fields[i].offset);
        store_rdi(si->fields[i].type);
      }
      E("lea rax, [rbp%+d]", slot);
      return (Val){true, slot};
    }
    if (e->aux == 3) { // enum variant
      StructInfo *si = t->st; layout(t);
      Variant *var = &si->variants[e->aux2];
      if (si->simple_enum) { E("mov eax, %lld", (long long)var->value); return V(false); }
      int slot = new_temp(t);
      zero_slot(slot, tsize(t));
      E("mov dword ptr [rbp%+d], %d", slot, e->aux2);
      for (int i = 0; i < var->nfields; i++) {
        gen_owned(e->list.data[i]);
        E("lea rdi, [rbp%+d]", slot + var->fields[i].offset);
        store_rdi(var->fields[i].type);
      }
      E("lea rax, [rbp%+d]", slot);
      return (Val){true, slot};
    }
    fatal(e->pos, "invalid call");
  }
  case N_INTRINSIC: return gen_intrinsic(e);
  case N_PARTIAL: return gen_partial(e);
  case N_LAMBDA: return gen_lambda(e);
  case N_FNREF: return gen_fnref(e);
  case N_UNARY:
    gen_expr(e->a);
    if (e->op == TK_MINUS) {
      if (vclass(t) == VC_FLT) {
        if (is_f32(t)) { E("movd eax, xmm0"); E("xor eax, 0x80000000"); E("movd xmm0, eax"); }
        else { E("movq rax, xmm0"); E("btc rax, 63"); E("movq xmm0, rax"); }
      } else { E("neg rax"); norm(t); }
    } else if (e->op == TK_TILDE) { E("not rax"); norm(t); }
    return V(false);
  case N_NOT: gen_expr(e->a); E("xor eax, 1"); return V(false);
  case N_AND: case N_OR: {
    int end = newlabel();
    gen_expr(e->a);
    E("test al, al");
    E(e->kind == N_AND ? "jz .L%d" : "jnz .L%d", end);
    gen_expr(e->b);
    L(".L%d:", end);
    E("movzx eax, al");
    return V(false);
  }
  case N_BINARY: return gen_binary(e);
  case N_CONV: return gen_conv(e);
  case N_CAST: {
    Type *from = prune(e->a->type);
    Val v = gen_expr(e->a);
    if (from->kind == TY_FLOAT && t->kind == TY_INT) { if (is_f32(from)) E("movd eax, xmm0"); else E("movq rax, xmm0"); norm(t); }
    else if (from->kind == TY_INT && t->kind == TY_FLOAT) { if (is_f32(t)) E("movd xmm0, eax"); else E("movq xmm0, rax"); }
    else if (t->kind == TY_INT) norm(t);
    if (is_managed(from)) { borrow(v, from); }
    if (is_managed(t)) return V(true); // raw pointer -> managed value: takes ownership of one reference
    return V(false);
  }
  case N_COALESCE: {
    Type *ot = prune(e->a->type);
    int rs = new_temp(t);
    gen_addr(e->a, false);
    int inner = tsize(ot->elem);
    int els = newlabel(), end = newlabel();
    E("cmp byte ptr [rax+%d], 0", inner); E("je .L%d", els);
    if (e->aux == 1) { Val v = own(V(false), ot); (void)v; }
    else { load_rax(ot->elem); own(V(false), ot->elem); }
    E("lea rdi, [rbp%+d]", rs); store_rdi(e->aux == 1 ? ot : ot->elem);
    E("jmp .L%d", end);
    L(".L%d:", els);
    gen_owned(e->b);
    E("lea rdi, [rbp%+d]", rs); store_rdi(t);
    L(".L%d:", end);
    return result_from_slot(rs, t);
  }
  case N_ARRAY: {
    Type *et = t->elem;
    int esz = tsize(et);
    int slot = new_temp(t);
    if (e->aux == 1) { // [v; n]
      Val v = gen_owned(e->list.data[0]); (void)v;
      int vs = new_temp(et);
      E("lea rdi, [rbp%+d]", vs); store_rdi(et);
      gen_expr(e->b); push_rax();
      E("push %d", esz); pushdepth++;
      call_rt("__arr_repeat", 2);
      E("mov qword ptr [rbp%+d], rax", slot);
      int idx = new_temp(t_int), lp = newlabel(), done = newlabel();
      E("mov qword ptr [rbp%+d], 0", idx);
      L(".L%d:", lp);
      E("mov rax, qword ptr [rbp%+d]", slot); E("test rax, rax"); E("jz .L%d", done);
      E("mov rcx, qword ptr [rbp%+d]", idx); E("cmp rcx, qword ptr [rax+8]"); E("jge .L%d", done);
      E("imul rcx, rcx, %d", esz); E("lea rdi, [rax+rcx+24]");
      E("lea rax, [rbp%+d]", vs);
      copy_bytes(esz);
      if (is_managed(et)) { E("lea rax, [rbp%+d]", vs); copy_at_rax(et); }
      E("inc qword ptr [rbp%+d]", idx); E("jmp .L%d", lp);
      L(".L%d:", done);
      E("lea rax, [rbp%+d]", vs); drop_at_rax(et);
      E("mov rax, qword ptr [rbp%+d]", slot);
      return V(true);
    }
    if (e->list.len == 0) { E("xor eax, eax"); return V(true); }
    E("push %d", e->list.len); pushdepth++; E("push %d", esz); pushdepth++;
    call_rt("__arr_repeat", 2);
    E("mov qword ptr [rbp%+d], rax", slot);
    for (int i = 0; i < e->list.len; i++) {
      gen_owned(e->list.data[i]);
      E("mov rdi, qword ptr [rbp%+d]", slot);
      E("add rdi, %d", 24 + i * esz);
      store_rdi(et);
    }
    E("mov rax, qword ptr [rbp%+d]", slot);
    return V(true);
  }
  case N_MAP: {
    int slot = new_temp(t);
    zero_slot(slot, tsize(t));
    for (int i = 0; i < e->list.len; i++) {
      Node *p = e->list.data[i];
      FnInst *f = e->sym;
      E("lea rax, [rbp%+d]", slot); push_rax();
      Val k = gen_expr(p->a); borrow(k, p->a->type); push_val(vclass(p->a->type));
      Val v = gen_expr(p->b); borrow(v, p->b->type); push_val(vclass(p->b->type));
      E("call %s", fn_sym(f)); E("add rsp, 24"); pushdepth -= 3;
    }
    E("lea rax, [rbp%+d]", slot);
    return (Val){true, slot};
  }
  case N_TUPLE: {
    if (vclass(t) == VC_VOID) return V(false);
    int slot = new_temp(t);
    int off = 0;
    for (int i = 0; i < t->nargs; i++) {
      Type *el = prune(t->args[i]);
      off = (off + talign(el) - 1) & ~(talign(el) - 1);
      gen_owned(e->list.data[i]);
      E("lea rdi, [rbp%+d]", slot + off);
      store_rdi(el);
      off += tsize(el);
    }
    E("lea rax, [rbp%+d]", slot);
    return (Val){true, slot};
  }
  case N_RANGE: {
    int slot = new_temp(t_range);
    if (e->a) gen_expr(e->a); else E("xor eax, eax");
    E("mov qword ptr [rbp%+d], rax", slot);
    if (e->b) { gen_expr(e->b); if (e->flags & NF_INCLUSIVE) E("inc rax"); } else E("movabs rax, 0x7fffffffffffffff");
    E("mov qword ptr [rbp%+d], rax", slot + 8);
    E("lea rax, [rbp%+d]", slot);
    return (Val){false, 0};
  }
  case N_ADDR: gen_addr(e->a, true); return V(false);
  case N_IF: {
    bool val = vclass(t) != VC_VOID && t != t_never && !(e->flags & NF_STMT);
    int rs = val ? new_temp(t) : 0;
    if (rs) zero_slot(rs, tsize(t));
    int els = newlabel(), end = newlabel();
    int cslot = alloc_slot(8, 8);
    stmt_begin(); gen_expr(e->a); E("mov qword ptr [rbp%+d], rax", cslot); stmt_end();
    E("cmp byte ptr [rbp%+d], 0", cslot);
    E("jz .L%d", els);
    if (val) gen_value_block(e->b, rs, t); else { scope_push(); gen_block_stmts(e->b); scope_pop(); }
    E("jmp .L%d", end);
    L(".L%d:", els);
    if (e->c) { if (val) gen_value_block(e->c, rs, t); else { scope_push(); gen_block_stmts(e->c); scope_pop(); } }
    L(".L%d:", end);
    if (val) return result_from_slot(rs, t);
    return V(false);
  }
  case N_IFLET: {
    bool val = vclass(t) != VC_VOID && t != t_never && !(e->flags & NF_STMT);
    int rs = val ? new_temp(t) : 0;
    if (rs) zero_slot(rs, tsize(t));
    Local *l = e->sym;
    Type *ot = prune(e->a->type);
    int els = newlabel(), end = newlabel();
    int flag = alloc_slot(8, 8);
    scope_push();
    stmt_begin();
    gen_addr(e->a, false);
    E("movzx ecx, byte ptr [rax+%d]", tsize(ot->elem));
    E("mov qword ptr [rbp%+d], rcx", flag);
    E("test ecx, ecx"); E("jz 1f");
    load_rax(ot->elem);
    own(V(false), ot->elem);
    E("lea rdi, [rbp%+d]", l->offset);
    store_rdi(l->type);
    L("1:");
    stmt_end();
    scope_add_local(l);
    E("cmp qword ptr [rbp%+d], 0", flag); E("je .L%d", els);
    if (val) gen_value_block(e->b, rs, t); else { scope_push(); gen_block_stmts(e->b); scope_pop(); }
    E("jmp .L%d", end);
    L(".L%d:", els);
    if (e->c) { if (val) gen_value_block(e->c, rs, t); else { scope_push(); gen_block_stmts(e->c); scope_pop(); } }
    L(".L%d:", end);
    scope_pop();
    if (val) return result_from_slot(rs, t);
    return V(false);
  }
  case N_MATCH: return gen_match(e, !(e->flags & NF_STMT));
  case N_BLOCK: {
    int rs = vclass(t) != VC_VOID ? new_temp(t) : 0;
    if (rs) zero_slot(rs, tsize(t));
    gen_value_block(e, rs, t);
    if (rs) return result_from_slot(rs, t);
    return V(false);
  }
  default:
    fatal(e->pos, "sloppy0: unsupported expression in codegen (kind %d)", e->kind);
  }
}

// ---------------- statements ----------------
static void gen_return(Node *s) {
  Type *rt = prune(curfn->ret);
  if (s->a && vclass(rt) != VC_VOID) {
    stmt_begin();
    gen_owned(s->a);
    if (vclass(rt) == VC_AGG) { E("mov rdi, qword ptr [rbp%+d]", sret_off_slot); store_rdi(rt); }
    else if (vclass(rt) == VC_FLT) { E("lea rdi, [rbp%+d]", ret_slot); store_rdi(rt); }
    else E("mov qword ptr [rbp%+d], rax", ret_slot);
    stmt_end();
  } else if (s->a) {
    stmt_begin(); Val v = gen_expr(s->a); borrow(v, s->a->type); stmt_end();
  }
  for (int i = nscopes - 1; i >= 0; i--) emit_scope_exit(i);
  E("jmp .L%d", ret_label);
}

static void assign_to_place(Node *target, Type *t) {
  // value (owned) in rax/xmm0 (aggregates: rax = address of owned temp)
  push_val(vclass(t));
  gen_addr(target, true);
  if (is_managed(t)) { push_rax(); drop_at_rax(t); pop_reg("rdi"); }
  else E("mov rdi, rax");
  pop_reg("rax");
  if (vclass(t) == VC_FLT) E("movq xmm0, rax");
  store_rdi(t);
}

static void gen_assign(Node *s) {
  Type *t = prune(s->a->type);
  if (s->aux == 1) { // tuple assignment
    Type *tt = prune(s->b->type);
    Val v = gen_owned(s->b);
    int ts = v.slot;
    int off = 0;
    for (int i = 0; i < tt->nargs; i++) {
      Type *el = prune(tt->args[i]);
      off = (off + talign(el) - 1) & ~(talign(el) - 1);
      Node *tg = s->a->list.data[i];
      E("lea rax, [rbp%+d]", ts + off);
      if (tg->kind == N_HOLE) drop_at_rax(el);
      else { load_rax(el); assign_to_place(tg, el); }
      off += tsize(el);
    }
    return;
  }
  if (s->aux == 2) { // string +=
    gen_borrowed(s->b); push_rax();
    gen_addr(s->a, true);
    pop_reg("rcx");
    push_rax(); E("push rcx"); pushdepth++;
    call_rt("__str_append", 2);
    return;
  }
  if (s->aux == 3) { // pointer +=
    gen_expr(s->b);
    E("imul rax, rax, %d", tsize(t->elem));
    push_rax();
    gen_addr(s->a, true);
    pop_reg("rcx");
    E(s->op == TK_PLUSEQ ? "add qword ptr [rax], rcx" : "sub qword ptr [rax], rcx");
    return;
  }
  if (s->op == TK_ASSIGN) {
    gen_owned(s->b);
    assign_to_place(s->a, t);
    return;
  }
  // compound arithmetic
  int op = 0;
  int map[][2] = {{TK_PLUSEQ, TK_PLUS}, {TK_MINUSEQ, TK_MINUS}, {TK_STAREQ, TK_STAR}, {TK_SLASHEQ, TK_SLASH}, {TK_PERCENTEQ, TK_PERCENT}, {TK_AMPEQ, TK_AMP}, {TK_PIPEEQ, TK_PIPE}, {TK_CARETEQ, TK_CARET}, {TK_SHLEQ, TK_SHL}, {TK_SHREQ, TK_SHR}};
  for (int i = 0; i < 10; i++) if (map[i][0] == s->op) op = map[i][1];
  gen_addr(s->a, true);
  int as = alloc_slot(8, 8);
  E("mov qword ptr [rbp%+d], rax", as);
  // build a binary node reading through the address
  Node tmpb = {0};
  tmpb.kind = N_BINARY; tmpb.op = op; tmpb.type = t; tmpb.pos = s->pos;
  Node lhs = {0};
  lhs.kind = N_IDENT; lhs.aux = S_LOCAL; lhs.type = t;
  Local fake = {0};
  fake.flags = LF_BYREF; fake.offset = as; fake.type = t;
  lhs.sym = &fake;
  tmpb.a = &lhs; tmpb.b = s->b;
  gen_binary(&tmpb);
  E("mov rdi, qword ptr [rbp%+d]", as);
  store_rdi(t);
}

static void gen_vardecl(Node *s) {
  if (s->list.len) { // tuple destructuring
    Type *tt = prune(s->b->type);
    Val v = gen_owned(s->b);
    int ts = v.slot;
    int off = 0;
    for (int i = 0; i < tt->nargs; i++) {
      Type *el = prune(tt->args[i]);
      off = (off + talign(el) - 1) & ~(talign(el) - 1);
      Node *id = s->list.data[i];
      E("lea rax, [rbp%+d]", ts + off);
      if (id->kind == N_HOLE) drop_at_rax(el);
      else if (id->flags & NF_GLOBAL) {
        Global *g = id->sym;
        load_rax(el);
        E("lea rdi, [rip+%s]", g->sym.p);
        store_rdi(el);
      } else {
        Local *l = id->sym;
        load_rax(el);
        E("lea rdi, [rbp%+d]", l->offset);
        store_rdi(el);
        scope_add_local(l);
      }
      off += tsize(el);
    }
    return;
  }
  if (s->flags & NF_GLOBAL) {
    Global *g = s->sym;
    Node *iv = s->b;
    bool zero = iv && ((iv->kind == N_INT && iv->ival == 0) || iv->kind == N_NULL || (iv->kind == N_BOOL && !iv->ival) || (iv->kind == N_FLOAT && iv->fval == 0.0 && !signbit(iv->fval)));
    if (iv && !zero) {
      gen_owned(s->b);
      E("lea rdi, [rip+%s]", g->sym.p);
      store_rdi(g->type);
    }
    return;
  }
  Local *l = s->sym;
  if (s->b) {
    gen_owned(s->b);
    E("lea rdi, [rbp%+d]", l->offset);
    store_rdi(l->type);
  } else zero_slot(l->offset, tsize(l->type));
  scope_add_local(l);
}

static void gen_loop_body(Node *b) { scope_push(); gen_block_stmts(b); scope_pop(); }

static void gen_for(Node *s) {
  int head = newlabel(), cont = newlabel(), brk = newlabel();
  scope_push();
  if (s->aux == 0 || s->aux == 4) { // range
    Local *l = s->sym;
    int endslot = alloc_slot(8, 8);
    stmt_begin();
    if (s->aux == 0) {
      gen_expr(s->a->a); E("mov qword ptr [rbp%+d], rax", l->offset);
      gen_expr(s->a->b); if (s->a->flags & NF_INCLUSIVE) E("inc rax");
      E("mov qword ptr [rbp%+d], rax", endslot);
    } else {
      gen_expr(s->a);
      E("mov rcx, qword ptr [rax]"); E("mov qword ptr [rbp%+d], rcx", l->offset);
      E("mov rcx, qword ptr [rax+8]"); E("mov qword ptr [rbp%+d], rcx", endslot);
    }
    stmt_end();
    int ctr = alloc_slot(8, 8);
    E("mov rax, qword ptr [rbp%+d]", l->offset); E("mov qword ptr [rbp%+d], rax", ctr);
    Type *it = prune(l->type);
    bool sign = it->sign;
    L(".L%d:", head);
    E("mov rax, qword ptr [rbp%+d]", ctr); E("cmp rax, qword ptr [rbp%+d]", endslot);
    E("%s .L%d", sign ? "jge" : "jae", brk);
    E("mov qword ptr [rbp%+d], rax", l->offset);
    loops[nloops++] = (Loop){brk, cont, nscopes};
    gen_loop_body(s->b);
    nloops--;
    L(".L%d:", cont);
    E("inc qword ptr [rbp%+d]", ctr);
    E("jmp .L%d", head);
    L(".L%d:", brk);
    scope_pop();
    return;
  }
  Local *idx = (Local *)s->c, *snap = (Local *)s->d, *el = s->sym;
  Type *ct = prune(s->a->type);
  // snapshot (retained) of the collection
  if (s->aux == 1 || s->aux == 3) {
    stmt_begin();
    gen_owned(s->a);
    E("lea rdi, [rbp%+d]", snap->offset);
    store_rdi(ct);
    stmt_end();
    scope_add_local(snap);
  }
  E("mov qword ptr [rbp%+d], 0", idx->offset);
  L(".L%d:", head);
  if (s->aux == 1) { // array/str by reference
    Type *et = ct->kind == TY_STR ? t_u8 : ct->elem;
    E("mov rax, qword ptr [rbp%+d]", snap->offset);
    E("test rax, rax"); E("jz .L%d", brk);
    E("mov rcx, qword ptr [rbp%+d]", idx->offset);
    E("cmp rcx, qword ptr [rax+8]"); E("jge .L%d", brk);
    int sz = tsize(et);
    E("imul rcx, rcx, %d", sz); E("lea rax, [rax+rcx+24]");
    E("mov qword ptr [rbp%+d], rax", el->offset);
  } else if (s->aux == 2) { // for mut: alias
    gen_addr(s->a, false);
    E("mov rax, qword ptr [rax]");
    E("test rax, rax"); E("jz .L%d", brk);
    E("mov rcx, qword ptr [rbp%+d]", idx->offset);
    E("cmp rcx, qword ptr [rax+8]"); E("jge .L%d", brk);
  } else if (s->aux == 3) { // map
    StructInfo *si = ct->st; layout(ct);
    int koff = si->fields[0].offset, voff = si->fields[1].offset;
    Type *kt = prune(si->fields[0].type)->elem, *vt = prune(si->fields[1].type)->elem;
    E("mov rax, qword ptr [rbp%+d]", snap->offset + koff);
    E("test rax, rax"); E("jz .L%d", brk);
    E("mov rcx, qword ptr [rbp%+d]", idx->offset);
    E("cmp rcx, qword ptr [rax+8]"); E("jge .L%d", brk);
    E("imul rdx, rcx, %d", tsize(kt)); E("lea rax, [rax+rdx+24]");
    E("mov qword ptr [rbp%+d], rax", el->offset);
    Local *vl = s->list2.len ? s->list2.data[0]->sym : NULL;
    if (vl && (vl->flags & LF_BYREF)) {
      E("mov rax, qword ptr [rbp%+d]", snap->offset + voff);
      E("mov rcx, qword ptr [rbp%+d]", idx->offset);
      E("imul rdx, rcx, %d", tsize(vt)); E("lea rax, [rax+rdx+24]");
      E("mov qword ptr [rbp%+d], rax", vl->offset);
    }
  }
  loops[nloops++] = (Loop){brk, cont, nscopes};
  gen_loop_body(s->b);
  nloops--;
  L(".L%d:", cont);
  E("inc qword ptr [rbp%+d]", idx->offset);
  E("jmp .L%d", head);
  L(".L%d:", brk);
  scope_pop();
}

static void gen_stmt(Node *s) {
  switch (s->kind) {
  case N_VARDECL: stmt_begin(); gen_vardecl(s); stmt_end(); break;
  case N_ASSIGN: stmt_begin(); gen_assign(s); stmt_end(); break;
  case N_EXPRSTMT: {
    if (s->a->kind == N_MATCH || s->a->kind == N_IF || s->a->kind == N_IFLET) {
      Val v = gen_expr(s->a);
      if (v.owned && is_managed(s->a->type)) { stmt_begin(); borrow(v, s->a->type); stmt_end(); }
      break;
    }
    stmt_begin();
    Val v = gen_expr(s->a);
    borrow(v, s->a->type);
    stmt_end();
    break;
  }
  case N_IF: case N_IFLET: gen_expr(s); break;
  case N_WHILE: {
    int head = newlabel(), brk = newlabel();
    scope_push();
    L(".L%d:", head);
    if (s->aux == 1) {
      Local *l = s->sym;
      Type *ot = prune(s->a->type);
      int flag = alloc_slot(8, 8);
      stmt_begin();
      gen_addr(s->a, false);
      E("movzx ecx, byte ptr [rax+%d]", tsize(ot->elem));
      E("mov qword ptr [rbp%+d], rcx", flag);
      E("test ecx, ecx"); E("jz 1f");
      load_rax(ot->elem);
      own(V(false), ot->elem);
      E("lea rdi, [rbp%+d]", l->offset);
      store_rdi(l->type);
      L("1:");
      stmt_end();
      E("cmp qword ptr [rbp%+d], 0", flag); E("je .L%d", brk);
      int cont = newlabel();
      loops[nloops++] = (Loop){brk, cont, nscopes + 1};
      scope_push();
      scope_add_local(l);
      gen_block_stmts(s->b);
      L(".L%d:", cont);
      scope_pop();
      nloops--;
      E("jmp .L%d", head);
    } else {
      int flag = alloc_slot(8, 8);
      stmt_begin(); gen_expr(s->a); E("mov qword ptr [rbp%+d], rax", flag); stmt_end();
      E("cmp byte ptr [rbp%+d], 0", flag); E("je .L%d", brk);
      loops[nloops++] = (Loop){brk, head, nscopes};
      gen_loop_body(s->b);
      nloops--;
      E("jmp .L%d", head);
    }
    L(".L%d:", brk);
    scope_pop();
    break;
  }
  case N_FOR: gen_for(s); break;
  case N_RETURN: gen_return(s); break;
  case N_BREAK: case N_CONTINUE: {
    Loop *lp = &loops[nloops - 1];
    for (int i = nscopes - 1; i >= lp->depth; i--) emit_scope_exit(i);
    E("jmp .L%d", s->kind == N_BREAK ? lp->brk : lp->cont);
    break;
  }
  case N_DEFER: vpush(scopes[nscopes - 1].defers, s->a); break;
  case N_BLOCK:
    if (s->aux == 5) { gen_block_stmts(s); break; }
    scope_push(); gen_block_stmts(s); scope_pop();
    break;
  case N_CONST: break;
  default:
    fatal(s->pos, "sloppy0: unsupported statement");
  }
}

static void gen_block_stmts(Node *b) {
  for (int i = 0; i < b->list.len; i++) gen_stmt(b->list.data[i]);
}

// ---------------- functions ----------------
static void begin_fn(FnInst *f) {
  curfn = f;
  frame = 0;
  nscopes = 0; nloops = 0; ntlists = 0;
  pushdepth = 0;
  ret_label = newlabel();
}

static void assign_param_offsets(FnInst *f, int hidden) {
  int n = hidden + f->np;
  // hidden: sret (if aggregate ret), env (if has_env)
  int k = 0;
  bool sret = vclass(f->ret) == VC_AGG;
  if (sret) { sret_off_slot = 16 + 8 * (n - 1 - k); k++; }
  if (f->has_env) { env_off_slot = 16 + 8 * (n - 1 - k); k++; }
  for (int i = 0; i < f->np; i++) {
    if (f->params && f->params[i]) f->params[i]->offset = 16 + 8 * (n - 1 - k);
    k++;
  }
}

static void emit_fn_text(FnInst *f, Buf *body) {
  int fs = (frame + 15) & ~15;
  L("  .text");
  L("  .globl %s", fn_sym(f));
  L("%s:", fn_sym(f));
  E("push rbp"); E("mov rbp, rsp");
  if (fs) {
    E("sub rsp, %d", fs);
    E("mov rdi, rsp"); E("mov rcx, %d", fs / 8); E("xor eax, eax"); E("rep stosq");
  }
  append_buf(body);
  L(".L%d:", ret_label);
  Type *rt = prune(f->ret);
  if (vclass(rt) == VC_INT) E("mov rax, qword ptr [rbp%+d]", ret_slot);
  else if (vclass(rt) == VC_FLT) { if (is_f32(rt)) E("movss xmm0, dword ptr [rbp%+d]", ret_slot); else E("movsd xmm0, qword ptr [rbp%+d]", ret_slot); }
  else if (vclass(rt) == VC_AGG) E("mov rax, qword ptr [rbp%+d]", sret_off_slot);
  E("mov rsp, rbp"); E("pop rbp"); E("ret");
}

static void gen_fn(FnInst *f) {
  if (f->decl && (f->decl->flags & NF_EXTERN)) return;
  begin_fn(f);
  int hidden = (vclass(f->ret) == VC_AGG ? 1 : 0) + (f->has_env ? 1 : 0);
  if (f->kind == FK_LAMBDA) env_layout(f);
  assign_param_offsets(f, hidden);
  ret_slot = alloc_slot(8, 8);
  // locals
  for (int i = 0; i < f->locals.len; i++) {
    Local *l = f->locals.data[i];
    if (l->flags & (LF_PARAM | LF_CAPTURE | LF_ALIAS)) continue;
    if (l->flags & LF_BYREF) { l->offset = alloc_slot(8, 8); continue; }
    l->offset = alloc_slot(tsize(l->type), talign(l->type));
  }
  Buf *body = push_buf();
  scope_push();
  Node *b = f->body;
  if (f->kind == FK_INIT) {
    gen_block_stmts(b);
  } else {
    for (int i = 0; i < b->list.len; i++) {
      Node *s = b->list.data[i];
      if (i == b->list.len - 1 && b->aux && vclass(f->ret) != VC_VOID) {
        Node r = {0}; r.kind = N_RETURN; r.a = s->a; r.pos = s->pos;
        gen_return(&r);
        continue;
      }
      gen_stmt(s);
    }
  }
  scope_pop();
  pop_buf();
  emit_fn_text(f, body);
}

// thunk for named function used as a value: (sret?, env, args...) -> f(sret?, args...)
static void gen_thunk(const char *sym, FnInst *f) {
  bool sret = vclass(f->ret) == VC_AGG;
  int n = (sret ? 1 : 0) + 1 + f->np;
  L("  .text");
  L("%s:", sym);
  E("push rbp"); E("mov rbp, rsp");
  for (int k = 0; k < n; k++) {
    if (k == (sret ? 1 : 0)) continue; // skip env
    E("push qword ptr [rbp+%d]", 16 + 8 * (n - 1 - k));
  }
  E("call %s", fn_sym(f));
  E("mov rsp, rbp"); E("pop rbp"); E("ret");
}

static void gen_partial_thunk(FnInst *th) {
  Node *e = th->partial;
  FnInst *target = e->sym;
  int offs[64];
  partial_layout(e, offs);
  bool sret = vclass(th->ret) == VC_AGG;
  int n = (sret ? 1 : 0) + 1 + th->np;
  int envk = sret ? 1 : 0;
  L("  .text");
  L("%s:", fn_sym(th));
  E("push rbp"); E("mov rbp, rsp");
  E("mov r11, qword ptr [rbp+%d]", 16 + 8 * (n - 1 - envk)); // env
  int pushes = 0;
  if (sret) { E("push qword ptr [rbp+%d]", 16 + 8 * (n - 1)); pushes++; }
  if (e->aux == 1) { E("push qword ptr [r11+24]"); pushes++; } // callee closure env
  int hk = 0;
  Type *ft = target ? NULL : prune(e->a->type);
  for (int i = 0; i < e->list.len; i++) {
    Node *a = e->list.data[i];
    if (a->kind == N_HOLE) {
      int k = (sret ? 1 : 0) + 1 + hk;
      E("push qword ptr [rbp+%d]", 16 + 8 * (n - 1 - k));
      hk++;
    } else {
      Type *pt = target ? target->ptypes[i] : ft->args[i];
      if (vclass(pt) == VC_AGG) { E("lea rax, [r11+%d]", offs[i]); E("push rax"); }
      else E("push qword ptr [r11+%d]", offs[i]);
    }
    pushes++;
    E("mov r11, qword ptr [rbp+%d]", 16 + 8 * (n - 1 - envk));
  }
  if (target) E("call %s", fn_sym(target));
  else { E("mov r11, qword ptr [rbp+%d]", 16 + 8 * (n - 1 - envk)); E("call qword ptr [r11+16]"); }
  E("mov rsp, rbp"); E("pop rbp"); E("ret");
}

// ---------------- helpers ----------------
static void hdr(const char *sym) { L("  .text"); L("%s:", sym); E("push rbp"); E("mov rbp, rsp"); }
static void ftr(void) { E("mov rsp, rbp"); E("pop rbp"); E("ret"); }

static void foreach_field(Type *t, void (*fn)(Type *ft, int off, void *ud), void *ud) {
  t = prune(t); layout(t);
  if (t->kind == TY_STRUCT) for (int i = 0; i < t->st->nfields; i++) fn(t->st->fields[i].type, t->st->fields[i].offset, ud);
  else if (t->kind == TY_TUPLE) {
    int off = 0;
    for (int i = 0; i < t->nargs; i++) { Type *el = prune(t->args[i]); off = (off + talign(el) - 1) & ~(talign(el) - 1); fn(el, off, ud); off += tsize(el); }
  }
}

static void drop_field(Type *ft, int off, void *ud) {
  (void)ud;
  if (!is_managed(ft)) return;
  E("mov rax, qword ptr [rbp+16]"); if (off) E("add rax, %d", off);
  drop_at_rax(ft);
}
static void copy_field(Type *ft, int off, void *ud) {
  (void)ud;
  if (!is_managed(ft)) return;
  E("mov rax, qword ptr [rbp+16]"); if (off) E("add rax, %d", off);
  if (vclass(ft) == VC_INT) { E("mov rax, qword ptr [rax]"); retain_rax(); }
  else copy_at_rax(ft);
}

static void gen_helper(Helper *h) {
  Type *t = h->t;
  pushdepth = 0;
  switch (h->kind) {
  case H_RELPLAIN:
    hdr(h->sym);
    E("mov rax, qword ptr [rbp+16]");
    E("test rax, rax"); E("jz 1f"); E("mov rcx, qword ptr [rax]"); E("test rcx, rcx"); E("jle 1f");
    E("dec rcx"); E("mov qword ptr [rax], rcx"); E("jnz 1f");
    E("push rax"); E("call %s", fn_sym(runtime_fn("__free_obj"))); E("add rsp, 8");
    L("1:");
    ftr();
    break;
  case H_ARRREL: {
    hdr(h->sym);
    Type *et = t->elem;
    int lp = newlabel(), done = newlabel(), out = newlabel();
    E("mov rax, qword ptr [rbp+16]");
    E("test rax, rax"); E("jz .L%d", out); E("mov rcx, qword ptr [rax]"); E("test rcx, rcx"); E("jle .L%d", out);
    E("dec rcx"); E("mov qword ptr [rax], rcx"); E("jnz .L%d", out);
    E("push 0"); // index at [rbp-8]
    L(".L%d:", lp);
    E("mov rax, qword ptr [rbp+16]"); E("mov rcx, qword ptr [rbp-8]");
    E("cmp rcx, qword ptr [rax+8]"); E("jge .L%d", done);
    E("imul rcx, rcx, %d", tsize(et)); E("lea rax, [rax+rcx+24]");
    drop_at_rax(et);
    E("inc qword ptr [rbp-8]"); E("jmp .L%d", lp);
    L(".L%d:", done);
    E("push qword ptr [rbp+16]"); E("call %s", fn_sym(runtime_fn("__free_obj")));
    L(".L%d:", out);
    ftr();
    break;
  }
  case H_DROP: {
    hdr(h->sym);
    if (t->kind == TY_FN) {
      E("mov rax, qword ptr [rbp+16]"); E("mov rax, qword ptr [rax+8]");
      E("test rax, rax"); E("jz 1f"); E("mov rcx, qword ptr [rax]"); E("test rcx, rcx"); E("jle 1f");
      E("dec rcx"); E("mov qword ptr [rax], rcx"); E("jnz 1f");
      E("push rax"); E("call qword ptr [rax+8]"); E("add rsp, 8");
      L("1:");
    } else if (t->kind == TY_OPT) {
      E("mov rax, qword ptr [rbp+16]"); E("cmp byte ptr [rax+%d], 0", tsize(t->elem)); E("je 9f");
      drop_at_rax(t->elem);
      L("9:");
    } else if (t->kind == TY_ENUM) {
      StructInfo *si = t->st; layout(t);
      for (int v = 0; v < si->nvariants; v++) {
        Variant *var = &si->variants[v];
        bool any = false;
        for (int i = 0; i < var->nfields; i++) if (is_managed(var->fields[i].type)) any = true;
        if (!any) continue;
        int next = newlabel();
        E("mov rax, qword ptr [rbp+16]"); E("cmp dword ptr [rax], %d", v); E("jne .L%d", next);
        for (int i = 0; i < var->nfields; i++) drop_field(var->fields[i].type, var->fields[i].offset, NULL);
        L(".L%d:", next);
      }
    } else foreach_field(t, drop_field, NULL);
    ftr();
    break;
  }
  case H_COPY: {
    hdr(h->sym);
    if (t->kind == TY_FN) {
      E("mov rax, qword ptr [rbp+16]"); E("mov rax, qword ptr [rax+8]"); retain_rax();
    } else if (t->kind == TY_OPT) {
      E("mov rax, qword ptr [rbp+16]"); E("cmp byte ptr [rax+%d], 0", tsize(t->elem)); E("je 9f");
      if (vclass(t->elem) == VC_INT) { E("mov rax, qword ptr [rax]"); retain_rax(); } else copy_at_rax(t->elem);
      L("9:");
    } else if (t->kind == TY_ENUM) {
      StructInfo *si = t->st; layout(t);
      for (int v = 0; v < si->nvariants; v++) {
        Variant *var = &si->variants[v];
        bool any = false;
        for (int i = 0; i < var->nfields; i++) if (is_managed(var->fields[i].type)) any = true;
        if (!any) continue;
        int next = newlabel();
        E("mov rax, qword ptr [rbp+16]"); E("cmp dword ptr [rax], %d", v); E("jne .L%d", next);
        for (int i = 0; i < var->nfields; i++) copy_field(var->fields[i].type, var->fields[i].offset, NULL);
        L(".L%d:", next);
      }
    } else foreach_field(t, copy_field, NULL);
    ftr();
    break;
  }
  case H_ARRUNIQ: {
    // arg: address of array slot
    hdr(h->sym);
    Type *et = t->elem;
    E("mov rax, qword ptr [rbp+16]"); E("mov rax, qword ptr [rax]");
    E("test rax, rax"); E("jz 9f"); E("cmp qword ptr [rax], 1"); E("je 9f");
    E("push rax"); E("push %d", tsize(et)); E("call %s", fn_sym(runtime_fn("__arr_clone"))); E("add rsp, 16");
    E("mov rcx, qword ptr [rbp+16]"); E("mov qword ptr [rcx], rax");
    if (is_managed(et)) {
      int lp = newlabel(), done = newlabel();
      E("push 0");
      L(".L%d:", lp);
      E("mov rax, qword ptr [rbp+16]"); E("mov rax, qword ptr [rax]"); E("mov rcx, qword ptr [rbp-8]");
      E("cmp rcx, qword ptr [rax+8]"); E("jge .L%d", done);
      E("imul rcx, rcx, %d", tsize(et)); E("lea rax, [rax+rcx+24]");
      if (vclass(et) == VC_INT) { E("mov rax, qword ptr [rax]"); retain_rax(); } else copy_at_rax(et);
      E("inc qword ptr [rbp-8]"); E("jmp .L%d", lp);
      L(".L%d:", done);
    }
    L("9:");
    ftr();
    break;
  }
  case H_ENVDROP: {
    FnInst *f = h->p;
    hdr(h->sym);
    if (f->kind == FK_PARTIAL) {
      Node *e = f->partial;
      int offs[64];
      partial_layout(e, offs);
      if (e->aux == 1) { E("mov rax, qword ptr [rbp+16]"); E("add rax, 16"); drop_at_rax(e->a->type); }
      for (int i = 0; i < e->list.len; i++) {
        if (offs[i] < 0) continue;
        E("mov rax, qword ptr [rbp+16]"); E("add rax, %d", offs[i]);
        drop_at_rax(e->list.data[i]->type);
      }
    } else {
      env_layout(f);
      for (int i = 0; i < f->caps.len; i++) {
        Local *in = f->caps.data[i].inner;
        if (!is_managed(in->type)) continue;
        E("mov rax, qword ptr [rbp+16]"); E("add rax, %d", in->env_off);
        drop_at_rax(in->type);
      }
    }
    E("push qword ptr [rbp+16]"); E("call %s", fn_sym(runtime_fn("__free")));
    ftr();
    break;
  }
  case H_THUNK: gen_thunk(h->sym, h->p); break;
  case H_EQ: {
    // args: a (addr) at [rbp+24], b (addr) at [rbp+16]; returns rax 0/1
    hdr(h->sym);
    int fail = newlabel(), done = newlabel(), ok = newlabel();
    #define LOADA(off) do { E("mov rax, qword ptr [rbp+24]"); if (off) E("add rax, %d", off); } while (0)
    #define LOADB(off) do { E("mov rax, qword ptr [rbp+16]"); if (off) E("add rax, %d", off); } while (0)
    void eq_member(Type *ft, int off, int fail);
    if (t->kind == TY_STRUCT || t->kind == TY_TUPLE) {
      layout(t);
      if (t->kind == TY_STRUCT) for (int i = 0; i < t->st->nfields; i++) eq_member(t->st->fields[i].type, t->st->fields[i].offset, fail);
      else { int off = 0; for (int i = 0; i < t->nargs; i++) { Type *el = prune(t->args[i]); off = (off + talign(el) - 1) & ~(talign(el) - 1); eq_member(el, off, fail); off += tsize(el); } }
    } else if (t->kind == TY_OPT) {
      int inner = tsize(t->elem);
      LOADA(0); E("movzx ecx, byte ptr [rax+%d]", inner); LOADB(0); E("movzx edx, byte ptr [rax+%d]", inner);
      E("cmp ecx, edx"); E("jne .L%d", fail); E("test ecx, ecx"); E("jz .L%d", ok);
      eq_member(t->elem, 0, fail);
    } else if (t->kind == TY_ENUM) {
      StructInfo *si = t->st; layout(t);
      LOADA(0); E("mov ecx, dword ptr [rax]"); LOADB(0); E("cmp ecx, dword ptr [rax]"); E("jne .L%d", fail);
      for (int v = 0; v < si->nvariants; v++) {
        Variant *var = &si->variants[v];
        if (!var->nfields) continue;
        int next = newlabel();
        LOADA(0); E("cmp dword ptr [rax], %d", v); E("jne .L%d", next);
        for (int i = 0; i < var->nfields; i++) eq_member(var->fields[i].type, var->fields[i].offset, fail);
        E("jmp .L%d", ok);
        L(".L%d:", next);
      }
    } else if (t->kind == TY_ARRAY) {
      Type *et = t->elem;
      int lp = newlabel();
      E("sub rsp, 32");
      LOADA(0); E("mov rax, qword ptr [rax]"); E("mov qword ptr [rbp-8], rax");
      LOADB(0); E("mov rax, qword ptr [rax]"); E("mov qword ptr [rbp-16], rax");
      E("xor ecx, ecx"); E("mov rax, qword ptr [rbp-8]"); E("test rax, rax"); E("jz 1f"); E("mov rcx, qword ptr [rax+8]"); L("1:");
      E("xor edx, edx"); E("mov rax, qword ptr [rbp-16]"); E("test rax, rax"); E("jz 1f"); E("mov rdx, qword ptr [rax+8]"); L("1:");
      E("cmp rcx, rdx"); E("jne .L%d", fail);
      E("mov qword ptr [rbp-24], rcx"); E("mov qword ptr [rbp-32], 0");
      L(".L%d:", lp);
      E("mov rcx, qword ptr [rbp-32]"); E("cmp rcx, qword ptr [rbp-24]"); E("jge .L%d", ok);
      E("imul rcx, rcx, %d", tsize(et));
      E("mov rax, qword ptr [rbp-8]"); E("lea rax, [rax+rcx+24]"); E("push rax");
      E("mov rax, qword ptr [rbp-16]"); E("lea rax, [rax+rcx+24]"); E("push rax");
      E("call %s", helper(H_EQ, et, NULL)); E("add rsp, 16");
      E("test eax, eax"); E("jz .L%d", fail);
      E("inc qword ptr [rbp-32]"); E("jmp .L%d", lp);
    } else {
      eq_member(t, 0, fail);
    }
    L(".L%d:", ok);
    E("mov eax, 1"); E("jmp .L%d", done);
    L(".L%d:", fail);
    E("xor eax, eax");
    L(".L%d:", done);
    ftr();
    #undef LOADA
    #undef LOADB
    break;
  }
  case H_HASH: {
    hdr(h->sym);
    // FNV-style combination over members
    E("sub rsp, 16");
    E("movabs rax, 0xcbf29ce484222325"); E("mov qword ptr [rbp-8], rax");
    void hash_member(Type *ft, int off);
    if (t->kind == TY_STRUCT || t->kind == TY_TUPLE) {
      layout(t);
      if (t->kind == TY_STRUCT) for (int i = 0; i < t->st->nfields; i++) hash_member(t->st->fields[i].type, t->st->fields[i].offset);
      else { int off = 0; for (int i = 0; i < t->nargs; i++) { Type *el = prune(t->args[i]); off = (off + talign(el) - 1) & ~(talign(el) - 1); hash_member(el, off); off += tsize(el); } }
    } else hash_member(t, 0);
    E("mov rax, qword ptr [rbp-8]");
    ftr();
    break;
  }
  }
}

void eq_member(Type *ft, int off, int fail) {
  ft = prune(ft);
  int vc = vclass(ft);
  if (ft->kind == TY_STR) {
    E("mov rax, qword ptr [rbp+24]"); E("push qword ptr [rax+%d]", off);
    E("mov rax, qword ptr [rbp+16]"); E("push qword ptr [rax+%d]", off);
    E("call %s", fn_sym(runtime_fn("__str_eq"))); E("add rsp, 16");
    E("test eax, eax"); E("jz .L%d", fail);
    return;
  }
  if (vc == VC_INT && ft->kind != TY_ARRAY) {
    int sz = tsize(ft);
    const char *w = sz == 1 ? "byte" : sz == 2 ? "word" : sz == 4 ? "dword" : "qword";
    const char *r = sz == 1 ? "cl" : sz == 2 ? "cx" : sz == 4 ? "ecx" : "rcx";
    E("mov rax, qword ptr [rbp+24]"); E("mov %s, %s ptr [rax+%d]", r, w, off);
    E("mov rax, qword ptr [rbp+16]"); E("cmp %s, %s ptr [rax+%d]", r, w, off);
    E("jne .L%d", fail);
    return;
  }
  if (vc == VC_FLT) {
    bool f32 = is_f32(ft);
    E("mov rax, qword ptr [rbp+24]"); E(f32 ? "movss xmm0, dword ptr [rax+%d]" : "movsd xmm0, qword ptr [rax+%d]", off);
    E("mov rax, qword ptr [rbp+16]"); E(f32 ? "ucomiss xmm0, dword ptr [rax+%d]" : "ucomisd xmm0, qword ptr [rax+%d]", off);
    E("jne .L%d", fail); E("jp .L%d", fail);
    return;
  }
  if (ft->kind == TY_FN) {
    E("mov rax, qword ptr [rbp+24]"); E("mov rcx, qword ptr [rax+%d]", off);
    E("mov rax, qword ptr [rbp+16]"); E("cmp rcx, qword ptr [rax+%d]", off); E("jne .L%d", fail);
    return;
  }
  // aggregate or array: call helper with member addresses
  E("mov rax, qword ptr [rbp+24]"); E("add rax, %d", off); E("push rax");
  E("mov rax, qword ptr [rbp+16]"); E("add rax, %d", off); E("push rax");
  E("call %s", helper(H_EQ, ft, NULL)); E("add rsp, 16");
  E("test eax, eax"); E("jz .L%d", fail);
}

void hash_member(Type *ft, int off) {
  ft = prune(ft);
  int vc = vclass(ft);
  if (ft->kind == TY_STR) {
    E("mov rax, qword ptr [rbp+16]"); E("push qword ptr [rax+%d]", off);
    E("call %s", fn_sym(runtime_fn("__str_hash"))); E("add rsp, 8");
  } else if (vc == VC_INT && ft->kind != TY_ARRAY) {
    E("mov rax, qword ptr [rbp+16]"); E("add rax, %d", off); load_rax(ft);
  } else if (vc == VC_FLT) {
    E("mov rax, qword ptr [rbp+16]"); E("mov rax, qword ptr [rax+%d]", off);
    if (is_f32(ft)) E("mov eax, eax");
  } else if (vc == VC_AGG && ft->kind != TY_FN) {
    E("mov rax, qword ptr [rbp+16]"); E("add rax, %d", off); E("push rax");
    E("call %s", helper(H_HASH, ft, NULL)); E("add rsp, 8");
  } else return;
  E("xor rax, qword ptr [rbp-8]");
  E("movabs rcx, 0x100000001b3"); E("imul rax, rcx");
  E("mov rcx, rax"); E("shr rcx, 29"); E("xor rax, rcx");
  E("mov qword ptr [rbp-8], rax");
}

// ---------------- program ----------------
void gen_program(FILE *out) {
  OUT = out;
  Buf text = {0};
  bufstack[0] = &text; nbuf = 1;
  fprintf(out, "  .intel_syntax noprefix\n");
  for (int i = 0; i < prog.fns.len; i++) {
    FnInst *f = prog.fns.data[i];
    if (f->state != 2 && f->kind != FK_PARTIAL) continue;
    if (f->kind == FK_PARTIAL) { gen_partial_thunk(f); continue; }
    gen_fn(f);
  }
  for (; helpers_done < helpers.len; helpers_done++) {
    Helper h = helpers.data[helpers_done];
    gen_helper(&h);
  }
  // entry point
  L("  .text");
  L("  .globl _start");
  L("_start:");
  E("mov qword ptr [rip+__sloppy_sp0], rsp");
  E("and rsp, -16");
  for (int i = 0; i < prog.init_stmts.len; i++) E("call %s", fn_sym(prog.init_stmts.data[i]->sym));
  if (prog.main_fn) E("call %s", fn_sym(prog.main_fn));
  E("xor edi, edi"); E("mov eax, 231"); E("syscall");
  fwrite(text.p, 1, text.len, out);
  fprintf(out, "  .section .rodata\n");
  if (rodata.len) fwrite(rodata.p, 1, rodata.len, out);
  fprintf(out, "  .bss\n  .balign 16\n__sloppy_sp0: .zero 8\n");
  for (int i = 0; i < prog.globals.len; i++) {
    Global *g = prog.globals.data[i];
    if (g->state != 2 || !g->type) continue;
    int sz = tsize(g->type); if (sz < 8) sz = 8;
    fprintf(out, "  .balign %d\n%s: .zero %d\n", talign(g->type) < 8 ? 8 : talign(g->type), g->sym.p, sz);
  }
  (void)databuf;
}
