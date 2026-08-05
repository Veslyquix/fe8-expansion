"""Deterministic source imports for full-game locale data.

This package deliberately does not integrate imported text with the runtime
catalog. Imported FE8J-layout identifiers remain source identifiers until a
separate mapping document has been semantically verified.
"""

from .mapping import MappingError, validate_mapping_document
from .parsers import LocaleSourceError

__all__ = (
    "LocaleSourceError",
    "MappingError",
    "validate_mapping_document",
)
