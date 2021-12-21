; ModuleID = 'hello.c'
source_filename = "hello.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@__const.main.buf = private unnamed_addr constant [15 x i8] c"Hello, World!\0A\00", align 1

; Function Attrs: nounwind uwtable
define dso_local i32 @write(i8* %0, i32 %1) local_unnamed_addr #0 {
  %3 = tail call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* %0, i32 %1) #3, !srcloc !2
  ret i32 %3
}

; Function Attrs: argmemonly nounwind willreturn
declare void @llvm.lifetime.start.p0i8(i64 immarg, i8* nocapture) #1

; Function Attrs: argmemonly nounwind willreturn
declare void @llvm.lifetime.end.p0i8(i64 immarg, i8* nocapture) #1

; Function Attrs: noreturn nounwind uwtable
define dso_local void @exit(i32 %0) local_unnamed_addr #2 {
  br label %2

2:                                                ; preds = %2, %1
  tail call void asm sideeffect "syscall\0A", "{ax},{di},~{dirflag},~{fpsr},~{flags}"(i32 60, i32 0) #3, !srcloc !3
  br label %2
}

; Function Attrs: nounwind uwtable
define dso_local i32 @main() local_unnamed_addr #0 {
  %1 = alloca [15 x i8], align 1
  %2 = getelementptr inbounds [15 x i8], [15 x i8]* %1, i64 0, i64 0
  call void @llvm.lifetime.start.p0i8(i64 15, i8* nonnull %2) #3
  call void @llvm.memcpy.p0i8.p0i8.i64(i8* nonnull align 1 dereferenceable(15) %2, i8* nonnull align 1 dereferenceable(15) getelementptr inbounds ([15 x i8], [15 x i8]* @__const.main.buf, i64 0, i64 0), i64 15, i1 false)
  %3 = call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull %2, i32 15) #3, !srcloc !2
  call void @llvm.lifetime.end.p0i8(i64 15, i8* nonnull %2) #3
  ret i32 0
}

; Function Attrs: argmemonly nounwind willreturn
declare void @llvm.memcpy.p0i8.p0i8.i64(i8* noalias nocapture writeonly, i8* noalias nocapture readonly, i64, i1 immarg) #1

; Function Attrs: noreturn nounwind uwtable
define dso_local void @_start() local_unnamed_addr #2 {
  %1 = alloca [15 x i8], align 1
  %2 = getelementptr inbounds [15 x i8], [15 x i8]* %1, i64 0, i64 0
  call void @llvm.lifetime.start.p0i8(i64 15, i8* nonnull %2) #3
  call void @llvm.memcpy.p0i8.p0i8.i64(i8* nonnull align 1 dereferenceable(15) %2, i8* nonnull align 1 dereferenceable(15) getelementptr inbounds ([15 x i8], [15 x i8]* @__const.main.buf, i64 0, i64 0), i64 15, i1 false) #3
  %3 = call i32 asm sideeffect "syscall\0A", "=A,{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i32 1, i32 2, i8* nonnull %2, i32 15) #3, !srcloc !2
  call void @llvm.lifetime.end.p0i8(i64 15, i8* nonnull %2) #3
  br label %4

4:                                                ; preds = %4, %0
  call void asm sideeffect "syscall\0A", "{ax},{di},~{dirflag},~{fpsr},~{flags}"(i32 60, i32 0) #3, !srcloc !3
  br label %4
}

attributes #0 = { nounwind uwtable "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "frame-pointer"="none" "less-precise-fpmad"="false" "min-legal-vector-width"="0" "no-infs-fp-math"="false" "no-jump-tables"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #1 = { argmemonly nounwind willreturn }
attributes #2 = { noreturn nounwind uwtable "correctly-rounded-divide-sqrt-fp-math"="false" "disable-tail-calls"="false" "frame-pointer"="none" "less-precise-fpmad"="false" "min-legal-vector-width"="0" "no-infs-fp-math"="false" "no-jump-tables"="false" "no-nans-fp-math"="false" "no-signed-zeros-fp-math"="false" "no-trapping-math"="false" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "unsafe-fp-math"="false" "use-soft-float"="false" }
attributes #3 = { nounwind }

!llvm.module.flags = !{!0}
!llvm.ident = !{!1}

!0 = !{i32 1, !"wchar_size", i32 4}
!1 = !{!"clang version 10.0.0-4ubuntu1 "}
!2 = !{i32 269}
!3 = !{i32 891}
