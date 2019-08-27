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

include fragments "common.eh"

segment text(flags: rx) {
  [_start]
  [_start]

  # print hello to stdout
  @common_syscall3(=4d4, =1d4, <<strings:hello>>, =13d4)

  # if ++counter <= 5 goto loop
  ff =00000101b <<data:counter>>
  81 =00111101b <<data:counter>> =5d4
  72 <_start>

  @common_exit()
}

segment data(flags: rw size: 4) {
  [counter]
}

segment strings(flags: r) {
  [hello] "Hello, world" 0a
}

