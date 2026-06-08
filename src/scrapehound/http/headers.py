"""Case-insensitive HTTP header helpers."""

from __future__ import annotations

from collections.abc import Iterable


class CaseInsensitiveHeaders(dict[str, str]):
    """A small dict that normalizes lookups while preserving readable keys."""

    def __init__(self, items: Iterable[tuple[str, str]] | None = None):
        super().__init__()
        self._keymap: dict[str, str] = {}
        if items:
            for key, value in items:
                self[key] = value

    def __setitem__(self, key: str, value: str) -> None:
        lower = key.lower()
        existing = self._keymap.get(lower)
        if existing is not None and existing != key:
            super().__delitem__(existing)
        self._keymap[lower] = key
        super().__setitem__(key, value)

    def __getitem__(self, key: str) -> str:
        return super().__getitem__(self._keymap[key.lower()])

    def __delitem__(self, key: str) -> None:
        actual = self._keymap.pop(key.lower())
        super().__delitem__(actual)

    def get(self, key: str, default: str | None = None) -> str | None:  # type: ignore[override]
        actual = self._keymap.get(key.lower())
        if actual is None:
            return default
        return super().get(actual, default)

    def setdefault(self, key: str, default: str = "") -> str:  # type: ignore[override]
        if key not in self:
            self[key] = default
            return default
        return self[key]

    def pop(self, key: str, *args: str) -> str:  # type: ignore[override]
        try:
            value = self[key]
        except KeyError:
            if args:
                return args[0]
            raise
        del self[key]
        return value

    def update(self, other: Iterable[tuple[str, str]] | dict[str, str]) -> None:  # type: ignore[override]
        items = other.items() if isinstance(other, dict) else other
        for key, value in items:
            self[key] = value

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return key.lower() in self._keymap

    def lower_items(self) -> dict[str, str]:
        return {key.lower(): value for key, value in self.items()}
