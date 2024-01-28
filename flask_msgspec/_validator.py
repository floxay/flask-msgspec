from __future__ import annotations

import sys
import typing
from functools import wraps
from inspect import Parameter, signature
from typing import Any, Callable, ClassVar, Sequence, TypeVar, cast

from flask import Response, current_app, request
from msgspec import DecodeError, EncodeError, ValidationError, convert
from msgspec.json import decode as msgspec_json_decode
from typing_extensions import ParamSpec, get_type_hints

from flask_msgspec._serializer import default_dec_hook
from flask_msgspec._types import Empty, ParameterData, ValidationErrorResponse
from flask_msgspec._utils import make_json_response, unpack_result
from flask_msgspec.config import ConfigKey
from flask_msgspec.exceptions import (
    FlaskMsgspecConfigurationError,
    FlaskMsgspecResponseValidationError,
    FlaskMsgspecValidationError,
)
from flask_msgspec.provider import MsgspecJSONProvider

if typing.TYPE_CHECKING:
    from flask.typing import ResponseValue

    from flask_msgspec._types import KwArgs

T = TypeVar("T")
P = ParamSpec("P")
_ACCEPTED_PARAM_KINDS = {
    Parameter.POSITIONAL_ONLY,
    Parameter.POSITIONAL_OR_KEYWORD,
    Parameter.KEYWORD_ONLY,
}

__all__ = ("validate",)


