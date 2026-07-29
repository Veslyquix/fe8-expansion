"""Source-driven census of every extensible-ID consumer (Issue #10).

The curated evidence rows in ``idspace.py`` prove *which* consumers were
runtime-verified; they can never prove that no consumer was *missed*.  This
module closes that gap from the other side: it scans the real source tree
(public headers, runtime C, hand assembly, host tools) with one deterministic
rule set, enumerates every declaration that stores, serialises, decodes or
exposes an extensible ID, and requires that every single hit is mapped -- in
the tracked classification fact source ``consumer_classification.json`` -- to
one audited category or to an explicit ``reviewed-exclusion`` with a reason.

Design constraints that shaped the rules:

* **Stable keys, never line numbers.**  A hit key is
  ``path|kind|domain|symbol`` where ``symbol`` is the normalised declaration
  (``StructName.field`` for members).  Re-indenting a header or inserting a
  comment does not churn the classification file; line numbers are carried
  only as human evidence.
* **Token-level matching, not substring matching.**  Identifiers are split
  into words (``gConvoyItemArray`` -> ``g convoy item array``), and a domain
  matches only when a domain lexeme is *immediately followed* by an ID noun
  (``item`` + ``array``), or when the whole identifier is a canonical bare ID
  name (``pid``, ``jid``, ``items``, ``item1``).  Substring matching produced
  nonsense hits such as ``MapIdle`` matching the character lexeme ``pid``.
* **Scope rules are configuration, not silent ignores.**  Everything the scan
  deliberately does not walk is listed in ``SCAN_ROOTS`` /
  ``EXCLUDED_PATH_PREFIXES`` / ``COVERAGE_LIMITATIONS`` and is reported inside
  the generated audit, so a reader sees the boundary instead of guessing it.
  A same-named false positive is never pattern-ignored: it is classified as
  ``reviewed-exclusion`` with a written reason.

Stdlib only.  Entry points::

    python3 -m scripts.generated_data.consumer_census scan
    python3 -m scripts.generated_data.consumer_census check
    python3 -m scripts.generated_data.consumer_census bootstrap
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CLASSIFICATION_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "consumer_classification.json")

SCHEMA_VERSION = 1

# Audited categories (superset of idspace.REQUIRED_CATEGORIES) plus the one
# escape hatch, which always carries a written reason.
CATEGORIES = (
    "runtime-struct",
    "runtime-macro",
    "event-operand",
    "save-field",
    "ui-buffer",
    "lookup-table",
    "link-network",
    "external-interface",
)
EXCLUSION_CATEGORY = "reviewed-exclusion"
ALL_CATEGORIES = CATEGORIES + (EXCLUSION_CATEGORY,)

# --------------------------------------------------------------------------
# Scan scope (explicit configuration -- see module docstring)
# --------------------------------------------------------------------------

SCAN_ROOTS = (
    {'root': 'include', 'exts': ('.h',), 'surface': 'public-header'},
    {'root': 'src', 'exts': ('.c', '.h'), 'surface': 'runtime-source'},
    {'root': 'asm', 'exts': ('.s', '.inc'), 'surface': 'assembly'},
    {'root': 'tools/gba-playtest', 'exts': ('.py',), 'surface': 'external-tool'},
)

# Never scanned, and why (reported in the audit as scan scope).
EXCLUDED_PATH_PREFIXES = (
    ('build/', 'ephemeral generated output, not source'),
    ('mgfembp/', 'vendored third-party sub-build'),
    ('tools/agbcc/', 'vendored third-party compiler'),
    ('src/data/', 'authored JSON/data payloads: records, not ID storage declarations'),
)
EXCLUDED_DIR_NAMES = frozenset(('__pycache__', '.git', '.mypy_cache'))

# Honest statement of what the rule set structurally cannot resolve. These
# are rendered into both audits so a reader never mistakes the census for
# semantic analysis.
COVERAGE_LIMITATIONS = (
    'Assembly is matched lexically (labels and .global directives): the scanner '
    'cannot prove what an assembly routine does with a register-held ID.',
    'Struct-typed data instances (for example the ~730 struct UnitDefinition '
    'blobs in src/events_udefs.c) are audited through their struct type hits, '
    'not once per instance; only scalar-element arrays and ID-record tables '
    'are enumerated as data symbols.',
    'Function bodies are not analysed: a function that consumes an ID only '
    'through a local variable is audited through the declaration it reads '
    'from (struct field, table, or public signature).',
)

# --------------------------------------------------------------------------
# Domain lexicon (token level)
# --------------------------------------------------------------------------

DOMAIN_LEXEMES = {
    'item': ('item', 'items', 'inventory', 'shop', 'convoy', 'supply', 'armory', 'vendor'),
    'class': ('class', 'jid', 'job'),
    'character': ('char', 'character', 'characters', 'pid', 'pids'),
    'chapter': ('chapter', 'chapters'),
    'unit': ('unit', 'units', 'faction', 'allegiance', 'deployment'),
    'event': ('evt', 'event', 'events'),
}

# Whole-identifier names that are themselves an ID (optionally with a slot
# number suffix, e.g. the save fields item1..item5).
DOMAIN_BARE_NAMES = {
    'item': ('item', 'items', 'itemid', 'iid', 'inventory'),
    'class': ('jid', 'classid', 'class'),
    'character': ('pid', 'pids', 'charid'),
    'chapter': ('chapter', 'chapterid'),
    'unit': ('faction', 'allegiance', 'unitid'),
    'event': (),
}

ID_NOUNS = (
    'id', 'ids', 'index', 'indices', 'idx', 'slot', 'slots',
    'list', 'lists', 'array', 'table', 'tables', 'data', 'count',
    'inventory', 'flags', 'bits', 'mask', 'lut', 'num',
)
# The event domain additionally treats operand/decoder words as ID nouns:
# an event lane is the transport for every other domain's IDs.
EVENT_EXTRA_NOUNS = ('cmd', 'arg', 'args', 'argv', 'param', 'params', 'operand', 'queue')

# Narrower noun set for domains whose lexeme is a very common English word in
# this codebase. 'unit' appears in hundreds of graphics/proc symbols
# (Img_UnitListBanner, Sprite_Unitlistscreen_0) that store tiles, not IDs, so
# the unit domain only matches an explicit ID/slot noun.
DOMAIN_NOUN_OVERRIDES = {
    'unit': ('id', 'ids', 'idx', 'index', 'indices', 'slot', 'slots'),
}

# Event DSL headers: every macro naming a domain is an operand by
# construction (the macro *is* the wire format), so the noun-adjacency rule
# is relaxed for these files only. Explicit list, no wildcards.
EVENT_DSL_FILES = (
    'include/EAstdlib.h',
    'include/eventscript.h',
    'include/event.h',
)
EVENT_DSL_PREFIXES = ('include/EA_Standard_Library/',)

_TOKEN_SPLIT_RE = re.compile(r'[^A-Za-z0-9]+')
_CAMEL_RE = re.compile(r'[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+')
_TRAILING_DIGITS_RE = re.compile(r'^([A-Za-z]+)(\d+)$')


def tokenize(name):
    """Split a C/Python identifier into lowercase word tokens."""
    tokens = []
    for chunk in _TOKEN_SPLIT_RE.split(name):
        if not chunk:
            continue
        for piece in _CAMEL_RE.findall(chunk):
            match = _TRAILING_DIGITS_RE.match(piece)
            if match:
                tokens.append(match.group(1).lower())
                tokens.append(match.group(2))
            else:
                tokens.append(piece.lower())
    return tokens


def _nouns_for(domain):
    # A domain lexeme followed by another lexeme of the same domain is a
    # compound ID phrase (supply + items, convoy + item, shop + list), so
    # each domain lexicon doubles as that domain nouns set.
    if domain in DOMAIN_NOUN_OVERRIDES:
        return DOMAIN_NOUN_OVERRIDES[domain]
    nouns = ID_NOUNS + DOMAIN_LEXEMES[domain]
    if domain == 'event':
        return nouns + EVENT_EXTRA_NOUNS
    return nouns


def domains_for(name, relaxed=False):
    """Return every ID domain the identifier declares, deterministically.

    ``relaxed`` drops the noun-adjacency requirement (event DSL macros only).
    """
    tokens = tokenize(name)
    if not tokens:
        return ()
    found = set()
    for domain, lexemes in DOMAIN_LEXEMES.items():
        bare = DOMAIN_BARE_NAMES[domain]
        # Whole identifier is a bare ID name (pid / items / item1 ...).
        if tokens[0] in bare and (len(tokens) == 1 or (len(tokens) == 2 and tokens[1].isdigit())):
            found.add(domain)
            continue
        nouns = _nouns_for(domain)
        # In an event DSL header, naming another domain *is* carrying that
        # domain ID as an operand (GIVEITEMTO), so the noun-adjacency rule is
        # relaxed -- but never for the event domain itself, or every event
        # macro (EvtAsmCall, EventCheckFlag) would masquerade as an ID
        # consumer. Event lanes still need an operand/decoder noun.
        domain_relaxed = relaxed and domain != 'event'
        for index, token in enumerate(tokens):
            if token not in lexemes:
                continue
            if domain_relaxed:
                found.add(domain)
                break
            following = tokens[index + 1] if index + 1 < len(tokens) else None
            if following is not None and (following in nouns or following.isdigit()):
                found.add(domain)
                break
        else:
            # Glued/all-caps identifiers (ITEMDATA, GIVEITEMTO) carry no case
            # boundary to split on, so fall back to *adjacent* lexeme+noun
            # substring matching -- still never a bare lexeme substring, which
            # is what produced nonsense hits such as MapIdle matching pid.
            if any(lexeme + noun in token
                   for token in tokens for lexeme in lexemes for noun in nouns):
                found.add(domain)
    return tuple(sorted(found))


# --------------------------------------------------------------------------
# Declaration extraction
# --------------------------------------------------------------------------

_INT_TYPES = ('u8', 's8', 'u16', 's16', 'u32', 's32', 'int', 'short', 'char', 'long', 'bool')
# Struct records that are *indexed by* a domain ID, so an array of them is a
# lookup table for that domain (as opposed to an ordinary data instance).
_ID_RECORD_STRUCTS = ('ItemData', 'ClassData', 'CharacterData', 'ChapterData', 'ShopList')

_QUALIFIERS = r'(?:extern\s+|static\s+|const\s+|volatile\s+|CONST_DATA\s+|EWRAM_DATA\s+|IWRAM_DATA\s+|ALIGNED\([^)]*\)\s+)*'
_TYPE = r'(?P<type>(?:struct|union|enum)\s+\w+|unsigned\s+\w+|signed\s+\w+|u8|s8|u16|s16|u32|s32|int|short|char|long|bool)'

FIELD_RE = re.compile(
    r'^\s*' + _QUALIFIERS + _TYPE +
    r'\s*(?P<ptr>\**)\s*(?P<name>[A-Za-z_]\w*)\s*(?P<arr>(?:\[[^\]]*\])*)\s*(?P<bits>:\s*\d+)?\s*;')
DATA_RE = re.compile(
    r'^\s*' + _QUALIFIERS + _TYPE +
    r'\s*(?P<ptr>\**)\s*' + _QUALIFIERS +
    r'(?P<name>[A-Za-z_]\w*)\s*(?P<arr>(?:\[[^\]]*\])*)\s*(?P<tail>=|;)')
PROTO_RE = re.compile(
    r'^\s*(?:extern\s+)?[A-Za-z_][\w\s\*]*?\b(?P<name>[A-Za-z_]\w*)\s*\((?P<params>[^;{]*)\)\s*;')
DEFINE_RE = re.compile(r'^\s*#\s*define\s+(?P<name>[A-Za-z_]\w*)')
STRUCT_TAG_RE = re.compile(r'\b(?:typedef\s+)?(?:struct|union)\s+(?P<tag>[A-Za-z_]\w*)?')
PARAM_NAME_RE = re.compile(r'\b(?P<name>[A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*(?:,|$)')
ASM_LABEL_RE = re.compile(r'^(?P<name>[A-Za-z_][\w]*):')
ASM_GLOBAL_RE = re.compile(r'^\s*\.globa?l\s+(?P<name>[A-Za-z_][\w]*)')
PY_ASSIGN_RE = re.compile(r'^\s*(?P<name>[A-Za-z_]\w*)\s*(?::[^=]+)?=')
PY_DEF_RE = re.compile(r'^\s*def\s+(?P<name>[A-Za-z_]\w*)\s*\(')

_BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/', re.DOTALL)
_LINE_COMMENT_RE = re.compile(r'//[^\n]*')


def _strip_comments(text):
    """Blank out comments while preserving line numbering (evidence lines)."""
    def blank(match):
        return re.sub(r'[^\n]', ' ', match.group(0))
    text = _BLOCK_COMMENT_RE.sub(blank, text)
    return _LINE_COMMENT_RE.sub(blank, text)


def _is_int_type(type_text):
    head = type_text.split()[0]
    return head in _INT_TYPES or head in ('unsigned', 'signed')


def _is_id_record_type(type_text):
    parts = type_text.split()
    return len(parts) == 2 and parts[0] in ('struct', 'union') and parts[1] in _ID_RECORD_STRUCTS


class Hit:
    """One scanned declaration that names an extensible ID."""

    __slots__ = ('domain', 'kind', 'path', 'symbol', 'declaration', 'line', 'surface')

    def __init__(self, domain, kind, path, symbol, declaration, line, surface):
        self.domain = domain
        self.kind = kind
        self.path = path
        self.symbol = symbol
        self.declaration = declaration
        self.line = line
        self.surface = surface

    @property
    def key(self):
        # Stable identity: never the line number.
        return '{}|{}|{}|{}'.format(self.path, self.kind, self.domain, self.symbol)

    def to_dict(self):
        return {
            'key': self.key,
            'domain': self.domain,
            'kind': self.kind,
            'path': self.path,
            'symbol': self.symbol,
            'declaration': self.declaration,
            'line': self.line,
            'surface': self.surface,
        }


def _normalize_declaration(line):
    return re.sub(r'\s+', ' ', line).strip()


def _is_event_dsl(rel_path):
    if rel_path in EVENT_DSL_FILES:
        return True
    return any(rel_path.startswith(prefix) for prefix in EVENT_DSL_PREFIXES)


# Cheap per-line prefilter: a line that mentions no domain lexeme at all can
# never produce a hit, so the expensive declaration regexes are skipped. This
# is a pure performance gate (never a scope decision) -- it is built from the
# same lexicon domains_for() uses, so it cannot silently drop a hit.
_PREFILTER_RE = re.compile(
    '|'.join(sorted({lexeme for lexemes in DOMAIN_LEXEMES.values() for lexeme in lexemes} |
                    {bare for bares in DOMAIN_BARE_NAMES.values() for bare in bares})),
    re.IGNORECASE)
# --------------------------------------------------------------------------
# Scope tracking (struct/union *definition* bodies only)
# --------------------------------------------------------------------------
#
# A hit of kind `struct-field` may only be emitted while the innermost open
# scope is a genuine struct/union *definition* body. Every other brace pair --
# a function body, an `if`/`for`/`while` block, an aggregate initializer, an
# `enum` body -- is a plain block that carries no field declarations. The old
# tracker pushed *every* `{` as a struct and reused the last-seen `struct X`
# token as the owner, so a signature such as
# `SupplyUsability(const struct MenuItemDef * def)` made the function body
# owned by `MenuItemDef`, and body locals (`int pid;`, `u16 item;`) were
# fabricated into `MenuItemDef.pid` / `ProcShop.item` / `anonymous.item`.
#
# The state machine below only opens a struct scope when a `struct`/`union`
# keyword (optionally with a tag) is *immediately* followed by `{` -- with
# nothing but the tag in between. A use of the type as a parameter, variable,
# cast, forward declaration or `sizeof(struct X)` inserts another token
# (`*`, an identifier, `;`, `)`) before any brace and can never open a body.

# Meaningful scope tokens: braces, identifiers/keywords, or a run of other
# punctuation (which, after a `struct`/`union` keyword, marks a *use*).
_SCOPE_TOKEN_RE = re.compile(r'\{|\}|[A-Za-z_]\w*|[^\s{}A-Za-z_]+')


class _ScopeTracker:
    """Track struct/union definition scopes across a C/H translation unit.

    Struct-field hits are buffered per open struct scope and flushed with a
    resolved owner when the scope closes, so an anonymous ``typedef struct { .. }
    Alias;`` names its fields ``Alias.field`` and a nested anonymous
    struct/union inherits its nearest named ancestor. Owner keys never depend
    on line numbers.
    """

    __slots__ = ('stack', '_cand', '_pending_alias')

    def __init__(self):
        self.stack = []            # list of scope dicts (see _push_* below)
        self._cand = None          # pending `struct/union [tag]` definition head
        self._pending_alias = None # anonymous struct closed, awaiting its alias

    # -- queries used by scan_c_file ------------------------------------
    def in_struct_def(self):
        return bool(self.stack) and self.stack[-1]['kind'] == 'struct'

    def add_field(self, name, evidence, number):
        """Buffer a field declaration in the innermost struct definition."""
        self.stack[-1]['buffer'].append((name, evidence, number))

    # -- internal helpers -----------------------------------------------
    def _nearest_named(self):
        for scope in reversed(self.stack):
            if scope['kind'] == 'struct' and scope['owner'] is not None:
                return scope['owner']
        return None

    def _flush(self, scope, owner, sink):
        for name, evidence, number in scope['buffer']:
            sink(owner, name, evidence, number)
        scope['buffer'] = []

    def _resolve_pending_alias(self, owner, sink):
        scope = self._pending_alias
        self._pending_alias = None
        self._flush(scope, owner, sink)

    def _close(self, sink):
        if not self.stack:
            return
        scope = self.stack.pop()
        if scope['kind'] != 'struct':
            return
        owner = scope['owner']
        if owner is not None:
            self._flush(scope, owner, sink)
            return
        ancestor = self._nearest_named()
        if ancestor is not None:
            # Nested anonymous struct/union: its fields belong to the nearest
            # named aggregate (e.g. a packed union inside `struct Unit`).
            self._flush(scope, ancestor, sink)
            return
        # Top-level anonymous aggregate: its name is the typedef/variable alias
        # that follows the closing brace. Defer until we see that identifier.
        if self._pending_alias is not None:
            self._flush(self._pending_alias, 'anonymous', sink)
        self._pending_alias = scope

    # -- the line feed ---------------------------------------------------
    def feed(self, line, sink):
        if (self._cand is None and self._pending_alias is None
                and '{' not in line and '}' not in line
                and 'struct' not in line and 'union' not in line):
            return
        for match in _SCOPE_TOKEN_RE.finditer(line):
            token = match.group(0)
            if token == '{':
                if self._cand is not None:
                    self.stack.append({'kind': 'struct', 'owner': self._cand['tag'], 'buffer': []})
                    self._cand = None
                else:
                    self.stack.append({'kind': 'block'})
                # A `{` that is not the alias identifier ends the alias window.
                if self._pending_alias is not None:
                    self._flush(self._pending_alias, 'anonymous', sink)
                    self._pending_alias = None
            elif token == '}':
                self._close(sink)
            elif token[0].isalpha() or token[0] == '_':
                if token in ('struct', 'union'):
                    self._cand = {'stage': 'kw', 'tag': None}
                elif self._cand is not None:
                    if self._cand['stage'] == 'kw':
                        self._cand['tag'] = token
                        self._cand['stage'] = 'tag'
                    else:
                        # `struct X var` -- a second identifier means a *use*.
                        self._cand = None
                elif self._pending_alias is not None:
                    self._resolve_pending_alias(token, sink)
                # a bare identifier otherwise carries no scope meaning
            else:
                # Any other punctuation (`*`, `;`, `(`, `,`, `=`, ...) after a
                # `struct`/`union` keyword proves it was a use, not a definition.
                if self._cand is not None:
                    self._cand = None
                if self._pending_alias is not None:
                    self._flush(self._pending_alias, 'anonymous', sink)
                    self._pending_alias = None

    def finish(self, sink):
        """Flush anything left open at EOF (defensive; sources are balanced)."""
        if self._pending_alias is not None:
            self._flush(self._pending_alias, 'anonymous', sink)
            self._pending_alias = None
        while self.stack:
            scope = self.stack.pop()
            if scope['kind'] == 'struct':
                self._flush(scope, scope['owner'] or (self._nearest_named() or 'anonymous'), sink)


def scan_c_file(rel_path, text, surface, hits):
    """Extract struct fields, data symbols, public signatures and macros.

    Struct fields are only harvested inside a real struct/union definition
    body; data symbols and public prototypes only at file scope. Function
    bodies (and every other block) are deliberately not analysed -- a local
    variable is never a consumer declaration.
    """
    relaxed = _is_event_dsl(rel_path)
    stripped = _strip_comments(text)
    tracker = _ScopeTracker()

    def sink(owner, name, evidence, number):
        for domain in domains_for(name):
            symbol = '{}.{}'.format(owner, name)
            hits.append(Hit(domain, 'struct-field', rel_path, symbol, evidence, number, surface))

    for number, line in enumerate(stripped.splitlines(), start=1):
        if _PREFILTER_RE.search(line):
            evidence = _normalize_declaration(line)

            macro = DEFINE_RE.match(line)
            if macro:
                name = macro.group('name')
                for domain in domains_for(name, relaxed=relaxed):
                    hits.append(Hit(domain, 'macro', rel_path, name, evidence, number, surface))

            if tracker.in_struct_def():
                field = FIELD_RE.match(line)
                if field and not field.group('ptr'):
                    tracker.add_field(field.group('name'), evidence, number)
            elif not tracker.stack:
                # File scope only: never inside a function/other block body.
                data = DATA_RE.match(line)
                if data and not data.group('ptr'):
                    type_text = ' '.join(data.group('type').split())
                    name = data.group('name')
                    array = bool(data.group('arr'))
                    keep = (_is_int_type(type_text) and (array or line.lstrip().startswith('extern'))) \
                        or _is_id_record_type(type_text)
                    if keep:
                        for domain in domains_for(name):
                            hits.append(Hit(domain, 'data-symbol', rel_path, name, evidence, number, surface))
                proto = PROTO_RE.match(line)
                if proto and not line.lstrip().startswith('#'):
                    name = proto.group('name')
                    domains = set(domains_for(name))
                    for param in PARAM_NAME_RE.findall(proto.group('params')):
                        domains.update(domains_for(param))
                    for domain in sorted(domains):
                        hits.append(Hit(domain, 'function-signature', rel_path, name, evidence, number, surface))

        # Scope bookkeeping runs for every line, after declaration matching, so
        # a one-line `struct X { ... };` never swallows same-line declarations
        # and a brace-free continuation line still cancels a pending struct head.
        tracker.feed(line, sink)

    tracker.finish(sink)


def scan_asm_file(rel_path, text, surface, hits):
    """Assembly is matched lexically: exported labels and .global symbols."""
    seen = set()
    for number, line in enumerate(text.splitlines(), start=1):
        match = ASM_LABEL_RE.match(line) or ASM_GLOBAL_RE.match(line)
        if not match:
            continue
        name = match.group('name')
        for domain in domains_for(name):
            if (name, domain) in seen:
                continue
            seen.add((name, domain))
            hits.append(Hit(domain, 'asm-symbol', rel_path, name, _normalize_declaration(line), number, surface))


def scan_tool_file(rel_path, text, surface, hits):
    """Host tools: module-level constants and functions naming a domain ID."""
    seen = set()
    for number, line in enumerate(text.splitlines(), start=1):
        match = PY_DEF_RE.match(line) or PY_ASSIGN_RE.match(line)
        if not match:
            continue
        name = match.group('name')
        for domain in domains_for(name):
            if (name, domain) in seen:
                continue
            seen.add((name, domain))
            hits.append(Hit(domain, 'tool-symbol', rel_path, name, _normalize_declaration(line), number, surface))


def _iter_scan_files(repo_root):
    for spec in SCAN_ROOTS:
        root = os.path.join(repo_root, spec['root'])
        if not os.path.isdir(root):
            continue
        for base, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIR_NAMES)
            for name in sorted(files):
                if not name.endswith(spec['exts']):
                    continue
                path = os.path.join(base, name)
                rel = os.path.relpath(path, repo_root).replace(os.sep, '/')
                if any(rel.startswith(prefix) for prefix, _reason in EXCLUDED_PATH_PREFIXES):
                    continue
                yield rel, path, spec['surface']


_SCAN_CACHE = {}


def reset_cache():
    """Drop memoized scan results (tests that mutate the tree call this)."""
    _SCAN_CACHE.clear()


def scan(repo_root=None):
    """Scan the configured source surface; deterministic, sorted hits.

    Memoized per repo root: the audit renderers ask for the census several
    times per run, and re-walking ~15 MB of sources each time turned a 2 s
    generate into a 60 s one.
    """
    repo_root = repo_root or REPO_ROOT
    if repo_root in _SCAN_CACHE:
        return _SCAN_CACHE[repo_root]
    hits = []
    for rel, path, surface in _iter_scan_files(repo_root):
        with open(path, 'r', encoding='utf-8', errors='replace') as handle:
            text = handle.read()
        if rel.endswith(('.c', '.h')):
            scan_c_file(rel, text, surface, hits)
        elif rel.endswith(('.s', '.inc')):
            scan_asm_file(rel, text, surface, hits)
        elif rel.endswith('.py'):
            scan_tool_file(rel, text, surface, hits)
    # Deduplicate identical keys (a header may repeat a declaration); keep
    # the first occurrence so the evidence line is stable.
    unique = {}
    for hit in hits:
        unique.setdefault(hit.key, hit)
    result = sorted(unique.values(), key=lambda h: (h.domain, h.kind, h.path, h.symbol))
    _SCAN_CACHE[repo_root] = result
    return result


# --------------------------------------------------------------------------
# Classification fact source
# --------------------------------------------------------------------------


class CensusError(Exception):
    """Actionable census failure (unclassified hit, stale entry, bad data)."""


def _reject_duplicate_keys(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise CensusError(
                'duplicate classification key {!r}: one hit must have exactly one '
                'classification row'.format(key))
        seen[key] = value
    return seen


def load_classification(path=None):
    """Load the tracked key -> category/reason map (duplicate keys are fatal)."""
    path = path or CLASSIFICATION_PATH
    if not os.path.exists(path):
        raise CensusError(
            'missing classification fact source {}; run `python3 -m '
            'scripts.generated_data.consumer_census bootstrap`'.format(path))
    with open(path, 'r', encoding='utf-8') as handle:
        payload = json.load(handle, object_pairs_hook=_reject_duplicate_keys)
    entries = payload.get('entries') or {}
    for key, entry in entries.items():
        category = entry.get('category')
        if category not in ALL_CATEGORIES:
            raise CensusError(
                'classification key {!r} has unknown category {!r}; allowed: {}'.format(
                    key, category, ', '.join(ALL_CATEGORIES)))
        if category == EXCLUSION_CATEGORY and not (entry.get('reason') or '').strip():
            raise CensusError(
                'classification key {!r} is a {} with no reason; a same-named false '
                'positive must state why it carries no extensible ID'.format(
                    key, EXCLUSION_CATEGORY))
    return entries


def classified_rows(hits=None, classification=None, repo_root=None):
    """Join scanner hits with their classification (1:1, fail-fast)."""
    hits = scan(repo_root) if hits is None else hits
    classification = load_classification() if classification is None else classification
    rows = []
    for hit in hits:
        entry = classification.get(hit.key)
        if entry is None:
            raise CensusError(
                'unclassified consumer hit {!r} ({} {} at {}:{}); classify it in '
                'scripts/generated_data/consumer_classification.json'.format(
                    hit.key, hit.kind, hit.symbol, hit.path, hit.line))
        row = hit.to_dict()
        row['category'] = entry['category']
        row['reason'] = entry.get('reason')
        rows.append(row)
    rows.sort(key=lambda r: (r['domain'], r['category'], r['path'], r['kind'], r['symbol']))
    return rows


def coverage_problems(hits=None, classification=None, repo_root=None):
    """Return actionable messages for unclassified hits and stale entries."""
    hits = scan(repo_root) if hits is None else hits
    classification = load_classification() if classification is None else classification
    hit_keys = {hit.key: hit for hit in hits}
    problems = []
    for key in sorted(hit_keys):
        if key not in classification:
            hit = hit_keys[key]
            problems.append(
                'unclassified: {} ({} {} declared at {}:{}) -- add it to '
                'consumer_classification.json with one of: {}'.format(
                    key, hit.kind, hit.symbol, hit.path, hit.line,
                    ', '.join(ALL_CATEGORIES)))
    for key in sorted(classification):
        if key not in hit_keys:
            problems.append(
                'stale: {} is classified but no longer exists in the source scan -- '
                'remove it from consumer_classification.json'.format(key))
    return problems


def census_digest(rows=None):
    """Stable sha256 over the classified census (drift fingerprint)."""
    rows = classified_rows() if rows is None else rows
    payload = [
        {
            'key': r['key'], 'domain': r['domain'], 'kind': r['kind'], 'path': r['path'],
            'symbol': r['symbol'], 'category': r['category'], 'reason': r.get('reason'),
        }
        for r in rows
    ]
    blob = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(blob).hexdigest()


def scan_scope():
    """Machine-readable description of what the scan does and does not walk."""
    return {
        'roots': [
            {'root': spec['root'], 'extensions': list(spec['exts']), 'surface': spec['surface']}
            for spec in SCAN_ROOTS
        ],
        'excluded': [{'prefix': prefix, 'reason': reason} for prefix, reason in EXCLUDED_PATH_PREFIXES],
        'coverage_limitations': list(COVERAGE_LIMITATIONS),
        'categories': list(ALL_CATEGORIES),
    }


# --------------------------------------------------------------------------
# Bootstrap proposals (developer aid; never run by check)
# --------------------------------------------------------------------------

_SAVE_PATHS = ('include/bmsave.h', 'include/sram-layout.h', 'include/savemenu.h', 'src/bmsave.c',
               'src/bmsave-lib.c', 'src/savemenu.c', 'src/save_stats.c')
_LINK_TOKENS = ('multiarena', 'link', 'serial', 'sio')
_UI_TOKENS = ('ui', 'menu', 'disp', 'font', 'text', 'screen', 'banner', 'popup', 'prep',
              'statscreen', 'opinfo', 'uisupport', 'worldmap', 'bksel', 'shop', 'help')


UI_VERB_TOKENS = ('put', 'draw', 'display', 'show', 'render', 'print', 'blit', 'text')


def propose_category(hit):
    """Deterministic first-pass proposal (a human still reviews every row).

    Token-level matching only: substring matching on file names silently
    mapped expansion_debugtools.h to link-network (it contains 'sio').
    """
    file_tokens = set(tokenize(os.path.basename(hit.path)))
    symbol_tokens = tokenize(hit.symbol)
    if hit.path in _SAVE_PATHS:
        return 'save-field'
    if file_tokens & set(_LINK_TOKENS):
        return 'link-network'
    if _is_event_dsl(hit.path) or hit.domain == 'event':
        return 'event-operand'
    if hit.kind in ('tool-symbol', 'asm-symbol'):
        return 'external-interface'
    if hit.kind == 'data-symbol':
        return 'lookup-table'
    if hit.kind == 'macro':
        return 'runtime-macro'
    if hit.kind == 'struct-field':
        return 'ui-buffer' if file_tokens & set(_UI_TOKENS) else 'runtime-struct'
    if symbol_tokens and symbol_tokens[0] in UI_VERB_TOKENS:
        return 'ui-buffer'
    if file_tokens & set(_UI_TOKENS):
        return 'ui-buffer'
    return 'external-interface'


def render_classification(entries):
    """Deterministic JSON text for the tracked classification fact source."""
    payload = {
        'schema_version': SCHEMA_VERSION,
        '_comment': (
            'Every scanner hit from scripts/generated_data/consumer_census.py maps to '
            'exactly one category here. reviewed-exclusion always carries a reason. '
            'Regenerate proposals with `python3 -m scripts.generated_data.consumer_census '
            'bootstrap`, then review every new row by hand.'),
        'entries': {key: entries[key] for key in sorted(entries)},
    }
    return json.dumps(payload, indent=2, sort_keys=True) + '\n'


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def cmd_scan(args):
    hits = scan()
    if args.json:
        print(json.dumps([hit.to_dict() for hit in hits], indent=2, sort_keys=True))
        return 0
    per_domain = {}
    per_kind = {}
    for hit in hits:
        per_domain[hit.domain] = per_domain.get(hit.domain, 0) + 1
        per_kind[hit.kind] = per_kind.get(hit.kind, 0) + 1
    print('scanned consumer hits: {}'.format(len(hits)))
    for domain in sorted(per_domain):
        print('  domain {:<10} {}'.format(domain, per_domain[domain]))
    for kind in sorted(per_kind):
        print('  kind   {:<18} {}'.format(kind, per_kind[kind]))
    return 0


def cmd_check(args):
    hits = scan()
    try:
        classification = load_classification()
    except CensusError as exc:
        print('census error: {}'.format(exc), file=sys.stderr)
        return 1
    problems = coverage_problems(hits, classification)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print('FAILED: {} consumer-census coverage problem(s)'.format(len(problems)), file=sys.stderr)
        return 1
    rows = classified_rows(hits, classification)
    excluded = sum(1 for row in rows if row['category'] == EXCLUSION_CATEGORY)
    print('consumer census clean: {} hit(s), {} audited, {} reviewed-exclusion, digest {}'.format(
        len(rows), len(rows) - excluded, excluded, census_digest(rows)))
    return 0


def cmd_bootstrap(args):
    hits = scan()
    existing = {}
    if os.path.exists(CLASSIFICATION_PATH):
        existing = load_classification()
    entries = {}
    added = 0
    for hit in hits:
        if hit.key in existing:
            entries[hit.key] = existing[hit.key]
            continue
        entries[hit.key] = {'category': propose_category(hit), 'reason': None}
        added += 1
    dropped = [key for key in existing if key not in entries]
    with open(CLASSIFICATION_PATH, 'w', encoding='utf-8') as handle:
        handle.write(render_classification(entries))
    print('bootstrap: {} hit(s), {} proposed, {} stale dropped'.format(len(hits), added, len(dropped)))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='python3 -m scripts.generated_data.consumer_census')
    sub = parser.add_subparsers(dest='command')
    scan_parser = sub.add_parser('scan', help='scan the source surface and report hit counts')
    scan_parser.add_argument('--json', action='store_true', help='emit raw hits as JSON')
    scan_parser.set_defaults(func=cmd_scan)
    check_parser = sub.add_parser('check', help='fail on unclassified or stale classification rows')
    check_parser.set_defaults(func=cmd_check)
    boot_parser = sub.add_parser('bootstrap', help='propose classification rows for new hits')
    boot_parser.set_defaults(func=cmd_bootstrap)
    args = parser.parse_args(argv)
    if not getattr(args, 'func', None):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except CensusError as exc:
        print('census error: {}'.format(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
