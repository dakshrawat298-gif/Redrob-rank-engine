---
name: Running long CPU batch jobs in the Replit sandbox
description: Why long background jobs die silently here, and the memory/cgroup limits that cause OOM — and how to run them reliably.
---

# Long-running CPU batch jobs in this sandbox

Running a multi-minute CPU job (e.g. embedding ~100k records) here is fragile for
two independent reasons. Both bit the Redrob Rank Engine 100k precompute.

## 1. `nohup ... &` from a bash tool call gets reaped (~5 min later)
A process started with `nohup cmd & ` inside a bash tool call **survives that tool
call returning, but is killed a few minutes later** when the sandbox tears down
that call's session/cgroup. `nohup` only blocks SIGHUP, not the cgroup teardown.
Symptom: the job dies silently mid-run with no traceback and no partial output,
always a few minutes after the launching tool call ended.

**Why:** each bash tool invocation runs in its own short-lived session; backgrounded
children are not durable across tool calls.

**How to apply:** for any job longer than the ~120s bash-tool timeout, run it as a
**managed workflow** (`configureWorkflow`, `outputType:"console"`, no `waitForPort`
for a batch job). Workflows are supervised and survive across tool calls. Redirect
the command's output to a log file and poll the file with `read`/grep between turns;
the workflow's own captured output will be empty if you redirect. A job that
*completes within one blocking bash call* (in-call `while` monitor) is also safe —
it's only cross-tool-call backgrounding that gets reaped.

## 2. cgroup `memory.max` is ~8GB, shared with the always-on artifact workflows
`/sys/fs/cgroup/memory.max` ≈ 8 GiB (NOT the node's ~7.7GB "free"; check
`memory.current`, `memory.peak`, and `memory.events` `oom_kill`). The api-server and
mockup-sandbox dev-server workflows hold a volatile ~3GB baseline and spike during
rebuilds. A single fastembed/onnxruntime embedding process plateaus at ~3GB RSS
within ~18s and stays there regardless of shard size (the onnxruntime CPU mem-arena,
not our data, dominates; smaller `batch_size` barely helps). So:
- 1 embedder (~3GB) + baseline fits and is the only reliably-safe config here.
- 2+ concurrent embedders (~6GB+) tip past 8GB → SIGKILL/-9 (`oom_kill` increments).

**How to apply:** default embedding `--workers 1` on this box. Make the precompute a
**resumable shard pool** (each shard subprocess writes its own `.npy`/`.json`, skip
shards already on disk) plus **retry-on-OOM** (re-spawn a `-9` shard a few times
after a cool-down) so a transient neighbour spike doesn't lose the whole run. Don't
remove the artifact workflows to free RAM — they're artifact-managed and removal is
destructive. The 16GB grader box won't have these limits; this is dev-sandbox only.

## Cost note
Single-core embedding throughput here is ~26 rec/s under workflow contention
(~84 rec/s isolated), so 100k is a ~30–60 min OFFLINE index build. That is the
precompute, NOT the hackathon's constrained stage — RANKING (FAISS search + rerank
over precomputed vectors) is sub-second and independent of corpus size.
