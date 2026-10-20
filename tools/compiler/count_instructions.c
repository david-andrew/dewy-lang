/* Count user-space instructions in a command launched by this process.
 * Linux only. Build: cc -O2 -Wall -Wextra count_instructions.c -o count-instructions
 * Run: ./count-instructions /absolute/path/to/compiler build input.dewy -o output
 * The final stderr line is JSON. Reject multiplexed counts (running != enabled)
 * when comparing raw values. Instruction counts supplement elapsed-time tests;
 * they do not measure cache misses, scheduling, or throughput directly.
 */
#define _GNU_SOURCE
#include <linux/perf_event.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <signal.h>
#include <unistd.h>
#include <stdint.h>
#include <stdio.h>

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    pid_t child = fork();
    if (child < 0) { perror("fork"); return 1; }
    if (!child) { raise(SIGSTOP); execv(argv[1], argv + 1); perror("execv"); _exit(127); }
    int status;
    if (waitpid(child, &status, WUNTRACED) != child) return 1;
    struct perf_event_attr a = {0};
    a.size = sizeof(a); a.type = PERF_TYPE_HARDWARE; a.config = PERF_COUNT_HW_INSTRUCTIONS;
    a.disabled = 1; a.enable_on_exec = 1; a.inherit = 1; a.pinned = 1;
    a.exclude_kernel = 1; a.exclude_hv = 1;
    a.read_format = PERF_FORMAT_TOTAL_TIME_ENABLED | PERF_FORMAT_TOTAL_TIME_RUNNING;
    int fd = syscall(SYS_perf_event_open, &a, child, -1, -1, 0);
    if (fd < 0) { perror("perf_event_open"); kill(child, SIGKILL); waitpid(child, &status, 0); return 1; }
    kill(child, SIGCONT);
    if (waitpid(child, &status, 0) != child) return 1;
    uint64_t result[3];
    ssize_t got = read(fd, result, sizeof(result)); close(fd);
    if (got != sizeof(result) || !result[2]) { fprintf(stderr, "counter unavailable\n"); return 1; }
    fprintf(stderr, "{\"instructions\":%llu,\"enabled_ns\":%llu,\"running_ns\":%llu}\n",
            (unsigned long long)result[0], (unsigned long long)result[1], (unsigned long long)result[2]);
    return !WIFEXITED(status) || WEXITSTATUS(status) != 0;
}
