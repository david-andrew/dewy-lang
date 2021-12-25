
target triple = "x86_64-unknown-linux-gnu"

; bit array type
%Array.i1 = type {
    i64, ; elements in the array (as packed 64-bit integers)
    i64, ; capacity of the array (number of i64s)
    i8*  ; pointer to the first element
}

declare dso_local i8* @malloc(i64)
declare dso_local void @free(i8*)

define dso_local void @Array.i1.new(%Array.i1* %this) {
    %1 = getelementptr %Array.i1, %Array.i1* %this, i32 0, i32 0
    store i64 0, i64* %1 ; set the current number of elements to 0
    %2 = getelementptr %Array.i1, %Array.i1* %this, i32 0, i32 1
    store i64 64, i64* %2 ; set the capacity to 64 (8 bits/byte * 8 bytes)
    %3 = getelementptr %Array.i1, %Array.i1* %this, i32 0, i32 2
    %4 = call i8* @malloc(i64 8)
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


define dso_local i32 @main() {
    %world = alloca %Array.i1
    call void @Array.i1.new(%Array.i1* %world)

    ; TODO->stuff in here

    call void @Array.i1.free(%Array.i1* %world)
    ret i32 0
}

define dso_local void @Array.i1.resize(%Array.i1* %this, i64 %newCapacity) {
    ret void
}

define dso_local void @Array.i1.push(%Array.i1* %this, i1 %value) {
    ret void
}