from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import Response, jsonify

if TYPE_CHECKING:
    from flask.typing import HeadersValue, ResponseReturnValue, ResponseValue


def make_json_response(data: ResponseValue | None, status_code: int | None = None) -> Response:
    resp = jsonify(data)

    if status_code:
        resp.status_code = status_code

    return resp


def unpack_result(result: ResponseReturnValue | Any) -> tuple[ResponseValue | None, int | None, HeadersValue | None]:
    response_value: ResponseValue | None = None
    status_code: int | None = None
    headers: HeadersValue | None = None

    if isinstance(result, tuple):
        if len(result) == 3:
            response_value, status_code, headers = result
        elif len(result) == 2:
            response_value, status_or_headers = result
            if isinstance(status_or_headers, int):
                status_code = status_or_headers
            else:
                headers = status_or_headers
        else:
            # the standard Flask error
            msg = (
                "The view function did not return a valid response tuple."
                " The tuple must have the form (body, status, headers),"
                " (body, status), or (body, headers)."
            )
            raise TypeError(msg)
    else:
        # apart from str, bytes, list, mapping the rest (response, callable, iterator/generator, unknown)
        # will fail later on conversion if response validation is enabled
        # incorrect stuff (unknown) will fail upon response creation by flask
        response_value = result  # type: ignore[assignment]

    return response_value, status_code, headers
