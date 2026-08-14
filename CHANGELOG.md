# Changelog

Notable changes to SemantiQL. Format follows [Keep a Changelog](https://keepachangelog.com);
versioning is [semantic](https://semver.org), with the caveat that while the version is
`0.0.x` the API may change in any release.

## [Unreleased]

## [0.0.2] — 2026-08-15

### Fixed

- `semantiql init` and `semantiql doctor` were parsed as SQL and answered with
  `Only SELECT is supported, and this is COLUMN`. Both are named in the README and the
  setup docs, so this was the first thing many people would have typed. They now say they
  are not implemented yet and show the command that does work.
- A non-SQL argument such as `semantiql hello` was explained as a `SELECT` problem. It now
  says `'hello' does not look like a query` and shows the expected shape.

### Changed

- `semantiql.__version__` is read from installed package metadata instead of being
  restated in source, so it cannot drift from `pyproject.toml`.

### Internal

- Releases publish from a version tag through PyPI Trusted Publishing (OIDC); no API token
  exists in the workflow or in repository secrets.
- Dependabot enabled for uv and GitHub Actions.

## [0.0.1] — 2026-08-15

First published release. Reserves the name, and works.

- Semantic model in YAML — dimensions, measures, metrics — validated with pydantic at load.
  Duplicate keys and names defined as both a dimension and a measure are rejected.
- Validation refuses anything it cannot faithfully compile, rather than silently dropping
  it: `WHERE`, `HAVING`, `ORDER BY`, `LIMIT`, `DISTINCT`, CTEs, subqueries and joins are
  each named in the refusal. A request whose identifiers do not resolve is refused with a
  suggestion, never guessed.
- Canonical SQL compiled with sqlglot and transpiled to the target dialect.
- DuckDB adapter reading CSV and Parquet directly, so the bundled example runs with no
  database installed, no credentials and no network.
- `semantiql` CLI, and a single `scripts/verify.sh` gate that CI runs unchanged.

[Unreleased]: https://github.com/lethuan127/SemantiQL/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/lethuan127/SemantiQL/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/lethuan127/SemantiQL/releases/tag/v0.0.1
