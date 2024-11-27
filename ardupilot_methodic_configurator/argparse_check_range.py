"""
Check the range of an Argparse parameter.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Dmitriy Kovalev

SPDX-License-Identifier: Apache-2.0

https://gist.github.com/dmitriykovalev/2ab1aa33a8099ef2d514925d84aa89e7
"""

from argparse import Action, ArgumentError, ArgumentParser, Namespace
from collections.abc import Sequence
from operator import ge, gt, le, lt
from typing import Any, Union

from ardupilot_methodic_configurator import _


class CheckRange(Action):
    """Check if the Argparse argument value is within the specified range."""

    def __init__(self, *args, **kwargs) -> None:
        if "min" in kwargs and "inf" in kwargs:
            raise ValueError(_("either min or inf, but not both"))
        if "max" in kwargs and "sup" in kwargs:
            raise ValueError(_("either max or sup, but not both"))

        self.ops = {"inf": gt, "min": ge, "sup": lt, "max": le}
        for name in self.ops:
            if name in kwargs:
                setattr(self, name, kwargs.pop(name))

        super().__init__(*args, **kwargs)

    def interval(self) -> str:
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

    def __call__(
        self,
        parser: ArgumentParser,  # noqa: ARG002
        namespace: Namespace,
        values: Union[str, Sequence[Any], None],
        option_string: Union[None, str] = None,  # noqa: ARG002
    ) -> None:
        if not isinstance(values, (int, float)):
            raise ArgumentError(self, _("Value must be a number."))

        for name, op in self.ops.items():
            if hasattr(self, name):
                check_value = getattr(self, name)
                if check_value is not None and not op(values, check_value):
                    raise ArgumentError(self, self.interval())
        setattr(namespace, self.dest, values)
