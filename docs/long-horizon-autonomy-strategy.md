# Long-Horizon Autonomy — Strategy Brief

**Status:** Strategy brief / north-star direction document. Not an implementation plan, not a frozen contract. It records *where the system is, where it is going, why, and how the parts map in practice*, so the team shares one deep model of the problem before tactical work begins.
**Date:** 2026-07-20
**Relationship to other documents:** `docs/VISION.md` states the *timeless* commitments of this repository (contracts before code; a mechanical floor with accountable judgement above it; evidence over narration; proportionality). `docs/mode-b-lite/` holds the *current* design (target design, blueprint, ledgers) of the shipped supervisor. This brief bridges them forward: it explains what the current system is *for* beyond itself, names the one hard problem that decides whether the larger goal is reachable, and sketches a pathway. The downstream payload it points at is described, separately and conservatively, in the Mimic repository's `docs/dev/MIMIC-MODEL-BUILDER-PLAN.md`. Where this brief and the vision conflict, the vision wins; where this brief speculates, it says so.

---

## 1. The thesis in one sentence

We are building a system that is **as effective after 24 hours on a problem as it is after 24 minutes**, running on **local-only models**, trustworthy enough to be left executing consequential work unattended for days.

Everything below is a consequence of taking that sentence literally. The flat-effectiveness property is not a nice-to-have; it is the acceptance test. A system that degrades as its history grows cannot be trusted to run for days, and a system that cannot run for days cannot do the science this is ultimately for.

---

## 2. Why this repository exists beyond itself

`ai-agent-coder` is valuable in its own right — a graduated autonomy system for software engineering, useful at every rung from a standalone code review to a supervised multi-slice run. That standalone value is real and should be protected.

But its larger purpose is to be the **cheap, fast, unambiguous proving ground** for a substrate that will later carry a much higher-stakes payload: the **Mimic model builder**, a system that turns an astrophysics paper plus a goal into a traceable, tested, calibrated simulation-model package, through a gate-driven workflow, under local models, over long campaigns.

Software is the right proving ground precisely because its gates are unambiguous and its iteration loop is cheap: a test suite passes or it does not, a diff is in-surface or it is not, a commit descends from its parent or it does not. Science gates — physical invariants, unit consistency, figure parity within a *defensible* tolerance, calibration trade-offs — are far subtler and far more expensive to get wrong. We do not want to be debugging the orchestration substrate and inventing science gates at the same time. So we harden the substrate here, where a mistake costs a red test, and only then instantiate the science-specific layer on top, where a mistake costs a subtly wrong model that could poison every future build.

The mapping is close enough that this is not a metaphor — it is a staging strategy. Section 9 makes the mapping concrete.

---

## 3. The central problem: context rot over long horizons

**Context rot** is the degradation of an agent's effectiveness as the accumulated history it must reason over grows — through dilution of attention, drift from the original task, compaction that silently drops load-bearing detail, and the simple fact that a working set assembled over hours is worse than one assembled fresh. It is the single force standing between "works for 24 minutes" and "works for 24 hours."

The flat-effectiveness property can be restated precisely as an anti-rot requirement:

> No seat's effectiveness may degrade with wall-clock time or history length.

This is the lens through which every architectural choice in this brief should be read. A feature that improves a 20-minute run but accumulates state that rots a 20-hour run is a *regression* against the north star, even if it looks like progress. Conversely, a change that adds a little ceremony but keeps a seat's working set bounded and fresh may be exactly right, despite the vision's general suspicion of ceremony — because here the outcome being protected (multi-day reliability) is the whole point.

---

## 4. History and the context-topology lesson

The system has been through one full architecture and one deliberate rebuild, and the difference between them is *entirely* about where context is forced to live. This is the most important lesson the project has learned, so it is worth stating carefully.

**Old Mode B** kept the Project Manager (PM) as a *lightweight* coordinator. Almost all responsibility sat with the Developer and Reviewer, each starting from fresh context per slice; the system kept everything on track through machinery. The intent was sound and directly targeted the north star: if the PM stays light, its context fills slowly, so a long run does not overflow it. Context stayed focused where the work was — in each slice — and the coordinator barely accumulated.

