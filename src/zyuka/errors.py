"""Plain-language errors shown to the user without stack traces by default."""

from __future__ import annotations


class ZyukaError(Exception):
    """Base class for all user-facing Zyuka errors.

    ``message`` is the plain-language description of what went wrong.
    ``suggest`` is a short, concrete next step the user can try.
    """

    def __init__(self, message: str, suggest: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.suggest = suggest

    def render(self) -> str:
        if self.suggest:
            return f"{self.message}\nSuggested fix: {self.suggest}"
        return self.message


class ConfigError(ZyukaError):
    """Raised when ``zyuka.yml`` or ``logframe.yml`` is invalid."""


class IngestError(ZyukaError):
    """Raised for problems reading Kobo / ODK / XLSForm inputs."""


class PrivacyError(ZyukaError):
    """Raised when a privacy guarantee cannot be upheld."""


class SecurityError(ZyukaError):
    """Raised for key, crypto, audit or sanitiser problems."""


class IndicatorError(ZyukaError):
    """Raised for logframe or indicator computation problems."""


class ReportError(ZyukaError):
    """Raised for report rendering problems."""
