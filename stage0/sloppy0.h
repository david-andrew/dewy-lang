// sloppy0 - bootstrap compiler for the Sloppy language.
// Implements the core language and emits x86-64 GNU assembly (Intel syntax).
// Only used to build the self-hosted compiler.
#ifndef SLOPPY0_H
#define SLOPPY0_H
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdarg.h>

typedef struct Type Type;
typedef struct Node Node;
typedef struct Module Module;
typedef struct FnInst FnInst;
typedef struct Local Local;
typedef struct Global Global;
typedef struct StructInfo StructInfo;
typedef struct Scope Scope;

// ---------- util ----------
typedef struct { const char *p; int len; } Str;
#define S(lit) ((Str){lit, sizeof(lit) - 1})
void *arena_alloc(size_t n);
char *xstrndup(const char *s, int n);
char *fmt(const char *f, ...);
bool str_eq(Str a, Str b);
bool str_eqc(Str a, const char *c);
Str intern(const char *p, int len);
Str internc(const char *c);
char *read_file(const char *path, int *len);

#define VEC(T) struct { T *data; int len, cap; }
#define vpush(v, x) do { if ((v).len == (v).cap) { (v).cap = (v).cap ? (v).cap * 2 : 8; (v).data = realloc((v).data, sizeof(*(v).data) * (v).cap); } (v).data[(v).len++] = (x); } while (0)

typedef struct { int file, line, col; } Pos;
typedef struct { const char *path; const char *dir; char *src; int len; } SrcFile;
extern VEC(SrcFile) g_files;
_Noreturn void fatal(Pos p, const char *f, ...);
void warn_at(Pos p, const char *f, ...);

// ---------- lexer ----------
typedef enum {
  TK_EOF, TK_NEWLINE, TK_INDENT, TK_DEDENT,
  TK_IDENT, TK_INT, TK_FLOAT, TK_STR,
  TK_FN, TK_STRUCT, TK_ENUM, TK_IF, TK_ELSE, TK_FOR, TK_IN, TK_WHILE, TK_BREAK, TK_CONTINUE,
  TK_RETURN, TK_MATCH, TK_IMPORT, TK_AS, TK_CONST, TK_TRUE, TK_FALSE, TK_NONE, TK_NULL,
  TK_AND, TK_OR, TK_NOT, TK_MUT, TK_WHEN, TK_DEFER, TK_EXTERN, TK_TEST, TK_BUILD, TK_USE, TK_PASS,
  TK_LOOP, TK_LET, TK_XOR, TK_IS,
  TK_LPAREN, TK_RPAREN, TK_LBRACK, TK_RBRACK, TK_LBRACE, TK_RBRACE,
  TK_COMMA, TK_COLON, TK_SEMI, TK_DOT, TK_DOTDOT, TK_DOTDOTEQ, TK_ARROW, TK_DECL,
  TK_ASSIGN, TK_PLUSEQ, TK_MINUSEQ, TK_STAREQ, TK_SLASHEQ, TK_PERCENTEQ, TK_AMPEQ, TK_PIPEEQ,
  TK_CARETEQ, TK_SHLEQ, TK_SHREQ,
  TK_PLUS, TK_MINUS, TK_STAR, TK_SLASH, TK_PERCENT, TK_AMP, TK_PIPE, TK_CARET, TK_TILDE,
  TK_SHL, TK_SHR, TK_EQ, TK_NE, TK_LT, TK_LE, TK_GT, TK_GE, TK_QUESTION, TK_QQ, TK_BANG, TK_AT,
  TK__COUNT
} TokKind;

enum { STRF_RAW = 1, STRF_TRIPLE = 2, INTF_CHAR = 4, TF_SPACE = 8 };  // TF_SPACE: whitespace before the token

typedef struct {
  uint8_t kind, flags;
  Pos pos;
  const char *start; int len;   // source text (for strings: contents between quotes)
  union { uint64_t ival; double fval; };
} Token;

Token *lex_file(int file, int *ntok);
const char *tok_name(int k);

