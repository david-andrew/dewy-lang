#include "sloppy0.h"

static const char *tok_names[TK__COUNT] = {
  "end of file", "newline", "indent", "dedent", "identifier", "integer", "float", "string",
  "fn", "struct", "enum", "if", "else", "for", "in", "while", "break", "continue", "return",
  "match", "import", "as", "const", "true", "false", "none", "null", "and", "or", "not", "mut",
  "when", "defer", "extern", "test", "build", "use", "pass", "loop", "let", "xor", "is",
  "(", ")", "[", "]", "{", "}", ",", ":", ";", ".", "..", "..=", "->", ":=",
  "=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=",
  "+", "-", "*", "/", "%", "&", "|", "^", "~", "<<", ">>", "==", "!=", "<", "<=", ">", ">=",
  "?", "??", "!", "@",
};
const char *tok_name(int k) { return tok_names[k]; }

static struct { const char *s; int k; } keywords[] = {
  {"fn", TK_FN}, {"struct", TK_STRUCT}, {"enum", TK_ENUM}, {"if", TK_IF}, {"else", TK_ELSE},
  {"for", TK_FOR}, {"in", TK_IN}, {"while", TK_WHILE}, {"break", TK_BREAK},
  {"continue", TK_CONTINUE}, {"return", TK_RETURN}, {"match", TK_MATCH}, {"import", TK_IMPORT},
  {"as", TK_AS}, {"const", TK_CONST}, {"true", TK_TRUE}, {"false", TK_FALSE}, {"none", TK_NONE},
  {"null", TK_NULL}, {"and", TK_AND}, {"or", TK_OR}, {"not", TK_NOT}, {"mut", TK_MUT},
  {"when", TK_WHEN}, {"defer", TK_DEFER}, {"extern", TK_EXTERN}, {"test", TK_TEST},
  {"build", TK_BUILD}, {"use", TK_USE}, {"pass", TK_PASS},
  {"loop", TK_LOOP}, {"let", TK_LET}, {"xor", TK_XOR}, {"is", TK_IS},
};

typedef struct { bool block; int base; } Ctx;

typedef struct {
  int file;
  const char *src, *p, *line_start;
  int line;
  VEC(Token) toks;
  int indents[256]; int nind;
  Ctx ctx[256]; int nctx;
  int line_indent;
} Lexer;

static Pos lpos(Lexer *L, const char *at) { return (Pos){L->file, L->line, (int)(at - L->line_start) + 1}; }

static void emit(Lexer *L, int kind, const char *start, int len) {
  Token t = {0};
  t.kind = kind; t.pos = lpos(L, start); t.start = start; t.len = len;
  if (start > L->src && (start[-1] == ' ' || start[-1] == '\t' || start[-1] == '\n' || start[-1] == '\r')) t.flags = TF_SPACE;
  vpush(L->toks, t);
}
static int last_kind(Lexer *L) { return L->toks.len ? L->toks.data[L->toks.len - 1].kind : TK_NEWLINE; }
static void emit_newline(Lexer *L) {
  int k = last_kind(L);
  if (k != TK_NEWLINE && k != TK_INDENT && k != TK_DEDENT) emit(L, TK_NEWLINE, L->p, 0);
}

// Measure indentation of the line starting at p; returns -1 for blank/comment lines.
static int measure(const char *p, const char **out) {
  int ind = 0;
  for (;; p++) {
    if (*p == ' ') ind++;
    else if (*p == '\t') ind = (ind + 4) & ~3;
    else if (*p == '\r') continue;
    else break;
  }
  *out = p;
  if (*p == '\n' || *p == '#' || *p == 0) return -1;
  return ind;
}

// Handle the start of a line in block context. p points at first char of line.
static void line_start(Lexer *L) {
  for (;;) {
    const char *q;
    int ind = measure(L->p, &q);
    if (*q == 0) { L->p = q; return; }
    if (ind < 0) { // blank or comment line: skip it
      while (*q && *q != '\n') q++;
      if (*q == '\n') { q++; L->line++; L->line_start = q; }
      L->p = q;
      continue;
    }
    L->p = q;
    L->line_indent = ind;
    Ctx *c = &L->ctx[L->nctx - 1];
    if (!c->block) return;
    int top = L->indents[L->nind - 1];
    if (ind > top) {
      if (L->nind >= 255) fatal(lpos(L, q), "indentation too deep");
      L->indents[L->nind++] = ind;
      emit(L, TK_INDENT, q, 0);
    } else {
      while (L->nind > c->base && ind < L->indents[L->nind - 1]) {
        L->nind--;
        emit(L, TK_DEDENT, q, 0);
      }
      if (L->nind == c->base && L->nctx > 1) {
        // nested block inside brackets ended
        L->nind--; L->nctx--;
        return;
      }
      if (ind != L->indents[L->nind - 1]) fatal(lpos(L, q), "inconsistent indentation");
    }
    return;
  }
}

static void close_block_ctx(Lexer *L, const char *at) {
  while (L->nctx > 1 && L->ctx[L->nctx - 1].block) {
    Ctx *c = &L->ctx[L->nctx - 1];
    emit_newline(L);
    while (L->nind > c->base) { L->nind--; emit(L, TK_DEDENT, at, 0); }
    L->nind--; L->nctx--;
  }
}