class validate:  # noqa: N801
    __slots__ = (
        "_dec_hook",
        "_parameter_map",
        "response_model",
        "strict_response_validation",
    )

    _namespace_map: ClassVar[dict[str, type[Any]]] = {}

    def __init__(
        self,
        *,
        strict_response_validation: bool | None = None,
        signature_types: Sequence[type[Any]] | None = None,
    ) -> None:
        """
        Args:
            strict_response_validation: An optional boolean for response validation. ``None`` will turn off response validation entirely.
                ``False`` enables looser type coercion rules ("Lax"), meanwhile ``True`` will strictly validate the types ("Strict).
                See more: https://jcristharif.com/msgspec/usage.html#strict-vs-lax-mode
        """
        self._parameter_map: dict[str, ParameterData] = {}
        self._dec_hook: Callable[[type[Any], Any], Any] | None = default_dec_hook

        self.strict_response_validation: bool | None = strict_response_validation
        self.response_model: type[Any] = Empty

        self._update_namespace_map(signature_types)

    def __call__(self, func: Callable[P, T]) -> Callable[P, Response]:
        self._resolve_signature(func)  # precompute what we can here

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            if isinstance(current_app.json, MsgspecJSONProvider):
                self._dec_hook = current_app.json.decoder.dec_hook

            if err := self._validate_parameters(kwargs):
                return err

            result: T = current_app.ensure_sync(func)(*args, **kwargs)
            response_value, status_code, headers = unpack_result(result)

            resp = (
                make_json_response(response_value)
                if self.strict_response_validation is None
                else self._validate_response(response_value, strict=self.strict_response_validation)
            )

            if headers:
                resp.headers.update(headers)  # type: ignore[arg-type]

            if resp.status_code != 400 and status_code is not None:
                resp.status_code = status_code

            return resp

        return wrapper

    @classmethod
    def _update_namespace_map(cls, signature_types: Sequence[type[Any]] | None) -> None:
        if signature_types:
            cls._namespace_map.update({type_.__name__: type_ for type_ in signature_types})

    def _resolve_signature(self, func: Callable[P, T]) -> None:
        merged_namespace_map = {
            **locals(),
            **globals(),
            **vars(typing),
            **vars(sys.modules[func.__module__]),
            **self._namespace_map,
        }
        type_hints = get_type_hints(func, merged_namespace_map, include_extras=True)

        self.response_model = type_hints.pop("return", Empty)
        if self.response_model is Empty:
            msg = "Missing return type annotation"
            raise FlaskMsgspecConfigurationError(msg)

        sig = signature(func)
        for name, param in sig.parameters.items():
            if param.kind not in _ACCEPTED_PARAM_KINDS:
                continue

            if param.annotation is Empty:
                msg = f"Type annonation is missing for `{name}` parameter"
                raise FlaskMsgspecConfigurationError(msg)

            self._parameter_map[name] = ParameterData(type_hints[name], param.default)

    def _add_missing_params(self, query_params: dict[str, str], argument_value_map: KwArgs) -> None:
        """
        Add missing positional parameters from handler signature
        to kwargs to avoid ``TypeError`` when calling the wrapped func
        """
        for name in self._parameter_map:
            if name not in argument_value_map:
                value = query_params.get(name) or self._parameter_map[name].default_value
                argument_value_map[name] = value

    def _check_for_missing_query_params(self, argument_value_map: KwArgs) -> Response | None:
        for key, value in argument_value_map.items():
            if key == "body":
                continue

            if value is Empty:
                err = ValidationErrorResponse(
                    {"error": ValidationError.__name__, "detail": {"key": key, "msg": "Missing parameter"}},
                )
                if current_app.config.get(ConfigKey.FLASK_MSGSPEC_VALIDATION_EXCEPTIONS):  # pyright: ignore[reportUnknownMemberType]
                    raise FlaskMsgspecValidationError(**err)
                return make_json_response(err, 400)
        return None

    def _convert_query_params(self, query_params: dict[str, str], argument_value_map: KwArgs) -> Response | None:
        for key, value in query_params.items():
            if key not in argument_value_map:
                continue

            try:
                argument_value_map[key] = convert(
                    value,
                    type=self._parameter_map[key].type_,
                    strict=False,
                    dec_hook=self._dec_hook,
                )
            except ValidationError as ex:
                err = ValidationErrorResponse(
                    {"error": type(ex).__name__, "detail": {"key": key, "msg": "".join(ex.args)}},
                )
                if current_app.config.get(ConfigKey.FLASK_MSGSPEC_VALIDATION_EXCEPTIONS):  # pyright: ignore[reportUnknownMemberType]
                    raise FlaskMsgspecValidationError(**err) from ex
                return make_json_response(err, 400)
        return None

    def _validate_path_params(
        self,
        view_args: dict[str, Any],
        argument_value_map: KwArgs,
    ) -> Response | None:
        try:
            for key, value in view_args.items():
                argument_value_map[key] = convert(
                    value,
                    type=self._parameter_map[key].type_,
                    strict=False,
                    dec_hook=self._dec_hook,
                )
        except ValidationError as ex:
            err = ValidationErrorResponse({"error": type(ex).__name__, "detail": {"key": key, "msg": "".join(ex.args)}})  # pyright: ignore[reportPossiblyUnboundVariable]
            if current_app.config.get(ConfigKey.FLASK_MSGSPEC_VALIDATION_EXCEPTIONS):  # pyright: ignore[reportUnknownMemberType]
                raise FlaskMsgspecValidationError(**err) from ex
            return make_json_response(err, 400)
        return None

    def _validate_body(
        self,
        body_data: bytes | dict[str, list[str]],
        argument_value_map: KwArgs,
    ) -> Response | None:
        body_model = self._parameter_map.get("body", Empty)

        if body_model is Empty:
            msg = "Expected a body model type"
            raise ValueError(msg)

        body_model = cast(ParameterData, body_model)

        try:
            if isinstance(body_data, bytes):
                if isinstance(current_app.json, MsgspecJSONProvider):
                    argument_value_map["body"] = current_app.json.loads(body_data, type_=Empty, strict=False)
                else:
                    argument_value_map["body"] = msgspec_json_decode(
                        body_data,
                        type=body_model.type_,
                        strict=False,
                        dec_hook=self._dec_hook,
                    )
            else:
                argument_value_map["body"] = convert(
                    body_data,
                    type=body_model.type_,
                    strict=False,
                    dec_hook=self._dec_hook,
                )
        except (ValidationError, DecodeError) as ex:
            err = ValidationErrorResponse(
                {"error": type(ex).__name__, "detail": {"key": "body", "msg": "".join(ex.args)}},
            )
            if current_app.config.get(ConfigKey.FLASK_MSGSPEC_VALIDATION_EXCEPTIONS):  # pyright: ignore[reportUnknownMemberType]
                raise FlaskMsgspecValidationError(**err) from ex
            return make_json_response(err, 400)
        return None

    def _validate_parameters(self, argument_value_map: KwArgs) -> Response | None:
        self._add_missing_params(request.args, argument_value_map)

        if err := self._check_for_missing_query_params(argument_value_map):
            return err

        if request.args and (
            err := self._convert_query_params(
                request.args,
                argument_value_map,
            )
        ):
            return err

        if request.view_args and (
            err := self._validate_path_params(
                request.view_args,
                argument_value_map,
            )
        ):
            return err

        if "body" in argument_value_map and (
            error := self._validate_body(
                request.data or request.form.to_dict(flat=False),
                argument_value_map,
            )
        ):
            return error
        return None

    def _validate_response(self, response_value: ResponseValue | None, *, strict: bool) -> Response:
        if response_value is not None:
            try:
                response_value = convert(
                    response_value,
                    type=self.response_model,
                    strict=strict,
                    dec_hook=self._dec_hook,
                )
            except (ValidationError, EncodeError, TypeError) as ex:
                raise FlaskMsgspecResponseValidationError(original_exception=ex) from ex

        return make_json_response(response_value)
