from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class Context:
    """Small state container shared by workflow nodes."""

    def __init__(self, initial_data: Mapping[str, Any] | None = None):
        self._data: dict[str, Any] = dict(initial_data or {})

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def update(self, values: Mapping[str, Any] | None) -> None:
        if values:
            self._data.update(values)

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __contains__(self, key: object) -> bool:
        return key in self._data
