# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

program 3 < 4096

include "function.eh"

fragment common_exit() {
    @common_syscall(=1d4)
}

fragment common_syscall3(number, ebx, ecx, edx) {
    bb $ebx
    b9 $ecx
    ba $edx
    @common_syscall($number)
}

fragment common_syscall(number) {
    b8 $number
    cd 80
}

fragment common_strlen() {
    31 c0 # xor eax, eax (eax is length)
    8b =01001101b 08 # mov ecx, [ebp + 8] (use ecx for str pointer)
    [__loop]
    80 =00111100b =00001000b 00 # cmp [ecx + eax * 1], 0
    74 <__break> # if zero goto __break
    40 # inc eax
    eb <__loop> # goto __loop
    [__break]
}

fragment common_strlen_fn() {
    [common_strlen_fn]

    # str_ptr: [ebp + 8]
    @function_def(@common_strlen())
}

fragment common_puts_fn() {
    [common_puts_fn]
    @function_def(
        @common_strlen()
        89 c2 # mov edx, eax
        8b =01001101b 08 # mov ecx, [ebp + 8]
        31 db 43 # xor ebx, ebx; inc ebx
        @common_syscall(=4d4)
    )
}

fragment common_getline_fn() {
    [common_getline_fn]
    # buffer: [ebp + 8]
    # restrict: [ebp + 12]
    @function_def(
        # read(0, [ebp + 8], [ebp + 12])
        31 db # xor ebx, ebx (stdin)
        8b 4d =8d # mov ecx, [ebp + 8]
        8b 55 =12d # mov edx, [ebp + 12]
        @common_syscall(=3d4)

        # null the newline character (or when restrict is reached)
        31 c0 # xor eax, eax (size)
        # ecx still holds pointer to start, edx max size

        [__loop]
        80 =00111100b =00001000b 0a # cmp [ecx + eax * 1], '\n'
        74 <__break> # if zero goto __break
        39 d0 # cmp eax, edx
        74 <__break>
        40 # inc eax
        eb <__loop>

        [__break]
        40 # inc eax
        c6 04 01 00 # mov8 [ecx + eax * 1], '\0'
    )
}
