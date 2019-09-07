program 3 < 4096

fragment include_exit() {
    @include_syscall(=1d4)
}

fragment include_syscall(number) {
    b8 $number
    cd 80
}