It did not work, but not for the reason it looks like. The failure was that making *every* acceptance decision deterministic required machinery that grew without bound: a taxonomy of failure signatures, repair-round classifiers, circuit breakers and streak detectors, dual state copies and reconciliation, closed schemas validating fields the models had to report perfectly. The overhead of avoiding trusting any model judgement eventually cost more than the work it supervised, and — the cruel part — it failed hardest on exactly the weak models it was built to protect.

Here is the subtle point that is easy to miss: **that rulebook was itself a form of context rot.** An ever-growing set of rules is state that must be loaded, maintained, and reasoned over on every run and every change. Old Mode B did not escape the accumulation problem; it *relocated* it from the run's conversation into the statute book — and a statute book is harder to keep fresh than a conversation, because you cannot compact it and it cannot be reconstructed from evidence.

**Mode B Lite** (the current system, a total rebuild rather than a refactor) made the opposite trade. It moved judgement *back* into an empowered, accountable PM, and shrank the machinery to a small mechanical floor plus a minimal durable state. Developer and Reviewer still keep slice-level fresh context; the PM now carries the judgement the old rulebook tried to encode.

This is the better base for the north star, for a reason that generalises into the organising principle of the whole system:

> **You never escape context. You only choose where it lives — and durable, structured state can be kept small and reconstructed; a rulebook and a raw conversation cannot.**

Mode B Lite did not, however, make the long-horizon problem disappear. It *surfaced* it honestly. By concentrating judgement in one persistent seat, it created a single, visible context-rot bottleneck — the PM — where the old system had hidden the same problem inside brittle rules. That is progress: a visible problem in the right place beats an invisible one in the wrong place. Section 6 is about that bottleneck, and Section 7 is about dissolving it.

---

## 5. The core principle: context is a cache, durable state is the truth

The unifying idea that makes multi-day autonomy possible is this:

> **An agent's conversation context is a cache. The source of truth is durable, structured state on disk. Nothing load-bearing may live only in an accumulating conversation.**

If that holds, any seat can be compacted, killed, and restarted, and it rehydrates from state without losing the thread. Effectiveness stops being a function of how long the seat has been running.

Mode B Lite already embodies this for *acceptance*, which is the highest-stakes decision. The run report regenerates from controller-owned state alone, with the human-facing mirror deleted entirely. Acceptance rests on Git-visible state, the diff, `validation.md`, and review artifacts — never on the implementing agent's narration. The mechanical floor is eight facts computed from the repository, not from anyone's account of it. In other words, the parts of the system that already refuse to trust an accumulating conversation are exactly the parts that already survive a context reset.

The three seats, seen through this lens:

| Seat | Context lifetime | Rots over a long run? |
|---|---|---|
| **Developer** | Fresh session per slice; dies at slice end | No — bounded by construction |
| **Reviewer** | Fresh per review, pinned to a fixed diff; dies at review end | No — bounded by construction |
| **PM (supervisor)** | Persists across the entire run | **Yes — this is the bottleneck** |

Two of the three seats already have the property we want. The Developer and Reviewer cannot rot because they do not live long enough to. The PM is the one seat that persists, and therefore the one seat where "24 hours as good as 24 minutes" is not yet guaranteed. Finishing the job means making the PM as reconstructable as acceptance already is.

---

## 6. The PM is the last unbounded seat

It is worth being blunt about the tension this creates with Mode B Lite's founding bet. Lite's thesis is "empower the persistent judge." The north star's requirement is "minimise what persists." Read naively, these conflict.

They only conflict if the PM's *judgement lives in its conversation*. If instead the PM's judgement is continuously externalised into small, structured, durable artifacts as it is formed, then the persistent seat holds nothing that a fresh instance could not reconstruct — and the tension dissolves. The PM stays empowered *and* becomes refreshable.

So the design target for the PM is not "a smaller PM" or "a dumber PM." It is a PM whose every load-bearing thought has a home on disk. The question to ask of any piece of PM reasoning is: *if this PM were replaced right now by a fresh instance holding only the durable state, would the replacement know this?* Every "no" is a rot risk to be closed.

