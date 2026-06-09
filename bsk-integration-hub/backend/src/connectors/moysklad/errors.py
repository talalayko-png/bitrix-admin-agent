"""Normalized MoySklad API errors."""

from __future__ import annotations

from typing import Any


class MoySkladError(RuntimeError):
    """A normalized MoySklad API error (parsed from the ``errors`` array)."""

    def __init__(self, status: int, errors: list[dict[str, Any]] | None, message: str) -> None:
        self.status = status
        self.errors = errors or []
        super().__init__(message)

    @classmethod
    def from_response(cls, status: int, body: Any) -> MoySkladError:
        errors: list[dict[str, Any]] = []
        if isinstance(body, dict):
            errors = body.get("errors") or []
        if errors:
            parts = [
                f"{e.get('error', 'error')} (code={e.get('code')})" for e in errors
            ]
            message = f"MoySklad {status}: " + "; ".join(parts)
        else:
            message = f"MoySklad {status}: {str(body)[:300]}"
        return cls(status, errors, message)


class MoySkladRateLimited(MoySkladError):
    """HTTP 429 from MoySklad. Carries the retry-after hint (seconds)."""

    def __init__(self, retry_after: float, body: Any = None) -> None:
        self.retry_after = retry_after
        super().__init__(429, (body or {}).get("errors") if isinstance(body, dict) else None,
                         f"MoySklad 429: rate limited, retry after {retry_after}s")
