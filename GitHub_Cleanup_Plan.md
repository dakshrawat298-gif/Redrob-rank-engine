# GitHub Cleanup Plan — Redrob Rank Engine

**Status:** PROPOSAL ONLY. **No files have been deleted or modified.** Deletions
will be performed only after you reply with an explicit **`EXECUTE`** command.

**Purpose:** the hackathon requires a "clean, complete, working GitHub repo."
This plan identifies development cruft (intermediate generator scripts, closed
audit/hotfix/process logs, and stray pasted-prompt dumps) for removal, while
guaranteeing the absolute safety of every deliverable, runtime, spec, and config
asset. The graded submission `team_vibecoder.csv` stays byte-identical
(sha256 `dc3432e2815a99951f80ffecee3e8169c956c2681b33a834da7cedfe142e6952`).

The scan was performed against `git ls-files` (the real tracked repo), not the
working directory, so installed dependencies (`.pythonlibs/`, `node_modules/`)
and git-ignored generated data are correctly excluded.

---

## 0. Findings that correct assumptions in the request (verified)

- **No `README.md` exists.** `replit.md` is the current project overview. The
  request listed `README.md` as a protected asset, but it is simply absent.
  Recommendation: at EXECUTE time, optionally add a short `README.md` for GitHub
  presentation (or promote `replit.md`). Not required for the cleanup itself.
- **No `replit.nix` exists** — only `.replit` (+ `.replitignore`). Both are
  protected.
- **No V1/V2/V3 `.txt` bundles are tracked.** Only `NotebookLM_Master_Codebase_V4.txt`
  exists (protected). The only V1/V2/V3 residue is the *generator scripts* listed
  in Category A; their output bundles are not in the repo.
- **No stray/backup CSVs and no residual `.log` files** are tracked.
  `team_vibecoder.csv` is the only CSV.
- **`engine/data/` (147 MB FAISS + indexes) and `candidates.jsonl`/`.gz` are
  git-ignored and reproducible** — they are NOT in the repo and are out of scope.
- **Nothing executable imports the cruft.** The only references are docstring
  cross-mentions (see the Borderline note); no runtime dependency exists.

---

## 1. Proposed for deletion (cruft)

### Category A — Intermediate bundle/audit generator scripts
| File | Justification |
|---|---|
| `build_master_v3.py` | One-off generator for the superseded V3 audit bundle; output not even retained. |
| `build_master_v4.py` | One-off generator that produced the kept `NotebookLM_Master_Codebase_V4.txt`; the artifact is kept, the generator is throwaway dev tooling. |
| `compile_audit.py` | First-generation audit-bundle generator, superseded by the V4 builder. |
| `compile_audit_v2.py` | Second-generation audit-bundle generator, superseded by the V4 builder. |

### Category B — Closed process / audit / hotfix logs (markdown)
| File | Justification |
|---|---|
| `Remediation_Plan.md` | Closed log of the 7-finding architectural audit; all remediations already shipped. |
| `Stage4_Hotfix_Plan.md` | Closed Stage-4 logic-hotfix log; changes already shipped. |
| `V4_Hotfix_Plan.md` | Closed V4 edge-case hotfix log; changes already shipped. |
| `CTO_Polish_Plan.md` | Closed production-polish log from the CTO audit pass; work already shipped. |
| `Tracker.md` | Internal kanban board; dev-process artifact, not a deliverable. |

### Category C — Stray prompt dumps
| File | Justification |
|---|---|
| `attached_assets/Pasted--System-Command-APPROVED-Proceed-to-Implementation-Phas_1781297326437.txt` | Raw pasted system-command prompt from development; not part of the product. |
| `attached_assets/Pasted--System-Command-ENTER-PLAN-MODE-CRITICAL-AUDIT-REMEDIAT_1781369446693.txt` | Raw pasted system-command prompt from development; not part of the product. |
| `attached_assets/Pasted--System-Command-Enter-PLAN-MODE-DO-NOT-generate-any-app_1781295378108.txt` | Raw pasted system-command prompt from development; not part of the product. |
| `attached_assets/` (directory) | Removed once empty after the three dumps above are deleted. |

**Total proposed for deletion: 12 files (+ 1 now-empty directory).**

---

## 2. Borderline — DEFAULT KEEP unless you say otherwise

| File | Note |
|---|---|
| `ImplementationPlan.md` | Phased delivery plan / process doc, but it is cross-referenced by a `phase1_precompute.py` docstring (line 7) and by `Tracker.md`/`compile_audit*.py`. Delete ONLY if that docstring line is also updated in the same change; otherwise keep to avoid a dangling reference. **Default: KEEP.** |

---

## 3. Protected assets — explicit safety guarantee (NEVER touched)

- **Deliverable:** `team_vibecoder.csv` (byte-identity must hold).
- **Engine:** entire `engine/` directory — `logging_util.py`, `phase1_precompute.py`,
  `phase2_ranker.py`, `phase3_reasoning.py`, `run_ranker.py`,
  `validate_submission.py`, `requirements.txt`.
- **Entrypoints:** `app.py`, `main.py`.
- **Runtime input:** `job_description.docx`. Git-ignored runtime data
  (`engine/data/`, `candidates.jsonl`) is left untouched.
- **Dependency mgmt:** `pyproject.toml`, `uv.lock`, `engine/requirements.txt`.
- **Deploy/config:** `.replit`, `.replitignore`, `.streamlit/config.toml`, `.gitignore`.
- **Reference bundle:** `NotebookLM_Master_Codebase_V4.txt`.
- **Project overview:** `replit.md`.
- **Evergreen spec docs (cross-referenced by engine docstrings — kept):**
  `PRD.md`, `TechSpec.md`, `Design.md`, `Schema.md`, `Rules.md`, `AppFlow.md`.
- **Monorepo / Replit scaffolding (deleting breaks the workspace and the hosted
  Streamlit dashboard):** `package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`,
  `.npmrc`, `tsconfig.json`, `tsconfig.base.json`, `lib/`, `artifacts/`,
  `scripts/`, `.agents/`.

---

## 4. Execution procedure (runs only after `EXECUTE`)

1. Delete the Category A, B, and C files, then remove the now-empty
   `attached_assets/` directory.
2. Handle `ImplementationPlan.md` only if you opt in — and if so, update the
   `phase1_precompute.py` docstring reference in the same change.
3. Verify integrity: confirm every protected asset is still present, run
   `engine/validate_submission.py` and expect `RESULT: PASS`, and assert
   `team_vibecoder.csv` sha256 is unchanged
   (`dc3432e2815a99951f80ffecee3e8169c956c2681b33a834da7cedfe142e6952`).
4. Leave the working tree clean and report exactly which files were removed.

---

**Reply `EXECUTE` to proceed with the deletions in Section 1.**
Optionally add: `+ImplementationPlan.md` to also remove the borderline file
(its docstring reference will be patched), and/or `+README` to generate a short
`README.md` for GitHub presentation.
