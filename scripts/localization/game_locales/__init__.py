"""Deterministic source imports for full-game locale data.

This package deliberately does not integrate imported text with the runtime
catalog. Imported FE8J-layout identifiers remain source identifiers until a
separate mapping document has been semantically verified.
"""

from .controls import (
    CANONICAL_CONTROL_GRAMMAR,
    ControlSyntaxError,
    canonical_control_token,
    expand_canonical_control,
    expand_canonical_control_bytes,
    expand_canonical_controls,
    expand_canonical_controls_bytes,
    expand_canonical_text,
    normalize_source_controls,
    validate_canonical_text,
)
from .crosswalk import (
    CrosswalkError,
    build_crosswalk_coverage_report,
    build_release_mapping,
    harvest_structural_evidence,
    validate_evidence_document,
)
from .mapping import MappingError, validate_mapping_document
from .parsers import LocaleSourceError

__all__ = (
    "CANONICAL_CONTROL_GRAMMAR",
    "ControlSyntaxError",
    "CrosswalkError",
    "LocaleSourceError",
    "MappingError",
    "canonical_control_token",
    "build_crosswalk_coverage_report",
    "build_release_mapping",
    "expand_canonical_control",
    "expand_canonical_control_bytes",
    "expand_canonical_controls",
    "expand_canonical_controls_bytes",
    "expand_canonical_text",
    "normalize_source_controls",
    "harvest_structural_evidence",
    "validate_canonical_text",
    "validate_evidence_document",
    "validate_mapping_document",
)
