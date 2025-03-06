"""
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator.

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import ast
import logging
import math
import operator
from typing import Callable, Union, cast

logger = logging.getLogger(__name__)

# Type aliases
Number = Union[int, float]
MathFunc = Callable[..., Number]
BinOperator = Callable[[Number, Number], Number]
UnOperator = Callable[[Number], Number]

def safe_eval(s: str) -> Number:
    def checkmath(x: str, *args: Number) -> Number:
        if x not in [x for x in dir(math) if "__" not in x]:
            msg = f"Unknown func {x}()"
            raise SyntaxError(msg)
        fun = cast(MathFunc, getattr(math, x))
        try:
            return fun(*args)
        except TypeError as e:
            msg = f"Invalid arguments for {x}(): {e!s}"
            raise SyntaxError(msg) from e

    bin_ops: dict[type[ast.operator], BinOperator] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.Call: checkmath,
        ast.BinOp: ast.BinOp,
    }

    un_ops: dict[type[ast.UnaryOp], UnOperator] = {
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
        ast.UnaryOp: ast.UnaryOp,
    }

    tree = ast.parse(s, mode="eval")

    def _eval(node: ast.AST) -> Number:
        if isinstance(node, ast.Expression):
            logger.debug("Expr")
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            logger.info("Const")
            return cast(Number, node.value)
        if isinstance(node, ast.Name):
            # Handle math constants like pi, e, etc.
            logger.info("MathConst")
            if hasattr(math, node.id):
                return cast(Number, getattr(math, node.id))
            msg = f"Unknown constant: {node.id}"
            raise SyntaxError(msg)
        if isinstance(node, ast.BinOp):
            logger.debug("BinOp")
            left = _eval(node.left)
            right = _eval(node.right)
            if type(node.op) not in bin_ops:
                msg = f"Unsupported operator: {type(node.op)}"
                raise SyntaxError(msg)
            return bin_ops[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp):
            logger.debug("UpOp")
            operand = _eval(node.operand)
            if type(node.op) not in un_ops:
                msg = f"Unsupported operator: {type(node.op)}"
                raise SyntaxError(msg)
            return un_ops[type(node.op)](operand)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                msg = "Only direct math function calls allowed"
                raise SyntaxError(msg)
            args = [_eval(x) for x in node.args]
            return checkmath(node.func.id, *args)
        msg = f"Bad syntax, {type(node)}"
        raise SyntaxError(msg)

    return _eval(tree)
