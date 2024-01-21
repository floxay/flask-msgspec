from enum import Enum
from typing import Any

__all__ = ("ConfigKey",)


class ConfigKey(str, Enum):
    """Because strings are evil!"""

    FLASK_MSGSPEC_VALIDATION_EXCEPTIONS = "FLASK_MSGSPEC_VALIDATION_EXCEPTIONS"

    def __get__(self, instance: Any, owner: Any = None) -> str:
        return self.value

    def __str__(self) -> str:
        return self.value
