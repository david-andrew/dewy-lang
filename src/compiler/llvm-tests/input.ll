; compile with `clang hello.ll metal.o`

target triple = "x86_64-unknown-linux-gnu"

@.str.0 = private unnamed_addr constant [19 x i8] c"What's your name? \00", align 1
@.str.1 = private unnamed_addr constant [7 x i8] c"Hello \00", align 1
@.str.2 = private unnamed_addr constant [3 x i8] c"!\0A\00", align 1


declare dso_local void @__puts(i8*)
declare dso_local i64 @__getl(i8**)
declare dso_local void @free(i8*)

define dso_local i32 @main() {
    call void @__puts(i8* getelementptr ([19 x i8], [19 x i8]* @.str.0, i64 0, i64 0))
    %1 = alloca i8*, align 8
    %2 = call i64 @__getl(i8** %1)
    call void @__puts(i8* getelementptr ([7 x i8], [7 x i8]* @.str.1, i64 0, i64 0))
    %3 = load i8*, i8** %1, align 8
    call void @__puts(i8* %3)
    call void @__puts(i8* getelementptr ([3 x i8], [3 x i8]* @.str.2, i64 0, i64 0))
    call void @free(i8* %3)
    ret i32 0
}