static bool is_ident_start(int c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_' || c >= 0x80; }
static bool is_ident_char(int c) { return is_ident_start(c) || (c >= '0' && c <= '9'); }

static void lex_number(Lexer *L) {
  const char *s = L->p;
  uint64_t v = 0;
  bool is_float = false;
  if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X' || s[1] == 'b' || s[1] == 'B' || s[1] == 'o' || s[1] == 'O')) {
    int base = (s[1] == 'x' || s[1] == 'X') ? 16 : (s[1] == 'b' || s[1] == 'B') ? 2 : 8;
    const char *p = s + 2;
    for (;; p++) {
      int c = *p, d;
      if (c == '_') continue;
      if (c >= '0' && c <= '9') d = c - '0';
      else if (c >= 'a' && c <= 'f') d = c - 'a' + 10;
      else if (c >= 'A' && c <= 'F') d = c - 'A' + 10;
      else break;
      if (d >= base) break;
      v = v * base + d;
    }
    L->p = p;
  } else {
    const char *p = s;
    char buf[128]; int n = 0;
    while ((*p >= '0' && *p <= '9') || *p == '_') { if (*p != '_' && n < 120) buf[n++] = *p; p++; }
    if (*p == '.' && p[1] >= '0' && p[1] <= '9') {
      is_float = true; buf[n++] = *p++;
      while ((*p >= '0' && *p <= '9') || *p == '_') { if (*p != '_' && n < 120) buf[n++] = *p; p++; }
    }
    if ((*p == 'e' || *p == 'E') && ((p[1] >= '0' && p[1] <= '9') || ((p[1] == '-' || p[1] == '+') && p[2] >= '0' && p[2] <= '9'))) {
      is_float = true; buf[n++] = *p++;
      if (*p == '-' || *p == '+') buf[n++] = *p++;
      while (*p >= '0' && *p <= '9') { if (n < 120) buf[n++] = *p; p++; }
    }
    buf[n] = 0;
    L->p = p;
    if (is_float) {
      emit(L, TK_FLOAT, s, p - s);
      L->toks.data[L->toks.len - 1].fval = strtod(buf, NULL);
      return;
    }
    for (int i = 0; i < n; i++) v = v * 10 + (buf[i] - '0');
  }
  if (is_ident_char(*L->p)) fatal(lpos(L, L->p), "invalid character in number literal");
  emit(L, TK_INT, s, L->p - s);
  L->toks.data[L->toks.len - 1].ival = v;
}

static void lex_string(Lexer *L, bool raw) {
  const char *s = L->p; // at opening quote
  char q = s[0];
  bool triple = q == '"' && s[1] == '"' && s[2] == '"';
  const char *p = s + (triple ? 3 : 1);
  const char *start = p;
  int depth = 0;
  for (;;) {
    if (*p == 0) fatal(lpos(L, s), "unterminated string");
    if (*p == '\n') { L->line++; L->line_start = p + 1; }
    if (depth == 0) {
      if (*p == '\\' && !raw) { p += 2; continue; }
      if (triple ? (p[0] == '"' && p[1] == '"' && p[2] == '"') : *p == q) break;
      if (!raw && *p == '{') { if (p[1] == '{') { p += 2; continue; } depth = 1; p++; continue; }
      p++;
    } else {
      if (*p == '{') depth++;
      else if (*p == '}') depth--;
      else if (*p == '"' || *p == '\'') { // nested string inside interpolation
        char nq = *p++;
        while (*p && *p != nq) { if (*p == '\\') p++; p++; }
      }
      p++;
    }
  }
  Token t = {0};
  t.kind = TK_STR; t.pos = lpos(L, s); t.start = start; t.len = p - start;
  t.flags = (raw ? STRF_RAW : 0) | (triple ? STRF_TRIPLE : 0);
  if (s > L->src && (s[-1] == ' ' || s[-1] == '\t' || s[-1] == '\n' || s[-1] == '\r')) t.flags |= TF_SPACE;
  // compute position based on start of string (line may have advanced for triple strings)
  vpush(L->toks, t);
  L->p = p + (triple ? 3 : 1);
}

