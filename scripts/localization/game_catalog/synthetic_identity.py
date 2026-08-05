"""Run expansion_config identity resolution for internal CJK test profiles."""

from __future__ import annotations

from scripts.localization import schema as locale_schema
from scripts.modernize import expansion_config


_validate_enabled_locales = expansion_config.validate_enabled_locales


def _validate_synthetic_enabled_locales(value):
    real_cjk_locales = locale_schema.REAL_CJK_LOCALES
    configurable_locales = locale_schema.CONFIGURABLE_LOCALES
    try:
        locale_schema.REAL_CJK_LOCALES = ()
        locale_schema.CONFIGURABLE_LOCALES = tuple(
            locale
            for locale in locale_schema.LOCALE_IDS
            if locale in configurable_locales or locale in real_cjk_locales
        )
        return _validate_enabled_locales(value)
    finally:
        locale_schema.REAL_CJK_LOCALES = real_cjk_locales
        locale_schema.CONFIGURABLE_LOCALES = configurable_locales


def main(argv=None) -> int:
    previous_validator = expansion_config.validate_enabled_locales
    try:
        expansion_config.validate_enabled_locales = _validate_synthetic_enabled_locales
        return expansion_config.main(argv)
    finally:
        expansion_config.validate_enabled_locales = previous_validator


if __name__ == "__main__":
    raise SystemExit(main())
