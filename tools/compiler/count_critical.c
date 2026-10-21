/* Count user-space instructions per process of a command that forks workers.
 * Linux only. Build: cc -O2 -Wall -Wextra count_critical.c -o count-critical
 * Run: ./count-critical /absolute/path/to/compiler build input.dewy -o output
 * Follows forks with ptrace and gives every process its own counter (no
 * inheritance), so the command's process and each worker are counted apart.
 * The final stderr line is JSON: the command's own instructions, each worker's,
 * the critical path (own plus the largest worker: wall time under ideal
 * parallelism) and the total. Deterministic under load, unlike elapsed time.
 */
#define _GNU_SOURCE
#include <linux/perf_event.h>
#include <sys/ptrace.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <signal.h>
#include <unistd.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define MAX 256
static pid_t pids[MAX];
static int fds[MAX];
static uint64_t counts[MAX];
static int done[MAX];
static int started[MAX];
static int n;

static int counter(pid_t pid, int on_exec) {
    struct perf_event_attr a;
    memset(&a, 0, sizeof(a));
    a.size = sizeof(a); a.type = PERF_TYPE_HARDWARE; a.config = PERF_COUNT_HW_INSTRUCTIONS;
    a.disabled = on_exec; a.enable_on_exec = on_exec; a.inherit = 0; a.pinned = 1;
    a.exclude_kernel = 1; a.exclude_hv = 1;
    a.read_format = PERF_FORMAT_TOTAL_TIME_ENABLED | PERF_FORMAT_TOTAL_TIME_RUNNING;
    return syscall(SYS_perf_event_open, &a, pid, -1, -1, 0);
}

static int find(pid_t pid) {
    for (int k = 0; k < n; k++) if (pids[k] == pid) return k;
    return -1;
}

static int add(pid_t pid, int on_exec) {
    if (n >= MAX) return -1;
    int fd = counter(pid, on_exec);
    if (fd < 0) { perror("perf_event_open"); return -1; }
    pids[n] = pid; fds[n] = fd; done[n] = 0; started[n] = 0;
    return n++;
}

static int finish(int k) {
    uint64_t r[3];
    ssize_t got = read(fds[k], r, sizeof(r));
    close(fds[k]);
    done[k] = 1;
    if (got != sizeof(r) || !r[2] || r[1] != r[2]) { fprintf(stderr, "counter unavailable or multiplexed\n"); return 1; }
    counts[k] = r[0];
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    pid_t child = fork();
    if (child < 0) { perror("fork"); return 1; }
    if (!child) {
        ptrace(PTRACE_TRACEME, 0, 0, 0);
        raise(SIGSTOP);
        execv(argv[1], argv + 1); perror("execv"); _exit(127);
    }
    int status;
    if (waitpid(child, &status, __WALL) != child) return 1;
    ptrace(PTRACE_SETOPTIONS, child, 0, PTRACE_O_TRACEFORK | PTRACE_O_TRACEVFORK | PTRACE_O_TRACECLONE | PTRACE_O_EXITKILL);
    if (add(child, 1) < 0) { kill(child, SIGKILL); return 1; }
    ptrace(PTRACE_CONT, child, 0, 0);
    int bad = 0, exit_status = 1, live = 1;
    while (live > 0) {
        pid_t pid = waitpid(-1, &status, __WALL);
        if (pid < 0) break;
        int k = find(pid);
        if (WIFEXITED(status) || WIFSIGNALED(status)) {
            if (k >= 0 && !done[k]) { bad |= finish(k); live--; }
            if (pid == child) exit_status = WIFEXITED(status) ? WEXITSTATUS(status) : 1;
            continue;
        }
        if (!WIFSTOPPED(status)) continue;
        int sig = WSTOPSIG(status), event = status >> 16;
        if (k < 0) {
            /* a new worker, stopped before its first instruction: count it from here */
            k = add(pid, 0);
            if (k < 0) bad = 1; else { started[k] = 1; live++; }
            ptrace(PTRACE_CONT, pid, 0, 0);
            continue;
        }
        if (sig == SIGTRAP && event) { ptrace(PTRACE_CONT, pid, 0, 0); continue; }
        if (sig == SIGSTOP && k > 0 && started[k] == 1) { started[k] = 2; ptrace(PTRACE_CONT, pid, 0, 0); continue; }
        if (sig == SIGTRAP && pid == child) { ptrace(PTRACE_CONT, pid, 0, 0); continue; }   /* exec */
        ptrace(PTRACE_CONT, pid, 0, sig);
    }
    if (bad) return 1;
    uint64_t own = counts[0], top = 0, total = counts[0];
    fprintf(stderr, "{\"own\":%llu,\"workers\":[", (unsigned long long)own);
    for (int k = 1; k < n; k++) {
        fprintf(stderr, "%s%llu", k > 1 ? "," : "", (unsigned long long)counts[k]);
        if (counts[k] > top) top = counts[k];
        total += counts[k];
    }
    fprintf(stderr, "],\"critical\":%llu,\"total\":%llu}\n", (unsigned long long)(own + top), (unsigned long long)total);
    return exit_status != 0;
}
