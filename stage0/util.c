#include "sloppy0.h"

typeof(g_files) g_files;

static char *arena_cur, *arena_end;
void *arena_alloc(size_t n) {
  n = (n + 15) & ~(size_t)15;
  if (arena_cur + n > arena_end) {
    size_t sz = n > (1 << 22) ? n : (1 << 22);
    arena_cur = calloc(1, sz);
    arena_end = arena_cur + sz;
  }
  void *p = arena_cur;
  arena_cur += n;
  return p;
}

char *xstrndup(const char *s, int n) {
  char *p = arena_alloc(n + 1);
  memcpy(p, s, n);
  p[n] = 0;
  return p;
}

char *fmt(const char *f, ...) {
  char buf[4096];
  va_list ap;
  va_start(ap, f);
  int n = vsnprintf(buf, sizeof buf, f, ap);
  va_end(ap);
  return xstrndup(buf, n);
}

bool str_eq(Str a, Str b) { return a.len == b.len && (a.p == b.p || memcmp(a.p, b.p, a.len) == 0); }
bool str_eqc(Str a, const char *c) { int n = strlen(c); return a.len == n && memcmp(a.p, c, n) == 0; }

static Str *itab; static int itab_cap, itab_n;
static uint32_t hash_bytes(const char *p, int n) {
  uint32_t h = 2166136261u;
  for (int i = 0; i < n; i++) h = (h ^ (uint8_t)p[i]) * 16777619u;
  return h;
}
Str intern(const char *p, int len) {
  if (itab_n * 2 >= itab_cap) {
    int nc = itab_cap ? itab_cap * 2 : 4096;
    Str *nt = calloc(nc, sizeof(Str));
    for (int i = 0; i < itab_cap; i++) if (itab[i].p) {
      uint32_t h = hash_bytes(itab[i].p, itab[i].len) & (nc - 1);
      while (nt[h].p) h = (h + 1) & (nc - 1);
      nt[h] = itab[i];
    }
    free(itab); itab = nt; itab_cap = nc;
  }
  uint32_t h = hash_bytes(p, len) & (itab_cap - 1);
  while (itab[h].p) {
    if (itab[h].len == len && memcmp(itab[h].p, p, len) == 0) return itab[h];
    h = (h + 1) & (itab_cap - 1);
  }
  itab[h] = (Str){xstrndup(p, len), len};
  itab_n++;
  return itab[h];
}
Str internc(const char *c) { return intern(c, strlen(c)); }

char *read_file(const char *path, int *len) {
  FILE *f = fopen(path, "rb");
  if (!f) return NULL;
  fseek(f, 0, SEEK_END);
  long n = ftell(f);
  fseek(f, 0, SEEK_SET);
  char *buf = malloc(n + 2);
  if (fread(buf, 1, n, f) != (size_t)n) { fclose(f); return NULL; }
  buf[n] = '\n'; buf[n + 1] = 0;
  fclose(f);
  if (len) *len = n;
  return buf;
}

static void print_loc(Pos p) {
  if (p.file < 0 || p.file >= g_files.len) { fprintf(stderr, "<unknown>: "); return; }
  SrcFile *f = &g_files.data[p.file];
  fprintf(stderr, "%s:%d:%d: ", f->path, p.line, p.col);
}
static void print_line(Pos p) {
  if (p.file < 0 || p.file >= g_files.len) return;
  SrcFile *f = &g_files.data[p.file];
  const char *s = f->src; int line = 1;
  while (*s && line < p.line) { if (*s == '\n') line++; s++; }
  const char *e = s; while (*e && *e != '\n') e++;
  fprintf(stderr, "    %.*s\n    ", (int)(e - s), s);
  for (int i = 1; i < p.col; i++) fputc(s[i - 1] == '\t' ? '\t' : ' ', stderr);
  fprintf(stderr, "^\n");
}
_Noreturn void fatal(Pos p, const char *f, ...) {
  print_loc(p);
  fprintf(stderr, "error: ");
  va_list ap; va_start(ap, f); vfprintf(stderr, f, ap); va_end(ap);
  fprintf(stderr, "\n");
  print_line(p);
  exit(1);
}
void warn_at(Pos p, const char *f, ...) {
  print_loc(p);
  fprintf(stderr, "warning: ");
  va_list ap; va_start(ap, f); vfprintf(stderr, f, ap); va_end(ap);
  fprintf(stderr, "\n");
}
