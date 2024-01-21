from __future__ import annotations

from typing import Any

from flask.json.provider import JSONProvider
from msgspec.json import Decoder, Encoder, decode, format

from flask_msgspec._serializer import default_msgspec_json_decoder, default_msgspec_json_encoder
from flask_msgspec._types import Empty

__all__ = ("MsgspecJSONProvider",)


class MsgspecJSONProvider(JSONProvider):
    compact: bool | None = None

    encoder: Encoder = default_msgspec_json_encoder
    """``msgspec.json.Encoder`` instance, you can supply your own, configured encoder"""
    decoder: Decoder[Any] = default_msgspec_json_decoder
    """
    ``msgspec.json.Decoder`` instance, you can supply your own, configured decoder\n
    If you specify a type on the decoder level then all serialized json will be attempted to load into that type,
    if you don't know what this means do not specify a type for your custom ``Decoder`` instance.
    """

    def dumpb(self, obj: Any, **kwargs: Any) -> bytes:  # noqa: ARG002
        encoded = self.encoder.encode(obj)

        if self.compact is False or (self.compact is None and self._app.debug):
            encoded = format(encoded, indent=2)

        return encoded

    def dumps(self, obj: Any, **kwargs: Any) -> str:
        return self.dumpb(obj, **kwargs).decode()

    def loads(self, s: str | bytes, *, type_: type[Any] = Empty, strict: bool = True, **kwargs: Any) -> Any:  # noqa: ARG002
        if type_ is Empty:
            return self.decoder.decode(s)
        return decode(
            s,
            type=type_,
            strict=strict,
            dec_hook=self.decoder.dec_hook,
        )
