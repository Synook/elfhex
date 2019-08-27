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

fragment function_initstack() {
    8b 2d <<stack:stack + 1024>> # mov ebp, stack
    8b e5 # mov esp, ebp
}

fragment function_def(body) {
    55 # push ebp
    8b ec # mov ebp, esp
    $body
    5d # pop ebp
    c3 # return
}

fragment function_call_rel32(callee, num_args) {
    e8 $callee
    83 =11000100b $num_args # add esp, num_args
}
