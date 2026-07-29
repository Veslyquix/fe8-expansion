# `changelog_fragments/` -- machine changelog fragments

Every merged change that a human would want listed in `CHANGELOG.md` adds
one `*.json` fragment here (this `README.md` itself is not a fragment; it
is excluded from the fragment glob because it does not end in `.json`).

## Schema

```json
{
  "issue": 9,
  "category": "added",
  "summary": "One-line, present-tense description.",
  "semver_impact": "none"
}
```

* `issue` -- the GitHub issue number this change is scoped to, or `null`.
* `category` -- one of `added`, `changed`, `deprecated`, `removed`,
  `fixed`, `security`, `docs`, `internal`.
* `summary` -- a short, present-tense, human-readable description.
* `semver_impact` -- the SemVer impact this change *would* have once
  publication is unblocked: one of `major`, `minor`, `patch`, `none`. See
  [`../docs/public_api_policy.md`](../docs/public_api_policy.md) for what
  counts as public API on this pre-1.0 project.

## Validating and rendering

```sh
python3 -m scripts.release_rehearsal.changelog check     # validate + freshness check
python3 -m scripts.release_rehearsal.changelog render     # print deterministic Unreleased body
python3 -m scripts.release_rehearsal.changelog write      # rewrite CHANGELOG.md's Unreleased section in place
```

`make release-check` runs the same validation as part of the full release
manifest check (see [`docs/release_process.md`](../docs/release_process.md)).
