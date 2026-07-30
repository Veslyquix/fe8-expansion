"""Schema/version dispatch and dependency graph representation.

Each generated-data table registers itself here under a stable
``(name, version)`` key (e.g. ``("supports", 1)``). The CLI resolves a
table name to its schema module through this registry instead of
hardcoding imports, so additional tables (Issue #5's later Chapter 2
slice) can be added without touching the dispatch logic.

The :class:`DependencyGraph` records which tables/headers a schema reads
(e.g. the ``supports`` table depends on the ``characters`` constants
header for reference validation). It provides a deterministic topological
order (for future multi-table generation) and a stable digest used in the
committed inventory/summary report so drift in dependencies is visible.
"""

from __future__ import annotations

import hashlib

from .diagnostics import GeneratedDataError


class SchemaRegistry:
    """Maps ``(name, version)`` to a registered :class:`TableSchema`."""

    def __init__(self):
        self._schemas = {}

    def register(self, schema):
        key = (schema.name, schema.version)
        if key in self._schemas:
            raise GeneratedDataError(
                "schema '{}' version {} already registered".format(schema.name, schema.version)
            )
        self._schemas[key] = schema
        return schema

    def resolve(self, name, version=None):
        if version is None:
            candidates = sorted(v for (n, v) in self._schemas if n == name)
            if not candidates:
                raise GeneratedDataError(
                    "unknown schema '{}'; known tables: {}".format(name, sorted({n for n, _ in self._schemas}))
                )
            version = candidates[-1]
        key = (name, version)
        if key not in self._schemas:
            raise GeneratedDataError(
                "unknown schema '{}' version {}; known: {}".format(name, version, sorted(self._schemas))
            )
        return self._schemas[key]

    def all_names(self):
        return sorted({n for n, _ in self._schemas})


REGISTRY = SchemaRegistry()


class TableSchema:
    """Base class every generated-data table schema derives from.

    Subclasses provide ``name``, ``version``, and override
    :meth:`load_records`, :meth:`validate`, and :meth:`dependencies`.

    The CLI (``cli.py``) drives every table exclusively through this
    interface -- no table-specific dispatch lives in the CLI itself. The
    ``default_*`` class attributes replace what used to be hardcoded
    per-table dicts in ``cli.py``; a table that has no hand-written C
    counterpart to round-trip against (e.g. metadata-only tables) simply
    leaves ``default_hand_source``/``default_output_name`` as ``None``.
    """

    name = None
    version = None

    # Fallback CLI defaults, overridable per-invocation with --source/
    # --hand-source/--out-dir/--inventory. `default_output_name = None`
    # means "this table has no generated-C output" (metadata-only tables
    # must leave it None rather than emit a meaningless C file).
    default_source = None
    default_hand_source = None
    default_output_name = None
    default_inventory_path = None

    # Optional record-budget diagnostic input. When a table maps onto a
    # fixed-size C array (a hard slot/memory bound), set ``record_budget``
    # to that capacity and ``record_budget_reason`` to a one-line human
    # explanation. The aggregate manifest surface (``manifest.py``) then
    # reports usage (``count/budget``) and raises an actionable
    # ``GeneratedDataError`` if a source ever authors more records than the
    # array can physically hold. Leave ``None`` for partial-file/open-ended
    # tables that have no single platform-wide capacity to honestly report.
    record_budget = None
    record_budget_reason = None

    def dependencies(self):
        """Return an iterable of dependency names (headers/other tables).

        Purely documentational/digest input (see ``DependencyGraph``) --
        entries here are not required to be other registered table names.
        Use :meth:`dependency_tables` for dependencies the CLI should
        actually load and hand to :meth:`validate`.
        """
        return ()

    def dependency_tables(self):
        """Return an iterable of *other registered table names* (see
        ``registry.py``) whose records this schema needs loaded for
        cross-table validation (e.g. ``eventlists`` resolving unit/shop/
        trap/eventscript symbol references against Batch A's tables).

        Default: empty -- most tables validate standalone against headers
        only. When non-empty, ``cli.py`` loads each named table
        deterministically (in the given order, via that table's own
        ``default_source`` unless overridden with ``--dep-source
        NAME=PATH``) and calls
        ``validate(records, diagnostics, dependency_records)`` instead of
        the 2-argument form, where ``dependency_records`` is a ``dict``
        of ``{table_name: records}``.
        """
        return ()

    def load_records(self, source_path):
        raise NotImplementedError

    def validate(self, records, diagnostics, dependency_records=None):
        raise NotImplementedError

    def generate_c(self, records, source_path):
        """Return generated C89 source text, or ``None`` to skip generation
        entirely (metadata-only tables that have nothing to compile)."""
        return None

    def build_inventory(self, records):
        """Return the committed inventory/summary report text."""
        raise NotImplementedError

    def manifest_record_count(self, records):
        """Record count reported in the committed platform manifest.

        Defaults to the full loaded set. Expandable tables override this so
        opt-in overlay records (validated + generated into the ROM table
        separately, and audited in reports/id_space_audit.md) do not drift
        the committed archival manifest between default and opt-in builds.
        """
        return len(records)

    def round_trip_errors(self, records, hand_source):
        """Compare ``records`` against a hand-written C file at
        ``hand_source``. Returns a list of :class:`GeneratedDataError`
        (empty if not applicable, e.g. ``hand_source`` is falsy/missing or
        the table has no round-trip counterpart)."""
        return []


class DependencyGraph:
    """A small deterministic directed graph of schema/header dependencies."""

    def __init__(self):
        self.edges = {}

    def add_node(self, name):
        self.edges.setdefault(name, set())

    def add_dependency(self, node, depends_on):
        self.add_node(node)
        self.add_node(depends_on)
        self.edges[node].add(depends_on)

    def nodes(self):
        return sorted(self.edges)

    def topo_order(self):
        """Kahn's algorithm with deterministic (sorted-name) tie-breaking.

        An edge ``node -> dep`` means "node depends on dep", so ``dep``
        must be ordered before ``node``.
        """
        # Reverse adjacency: dep -> {nodes that depend on it}
        dependents = {n: set() for n in self.edges}
        indegree = {n: 0 for n in self.edges}
        for node, deps in self.edges.items():
            indegree[node] = len(deps)
            for dep in deps:
                dependents[dep].add(node)

        ready = sorted(n for n, deg in indegree.items() if deg == 0)
        order = []
        while ready:
            node = ready.pop(0)
            order.append(node)
            for dependent in sorted(dependents.get(node, ())):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
                    ready.sort()
        if len(order) != len(self.edges):
            remaining = sorted(set(self.edges) - set(order))
            raise GeneratedDataError(
                "dependency graph has a cycle involving: {}".format(remaining)
            )
        return order

    def digest(self):
        """Stable sha256 digest of the graph shape, for drift detection."""
        parts = []
        for node in sorted(self.edges):
            deps = sorted(self.edges[node])
            parts.append("{}:{}".format(node, ",".join(deps)))
        blob = "|".join(parts).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()
