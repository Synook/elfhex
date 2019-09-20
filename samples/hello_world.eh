program 3 < 4096

include "common.eh"

segment text(flags: rx) {
    @!common_puts_fn()

    [_start]
    68 <<string>>
    @function_call_rel32(<common_puts_fn:4>, =1d)
    31 c0
    @common_exit()

    [string] "Hello, world!" 0a 00
}
