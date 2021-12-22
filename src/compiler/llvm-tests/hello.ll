; ModuleID = 'hello.c'
source_filename = "hello.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@buf = common dso_local global [32 x i8] zeroinitializer, align 16
@.str = private unnamed_addr constant [2 x i8] c"\0A\00", align 1
@.str.1 = private unnamed_addr constant [15 x i8] c"Hello, World!\0A\00", align 1
@.str.2 = private unnamed_addr constant [7 x i8] c"apple\0A\00", align 1
@.str.3 = private unnamed_addr constant [6 x i8] c"apple\00", align 1
@.str.4 = private unnamed_addr constant [7 x i8] c"banana\00", align 1
@.str.5 = private unnamed_addr constant [7 x i8] c"carrot\00", align 1
@.str.6 = private unnamed_addr constant [7 x i8] c"durian\00", align 1
@.str.7 = private unnamed_addr constant [11 x i8] c"elderberry\00", align 1
@.str.8 = private unnamed_addr constant [4 x i8] c"fig\00", align 1
@.str.9 = private unnamed_addr constant [6 x i8] c"grape\00", align 1
@.str.10 = private unnamed_addr constant [12 x i8] c"huckleberry\00", align 1
@.str.11 = private unnamed_addr constant [10 x i8] c"jackfruit\00", align 1
@.str.12 = private unnamed_addr constant [5 x i8] c"kiwi\00", align 1
@.str.13 = private unnamed_addr constant [6 x i8] c"lemon\00", align 1
@.str.14 = private unnamed_addr constant [6 x i8] c"mango\00", align 1
@.str.15 = private unnamed_addr constant [10 x i8] c"nectarine\00", align 1
@.str.16 = private unnamed_addr constant [7 x i8] c"orange\00", align 1
@.str.17 = private unnamed_addr constant [7 x i8] c"papaya\00", align 1
@.str.18 = private unnamed_addr constant [7 x i8] c"quince\00", align 1
@.str.19 = private unnamed_addr constant [10 x i8] c"raspberry\00", align 1
@.str.20 = private unnamed_addr constant [11 x i8] c"strawberry\00", align 1
@.str.21 = private unnamed_addr constant [10 x i8] c"tangerine\00", align 1
@.str.22 = private unnamed_addr constant [11 x i8] c"watermelon\00", align 1
@.str.23 = private unnamed_addr constant [10 x i8] c"xylophone\00", align 1
@.str.24 = private unnamed_addr constant [4 x i8] c"yam\00", align 1
@.str.25 = private unnamed_addr constant [9 x i8] c"zucchini\00", align 1
@test_argv = dso_local local_unnamed_addr global [23 x i8*] [i8* getelementptr inbounds ([6 x i8], [6 x i8]* @.str.3, i32 0, i32 0), i8* getelementptr inbounds ([7 x i8], [7 x i8]* @.str.4, i32 0, i32 0), i8* getelementptr inbounds ([7 x i8], [7 x i8]* @.str.5, i32 0, i32 0), i8* getelementptr inbounds ([7 x i8], [7 x i8]* @.str.6, i32 0, i32 0), i8* getelementptr inbounds ([11 x i8], [11 x i8]* @.str.7, i32 0, i32 0), i8* getelementptr inbounds ([4 x i8], [4 x i8]* @.str.8, i32 0, i32 0), i8* getelementptr inbounds ([6 x i8], [6 x i8]* @.str.9, i32 0, i32 0), i8* getelementptr inbounds ([12 x i8], [12 x i8]* @.str.10, i32 0, i32 0), i8* getelementptr inbounds ([10 x i8], [10 x i8]* @.str.11, i32 0, i32 0), i8* getelementptr inbounds ([5 x i8], [5 x i8]* @.str.12, i32 0, i32 0), i8* getelementptr inbounds ([6 x i8], [6 x i8]* @.str.13, i32 0, i32 0), i8* getelementptr inbounds ([6 x i8], [6 x i8]* @.str.14, i32 0, i32 0), i8* getelementptr inbounds ([10 x i8], [10 x i8]* @.str.15, i32 0, i32 0), i8* getelementptr inbounds ([7 x i8], [7 x i8]* @.str.16, i32 0, i32 0), i8* getelementptr inbounds ([7 x i8], [7 x i8]* @.str.17, i32 0, i32 0), i8* getelementptr inbounds ([7 x i8], [7 x i8]* @.str.18, i32 0, i32 0), i8* getelementptr inbounds ([10 x i8], [10 x i8]* @.str.19, i32 0, i32 0), i8* getelementptr inbounds ([11 x i8], [11 x i8]* @.str.20, i32 0, i32 0), i8* getelementptr inbounds ([10 x i8], [10 x i8]* @.str.21, i32 0, i32 0), i8* getelementptr inbounds ([11 x i8], [11 x i8]* @.str.22, i32 0, i32 0), i8* getelementptr inbounds ([10 x i8], [10 x i8]* @.str.23, i32 0, i32 0), i8* getelementptr inbounds ([4 x i8], [4 x i8]* @.str.24, i32 0, i32 0), i8* getelementptr inbounds ([9 x i8], [9 x i8]* @.str.25, i32 0, i32 0)], align 16
@test_argc = dso_local local_unnamed_addr global i32 23, align 4

