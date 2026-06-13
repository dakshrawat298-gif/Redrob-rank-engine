---
name: Streamlit in this pnpm monorepo
description: How to run a Streamlit app here given there is no Python artifact type.
---

# Streamlit sandbox UI

This is a pnpm/Node monorepo with path-based artifact routing, but `createArtifact`
offers NO python/streamlit type (only expo, data-visualization, mockup-sandbox,
react-vite, slides, video-js). So a Streamlit app is NOT an artifact.

**How it's wired (Sandbox UI for Redrob Rule 10.5):**
- `app.py` lives at repo root and reads `team_vibecoder.csv` (relative to the script
  dir, not CWD, so the workflow can launch from anywhere).
- `.streamlit/config.toml`: headless, address 0.0.0.0, port 5000, `enableCORS=false`,
  `enableXsrfProtection=false` (required so the proxied iframe preview works).
- Run as a standalone webview workflow named "Streamlit Sandbox":
  `streamlit run app.py --server.port 5000 --server.address 0.0.0.0`
  (port 5000 is in the workflow tool's supported-port list).

**Gotchas:**
- `configureWorkflow` may report "failed to start" on the very first attempt
  (port-open race); a `restart_workflow` after it succeeds.
- `screenshot type=app_preview` does NOT work for this — it only accepts registered
  artifact dirs. Verify with `curl -s -o /dev/null -w "%{http_code}" localhost:5000/`.
- Streamlit 1.58: `use_container_width` is deprecated; use `width="stretch"`.
- Deployment in `.replit` is configured for the Node/pnpm autoscale router, NOT
  Streamlit — publishing the Streamlit app would need separate deployment config.
