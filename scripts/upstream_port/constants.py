"""Fixed constants for the upstream porting tool (Issue #12).

Keeping these in one place makes the canonical-URL pin and schema contract
auditable at a glance, instead of scattered magic strings.
"""

# Canonical upstream URL. Fetch is only ever performed against a remote whose
# configured URL matches this string exactly (see git_utils.verify_remote_url).
CANONICAL_UPSTREAM_URL = "https://github.com/laqieer/fireemblem8u.git"

# Default reusable remote name, matching the remote already configured in
# maintainer clones (see `git remote -v`).
DEFAULT_REMOTE_NAME = "decomp"

# Persistent state/manifest schema version. Bump on breaking layout changes.
STATE_SCHEMA_VERSION = 1

# Default committed state path, relative to the repo root.
DEFAULT_STATE_PATH = "config/upstream-port-state.json"

# Default (gitignored) output root for generated review reports/patches.
DEFAULT_OUTPUT_ROOT = "build/upstream-port"

# Legal per-commit review statuses.
STATUSES = ("pending", "ported", "skipped", "superseded", "conflict")

# Legal path classification categories, in priority order (first match wins).
CATEGORIES = (
    "linker",
    "build",
    "symbol",
    "docs",
    "config",
    "tools",
    "data",
    "code",
    "other",
)

# Allowed status transitions. Keys are the *current* status (or None for a
# commit with no recorded status yet, i.e. implicit "pending"); values are the
# set of statuses that may be recorded next via explicit update-state calls.
# "superseded" is intentionally terminal unless --force is passed, to avoid
# silently reopening a decision that was explicitly closed out.
ALLOWED_TRANSITIONS = {
    None: {"pending", "ported", "skipped", "conflict", "superseded"},
    "pending": {"pending", "ported", "skipped", "conflict", "superseded"},
    "conflict": {"pending", "ported", "skipped", "superseded"},
    "ported": {"superseded", "ported"},
    "skipped": {"pending", "ported", "superseded", "skipped"},
    "superseded": set(),  # terminal; requires --force to leave
}

# Statuses that require a non-empty rationale and validation_evidence field.
STATUSES_REQUIRING_EVIDENCE = {"ported", "skipped", "superseded", "conflict"}
