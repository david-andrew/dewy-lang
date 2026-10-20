#include "sloppy0.h"
#include <unistd.h>
#include <sys/wait.h>

static void usage(void) {
  fprintf(stderr, "usage: sloppy0 file.jo [-o output] [-S] [--run]\n");
  exit(2);
}

int main(int argc, char **argv) {
  const char *in = NULL, *out = NULL;
  bool asm_only = false, run = false;
  for (int i = 1; i < argc; i++) {
    if (strcmp(argv[i], "-o") == 0 && i + 1 < argc) out = argv[++i];
    else if (strcmp(argv[i], "-S") == 0) asm_only = true;
    else if (strcmp(argv[i], "--run") == 0) run = true;
    else if (argv[i][0] == '-') usage();
    else if (!in) in = argv[i];
    else usage();
  }
  if (!in) usage();
  g_lib_dir = getenv("SLOPPY_LIB");
  if (!g_lib_dir) {
    char exe[1024];
    ssize_t n = readlink("/proc/self/exe", exe, sizeof exe - 1);
    if (n > 0) {
      exe[n] = 0;
      char *s = strrchr(exe, '/'); if (s) *s = 0;
      s = strrchr(exe, '/'); if (s) *s = 0;
      g_lib_dir = strdup(fmt("%s/lib", exe));
    } else g_lib_dir = "lib";
  }
  check_program(in);
  char defout[1024];
  if (!out) {
    snprintf(defout, sizeof defout, "%s", in);
    char *dot = strrchr(defout, '.'); if (dot) *dot = 0;
    out = defout;
  }
  char asmpath[1100];
  snprintf(asmpath, sizeof asmpath, "%s.s", out);
  FILE *f = fopen(asmpath, "w");
  if (!f) { perror(asmpath); return 1; }
  gen_program(f);
  fclose(f);
  if (asm_only) return 0;
  char cmd[4096];
  snprintf(cmd, sizeof cmd, "gcc -nostdlib -static -no-pie -o '%s' '%s'", out, asmpath);
  int rc = system(cmd);
  if (rc != 0) { fprintf(stderr, "sloppy0: assembler failed\n"); return 1; }
  unlink(asmpath);
  if (run) {
    char path[1200];
    snprintf(path, sizeof path, "%s%s", out[0] == '/' ? "" : "./", out);
    execv(path, (char *[]){path, NULL});
    perror("exec");
    return 1;
  }
  return 0;
}
