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