The P2/P3 convergence-read added in the Test 21 follow-up is a small but exact instance of this move. "Are review findings trending toward zero across slices, or accumulating?" was a judgement that previously lived only in the PM's head. Forcing it into the assessment/run-report turns it into durable state that survives a reset. That is the template, scaled down to one sentence. The frontier is applying the same discipline systematically to everything the PM currently knows only in-context.

---

## 7. The PM rehydration contract — the central deliverable

The single most important thing to build and prove for the north star is a **PM rehydration contract**:

> A fresh PM instance, handed only the durable state — `run.json` (the authenticated `lite-1` run state), `events.jsonl`, `notes.md`, and the per-slice `assessment.md` files — can resume a mid-run plan and make the *same next decision* the original PM would have made.

If this property holds, days-long autonomy is solved in principle: the PM can be compacted or restarted at any point, and the run continues at full fidelity. If it does not hold, no context-window size saves you — the twentieth hour will be worse than the first no matter what, because the seat carrying the run cannot be refreshed without loss.

Making the contract real has three parts:

1. **Enumerate the durable judgement surface.** Catalogue every kind of decision the PM makes and every piece of cross-slice context it relies on (accepted interfaces, deferred findings, failed approaches, evolving suspicion about a model's behaviour, interpretation calls on ambiguous plan prose, risk raises and their triggers). For each, identify where it currently lives. Anything living only in-context is a gap.

2. **Externalise the gaps.** Extend `notes.md`, `assessment.md`, and the event log so the catalogued judgement is written as it is formed — in the same spirit as the convergence-read, and always kept small and curated (the notes file already tripwires at a hard cap precisely because an unbounded notes file would itself rot every later prompt).

3. **Adversarially test resume.** Build a real `resume` capability, then kill the PM at many points across a multi-slice run — mid-observation, after a floor pass but before acceptance, mid-steer, between slices — rehydrate from durable state alone, and verify the resumed PM makes the same next decision. This kill-and-resume harness *is* the "24 hours as good as 24 minutes" proof, and it belongs here, in the cheap software domain, long before any science is at stake.

**The asymptote worth naming.** The most rot-proof design has *no long-lived conversational seat at all*. Developer, Reviewer, and PM are each fresh-per-unit-of-work, and durable state is the only thing that persists. In that design the PM loop is stateless-per-tick: invoke fresh, hand it the state, get one decision, exit. This is the same "call it, don't keep it live" question raised about the Developer session, applied to the seat where it matters most. Whether a per-tick PM can match a live PM's continuity is precisely what the rehydration contract measures. We do not have to commit to the asymptote to benefit from moving toward it: every judgement we externalise makes the persistent PM more disposable, whether or not we ever make it fully stateless.

---

## 8. The judgement-load lever — one move that helps two goals at once

The PM in the target deployment will be a *local* model, and a persistent local judge is the system's weakest link. The vision already says this plainly and refuses to pretend the architecture absorbs it. For long-horizon local-model science, the PM seat is simultaneously the most important and the most fragile.

The lever that addresses this is the same one that addresses rot, which is why it is worth stating on its own:

> **The more judgement is pushed into validated gates and human escalation, the less the persistent PM has to carry — which improves local-model reliability and reduces context load at the same time.**

These are not two levers to trade off; they are one lever with two payoffs. A PM asked to make small, evidence-bounded decisions is both more reliable on a modest local model *and* lighter to keep fresh across a long run.

This refines — it does not retreat from — Mode B Lite's "empower the PM" bet. Lite's real insight was never "make the PM do everything"; it was "do not try to make *everything* deterministic." The refinement for high-stakes science states the boundary precisely:

- **Mechanise what you can validate.** A gate may auto-clear only where its tolerance has been demonstrated to catch realistic injected errors. This is the vision's "mechanise the floor" principle, extended to domain gates.
- **Judge what you cannot mechanise.** The PM's accountable judgement covers everything semantic that no validated gate can settle.
- **Escalate what is irreducibly a human's call.** Calibration weighting the paper does not define, and promotion of knowledge into shared memory, are scientific decisions, not task advancement — they go to a human by design.

Framed this way, the local PM is not asked to be a brilliant scientist. It is asked to be a reliable **gate-runner, evidence-assembler, and escalation-router**. That is a job a modest local model can do well and hold in a small, refreshable context — and it is exactly the job the north star needs the persistent seat to do.

---

## 9. The pluggable gate stack — the bridge from software to science

Today the mechanical floor is eight hardcoded facts: plan digest unchanged; repo and branch identity; recorded approval for approval-flagged slices; `result.json` present and naming the slice; changed files within the frozen authorised surface; commit ancestry and branch head; clean worktree; no hard-stop prompt visible. These are universal — they protect *any* autonomous run regardless of domain.

Science needs more: physical invariants (non-negativity, mass/metal/baryon conservation where applicable, physical ranges), unit consistency as a first-class assertion (a silent unit mismatch has already caused a severe real defect in Mimic), figure or relation parity against digitised paper targets within *defensible* tolerances, and non-regression against trusted baselines where physics is shared. These are domain-specific and, crucially, *not all mechanisable* — some relations can be auto-cleared, others must remain review-class because no tolerance can safely separate correct physics from subtly wrong physics.

The abstraction that lets one substrate serve both software and science, without baking science into the PM, is a **plan-declared, pluggable gate stack**:

- The **mechanical floor stays universal** — the base every run gets, unchanged.
- The **plan declares which additional gates apply per slice** (or per science process), and for each gate declares whether it is *mechanical-auto-clear* or *review-class*.
- A gate may be marked auto-clear **only if** it comes with evidence that it catches realistic injected errors for the relation it guards. Absent that evidence, it is review-class: it produces evidence for the PM's or a human's judgement, not a mechanical pass.

This is a direct generalisation of the floor/judgement split the vision already commits to. It keeps the PM *gate-agnostic*: the PM runs whatever gates the plan declares, mechanises what is validated, and routes the rest to judgement or escalation. Software runs declare test/lint/surface gates; science runs declare invariant/unit/parity/calibration gates. Same supervisor, same rehydration contract, same anti-rot properties — different declared gates.

The mapping between the current system and the Mimic requirements is close enough to be a staging plan rather than an analogy:

| Mimic model-builder requirement | What the current substrate already provides | Gap to close |
|---|---|---|
| "Done" defined by evidence and gates, not plausible narration | Evidence over narration; the mechanical floor; PM assessment from repository state | None of principle; extend to science gates |
| Implement one process at a time in isolation | Fresh Developer session per slice; clean `before_head` authorisation boundary | Map "process" to "slice"; per-process science gates |
| Human-approved specification before production code | Approval-gated slices; `approve` reserved to the human; PM may never self-approve | Intake/Evidence/Specification stages ahead of implementation |
| Isolation of orchestration artifacts from the product repo | Authenticated run state under the git dir; gitignored `.pm/` mirror; clean branch/patch out | Mimic-workspace isolation model (separate orchestration environment) |
| Independent audit and a quality report | PM-commissioned drift-audit + code-review on elevated slices; regenerable run report | Scientific quality report with paper-to-code traceability |
| Auto-clear only where tolerance is injected-error-validated; else review-class | The floor/judgement split; proportional review; risk raises | Injected-error validation harness; a science-gate layer that does not yet exist |
| Traceability of every formula/parameter/unit to a source | Assessment records what was examined; events log every act | An evidence ledger keyed to paper locations and explicit user decisions |
| Deterministic stochastic physics | Determinism as a stated value; the floor checks Git-visible state | Enforce stable per-halo/per-FoF seeds as a domain invariant gate |
| Protected institutional memory; promotion gated harder than task advancement | Elevated-slice + mandatory-human-approval shape | A cross-run knowledge store with human-signed promotion; no cross-run memory exists today |
| Long, steerable campaigns | Notes curation; bounded attempt budget; stop-for-human discipline | The PM rehydration contract (Section 7) — the load-bearing gap |

Read top to bottom, the left column is the Mimic plan and the middle column is Mode B Lite. The philosophy is already shared; the right column is the honest work remaining. The two rows that are genuinely new subsystems — a validated science-gate layer and a human-gated institutional memory — are also the two the Mimic plan itself flags as unsolved, so the substrate is not behind the science plan; they are converging.

---

## 10. The desired end state

Concretely, the system is fit for its purpose when it has all of the following properties. This is the checklist the pathway in Section 11 is trying to reach.

- **Every seat operates on a bounded, reconstructable working set.** No seat's effectiveness depends on how long it has been running. The Developer and Reviewer already satisfy this; the PM satisfies it via the rehydration contract.
- **Durable state is the sole source of truth.** Any seat can be killed and rehydrated from disk with no loss of decision fidelity, demonstrated by an adversarial kill-and-resume harness.
- **The supervisor is gate-agnostic.** Domain gates are declared by the plan, not wired into the PM. The same supervisor runs software and science.
- **Mechanisation is earned, not assumed.** A gate auto-clears only where it has been shown to catch realistic injected errors. Everything else is review-class evidence.
- **The persistent seat carries the least judgement it can.** Validated gates and human escalation absorb as much as possible, keeping the local PM reliable and light.
- **The irreducibly human decisions are reserved for humans** — the model specification, calibration trade-offs the source does not define, and any promotion into shared memory — by mechanism, not by politeness.
- **Traceability is total and durable.** Every accepted claim links to its evidence (paper location, reference implementation, or explicit human decision), surviving any context reset.
- **Orchestration never contaminates the product.** The subject repository receives a clean, reviewable branch or patch series; all campaign state, ledgers, drafts, and failed attempts live in an isolated workspace.
- **The highest-harm failures remain mechanically impossible**, exactly as the vision guarantees today — unauthorised surface changes, broken ancestry, self-approved human gates — with the residual, honestly-documented threat boundary unchanged.

---

## 11. The pathway

The stages are ordered by dependency, not by calendar. Each is a proving step; do not begin one before its predecessor is trustworthy.

**Stage A — Make the substrate boringly reliable (now).** Continue running the test plans until hiccups stop recurring. Resolve the empirical seat-model questions: can a supported local harness sustain the full agentic implement→test→commit loop headless (the Developer-session question), and do multi-slice runs stay stable with real local models across both risk paths? This is the *trustworthy* leg, and it is a prerequisite for everything else. It happens entirely on `ai-agent-coder`.

**Stage B — Build and adversarially prove the PM rehydration contract (the key deliverable).** Enumerate the PM's durable judgement surface, externalise the gaps into curated durable artifacts, build a real `resume`, and prove with a kill-and-resume harness that a rehydrated PM makes the same next decision. This is the direct, testable answer to "24 hours as good as 24 minutes," and it belongs on `ai-agent-coder`, where a wrong resume costs a red test rather than a corrupted campaign.

**Stage C — Generalise the floor into a plan-declared pluggable gate stack.** Keep the eight-fact mechanical floor universal; let the plan declare per-slice gates, each mechanical-auto-clear (with injected-error validation) or review-class. Prove it still on software, with software gates, so the abstraction is exercised before any science depends on it. Build the injected-error validation harness here too — it is domain-agnostic in shape even though its instances will be domain-specific.

**Stage D — Prove the whole substrate end to end on software.** A multi-slice, multi-hour run, on local models, with the pluggable gate stack, that survives kill-and-resume and produces a fully traceable, reconstructable record. This is the graduation criterion: trustworthy + rot-proof + gate-pluggable, demonstrated, not asserted.

**Stage E — Instantiate the Mimic science layer (later, gated by the Mimic plan's own preconditions).** Only once the substrate has graduated: add the science-gate definitions (invariants, unit-explicit assertions, validated-tolerance parity), calibration escalation, the paper-traceable evidence ledger, workspace isolation against the Mimic product repo, and the human-signed institutional-memory promotion. These sit *on* the proven substrate; none of them should require changing the supervisor's core, which is the whole point of Stage C.

A note on repository boundaries: Stages A–D live on `ai-agent-coder` and make it a better standalone system as a side effect. Stage E is where the substrate is carried into the Mimic environment. Keeping the science-specific work strictly on top of a proven, gate-agnostic core is what prevents the classic failure of co-evolving the harness and the domain until neither is trustworthy.

---

## 12. Risks, open questions, and honest limits

- **Local PM judgement quality is the load-bearing risk.** The whole edifice rests on a local model in the supervisor seat making sound calls. The judgement-load lever (Section 8) is the mitigation, not a cure. If, in real runs, local-PM judgement disappoints even on the reduced job, the honest response is to push still more into validated gates and human escalation — or to accept a stronger PM seat where the stakes justify it. The vision's calibration point stands: a weak model in the PM seat weakens the judgement layer itself, and no architecture fully absorbs that.
- **Does a per-tick PM match a live PM?** The rehydration contract assumes reconstructed continuity can equal live continuity. This is an empirical claim to be measured in Stage B, not assumed. If some judgement proves genuinely irreducible to durable artifacts, that is a finding that reshapes the design, not a failure to paper over.
- **Harness headless reliability is unresolved.** Whether local harnesses sustain long agentic loops without an interactive terminal is the open question behind both the Developer-session design and the eventual seat topology. It must be answered by a spike, not by preference.
- **The science-gate open problems are real and unsolved** (they are catalogued in the Mimic plan): tolerance selection, injected-error validation per relation, validating novel models that are not byte-identical to any baseline, multi-relation calibration weighting, and missing-data handling. Stage E cannot begin until these have grounded answers; the substrate work (Stages A–D) does not depend on them, which is why we do the substrate first.
- **The threat model is unchanged and still honest.** This system defends against corner-cutting, drift, and overconfidence — not a determined adversary fabricating coherent evidence, and not a same-user process that steals the run capability or subverts the supervisor. Long-horizon operation does not expand what is mechanically guaranteed; it raises the stakes of the judgement layer, which is exactly why the rehydration contract and the judgement-load lever matter.

---

## 13. Design principles specific to long-horizon autonomy

These extend the vision's principles for the multi-day, local-model regime. Where they add to the vision, they are consistent with it; where the vision speaks, it governs.

1. **No load-bearing state in an accumulating conversation.** If losing a context would change a decision, that state belongs on disk, small and structured, before the decision is made.
2. **Every seat operates on a bounded, reconstructable working set.** Effectiveness must not be a function of elapsed time. Two of three seats already satisfy this by dying young; the third must satisfy it by rehydration.
3. **Context is a cache; durable state is the truth.** The report already regenerates from state; make judgement do the same.
4. **Mechanise only what you can validate; judge the rest; escalate the irreducible.** A gate that auto-clears without injected-error evidence is determinism dressed as safety — the failure the vision names in the other direction.
5. **Push judgement off the persistent seat.** Every decision moved into a validated gate or a human escalation makes the local PM both more reliable and more disposable — one move, two payoffs.
6. **Prove reconstructability adversarially.** Kill-and-resume is to long-horizon autonomy what the fake-harness floor tests are to the mechanical guarantees: the property is only real once something has actively tried to break it.
7. **Keep the supervisor gate-agnostic.** Domains are declared, not compiled in. The same core must run software and science, or the substrate was never really the substrate.
8. **Harden the substrate where mistakes are cheap.** Every property the science payload needs is proven first on software, where a defect costs a red test, not a poisoned model.

---

## 14. Stability note

This is a direction document, deliberately silent on tactical tooling — model choices, serving stack, persistence formats, workspace isolation mechanism — because those depend on the ecosystem at the time the work is done, and the Mimic plan is rightly conservative about not fixing them early. What is stable here is the *shape* of the problem and the *properties* of the solution: flat effectiveness across time, context as a cache, a reconstructable persistent seat, a gate-agnostic supervisor with validated mechanisation and honest escalation, and a substrate proven on cheap gates before it carries expensive ones. Revise this brief when a stage completes and teaches something, or when the north star itself changes — not for tactical detail that was always meant to be decided late.
