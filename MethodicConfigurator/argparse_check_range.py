#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Dmitriy Kovalev

SPDX-License-Identifier: Apache-2.0

https://gist.github.com/dmitriykovalev/2ab1aa33a8099ef2d514925d84aa89e7
'''

from argparse import Action, ArgumentError
from operator import ge, gt, le, lt

from MethodicConfigurator.internationalization import _


class CheckRange(Action):
    '''
    Check if the Argparse argument value is within the specified range
    '''
    ops = frozenset({"inf": gt,
           "min": ge,
           "sup": lt,
           "max": le})

    def __init__(self, *args, **kwargs):
        if "min" in kwargs and "inf" in kwargs:
            raise ValueError(_("either min or inf, but not both"))
        if "max" in kwargs and "sup" in kwargs:
            raise ValueError(_("either max or sup, but not both"))

        for name in self.ops:
            if name in kwargs:
                setattr(self, name, kwargs.pop(name))

        super().__init__(*args, **kwargs)

    def interval(self):
        if hasattr(self, "min"):
            _lo = f"[{self.min}"
        elif hasattr(self, "inf"):
            _lo = f"({self.inf}"
        else:
            _lo = "(-infinity"

        if hasattr(self, "max"):
            _up = f"{self.max}]"
        elif hasattr(self, "sup"):
            _up = f"{self.sup})"
        else:
            _up = "+infinity)"

        msg = _("valid range: {_lo}, {_up}")
        return msg.format(**locals())

    def __call__(self, parser, namespace, values, option_string=None):
        for name, op in self.ops.items():
            if hasattr(self, name) and not op(values, getattr(self, name)):
                raise ArgumentError(self, self.interval())
        setattr(namespace, self.dest, values)