// ---------- AST ----------
typedef enum {
  // expressions
  N_INT, N_FLOAT, N_STR, N_BOOL, N_NONE, N_NULL, N_IDENT, N_FIELD, N_DOTNAME, N_CALL, N_INDEX,
  N_UNARY, N_BINARY, N_AND, N_OR, N_NOT, N_COALESCE, N_UNWRAP, N_LAMBDA, N_ARRAY, N_MAP,
  N_TUPLE, N_IF, N_MATCH, N_CAST, N_RANGE, N_ADDR, N_HOLE, N_NAMEDARG, N_PAIR, N_BLOCK,
  N_IFLET, N_WHILELET,
  // checker-produced expressions
  N_CONV, N_FNREF, N_PARTIAL, N_SEQ, N_INTRINSIC, N_TYPEVAL,
  // statements
  N_VARDECL, N_ASSIGN, N_EXPRSTMT, N_WHILE, N_FOR, N_RETURN, N_BREAK, N_CONTINUE, N_DEFER,
  N_WHEN, N_ARM,
  // declarations
  N_FN, N_PARAM, N_STRUCT, N_ENUM, N_VARIANT, N_CONST, N_IMPORT, N_TEST, N_BUILD,
  // types
  N_TNAME, N_TARRAY, N_TMAP, N_TTUPLE, N_TOPT, N_TPTR, N_TFN,
  // patterns
  N_PWILD, N_PLIT, N_PRANGE, N_PVARIANT,
  N__COUNT
} NodeKind;

typedef VEC(Node *) NodeList;

enum { // node flags
  NF_MUT = 1,        // mut param / for mut
  NF_INCLUSIVE = 2,  // ..=
  NF_EXTERN = 4,
  NF_PUB = 8,
  NF_STMT = 16,      // if/match used as statement
  NF_TERMINATED = 32,
  NF_GENERIC = 64,
  NF_CHECKED = 128,
  NF_LITERAL = 256,  // untyped literal (can adapt to context)
  NF_TYPED = 512,
  NF_CONSTVAL = 1024,
  NF_GLOBAL = 2048,  // top-level variable declaration (global)
  NF_BARE = 4096,    // a..b not (yet) closed by brackets
  NF_CHARLIKE = 8192, // one-character string literal (may stand for its character code)
};

struct Node {
  uint16_t kind, op;
  uint32_t flags;
  Pos pos;
  Type *type;
  Node *a, *b, *c, *d;
  NodeList list, list2;
  Str name;
  int64_t ival;
  double fval;
  Str sval;
  void *sym;      // resolved symbol (Local*, Global*, FnInst*, ...)
  int aux, aux2;  // misc ints (field index, intrinsic id, conv kind ...)
  Module *mod;    // module this node belongs to (decls)
};

Node *new_node(int kind, Pos pos);
Node *clone_node(Node *n);
typedef struct { Node *build; NodeList decls; NodeList stmts; } ParseResult;
void parse_file(int file, NodeList *decls);

// ---------- types ----------
typedef enum {
  TY_VOID, TY_BOOL, TY_INT, TY_FLOAT, TY_STR, TY_ARRAY, TY_PTR, TY_FN, TY_STRUCT, TY_ENUM,
  TY_TUPLE, TY_OPT, TY_VAR, TY_PARAM, TY_NULL, TY_RANGE, TY_MODULE, TY_TYPE, TY_NONE_LIT,
} TypeKind;

struct Type {
  uint8_t kind, bits, sign;
  bool has_var, laid_out, managed;
  int size, align;
  Type *elem;            // array/ptr/opt elem; fn return
  Type **args; int nargs; // fn params, tuple elems, struct type args
  StructInfo *st;
  Type *ref;             // TY_VAR binding
  int id;                // TY_PARAM index / var id
  Module *mod;           // TY_MODULE
  uint32_t mutmask;      // TY_FN: which params are mut
};

typedef struct { Str name; Type *type; int offset; Node *defval; } Field;
typedef struct { Str name; Field *fields; int nfields; int tag; int64_t value; } Variant;

struct StructInfo {
  Node *decl;
  Type **targs; int ntargs;
  Field *fields; int nfields;
  Variant *variants; int nvariants;
  int payload_off;
  bool simple_enum;
  bool resolving, resolved;
  Type *type;
  Str mangled;
};

extern Type *t_void, *t_bool, *t_int, *t_i8, *t_i16, *t_i32, *t_u8, *t_u16, *t_u32, *t_u64,
  *t_float, *t_f32, *t_str, *t_null, *t_range, *t_none, *t_rawptr;

