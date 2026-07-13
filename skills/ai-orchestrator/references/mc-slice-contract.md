# Master Controller Slice Delegation Contract

This is the complete delegation contract embedded into a Master Controller slice prompt. It is intentionally narrower than the general `ai-orchestrator` skill: the operator and MC have already selected the worker tools, model, effort, repository, slice, and authorization policy, and the validated launcher owns all harness-specific flags.

## Role Boundary

The slice session is the orchestrator. Workers are bounded helpers: they never become orchestrators, re-delegate, create the slice commit, approve drift, or make the final acceptance decision. The orchestrator remains responsible for reading worker output, deciding whether it satisfies the request, fixing permitted defects, and producing the structured slice result.

Keep work local when delegation adds no value. Prefer a separate model for the hostile drift audit and independent code review. When the plan marks `Independent audit required: yes`, both audits must be delegated through separate validated requests; a local substitute does not satisfy the slice.

## Authoritative Policy

`worker-policy.json` is authoritative for run and slice identity, plan digest, repository, worker artifact root, required tools/model/effort, permitted roles and access modes, and authorized files. Copy identity values from the policy rather than retyping them.

Never construct or invoke a worker harness command directly. Write one semantic request JSON per bounded task and pass it to `worker_jobs.py launch` with the policy. The launcher validates the request, embeds every skill named in `required_skills`, composes tested harness flags, forces the policy repository as the working directory, and records launch evidence. A rejected request starts no worker; read its feedback artifact and correct only the named fields.

Do not set, unset, redirect, or invent tool-home or credential variables. Use the environment MC supplied. Report authentication failures as blockers.

## Semantic Request

Each request must include the policy's `slice_id`, `plan_sha256`, configured tool/model/effort, a permitted role and access mode, a bounded task, task-specific context, exact `required_skills`, relevant files, constraints, and an exact expected-output contract. Use `read-only` for audits and reviews. A drift-audit request must name only `drift-audit`; a code-review request must name only `code-review`.

For an independent audit sequence:

1. Launch the drift-audit request.
2. Wait for it to complete, extract and read its output, and obtain a passing authorization verdict.
3. Only then launch the code-review request.
4. Wait for it to complete, extract and read its output, and decide whether findings require an in-contract fix, a stop, or a post-plan consideration.

Do not launch the two audits in parallel. Distinct validated launches are required on opt-in slices.

## Helper Lifecycle

Use the helper path and artifact locations supplied in the slice prompt:

1. `worker_jobs.py init --prefix workers` once to create the run directory.
2. `worker_jobs.py launch --run-dir <run-dir> --policy <policy> --request <request>` for each request.
3. `worker_jobs.py activity` for lightweight health checks.
4. `worker_jobs.py wait` with a bounded timeout.
5. `worker_jobs.py extract` to read the clean final output.
6. `worker_jobs.py cancel` if a worker must be stopped.

A worker may remain silent while reasoning or using tools. Do not infer failure from empty output alone while its process is healthy. A clean exit is still insufficient when the contracted answer is missing, refused, or replaced by a question. Correct the request and relaunch with an `-rN` label; do not cite the incomplete attempt as semantic evidence.

## Evidence

When any worker is used, write `worker-evidence.md` in the slice artifact directory with each label, role/tool, bounded purpose, run directory, extract command, result summary, and why the output was or was not sufficient. MC verifies validated process evidence for opt-in audits; semantic sufficiency remains the orchestrator's responsibility.

The launcher and MC gates are the mutation backstop. Harness access labels vary in mechanical strength, so never claim a stronger isolation guarantee than the configured harness actually provides.
