# Test program expected to print out "aaaaa".

program 3 < 4096

include "include.eh"

segment text(flags: rx) {
    [_start]

    bb =1h4
    b9 <<data:string>>
    ba =1d4
    @include_syscall(=4d4)

    ff :x86.args{ 0, [dword ptr data:counter] }
    81 =00111101b <<data:counter>> =5d4
    72 <_start>

    bb =0h4
    @include_exit()
}

segment data(flags: rw) {
  [string] "a"
  [[counter: 4]]
}
