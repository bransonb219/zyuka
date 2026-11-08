"""Plain-language errors shown to the user without stack traces by default."""

from __future__ import annotations


class LingaError(Exception):
    """Base class for all user-facing Linga errors.

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


class ConfigError(LingaError):
    """Raised when ``linga.yml`` or ``logframe.yml`` is invalid."""


class IngestError(LingaError):
    """Raised for problems reading Kobo / ODK / XLSForm inputs."""


class PrivacyError(LingaError):
    """Raised when a privacy guarantee cannot be upheld."""


class SecurityError(LingaError):
    """Raised for key, crypto, audit or sanitiser problems."""


class IndicatorError(LingaError):
    """Raised for logframe or indicator computation problems."""


class ReportError(LingaError):
    """Raised for report rendering problems."""
