# 1. Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-06-20

## Context

The specification asks that every decision made while building ChoCacao be
logged in `.md` files inside an `ADR/` folder.

## Decision

We use lightweight Architecture Decision Records (ADRs), one Markdown file per
decision, numbered sequentially. Each record states the **context**, the
**decision**, and its **consequences**. Records are immutable once accepted; if a
decision is later reversed, a new ADR supersedes the old one rather than editing
history.

## Consequences

- The reasoning behind the project is discoverable in one place.
- Reviewers and future maintainers can see *why*, not just *what*.
