# P3 v2 brief (PMS Director, 2026-10-24)

**SYNTHETIC educational project. Tier B (agent-produced under Taim's direction). No publishing, no GitHub/LinkedIn action, no real Airbus data or claims.**

v1 (audited, left untouched, read-only reference): `C:\Users\USER\Documents\anylogic-pms\portfolio\p3-assembly-flow\`
v2 (this workspace, all edits go here): `C:\Users\USER\Documents\anylogic-pms\portfolio\p3-assembly-flow-v2\`
Original prompt: `..\prompts\P3-anylogic-assembly-flow.md`. Playbook section 0 overrides everything.
Central question: where does ONE added station cut lead time most, Assembly (high mean) or Test (long tail), and what does it buy under explicit capacity and cost assumptions?

## Why v2 exists: independent audit of v1 (verdict READY WITH LIMITATIONS)
Verified OK in v1 (do not break): workbook cleaning (200 rows, 195 clean, excluded ORD-0195/0166/0162/0053/0012), replay 195/195 within 3.64e-12 h,
M/M/1 native pass, CRN per-job tapes, paired CIs (baseline mean 86.99 h / P90 138.75 h; Assembly +1 saves 12.35 h, Test +1 saves 7.79 h, direct 4.56 h [4.05,5.06]), 70 tests.

Open items v2 must fix (audit ids):
- H1 Capacity result rests on assumed inputs: arrival mean 30 h (data: 5.054 h gap), all capacities 1, elapsed durations (include waiting) used as service times -> double counting of waiting (~31.5 h simulated wait on top of 55.46 h elapsed).
- H2 The two sensitivities are ONE experiment: service-scale 0.75 == arrival 40 h rescaled in time (WIP identical, lead x0.75); arrival 25 ~ service 1.25. Need two genuinely different axes (baseline capacity vector, waiting-share haircut, input family, rework, component availability) with n >= 30.
- H3 "Starvation" leg is 100% minus utilization for capacity-1 stages (identity), not independent evidence. After Assembly +1 the bottleneck MOVES to Test (util 33.6% vs 58.8%, queue 0.042 vs 0.545): the report never says so. Need real blocked/starved-by-upstream evidence (time a stage is idle while its upstream stage is busy/queued, or per-resource starvation) and a post-change bottleneck table.
- H4 No validation of the capacity model vs observed data. Need stated accuracy criteria BEFORE running, a no-wait-limit check (simulated lead ~ 55.46 h), observed-rate runs, honest statement of what cannot be validated.
- M1 Undisclosed earlier sweep `results/diagnostics/first-truncated-sweep/` (v1) must be disclosed; do not claim the finite amendment preceded capacity results unless evidence supports it.
- M2 Fitted distributions are decorative: add a fitted-input mode (lognormal/Weibull via inverse CDF on the existing per-stage uniform draw, so CRN is preserved) and compare effects with empirical rows.
- M3 Finite-campaign start-up bias: add Welch analysis and a steady-state production design (warm-up deleted by job index/time, analysis side).
- M4 Cost metric scaled by arbitrary campaign length: express cost per added station-hour and per order-lead-hour saved in a steady-state window.
- M5/L Visual evidence: no editor canvas capture, blank `anylogic-editor.png` (do not copy), schematic lacks pass/rework, PDF is a re-render of the report without block/parameter description, duplicated sentence in report.
- Requirements still unmet from the original prompt: kitting synchronization (Assembler/Combine), real rework logic, Welch/warm-up decision, validation, cross-tool replica (playbook 4.3), canvas PNG.
- NEW from Taim: a **3D animation** so the workflow can be watched in AnyLogic like his other homeworks (queues, stations, resource units, moving order boxes), runnable from the editor.

## Hard rules for every specialist
1. Edit only inside the v2 workspace. Never modify v1. Never delete v1 logs.
2. **Do NOT launch AnyLogic (or `AnyLogic.exe`, or java on a model).** Another session (P2) is running AnyLogic now and only one instance may run at a time; the PMS Director launches every native run. You may read AnyLogic's installed jars/help/example models and compile-check Java snippets against the installed libraries (v1 `tools/check_model.py` shows how).
3. Never claim a model ran unless AnyLogic produced the numbers; label static checks as static checks.
4. Default behaviour of the v2 model (all new features OFF) must reproduce v1 per-job lead times (same seed/scenario) to 1e-9 h. New random draws use NEW, separate java.util.Random streams that are always consumed per job at release (CRN-safe), never the v1 streams.
5. Keep files < 800 lines (split generators/modules). Keep every artefact labelled SYNTHETIC.
6. Do not overwrite or weaken limitations text; report failures and unmet precision as failures.
7. Your final message IS the deliverable: list files changed/created, what you verified (with command output), what is open. Do not end with "waiting".
