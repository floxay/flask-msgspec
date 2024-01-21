from __future__ import annotations

from inspect import Signature
from typing import Any, Dict, NamedTuple, TypedDict

KwArgs = Dict[str, Any]
Empty = Signature.empty


class ParameterData(NamedTuple):
    type_: type[Any]
    """Type of the parameter"""
    default_value: Any
    """The default value of the parameter, if specified in the signature, otherwise ``_Empty``"""


class ValidationErrorResponse(TypedDict):
    error: str
    detail: dict[str, str | dict[str, str]] | None