Type *mk_array(Type *e);
Type *mk_ptr(Type *e);
Type *mk_opt(Type *e);
Type *mk_fn(Type **params, int n, Type *ret, uint32_t mutmask);
Type *mk_tuple(Type **elems, int n);
Type *mk_var(void);
Type *mk_param(int idx);
Type *prune(Type *t);
bool type_eq(Type *a, Type *b);
bool unify(Type *a, Type *b);
void layout(Type *t);
const char *type_str(Type *t);
bool is_managed(Type *t);
bool is_aggregate(Type *t);  // lives in memory (passed by address)
bool is_int(Type *t);
bool is_float(Type *t);
bool is_numeric(Type *t);
Type *zonk(Type *t);

// ---------- semantic ----------
enum { S_LOCAL, S_GLOBAL, S_FNS, S_STRUCT, S_ENUM, S_CONST, S_MODULE, S_TYPE, S_BUILTIN };

typedef struct Sym { Str name; int kind; void *p; struct Sym *next_overload; Node *decl; } Sym;

struct Scope {
  Scope *parent;
  Scope **uses; int nuses;   // `use`d module scopes (module scopes only)
  Sym *syms; int n, cap;
  int kind;               // 0 module, 1 fn, 2 block
  struct FnCtx *fn;
};

struct Module {
  Str name;
  int file;
  const char *dir;
  Scope *scope;
  NodeList decls;
  bool is_prelude, is_main;
  int order;
};

enum { LF_PARAM = 1, LF_MUTPARAM = 2, LF_CAPTURE = 4, LF_ALIAS = 8, LF_ASSIGNED = 16, LF_BYREF = 32, LF_CAPTURED = 64 };
struct Local {
  Str name;
  Type *type;
  int flags;
  int offset;        // frame offset (codegen)
  int env_off;       // offset in closure env (captures)
  Node *alias;       // LF_ALIAS: place expression this name stands for
  FnInst *fn;
  Pos pos;
};

struct Global {
  Str name;
  Type *type;
  Node *decl;        // N_VARDECL
  Module *mod;
  Str sym;
  int state;         // 0 unchecked, 1 checking, 2 done
  bool is_const;
  Node *init;
};

typedef struct { Local *outer; Local *inner; } Capture;

enum { FK_NORMAL, FK_LAMBDA, FK_THUNK, FK_PARTIAL, FK_INIT };

struct FnInst {
  Node *decl;            // N_FN or N_LAMBDA
  Node *body;
  Type **targs; int ntargs;
  Type **ptypes; int np;
  Local **params;
  Type *ret;
  Str sym;
  int state;             // 0 new, 1 checking, 2 done
  int kind;
  bool has_env;          // takes closure env as first hidden arg
  VEC(Capture) caps;
  int env_size;
  Module *mod;
  FnInst *target;        // thunk/partial target
  Node *partial;         // partial call node
  VEC(Local *) locals;
  bool emitted;
  bool aux_void;
  Type *fntype;
};

typedef struct {
  VEC(FnInst *) fns;
  VEC(Global *) globals;
  VEC(Node *) init_stmts;     // top-level statements (in order)
  FnInst *main_fn, *update_fn, *draw_fn;
  Node *build;
} Program;

extern Program prog;
extern int g_target_wasm;
extern const char *g_lib_dir;

void check_program(const char *main_path);
FnInst *fn_value_thunk(FnInst *f);

// intrinsics
enum {
  IN_NONE, IN_LEN, IN_PUSH, IN_POP, IN_INSERT, IN_REMOVE, IN_CLEAR, IN_RESERVE, IN_SLICE,
  IN_SYSCALL, IN_MEMCPY, IN_MEMSET, IN_SIZEOF, IN_ARRDATA, IN_PANIC, IN_ASSERT, IN_PRINT,
  IN_STR, IN_EMBED, IN_STRDATA, IN_FROM_BYTES, IN_TO_BYTES, IN_ARGV, IN_ENVP, IN_SETLEN,
  IN_TRUNCATE, IN_RESIZE, IN_FMT, IN_EQ, IN_CMP, IN_HASH, IN_ALIGNOF, IN_UNREACHABLE,
  IN_ARRCAP, IN_FMT_STRUCT, IN_SQRT, IN_FBITS, IN_FFROMBITS, IN_ATOMIC_ADD, IN_ATOMIC_CAS,
  IN_STACK_PTR, IN_FILL, IN_FMT_ELEM, IN_CPU_FEATURES,
};

// conversions
enum { CV_NONE, CV_INT, CV_INT2FLOAT, CV_FLOAT2INT, CV_FLOAT, CV_OPT, CV_PTR, CV_BITS, CV_FN2CLOS };

// codegen
void gen_program(FILE *out);

#endif
