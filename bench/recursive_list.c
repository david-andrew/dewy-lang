#include "harness.h"
typedef struct Node { int64_t value; struct Node *next; } Node;
static Node *build_list(int64_t count) {
    Node *root = NULL;
    for (int64_t i = 0; i < count; i++) {
        Node *n = malloc(sizeof(*n)); *n = (Node){i, root}; root = n;
    }
    return root;
}
static int64_t sum(const Node *cur, int64_t left) {
    int64_t result = 0;
    while (left > 0) {
        if (!cur) break;
        result += cur->value; cur = cur->next; left--;
    }
    return result;
}
static int64_t kernel(const Node *root, int64_t count) {
    int64_t result = 0;
    for (int64_t i = 0; i < count; i++) result += sum(root, 512 + i % 512);
    return result;
}
int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 20000);
    Node *root = build_list(1023);
    int64_t start = clock_now(), result = kernel(root, count), finish = clock_now();
    report(result, finish - start);
    while (root) { Node *next = root->next; free(root); root = next; }
    return 0;
}
