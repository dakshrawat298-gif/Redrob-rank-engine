---
name: Streamlit in this pnpm monorepo (dev + deploy)
description: How to run AND publicly deploy a Streamlit app here given there is no Python artifact type.
---

# Streamlit sandbox UI

pnpm/Node monorepo with path-based artifact routing. `createArtifact` has NO
python/streamlit type (only expo, data-visualization, mockup-sandbox, react-vite,
slides, video-js), so Streamlit cannot be its own artifact.

## App wiring
- `app.py` at repo root reads `team_vibecoder.csv` relative to the SCRIPT dir
  (`os.path.abspath(__file__)`), not CWD — so it loads no matter the launch CWD.
- `.streamlit/config.toml`: headless, address 0.0.0.0, `enableCORS=false`,
  `enableXsrfProtection=false` (required so the proxied iframe preview / router works).
- Streamlit 1.58: `use_container_width` deprecated → use `width="stretch"`.

## Public deployment (Redrob Rule 10.5 sandbox link) — the durable decision
This project deploys via `router = "application"` in `.replit` (autoscale). In that
mode **`.replit` `deployment.run` is IGNORED**; production is driven entirely by each
artifact's `.replit-artifact/artifact.toml` `[services.<name>.production]`. There is
NO `deployConfig()` callback in the code sandbox, and `.replit` cannot be edited
directly (run/ports/services each have their own tool).

**So: serve Streamlit by repurposing an existing artifact** rather than creating one.
Here the unused `api-server` artifact (only a `/api/healthz` scaffold) was pointed at
Streamlit, served at `paths = ["/"]`:
- Edit `artifact.toml` ONLY via `verifyAndReplaceArtifactToml` (temp-file flow).
  - `verifyAndReplaceArtifactToml` CANNOT change `kind` — leave `kind = "api"`.
- `[services.development].run` runs from the **artifact dir** (CWD = `artifacts/<x>`),
  so reference the root app as `streamlit run ../../app.py ...`.
- `[services.production.run].args` runs from the **repo root** (matches scaffold's
  repo-root-relative paths), so reference it as `app.py`. This dev-vs-prod CWD
  asymmetry is real; app.py's `__file__`-relative CSV load makes it CWD-proof anyway.
- `[services.production.health.startup].path = "/"` (Streamlit `/` returns 200).
- Use one localPort consistently (8080 here) with `[services.env] PORT` matching.

**Python deps in production:** packages live in `.pythonlibs/bin` (Replit-managed,
on PATH), NOT a uv `.venv`. Do NOT add a `uv sync` build step — it creates a
conflicting `.venv`. Rely on Replit's standard python-module provisioning from
`pyproject.toml`/`uv.lock`. If a publish build fails, the two signatures to check via
`getDeploymentBuild` are `streamlit: command not found` (deps not provisioned) and
`File does not exist: app.py` (prod CWD assumption wrong).

## Gotchas
- After repurposing the artifact, the OLD dev workflow's node process can linger and
  hold the port → new workflow fails "Port 8080 is not available". `kill -9` the
  stale `node ./dist/index.mjs` PIDs, then restart.
- `screenshot type=app_preview` DOES work once the artifact serves "/"; a blank first
  shot is just Streamlit's websocket render lag — re-shoot after it boots.
- Deployment is user-initiated: configure, then `suggestDeploy()`. The `*.replit.app`
  URL only exists AFTER the user clicks Publish (read `getDeploymentInfo().primaryUrl`).
