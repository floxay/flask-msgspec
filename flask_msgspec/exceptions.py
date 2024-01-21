from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "BaseFlaskMsgspecError",
    "FlaskMsgspecConfigurationError",
    "BaseFlaskMsgspecValidationError",
    "FlaskMsgspecValidationError",
    "FlaskMsgspecResponseValidationError",
)


class BaseFlaskMsgspecError(Exception):
    """Base exception class for all ``flask-msgspec`` exceptions"""


class FlaskMsgspecConfigurationError(BaseFlaskMsgspecError):
    """Base exception for all validator initialization related ``flask-msgspec`` exceptions"""


class BaseFlaskMsgspecValidationError(BaseFlaskMsgspecError):
    """Base exception for all runtime validation related ``flask-msgspec`` exceptions"""


@dataclass
class FlaskMsgspecValidationError(BaseFlaskMsgspecValidationError):
    """Exception for client-related runtime validation ``flask-msgspec`` exceptions"""

    error: str
    status_code: int = 400
    detail: dict[str, str | dict[str, str]] | None = None


@dataclass
class FlaskMsgspecResponseValidationError(BaseFlaskMsgspecValidationError):
    """
    Internal exception for response validation related ``flask-msgspec`` exceptions

    Generally this should not be returned to the client as response validation is an internal error
    """

    original_exception: BaseException
