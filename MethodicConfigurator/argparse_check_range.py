#!/usr/bin/env python3

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# SPDX-FileCopyrightText: 2024 Dmitriy Kovalev

# SPDX-License-Identifier: Apache-2.0

# https://gist.github.com/dmitriykovalev/2ab1aa33a8099ef2d514925d84aa89e7

from argparse import Action
from argparse import ArgumentError
from operator import gt
from operator import ge
from operator import lt
from operator import le


class CheckRange(Action):
  ops = {'inf': gt,
         'min': ge,
         'sup': lt,
         'max': le}

  def __init__(self, *args, **kwargs):
    if 'min' in kwargs and 'inf' in kwargs:
      raise ValueError('either min or inf, but not both')
    if 'max' in kwargs and 'sup' in kwargs:
      raise ValueError('either max or sup, but not both')

    for name in self.ops:
      if name in kwargs:
        setattr(self, name, kwargs.pop(name))

    super().__init__(*args, **kwargs)

  def interval(self):
    if hasattr(self, 'min'):
      l = f'[{self.min}'
    elif hasattr(self, 'inf'):
      l = f'({self.inf}'
    else:
      l = '(-infinity'

    if hasattr(self, 'max'):
      u = f'{self.max}]'
    elif hasattr(self, 'sup'):
      u = f'{self.sup})'
    else:
      u = '+infinity)'

    return f'valid range: {l}, {u}'

  def __call__(self, parser, namespace, values, option_string=None):
    for name, op in self.ops.items():
      if hasattr(self, name) and not op(values, getattr(self, name)):
        raise ArgumentError(self, self.interval())
    setattr(namespace, self.dest, values)