Token *lex_file(int file, int *ntok) {
  Lexer L = {0};
  L.file = file;
  L.src = L.p = L.line_start = g_files.data[file].src;
  L.line = 1;
  L.indents[L.nind++] = 0;
  L.ctx[L.nctx++] = (Ctx){true, 1};
  line_start(&L);
  for (;;) {
    const char *p = L.p;
    int c = *p;
    if (c == 0) break;
    if (c == ' ' || c == '\t' || c == '\r') { L.p++; continue; }
    if (c == '\\' && p[1] == '\n') { L.p += 2; L.line++; L.line_start = L.p; continue; }
    if (c == '#') { while (*L.p && *L.p != '\n') L.p++; continue; }
    if (c == '\n') {
      L.p++; L.line++; L.line_start = L.p;
      if (L.ctx[L.nctx - 1].block) emit_newline(&L);
      line_start(&L);
      continue;
    }
    if (is_ident_start(c)) {
      if (c == 'r' && (p[1] == '"' || p[1] == '\'')) { L.p++; lex_string(&L, true); continue; }
      const char *s = p;
      while (is_ident_char(*p)) p++;
      L.p = p;
      int kind = TK_IDENT;
      for (size_t i = 0; i < sizeof keywords / sizeof *keywords; i++)
        if ((int)strlen(keywords[i].s) == p - s && memcmp(keywords[i].s, s, p - s) == 0) { kind = keywords[i].k; break; }
      emit(&L, kind, s, p - s);
      continue;
    }
    if (c >= '0' && c <= '9') { lex_number(&L); continue; }
    if (c == '"') { lex_string(&L, false); continue; }
    if (c == '\'') { lex_string(&L, false); continue; }
    // punctuation
    int k = -1, n = 1;
    char c1 = p[1];
    switch (c) {
    case '(': k = TK_LPAREN; break;
    case ')': k = TK_RPAREN; break;
    case '[': k = TK_LBRACK; break;
    case ']': k = TK_RBRACK; break;
    case '{': k = TK_LBRACE; break;
    case '}': k = TK_RBRACE; break;
    case ',': k = TK_COMMA; break;
    case ';': k = TK_SEMI; break;
    case '~': k = TK_TILDE; break;
    case '@': k = TK_AT; break;
    case ':': if (c1 == '=') { k = TK_DECL; n = 2; } else k = TK_COLON; break;
    case '.': if (c1 == '.') { if (p[2] == '=') { k = TK_DOTDOTEQ; n = 3; } else { k = TK_DOTDOT; n = 2; } } else k = TK_DOT; break;
    case '-': if (c1 == '>') { k = TK_ARROW; n = 2; } else if (c1 == '=') { k = TK_MINUSEQ; n = 2; } else k = TK_MINUS; break;
    case '+': if (c1 == '=') { k = TK_PLUSEQ; n = 2; } else k = TK_PLUS; break;
    case '*': if (c1 == '=') { k = TK_STAREQ; n = 2; } else k = TK_STAR; break;
    case '/': if (c1 == '=') { k = TK_SLASHEQ; n = 2; } else k = TK_SLASH; break;
    case '%': if (c1 == '=') { k = TK_PERCENTEQ; n = 2; } else k = TK_PERCENT; break;
    case '&': if (c1 == '=') { k = TK_AMPEQ; n = 2; } else k = TK_AMP; break;
    case '|': if (c1 == '=') { k = TK_PIPEEQ; n = 2; } else k = TK_PIPE; break;
    case '^': if (c1 == '=') { k = TK_CARETEQ; n = 2; } else k = TK_CARET; break;
    case '=': if (c1 == '=') { k = TK_EQ; n = 2; } else k = TK_ASSIGN; break;
    case '!': if (c1 == '=') { k = TK_NE; n = 2; } else k = TK_BANG; break;
    case '?': if (c1 == '?') { k = TK_QQ; n = 2; } else k = TK_QUESTION; break;
    case '<':
      if (c1 == '<') { if (p[2] == '=') { k = TK_SHLEQ; n = 3; } else { k = TK_SHL; n = 2; } }
      else if (c1 == '=') { k = TK_LE; n = 2; } else k = TK_LT;
      break;
    case '>':
      if (c1 == '>') { if (p[2] == '=') { k = TK_SHREQ; n = 3; } else { k = TK_SHR; n = 2; } }
      else if (c1 == '=') { k = TK_GE; n = 2; } else k = TK_GT;
      break;
    }
    if (k < 0) fatal(lpos(&L, p), "unexpected character '%c'", c);
    if (k == TK_RPAREN || k == TK_RBRACK || k == TK_RBRACE) {
      close_block_ctx(&L, p);
      if (L.nctx <= 1) fatal(lpos(&L, p), "unmatched '%c'", c);
      L.nctx--;
    }
    emit(&L, k, p, n);
    L.p += n;
    if (k == TK_LPAREN || k == TK_LBRACK || k == TK_LBRACE) {
      if (L.nctx >= 255) fatal(lpos(&L, p), "brackets nested too deeply");
      L.ctx[L.nctx++] = (Ctx){false, 0};
    }
    if (k == TK_COLON && !L.ctx[L.nctx - 1].block) {
      // ':' at end of line inside brackets opens an indented block
      const char *q = L.p;
      while (*q == ' ' || *q == '\t' || *q == '\r') q++;
      if (*q == '#') while (*q && *q != '\n') q++;
      if (*q == '\n') {
        L.indents[L.nind++] = L.line_indent;
        L.ctx[L.nctx++] = (Ctx){true, L.nind};
      }
    }
  }
  close_block_ctx(&L, L.p);
  if (L.nctx > 1) fatal(lpos(&L, L.p), "unclosed bracket at end of file");
  emit_newline(&L);
  while (L.nind > 1) { L.nind--; emit(&L, TK_DEDENT, L.p, 0); }
  emit(&L, TK_EOF, L.p, 0);
  *ntok = L.toks.len;
  return L.toks.data;
}
