# Security Policy

## Reporting a vulnerability

Report privately through GitHub's **"Report a vulnerability"** button under this
repository's Security tab. That channel does not depend on anyone watching an inbox, which
is why it is the only one published here.

**Please do not open a public issue for a security problem.** A public report with a
working reproduction is available to everyone the moment it is filed.

You can expect:

| | |
|---|---|
| Acknowledgement | within **5 business days** |
| A fix, or a timeline for one | within **30 days** of acknowledgement |

These are windows a single maintainer can actually meet. If a report goes past them,
assume it was missed rather than ignored, and comment on the advisory thread.

## Supported versions

SemantiQL is pre-release and has cut no versions yet. Until a `0.1` release exists, only
the `main` branch is supported.

| Version | Supported |
|---|---|
| `main` | ✅ |

## Scope

SemantiQL generates and runs SQL against a database you point it at. Two things are in
scope and worth reporting:

- **A path from a semantic query to SQL that was never validated** against the semantic
  model. Validation is the project's core safety property; a bypass is a real
  vulnerability, not a bug.
- **A semantic query that reaches data the model does not expose** — reading a column the
  model omits, or escaping the single table a request declares.

Running SemantiQL against a database account with write permissions is out of scope: the
documented setup recommends a read-only account, and that recommendation is the control.
