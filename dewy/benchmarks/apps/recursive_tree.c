#include "harness.h"
typedef struct Node { int64_t key; struct Node *left, *right; } Node;
static Node *build_tree(int64_t lo, int64_t hi) {
    if (lo >= hi) return NULL;
    int64_t mid = (lo + hi) / 2;
    Node *n = malloc(sizeof(*n));
    *n = (Node){mid, build_tree(lo, mid), build_tree(mid + 1, hi)};
    return n;
}
static void destroy(Node *n) { if (n) { destroy(n->left); destroy(n->right); free(n); } }
static int64_t find_key(const Node *cur, int64_t key) {
    while (cur) {
        if (key < cur->key) cur = cur->left;
        else if (key > cur->key) cur = cur->right;
        else return cur->key + 1;
    }
    return 0;
}
static int64_t kernel(const Node *root, int64_t count) {
    int64_t result = 0;
    for (int64_t i = 0; i < count; i++) result += find_key(root, (i * 73) % 4096);
    return result;
}
int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 2000000);
    Node *root = build_tree(0, 2047);
    int64_t start = clock_now(), result = kernel(root, count), finish = clock_now();
    report(result, finish - start);
    destroy(root);
    return 0;
}
