from typing import Any


class MockSessionState(dict):
    """Mock for streamlit.session_state that supports attribute and item access."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'MockSessionState' object has no attribute '{name}'") from None

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    def __delattr__(self, name: str) -> None:
        try:
            del self[name]
        except KeyError:
            raise AttributeError(f"'MockSessionState' object has no attribute '{name}'") from None

    def get(self, key: str, default: Any = None) -> Any:
        return super().get(key, default)
