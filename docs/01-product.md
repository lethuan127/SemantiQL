# Product

## Goal

An open-source semantic layer that lets AI (LLMs/agents) query databases with **high effectiveness**: high accuracy, consistency, strong capability, low cost.

## Primary users

- **Data analysts** — build and own the semantic model.
- **Non-technical business users** — ask questions about data in natural language; never write SQL, never see SQL.

## Core use case (demo + benchmark)

AI agent Q&A over business data:

1. User asks: *"Revenue this month by channel?"*
2. AI generates **semantic SQL** against the semantic model.
3. Engine translates it into raw SQL and runs it on the real database.
4. User gets an accurate, consistent answer.

## Interface decisions

- **MVP: Claude integration (MCP server / connector).** End users chat with Claude Desktop; SemantiQL is the "data brain" behind it. No UI to build — the shortest path to non-technical users.
- **Post-MVP: consider a dedicated desktop app** (rather than a webapp) for data analysts — once value is proven through Claude.

## Design consequence

Because end users cannot read SQL, **accuracy and the validation layer (check + repair queries) are critical**. A wrong answer that nobody detects is the single biggest risk.
