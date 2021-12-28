
target triple = "x86_64-unknown-linux-gnu"

; bit array type
%Array.i1 = type {
    i64, ; elements in the array (as packed 64-bit integers)
    i64, ; capacity of the array (number of i8s in the array)
    i8*  ; pointer to the first element
}

; declare dso_local i8* @malloc(i64)
declare dso_local i8* @calloc(i64, i64)
declare dso_local void @free(i8*)
declare dso_local void @__putu64(i64)
declare dso_local void @__putl()

define dso_local void @Array.i1.new(%Array.i1* %this) {
    %1 = getelementptr %Array.i1, %Array.i1* %this, i32 0, i32 0
    store i64 0, i64* %1 ; set the current number of elements to 0
    %2 = getelementptr %Array.i1, %Array.i1* %this, i32 0, i32 1
    store i64 8, i64* %2 ; set the capacity to 64 (8 bits/byte * 8 bytes)
    %3 = getelementptr %Array.i1, %Array.i1* %this, i32 0, i32 2
    %4 = call i8* @calloc(i64 8, i64 1)
    store i8* %4, i8** %3 ; initialize the memory for the array
    ret void
}

define dso_local void @Array.i1.free(%Array.i1* %this) {
    %1 = getelementptr %Array.i1, %Array.i1* %this, i32 0, i32 2
    %2 = load i8*, i8** %1
    call void @free(i8* %2)
    ret void
}

define dso_local i64 @Array.i1.size(%Array.i1* %this) {
    %1 = getelementptr %Array.i1, %Array.i1* %this, i32 0, i32 0
    %2 = load i64, i64* %1
    ret i64 %2
}

define dso_local i64 @Array.i1.capacity(%Array.i1* %this) {
    %1 = getelementptr %Array.i1, %Array.i1* %this, i32 0, i32 1
    %2 = load i64, i64* %1
    ret i64 %2
}

define dso_local void @Array.i1.resize(%Array.i1* %this, i64 %newCapacity) {
    ; realloc and then memset new memory to 0
    ret void
}

define dso_local void @Array.i1.push(%Array.i1* %this, i1 %value) {
entry:
    ; check if the array needs to be resized
    %0 = call i64 @Array.i1.size(%Array.i1* %this)
    %1 = call i64 @Array.i1.capacity(%Array.i1* %this)
    %2 = mul i64 8, %1 ; true capacity is times 8 for 8 bits/byte
    %3 = icmp eq i64 %0, %2
    br i1 %3, label %resize, label %push

resize:
    ; double the array capacity
    %4 = phi i64 [ %1, %entry ]
    %5 = mul i64 %4, 2
    call void @Array.i1.resize(%Array.i1* %this, i64 %4)
    br label %push

push:
    ; push the value into the array
    %6 = phi i64 [ %0, %entry ], [ %4, %resize ]
    %7 = udiv i64 %6, 8 ; byte offset into the array
    %8 = urem i64 %6, 8 ; bit offset into the byte
    %9 = trunc i64 %8 to i8
    %bytesptr = getelementptr %Array.i1, %Array.i1* %this, i32 0, i32 2
    %bytes = load i8*, i8** %bytesptr
    %byteptr = getelementptr i8, i8* %bytes, i64 %7
    %byte = load i8, i8* %byteptr
    %10 = zext i1 %value to i8
    %11 = shl i8 %10, %9
    %update = or i8 %byte, %11
    store i8 %update, i8* %byteptr

    ; increment the number of elements
    %12 = getelementptr %Array.i1, %Array.i1* %this, i32 0, i32 0
    %13 = load i64, i64* %12
    %14 = add i64 %13, 1
    store i64 %14, i64* %12

    ret void
}


define dso_local i32 @main() {
    %world = alloca %Array.i1
    call void @Array.i1.new(%Array.i1* %world)

    ; push some test values into the array
    call void @Array.i1.push(%Array.i1* %world, i1 true)
    call void @Array.i1.push(%Array.i1* %world, i1 false)
    call void @Array.i1.push(%Array.i1* %world, i1 true)
    call void @Array.i1.push(%Array.i1* %world, i1 false)
    call void @Array.i1.push(%Array.i1* %world, i1 true)
    call void @Array.i1.push(%Array.i1* %world, i1 true)
    call void @Array.i1.push(%Array.i1* %world, i1 true)

    ; collect the first byte in the array and debug print it
    %1 = getelementptr %Array.i1, %Array.i1* %world, i32 0, i32 2
    %2 = load i8*, i8** %1
    %3 = load i8, i8* %2
    %4 = zext i8 %3 to i64
    call void @__putu64(i64 %4)
    call void @__putl()


    call void @Array.i1.free(%Array.i1* %world)
    ret i32 0
}