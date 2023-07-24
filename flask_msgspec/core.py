import inspect
from functools import wraps
from inspect import Parameter, Signature
from typing import Any, Callable, Dict, Optional, Tuple, Type, Union

from flask import current_app, make_response, request
from msgspec import EncodeError, ValidationError, convert
from msgspec.json import decode as msgspec_json_decode
from msgspec.json import encode as msgspec_json_encode
from werkzeug.wrappers import Response

Empty = Signature.empty
ACCEPTED_PARAMS_KINDS = {
    Parameter.POSITIONAL_ONLY,
    Parameter.POSITIONAL_OR_KEYWORD,
    Parameter.KEYWORD_ONLY,
}


def _dec_hook(type_: Type[Any], value: Any) -> Any:
    if isinstance(value, type_):
        return value
    raise TypeError(f"Type `{type(value)}` is not supported.")


def _build_param_type_map(
    signature: Signature,
    kwargs: Dict[str, Any],
    namespace: Optional[Dict[str, Type[Any]]],
):
    param_type_map: Dict[str, Type[Any]] = {}

    for name, param in signature.parameters.items():
        if param.kind not in ACCEPTED_PARAMS_KINDS:
            continue
        if param.annotation is Empty:
            raise TypeError(f"Type annonation is missing for `{name}` parameter.")

        if name not in kwargs:
            kwargs[name] = param.default

        if isinstance(param.annotation, str):
            type_ = None if namespace is None else namespace.get(param.annotation)
            if type_ is None:
                if namespace is None:
                    raise KeyError(
                        f"Unable to resolve type annotation `{param.annotation}`. "
                        f"Consider supplying a signature namespace."
                    )
                raise KeyError(f"Unable to resolve type annotation `{param.annotation}`.")
            param_type_map[name] = type_
        else:
            param_type_map[name] = param.annotation
    return param_type_map


def _convert_query_params(
    kwargs: Dict[str, Any], param_type_map: Dict[str, Type[Any]]
) -> Dict[str, Union[str, Dict[str, Any]]]:
    for key, value in request.args.items():
        if key not in kwargs:
            continue
        try:
            kwargs[key] = convert(value, type=param_type_map[key], strict=False, dec_hook=_dec_hook)
        except ValidationError as ex:
            return {"error": ValidationError.__name__, "detail": {"key": key, "msg": "".join(ex.args)}}
    return {}


def _check_for_missing_query_params(kwargs: Dict[str, Any]) -> Optional[Dict[str, Union[str, Dict[str, Any]]]]:
    for key, value in kwargs.items():
        if key == "body":
            continue
        if value is Empty:
            return {"error": ValidationError.__name__, "detail": {"key": key, "msg": "Missing"}}
    return None


def _validate_path_params(
    view_args: Dict[str, Any],
    kwargs: Dict[str, Any],
    param_type_map: Dict[str, Type[Any]],
) -> Optional[Dict[str, Union[str, Dict[str, Any]]]]:
    try:
        for name, value in view_args.items():
            kwargs[name] = convert(value, type=param_type_map[name], strict=False, dec_hook=_dec_hook)
    except ValidationError as ex:
        return {"error": ValidationError.__name__, "detail": {"key": name, "msg": "".join(ex.args)}}


def _validate_body(
    body_data: Union[bytes, Dict[str, str]], kwargs: Dict[str, Any], param_type_map: Dict[str, Type[Any]]
) -> Optional[Dict[str, Union[str, Dict[str, Any]]]]:
    body_model = param_type_map.get("body", Empty)
    if body_model is Empty:
        raise ValueError("Expected a body model type.")

    try:
        if isinstance(body_data, bytes):
            kwargs["body"] = msgspec_json_decode(body_data, type=body_model, strict=False, dec_hook=_dec_hook)
        else:
            kwargs["body"] = convert(body_data, type=body_model, strict=False, dec_hook=_dec_hook)
    except ValidationError as ex:
        return {"error": ValidationError.__name__, "detail": {"key": "body", "msg": "".join(ex.args)}}


def _unpack_result(result: Any) -> Tuple[Any, Optional[int], Any]:
    response_value: Any = None
    status_code: Optional[int] = None
    headers: Any = None

    if not isinstance(result, (tuple, Response)):
        response_value = result
    elif isinstance(result, tuple):
        assert len(result) in {2, 3}  # noqa: S101
        if len(result) == 2:
            if isinstance(result[1], int):
                response_value, status_code = result
            else:
                response_value, headers = result
        elif len(result) == 3:
            response_value, status_code, headers = result
    else:
        raise ValueError(f"Unhandled return type: {type(result)!r}.")

    return response_value, status_code, headers


def validate(
    return_model: Optional[Type[Any]] = None,
    status_code: int = 200,
    signature_namespace: Optional[Dict[str, Type[Any]]] = None,
):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            sig = inspect.signature(func)
            _return_model = return_model or sig.return_annotation
            if _return_model is Empty:
                raise TypeError("Missing return type.")

            param_type_map = _build_param_type_map(sig, kwargs, signature_namespace)

            if request.args and (error := _convert_query_params(kwargs, param_type_map)):
                return error, 422

            if error := _check_for_missing_query_params(kwargs):
                return error, 422

            if request.view_args and (error := _validate_path_params(request.view_args, kwargs, param_type_map)):
                return error, 422

            if "body" in kwargs and (
                error := _validate_body(request.data or request.form.to_dict(), kwargs, param_type_map)
            ):
                return error, 422

            result = current_app.ensure_sync(func)(*args, **kwargs)

            response_value, _status_code, headers = _unpack_result(result)
            _status_code = _status_code or status_code

            try:
                response_value = convert(response_value, type=_return_model, strict=False, dec_hook=_dec_hook)
                json_data = msgspec_json_encode(response_value)
            except (ValidationError, EncodeError) as ex:
                return {"error": type(ex).__name__, "detail": {"msg": "".join(ex.args)}}, 422

            resp = make_response(json_data, _status_code)
            resp.mimetype = "application/json"

            if headers:
                resp.headers.update(headers)

            return resp

        return wrapper

    return decorator
