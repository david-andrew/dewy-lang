; compile with `clang hello.ll metal.o`

target triple = "x86_64-unknown-linux-gnu"

@.str.0 = private unnamed_addr constant [15 x i8] c"Hello, World!\0A\00", align 1

declare dso_local void @__puts(i8*)

define dso_local i32 @main() {
    call void @__puts(i8* getelementptr ([15 x i8], [15 x i8]* @.str.0, i64 0, i64 0))
    ret i32 0
}