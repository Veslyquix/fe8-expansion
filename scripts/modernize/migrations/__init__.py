"""Adjacent save-format migration registry/framework (issue #9).

Lives next to scripts/modernize/save_format_tool.py and reuses it (via
subprocess, never re-implementing its classify/publish safety model) for
every mechanical migration step it declares. See
docs/migration_registry.md.
"""
