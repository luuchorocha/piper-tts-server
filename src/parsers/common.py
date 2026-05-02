from typing import Any, TypeVar

ExcT = TypeVar("ExcT", bound=Exception)


def parse_bool(
    value: Any,
    *,
    field_name: str,
    default: bool,
    error_type: type[ExcT] = ValueError,
) -> bool:
    if value is None or value == "":
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False

    raise error_type(f"{field_name} must be a boolean")


__all__ = ["parse_bool"]