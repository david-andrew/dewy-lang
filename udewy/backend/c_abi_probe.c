#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint64_t udewy_word;
typedef udewy_word (*udewy_fn)(void);
typedef union {
    udewy_word w;
    void *obj;
    udewy_fn fn;
} udewy_slot;

typedef char udewy_obj_ptr_must_be_word_sized[
    sizeof(void *) == sizeof(udewy_word) ? 1 : -1
];
typedef char udewy_fn_ptr_must_be_word_sized[
    sizeof(udewy_fn) == sizeof(udewy_word) ? 1 : -1
];
typedef char udewy_slot_must_be_word_sized[
    sizeof(udewy_slot) == sizeof(udewy_word) ? 1 : -1
];

static udewy_word object_value = UINT64_C(41);
static struct {
    udewy_word len;
    unsigned char data[3];
} text = {UINT64_C(2), {'o', 'k', '\0'}};

static udewy_word increment(udewy_word value)
{
    return value + UINT64_C(1);
}

static udewy_word add(udewy_word lhs, udewy_word rhs)
{
    return lhs + rhs;
}

static udewy_slot words[] = {
    {.w = UINT64_C(7)},
    {.obj = &object_value},
    {.obj = ((unsigned char *)&text) + sizeof(udewy_word)},
    {.fn = (udewy_fn)increment},
    {.fn = (udewy_fn)add},
};

static udewy_slot function_global = {.fn = (udewy_fn)increment};
static udewy_slot object_global = {.obj = &object_value};

static int fail(int code, const char *assumption)
{
    fprintf(stderr, "udewy C ABI probe failed: %s\n", assumption);
    return code;
}

static udewy_word object_pointer_bits(void *pointer)
{
    udewy_word bits = UINT64_C(0);
    memcpy(&bits, &pointer, sizeof(bits));
    return bits;
}

static udewy_word function_pointer_bits(udewy_fn pointer)
{
    udewy_word bits = UINT64_C(0);
    memcpy(&bits, &pointer, sizeof(bits));
    return bits;
}

int main(void)
{
    udewy_word object_bits;
    udewy_word string_bits;
    udewy_word increment_bits;
    udewy_word add_bits;
    udewy_word *object_pointer;
    const unsigned char *string_pointer;
    udewy_word (*increment_pointer)(udewy_word);
    udewy_word (*add_pointer)(udewy_word, udewy_word);

    if ((unsigned char *)&words[1] - (unsigned char *)&words[0] != 8) {
        return fail(1, "udewy_slot array stride is not eight bytes");
    }

    object_bits = object_pointer_bits(words[1].obj);
    if (object_bits != (udewy_word)(uintptr_t)&object_value) {
        return fail(2, "object-pointer bytes do not match uintptr_t");
    }

    string_bits = object_pointer_bits(words[2].obj);
    if (string_bits != (udewy_word)(uintptr_t)text.data) {
        return fail(3, "offset object-pointer initializer has unexpected bytes");
    }

    increment_bits = function_pointer_bits(words[3].fn);
    if (increment_bits != (udewy_word)(uintptr_t)increment) {
        return fail(4, "one-argument function-pointer bytes do not match uintptr_t");
    }

    add_bits = function_pointer_bits(words[4].fn);
    if (add_bits != (udewy_word)(uintptr_t)add) {
        return fail(5, "two-argument function-pointer bytes do not match uintptr_t");
    }

    object_pointer = (udewy_word *)(uintptr_t)object_bits;
    if (*object_pointer != UINT64_C(41)) {
        return fail(6, "object pointer does not survive the integer round trip");
    }

    string_pointer = (const unsigned char *)(uintptr_t)string_bits;
    if (string_pointer[0] != 'o' || string_pointer[1] != 'k') {
        return fail(7, "offset string pointer does not survive the integer round trip");
    }

    increment_pointer = (udewy_word(*)(udewy_word))(uintptr_t)increment_bits;
    if (increment_pointer(UINT64_C(41)) != UINT64_C(42)) {
        return fail(8, "one-argument indirect call failed");
    }

    add_pointer = (udewy_word(*)(udewy_word, udewy_word))(uintptr_t)add_bits;
    if (add_pointer(UINT64_C(19), UINT64_C(23)) != UINT64_C(42)) {
        return fail(9, "two-argument indirect call failed");
    }

    if (function_global.w != (udewy_word)(uintptr_t)increment) {
        return fail(10, "function-initialized union global has unexpected word value");
    }
    if (object_global.w != (udewy_word)(uintptr_t)&object_value) {
        return fail(11, "object-initialized union global has unexpected word value");
    }

    function_global.w = UINT64_C(17);
    object_global.w = UINT64_C(29);
    if (function_global.w != UINT64_C(17) || object_global.w != UINT64_C(29)) {
        return fail(12, "union globals do not preserve word writes");
    }

    puts("udewy C ABI probe passed");
    return 0;
}
