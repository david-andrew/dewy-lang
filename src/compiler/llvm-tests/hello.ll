; ModuleID = 'hello.c'
source_filename = "hello.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@buf = common dso_local global [32 x i8] zeroinitializer, align 16
@.str = private unnamed_addr constant [2 x i8] c"\0A\00", align 1
@.str.1 = private unnamed_addr constant [7 x i8] c"argc: \00", align 1
@.str.2 = private unnamed_addr constant [15 x i8] c"Hello, World!\0A\00", align 1
@argc = common dso_local local_unnamed_addr global i32* null, align 8
@argv = common dso_local local_unnamed_addr global i8** null, align 8

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
  %3 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([7 x i8], [7 x i8]* @.str.1, i64 0, i64 0), i32 7) #3, !srcloc !2
  br label %4

4:                                                ; preds = %4, %2
  %5 = phi i64 [ %10, %4 ], [ 0, %2 ]
  %6 = phi i32 [ %13, %4 ], [ %0, %2 ]
  %7 = urem i32 %6, 10
  %8 = trunc i32 %7 to i8
  %9 = or i8 %8, 48
  %10 = add nuw i64 %5, 1
  %11 = sub nsw i64 31, %5
  %12 = getelementptr inbounds [32 x i8], [32 x i8]* @buf, i64 0, i64 %11
  store i8 %9, i8* %12, align 1, !tbaa !4
  %13 = udiv i32 %6, 10
  %14 = icmp ugt i32 %6, 9
  br i1 %14, label %4, label %15

15:                                               ; preds = %4
  %16 = getelementptr inbounds [32 x i8], [32 x i8]* @buf, i64 0, i64 %11
  %17 = trunc i64 %10 to i32
  %18 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull %16, i32 %17) #3, !srcloc !2
  %19 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* getelementptr inbounds ([2 x i8], [2 x i8]* @.str, i64 0, i64 0), i32 1) #3, !srcloc !2
  %20 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([15 x i8], [15 x i8]* @.str.2, i64 0, i64 0), i32 15) #3, !srcloc !2
  ret i32 0
}

; Function Attrs: noreturn nounwind
define dso_local void @_start() local_unnamed_addr #1 {
  %1 = tail call i32* asm sideeffect "movq %rsp, $0\0A", "=r,~{dirflag},~{fpsr},~{flags}"() #3, !srcloc !7
  store i32* %1, i32** @argc, align 8, !tbaa !8
  %2 = getelementptr inbounds i32, i32* %1, i64 2
  store i32* %2, i32** bitcast (i8*** @argv to i32**), align 8, !tbaa !8
  %3 = load i32, i32* %1, align 4, !tbaa !10
  %4 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([7 x i8], [7 x i8]* @.str.1, i64 0, i64 0), i32 7) #3, !srcloc !2
  br label %5

5:                                                ; preds = %5, %0
  %6 = phi i64 [ %11, %5 ], [ 0, %0 ]
  %7 = phi i32 [ %14, %5 ], [ %3, %0 ]
  %8 = urem i32 %7, 10
  %9 = trunc i32 %8 to i8
  %10 = or i8 %9, 48
  %11 = add nuw i64 %6, 1
  %12 = sub nsw i64 31, %6
  %13 = getelementptr inbounds [32 x i8], [32 x i8]* @buf, i64 0, i64 %12
  store i8 %10, i8* %13, align 1, !tbaa !4
  %14 = udiv i32 %7, 10
  %15 = icmp ugt i32 %7, 9
  br i1 %15, label %5, label %16

16:                                               ; preds = %5
  %17 = getelementptr inbounds [32 x i8], [32 x i8]* @buf, i64 0, i64 %12
  %18 = trunc i64 %11 to i32
  %19 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull %17, i32 %18) #3, !srcloc !2
  %20 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* getelementptr inbounds ([2 x i8], [2 x i8]* @.str, i64 0, i64 0), i32 1) #3, !srcloc !2
  %21 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull getelementptr inbounds ([15 x i8], [15 x i8]* @.str.2, i64 0, i64 0), i32 15) #3, !srcloc !2
  br label %22

22:                                               ; preds = %22, %16
  tail call void asm sideeffect "syscall\0A", "{ax},{di},~{dirflag},~{fpsr},~{flags}"(i32 60, i32 0) #3, !srcloc !3
  br label %22
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
!7 = !{i32 2433}
!8 = !{!9, !9, i64 0}
!9 = !{!"any pointer", !5, i64 0}
!10 = !{!11, !11, i64 0}
!11 = !{!"int", !5, i64 0}
