from __future__ import annotations

from pathlib import PurePath
from typing import Any

from msgspec.json import Decoder, Encoder


def default_enc_hook(obj: Any) -> Any:
    if isinstance(obj, PurePath):
        return str(obj)

    if hasattr(obj, "__html__"):
        return str(obj.__html__())

    msg = f"Object of type {type(obj).__name__} is not JSON serializable"
    raise TypeError(msg)


def default_dec_hook(type_: type[Any], value: Any) -> Any:
    if isinstance(value, type_):
        return value

    if issubclass(type_, PurePath):
        return type_(value)

    msg = f"Type {type_.__name__} is not supported"
    raise TypeError(msg)


default_msgspec_json_encoder = Encoder(enc_hook=default_enc_hook)
default_msgspec_json_decoder = Decoder(dec_hook=default_dec_hook)