; Function Attrs: nounwind
define dso_local i32 @write(i8* %0, i32 %1) local_unnamed_addr #0 {
  %3 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* %0, i32 %1) #3, !srcloc !2
  ret i32 %3
}

; Function Attrs: noreturn nounwind
define dso_local void @exit(i32 %0) local_unnamed_addr #1 {
  br label %2

2:                                                ; preds = %2, %1
  tail call void asm sideeffect "syscall\0A", "{ax},{di},~{dirflag},~{fpsr},~{flags}"(i32 60, i32 %0) #3, !srcloc !3
  br label %2
}

; Function Attrs: norecurse nounwind readonly
define dso_local i32 @strlen(i8* nocapture readonly %0) local_unnamed_addr #2 {
  br label %2

2:                                                ; preds = %2, %1
  %3 = phi i64 [ %4, %2 ], [ 0, %1 ]
  %4 = add nuw i64 %3, 1
  %5 = getelementptr inbounds i8, i8* %0, i64 %3
  %6 = load i8, i8* %5, align 1, !tbaa !4
  %7 = icmp eq i8 %6, 0
  br i1 %7, label %8, label %2

8:                                                ; preds = %2
  %9 = trunc i64 %4 to i32
  ret i32 %9
}

; Function Attrs: nounwind
define dso_local void @puts(i8* %0) local_unnamed_addr #0 {
  br label %2

2:                                                ; preds = %2, %1
  %3 = phi i64 [ %4, %2 ], [ 0, %1 ]
  %4 = add nuw i64 %3, 1
  %5 = getelementptr inbounds i8, i8* %0, i64 %3
  %6 = load i8, i8* %5, align 1, !tbaa !4
  %7 = icmp eq i8 %6, 0
  br i1 %7, label %8, label %2

8:                                                ; preds = %2
  %9 = trunc i64 %4 to i32
  %10 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull %0, i32 %9) #3, !srcloc !2
  ret void
}

; Function Attrs: nounwind
define dso_local void @puti(i32 %0) local_unnamed_addr #0 {
  br label %2

2:                                                ; preds = %2, %1
  %3 = phi i64 [ %8, %2 ], [ 0, %1 ]
  %4 = phi i32 [ %11, %2 ], [ %0, %1 ]
  %5 = urem i32 %4, 10
  %6 = trunc i32 %5 to i8
  %7 = or i8 %6, 48
  %8 = add nuw i64 %3, 1
  %9 = sub nsw i64 31, %3
  %10 = getelementptr inbounds [32 x i8], [32 x i8]* @buf, i64 0, i64 %9
  store i8 %7, i8* %10, align 1, !tbaa !4
  %11 = udiv i32 %4, 10
  %12 = icmp ugt i32 %4, 9
  br i1 %12, label %2, label %13

13:                                               ; preds = %2
  %14 = getelementptr inbounds [32 x i8], [32 x i8]* @buf, i64 0, i64 %9
  %15 = trunc i64 %8 to i32
  %16 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull %14, i32 %15) #3, !srcloc !2
  ret void
}

; Function Attrs: nounwind
define dso_local void @putx(i32 %0) local_unnamed_addr #0 {
  br label %2

