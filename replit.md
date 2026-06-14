# Redrob Rank Engine

A CPU-only candidate ranking system (Redrob "India Runs" Hackathon — Track 1) that scores 100,000 synthetic candidate profiles against a job description and emits the Top 100 as `team_xxx.csv`, within a 5-minute / 16GB / no-network budget.

## Architecture docs (source of truth — review before any code)

- `PRD.md` — objective, metrics (NDCG@10, MAP), the 3 pillars
- `TechSpec.md` — two-pass FAISS pipeline + scoring math
- `AppFlow.md` — end-to-end data flow
- `Design.md` — output CSV contract + terminal logging
- `Schema.md` — input record, the 23 `redrob_signals`, honeypot criteria
- `Rules.md` — unbreakable guardrails (precedence over other docs)

> Implementation (Python ranking code) is gated until the user approves the docs above.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

_Populate as you build — short repo map plus pointers to the source-of-truth file for DB schema, API contracts, theme files, etc._

## Architecture decisions

_Populate as you build — non-obvious choices a reader couldn't infer from the code (3-5 bullets)._

## Product

_Describe the high-level user-facing capabilities of this app once they exist._

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

_Populate as you build — sharp edges, "always run X before Y" rules._

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