2:                                                ; preds = %2, %1
  %3 = phi i64 [ %8, %2 ], [ 0, %1 ]
  %4 = phi i32 [ %11, %2 ], [ %0, %1 ]
  %5 = trunc i32 %4 to i8
  %6 = and i8 %5, 15
  %7 = add nuw nsw i8 %6, 55
  %8 = add nuw nsw i64 %3, 1
  %9 = sub nsw i64 31, %3
  %10 = getelementptr inbounds [32 x i8], [32 x i8]* @buf, i64 0, i64 %9
  store i8 %7, i8* %10, align 1, !tbaa !4
  %11 = lshr i32 %4, 4
  %12 = icmp eq i32 %11, 0
  br i1 %12, label %13, label %2

13:                                               ; preds = %2
  %14 = trunc i64 %3 to i32
  %15 = shl i64 %3, 32
  %16 = sub i64 128849018880, %15
  %17 = ashr exact i64 %16, 32
  %18 = getelementptr inbounds [32 x i8], [32 x i8]* @buf, i64 0, i64 %17
  store i8 120, i8* %18, align 1, !tbaa !4
  %19 = add nuw nsw i32 %14, 3
  %20 = shl i64 %3, 32
  %21 = sub i64 124554051584, %20
  %22 = ashr exact i64 %21, 32
  %23 = getelementptr inbounds [32 x i8], [32 x i8]* @buf, i64 0, i64 %22
  store i8 48, i8* %23, align 1, !tbaa !4
  %24 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull %23, i32 %19) #3, !srcloc !2
  ret void
}

; Function Attrs: nounwind
define dso_local void @putl() local_unnamed_addr #0 {
  %1 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* getelementptr inbounds ([2 x i8], [2 x i8]* @.str, i64 0, i64 0), i32 1) #3, !srcloc !2
  ret void
}

; Function Attrs: nounwind
define dso_local i32 @main(i32 %0, i8** nocapture readnone %1) local_unnamed_addr #0 {
  %3 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([15 x i8], [15 x i8]* @.str.1, i64 0, i64 0), i32 15) #3, !srcloc !2
  store i8 50, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 31), align 1, !tbaa !4
  store i8 52, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 30), align 2, !tbaa !4
  %4 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 30), i32 2) #3, !srcloc !2
  %5 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* getelementptr inbounds ([2 x i8], [2 x i8]* @.str, i64 0, i64 0), i32 1) #3, !srcloc !2
  store i8 70, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 31), align 1, !tbaa !4
  store i8 69, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 30), align 2, !tbaa !4
  store i8 69, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 29), align 1, !tbaa !4
  store i8 66, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 28), align 4, !tbaa !4
  store i8 68, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 27), align 1, !tbaa !4
  store i8 65, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 26), align 2, !tbaa !4
  store i8 69, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 25), align 1, !tbaa !4
  store i8 68, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 24), align 8, !tbaa !4
  store i8 120, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 23), align 1, !tbaa !4
  store i8 48, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 22), align 2, !tbaa !4
  %6 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 22), i32 10) #3, !srcloc !2
  %7 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* getelementptr inbounds ([2 x i8], [2 x i8]* @.str, i64 0, i64 0), i32 1) #3, !srcloc !2
  store i8 57, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 31), align 1, !tbaa !4
  store i8 57, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 30), align 2, !tbaa !4
  store i8 57, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 29), align 1, !tbaa !4
  %8 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 29), i32 3) #3, !srcloc !2
  %9 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* getelementptr inbounds ([2 x i8], [2 x i8]* @.str, i64 0, i64 0), i32 1) #3, !srcloc !2
  %10 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([7 x i8], [7 x i8]* @.str.2, i64 0, i64 0), i32 7) #3, !srcloc !2
  store i8 50, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 31), align 1, !tbaa !4
  store i8 52, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 30), align 2, !tbaa !4
  %11 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 30), i32 2) #3, !srcloc !2
  %12 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* getelementptr inbounds ([2 x i8], [2 x i8]* @.str, i64 0, i64 0), i32 1) #3, !srcloc !2
  store i8 48, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 31), align 1, !tbaa !4
  store i8 48, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 30), align 2, !tbaa !4
  store i8 50, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 29), align 1, !tbaa !4
  %13 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 29), i32 3) #3, !srcloc !2
  %14 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* getelementptr inbounds ([2 x i8], [2 x i8]* @.str, i64 0, i64 0), i32 1) #3, !srcloc !2
  ret i32 0
}

; Function Attrs: noreturn nounwind
define dso_local void @_start() local_unnamed_addr #1 {
  %1 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([15 x i8], [15 x i8]* @.str.1, i64 0, i64 0), i32 15) #3, !srcloc !2
  store i8 50, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 31), align 1, !tbaa !4
  store i8 52, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 30), align 2, !tbaa !4
  %2 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 30), i32 2) #3, !srcloc !2
  %3 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* getelementptr inbounds ([2 x i8], [2 x i8]* @.str, i64 0, i64 0), i32 1) #3, !srcloc !2
  store i8 70, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 31), align 1, !tbaa !4
  store i8 69, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 30), align 2, !tbaa !4
  store i8 69, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 29), align 1, !tbaa !4
  store i8 66, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 28), align 4, !tbaa !4
  store i8 68, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 27), align 1, !tbaa !4
  store i8 65, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 26), align 2, !tbaa !4
  store i8 69, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 25), align 1, !tbaa !4
  store i8 68, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 24), align 8, !tbaa !4
  store i8 120, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 23), align 1, !tbaa !4
  store i8 48, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 22), align 2, !tbaa !4
  %4 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 22), i32 10) #3, !srcloc !2
  %5 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* getelementptr inbounds ([2 x i8], [2 x i8]* @.str, i64 0, i64 0), i32 1) #3, !srcloc !2
  store i8 57, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 31), align 1, !tbaa !4
  store i8 57, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 30), align 2, !tbaa !4
  store i8 57, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 29), align 1, !tbaa !4
  %6 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 29), i32 3) #3, !srcloc !2
  %7 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* getelementptr inbounds ([2 x i8], [2 x i8]* @.str, i64 0, i64 0), i32 1) #3, !srcloc !2
  %8 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([7 x i8], [7 x i8]* @.str.2, i64 0, i64 0), i32 7) #3, !srcloc !2
  store i8 50, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 31), align 1, !tbaa !4
  store i8 52, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 30), align 2, !tbaa !4
  %9 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 30), i32 2) #3, !srcloc !2
  %10 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* getelementptr inbounds ([2 x i8], [2 x i8]* @.str, i64 0, i64 0), i32 1) #3, !srcloc !2
  store i8 48, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 31), align 1, !tbaa !4
  store i8 48, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 30), align 2, !tbaa !4
  store i8 50, i8* getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 29), align 1, !tbaa !4
  %11 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([32 x i8], [32 x i8]* @buf, i64 0, i64 29), i32 3) #3, !srcloc !2
  %12 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* getelementptr inbounds ([2 x i8], [2 x i8]* @.str, i64 0, i64 0), i32 1) #3, !srcloc !2
  br label %13

13:                                               ; preds = %13, %0
  tail call void asm sideeffect "syscall\0A", "{ax},{di},~{dirflag},~{fpsr},~{flags}"(i32 60, i32 0) #3, !srcloc !3
  br label %13
}

attributes #0 = { nounwind "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "frame-pointer"="none" "less-precise-fpmad"="false" "min-legal-vector-width"="0" "no-builtins" "no-infs-fp-math"="false" "no-jump-tables"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #1 = { noreturn nounwind "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "frame-pointer"="none" "less-precise-fpmad"="false" "min-legal-vector-width"="0" "no-builtins" "no-infs-fp-math"="false" "no-jump-tables"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #2 = { norecurse nounwind readonly "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "frame-pointer"="none" "less-precise-fpmad"="false" "min-legal-vector-width"="0" "no-builtins" "no-infs-fp-math"="false" "no-jump-tables"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #3 = { nounwind }

!llvm.module.flags = !{!0}
!llvm.ident = !{!1}

!0 = !{i32 1, !"wchar_size", i32 4}
!1 = !{!"clang version 10.0.0-4ubuntu1 "}
!2 = !{i32 665}
!3 = !{i32 922}
!4 = !{!5, !5, i64 0}
!5 = !{!"omnipotent char", !6, i64 0}
!6 = !{!"Simple C/C++ TBAA"}
