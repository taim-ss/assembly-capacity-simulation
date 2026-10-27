# P3 v2 preregistration — written BEFORE any v2 native run

**SYNTHETIC educational project. Tier B (agent-produced under Taim's direction).** This document is
frozen as the decision/acceptance contract before any v2 AnyLogic run is launched. Any deviation
discovered after runs start must be recorded as a deviation in `report.md`, not silently folded
into this file.

## 1. Purpose and decision question

Central question (unchanged from `v2-brief.md`): under explicit hypothetical capacity and cost
assumptions, where does **one added station** cut lead time most — **Assembly** (highest elapsed
mean, 20.18 h) or **Test** (longest elapsed tail, P90 33.87 h) — and what does it buy in cost and
lead-time terms? v2 additionally must (a) validate the capacity model against the observed data
before trusting any capacity comparison, (b) separate the arrival-rate/service-scale confound into
genuinely independent sensitivity axes, (c) produce real bottleneck evidence (utilization + queue +
starved-by-upstream, not the one-minus-utilization identity), (d) run a steady-state design with a
Welch-derived warm-up instead of only the v1 finite 600-order campaign, and (e) disclose the
undisclosed v1 diagnostic sweep.

## 2. Observed-input facts (frozen; do not re-derive mid-analysis)

| Fact | Value | Source |
|---|---|---|
| Clean orders | 195 of 200 (5 excluded: ORD-0195, ORD-0166, ORD-0162, ORD-0053, ORD-0012) | `analysis/calibration/summary.json` |
| Observed arrival gap mean | 5.0540201005 h (199 gaps) | v1 `design.md` |
| Stage mean elapsed (h) | Kitting 5.91, Assembly 20.18, Test 17.67, Quality 8.74, Handover 2.97 | v1 `report.md` Table 2 |
| Stage P90 elapsed (h) | Kitting 9.02, Assembly 27.37, Test 33.87, Quality 13.51, Handover 4.43 | v1 `report.md` Table 2 |
| End-to-end mean / P90 | 55.4602564103 h / 73.8633333333 h | v1 `results/native-replay/native_analysis.json` |
| Observed-rate offered loads A_j (elapsed-as-service, lambda=1/5.054) | [1.169, 3.992, 3.497, 1.729, 0.587] | v1 `design.md` |
| Baseline capacity policy c_j = ceil(A_j/0.85) | [2, 5, 5, 3, 1] (Kitting, Assembly, Test, Quality, Handover) — queueing-analyst verifying | derived; this preregistration assumes it pending that check |
| v1 illustrative baseline (used in E3) | arrival mean 30 h, capacities [1,1,1,1,1], 600-order finite campaign | v1 `experiments.md` |

If queueing-analyst's verification changes the c_j vector, E2/E4/E5 configurations below are
re-derived with the corrected vector and the change is logged as a deviation, not silently applied.

## 3. Experiment families: exact configuration, acceptance rule, run counts

Common fixed facts for every v2 native run: model time unit hours; `repSeed` = the seed column;
streams reset at Source first-arrival scheduling (arrival 11001, row 12001, quality 13001, stage
21001+1000k, rework 14001, component 15001, all +repSeed); every job's full service vector is drawn
at release before resource-dependent ordering; single AnyLogic PLE instance, runs launched serially
by the Director. Runtime assumptions used for budgeting: ~5–10 s per 600-order finite run, ~10–20 s
per 2,000-order run (linear interpolation), ~30–60 s per 5,000-order run, M/M/1-class 10,000-job
verification runs priced like v1 (~fast, single real resource).

### E0 — Replay regression and v2-default regression vs v1

| | |
|---|---|
| Purpose | Prove v2 with all new parameters at default reproduces v1 bit-for-bit, per `regress_vs_v1.py` criteria (§9). |
| Configuration | (a) Replay: seed 1, 195 clean orders, replay=true (reuses v1's own replay log — **0 new runs**, just re-analysis with the v2 parser). (b) Finite default regression: replay=false, target=600, meanInterarrival=30, scale=1, jointBootstrap=true, rework=0, warmup=0, capacities=[1,1,1,1,1], inputMode=0, componentMode=0, maxRework=5 (irrelevant at rework=0), seeds 1–10, scenarios 0–5. |
| Study label | `v2-regression` |
| Seeds / orders | (a) seed 1, 195 orders — 0 new logs (reuse v1). (b) seeds 1–10 x scenarios 0–5, 600 orders each — **60 new logs**. |
| Capacity vector | [1,1,1,1,1] (+1 per scenario, as v1) |
| Acceptance rule | Every v2-default log's `P3_ORDER` (release, finish, lead) and `P3_STAGE` (entered, started, finished, duration) match the matching v1 log's values to **1e-9 h** per job, for seeds 1–10 x 6 scenarios. Any single job over tolerance fails the whole regression. |
| Expected log count | 60 |

### E1 — No-wait-limit validation

| | |
|---|---|
| Purpose | Confirm the finite capacity model, run with effectively unlimited capacity and the **observed** arrival rate, reproduces the observed end-to-end mean/P90 (55.46 h / 73.86 h) and per-stage means/P90 within tolerance — i.e. that elapsed-as-service plus zero queueing recovers the source data. |
| Configuration | replay=false, target=600, meanInterarrival=5.0540201005, scale=1, jointBootstrap=true, rework=0, warmup=0, capacities=[50,50,50,50,50] (all stages), inputMode=0, componentMode=0, scenario 0 only (no sweep — capacity is already saturating at 50). |
| Study label | `e1-no-wait-limit` |
| Seeds / orders | Pilot: seeds 1–10, 600 orders. Confirmation (if pilot misses precision): seeds 11–40, 600 orders. |
| Capacity vector | [50,50,50,50,50] |
| Acceptance rule | Mean and P90 end-to-end lead time, and each stage's mean/P90, must lie within the v1 design's declared accuracy band: mean error <=10%, P90 error <=15% against the observed values in §2 (same targets v1 used for fitted distributions — this is the equivalent capacity-model check). Additionally each stage's simulated mean queue and utilization must be ~0 (capacity never binds), proving the 50-unit pools are non-constraining. |
| Expected log count | Pilot 10; confirmation up to 30 (total <=40) |

### E2 — Main decision experiment (observed arrival rate, steady state)

| | |
|---|---|
| Purpose | The central Assembly-vs-Test decision, at the **observed** arrival rate and the derived 85%-utilization baseline capacity vector, run long enough to support a Welch-trimmed steady-state read (not the v1 finite-campaign read). |
| Configuration | replay=false, meanInterarrival=5.0540201005, scale=1, jointBootstrap=true, rework=0, warmup=0 (warm-up is deleted in analysis, never passed to the model), capacities baseline [2,5,5,3,1]; scenarios 1–5 add one unit to the corresponding stage; inputMode=0, componentMode=0. Target length **5,000 orders** per run (long enough for a post-warm-up steady window after Welch trimming). |
| Study label | `e2-main-decision` |
| Seeds / orders | Pilot: seeds 1–10 x scenarios 0–5 (**60 runs**, 5,000 orders each). Confirmation: fresh disjoint seeds, batch size set from pilot half-widths per §6 stopping rule, **capped at 40 replications per scenario (240 runs)** — Director sign-off item 1 below. |
| Capacity vector | [2,5,5,3,1] baseline; +1 at the swept stage per scenario |
| Acceptance rule | Not a pass/fail gate by itself — this is the decision experiment. Precision targets apply (§6/§7). Primary confirmatory claim is the Holm-adjusted Assembly+1 vs Test+1 contrast on mean and P90 lead time (§7). |
| Expected log count | Pilot 60; confirmation up to 240; total up to 300 |
| **Director sign-off item 1** | 300 runs x 5,000 orders at ~30–60 s each is roughly 2.5–5 h of serial AnyLogic wall time. If that is too long, cut the confirmation cap to 20 replications/scenario (120 runs, total 180) and say so in the run log — precision will likely not reach 5% relative half-width on the smallest effects (Kitting/Quality/Handover +1), which is acceptable since those are not the primary contrast. |

### E3 — Scaled-down contrast case (v1, read-only, no rerun)

| | |
|---|---|
| Purpose | Keep the v1 600-order, all-capacity-1, 30 h-interarrival finite campaign as the explicit **"marginal value of the 2nd station in a scaled-down system"** contrast case against E2's observed-rate steady-state result. |
| Configuration | Unchanged from v1: replay=false, target=600, meanInterarrival=30, capacities=[1,1,1,1,1], scale=1. |
| Study label | `e3-scaled-down-contrast` (presentation label only; data is v1's) |
| Seeds / orders | **0 new runs.** Read `results/native/confirmation/` (190 seeds x 6 scenarios, seeds 11–200) read-only from the v1 tree. |
| Capacity vector | [1,1,1,1,1] |
| Acceptance rule | None (reuse of already-accepted v1 results). Presentation requirement: every table/figure built from E3 must be labelled "scaled-down illustrative campaign (30 h interarrival, capacity 1 baseline) — not the observed-rate steady-state result" and placed next to, never merged with, E2's numbers. |
| Expected log count | 0 (reads 1,140 existing v1 logs) |

### E4 — Identifiability / calibration manifold

| | |
|---|---|
| Purpose | Show that (capacity vector c, waiting-share haircut s = serviceScale) is **not identifiable** from the observed end-to-end mean alone: many (c, s) pairs reproduce 55.46 h. Report how the Assembly+1-vs-Test+1 ranking behaves along that manifold. |
| Configuration | Four baseline capacity vectors, Assembly capacity in {4,5,6,8}; Test capacity co-scaled to preserve the Assembly:Test load ratio, c_Test = round(c_Assembly x A_Test/A_Assembly); Kitting/Quality/Handover held at the E2 baseline [2,_,3,1]. meanInterarrival=5.0540201005 (observed), inputMode=0, componentMode=0, rework=0. For each c vector, sweep `serviceScale` over a coarse grid {0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2} to locate s* where simulated end-to-end mean ~ 55.46 h (interpolate between grid points; exact root-finding is not required — the point of this experiment is the *shape* of the manifold, not pinpoint calibration). |
| Study label | `e4-identifiability` |
| Seeds / orders | Grid search: 4 vectors x 8 scale points x 5 seeds, 2,000 orders each = **160 runs**. Contrast at interpolated s*: 4 vectors x 3 scenarios (baseline, Assembly+1, Test+1) x 10 seeds, 2,000 orders = **120 runs**. |
| Capacity vector | Assembly in {4,5,6,8}; see co-scaling rule above |
| Acceptance rule | No statistical pass/fail. Required reporting: a table of (c_Assembly, c_Test, s*, resulting end-to-end mean, Assembly+1 vs Test+1 mean/P90 ranking) for all four vectors, plus an explicit sentence per outcome using the pre-registered wording in §8. |
| Expected log count | 280 |
| **Director sign-off item 2** | 280 runs x 2,000 orders at ~10–20 s each is roughly 0.8–1.5 h. If tight, cut to 3 capacity vectors ({4,6,8}) and a 5-point scale grid ({0.6,0.8,1.0,1.2,1.4}): 3x5x5=75 grid runs + 3x3x10=90 contrast runs = 165 runs, ~35–55 min. |

### E5 — Independent sensitivities (n>=30 seeds; genuinely separate axes)

| | |
|---|---|
| Purpose | Five axes that are NOT the same experiment in disguise (unlike v1's arrival-mean/service-scale pair). Each axis is tested only against the three scenarios that matter for the decision (baseline, Assembly+1, Test+1) to keep the run count affordable; full six-scenario sweeps are not repeated per axis. |
| Axis 1: capacity-vector scale | E2 baseline x {0.5, 1.5} (round to nearest integer, minimum 1) — the *overall* capacity level, distinct from adding one unit at one stage. |
| Axis 2: waiting-share haircut | `serviceScale` in {0.5, 0.75} at the E2 baseline capacity vector (1.0 is already the E2 reference — not retested here). |
| Axis 3: input family | `inputMode=1` (fitted marginals) vs the default 0 (already covered as reference in E2) — tested once, at inputMode=1, against the E2 baseline capacity vector. |
| Axis 4: rework | `reworkProbability` p in {0.05, 0.10}, maxRework=5, at the E2 baseline capacity vector. |
| Axis 5: component availability | `componentMode=1`, `componentMeanInterarrival=5.0540201005` h (set equal to the arrival gap mean so the kit feed is deliberately **binding**), at the E2 baseline capacity vector. |
| Study label | `e5-sensitivity-<axis>` |
| Seeds / orders | Each axis-level x 3 scenarios (baseline, Assembly+1, Test+1) x **n=30 seeds**, 600 orders (cheap, 600-order target is adequate for a sensitivity check, not the primary steady-state claim). Levels: axis1 2, axis2 2, axis3 1, axis4 2, axis5 1 = 8 axis-levels total x 3 scenarios x 30 seeds = **720 runs**. |
| Capacity vector | Per axis (see above); baseline/Assembly+1/Test+1 within each |
| Acceptance rule | No pass/fail; report paired mean/P90 effect with 95% CI per axis-level, explicitly labelled as exploratory relative to the primary E2 confirmation. State in the writeup which v1 sensitivities (arrival mean, service scale) were ONE axis in disguise and that E5's axes were chosen to not repeat that mistake. |
| Expected log count | 720 |
| **Director sign-off item 3** | 720 runs x 600 orders at ~5–10 s each is roughly 1–2 h — the single biggest E5 cost driver is doing 3 scenarios x 30 seeds per axis-level. If tight, drop to n=30 but only baseline + the single better-performing scenario from E2 (e.g. Assembly+1 only) per axis-level, halving the count to ~360–480 runs; state explicitly that this forgoes the three-way comparison at each axis-level. |

### E6 — M/M/1 (existing) and new M/M/c (c=3) verification

| | |
|---|---|
| Purpose | Extend the passed M/M/1 benchmark with an M/M/c, c=3 analytic check (Erlang C), to verify the multi-server queueing logic used everywhere c_j>1 in E2/E4. |
| Configuration | M/M/1: **0 new runs** — reuse v1's accepted `results/native-mm1-confirmation/`. M/M/c: one real exponential-service station with capacity 3, exponential arrivals; choose rho=0.7 (lambda=2.1/h, mu=1/h per server, c=3) so the Erlang-C queue is non-trivial; downstream stage durations zero (same pattern as v1's `MM1Verification`). |
| Study label | `e6-mmc-verification` |
| Seeds / orders | M/M/c pilot: seeds 1–10, 10,000 jobs/run. Confirmation: seeds 11–40 (30 fresh seeds), 10,000 jobs/run, only if pilot misses a target. |
| Capacity vector | c=3 at the single real stage; capacity irrelevant elsewhere (zero-duration stages) |
| Acceptance rule | Analytic Erlang-C targets at rho=0.7, c=3: P_wait (Erlang C) computed from rho/c/mu; Wq = P_wait/(c*mu*(1-rho)); W = Wq + 1/mu; Lq = lambda*Wq; L = lambda*W; utilization = rho. Each target inside its replication 95% CI, point error <=5%, relative half-width <=5% (same acceptance pattern as v1 M/M/1, §7 of v1 `experiments.md`). |
| Expected log count | Pilot 10; confirmation up to 30; total <=40 |

### Budget summary (for Director review)

| Family | New native runs | Rough wall time (serial) |
|---|---:|---:|
| E0 | 60 | ~10 min |
| E1 | <=40 | ~10 min |
| E2 | <=300 | 2.5–5 h (or <=180 at reduced cap, 1.5–3 h) |
| E3 | 0 | — |
| E4 | 280 | 0.8–1.5 h (or 165, 35–55 min at reduced grid) |
| E5 | 720 | 1–2 h (or ~420, 35–70 min at reduced scenario set) |
| E6 | <=40 | ~10 min |
| **Total** | **~1,440** (full) / **~845** (reduced) | **~5–9 h** (full) / **~2.5–4 h** (reduced) |

This is a portfolio project, not a deadline-bound homework submission, so the full plan is the
default; the reduced variants above are the explicit fallback if Taim or the Director wants a
shorter run. **Director sign-off required before launching E2, E4 and E5 at full size.**

## 4. Precision targets (restated, frozen)

- Relative half-width < 5% for every strictly-positive KPI mean (lead time, P90, WIP, throughput,
  utilization, Erlang-C targets).
- Absolute tolerances for near-zero paired effects (unchanged from v1 design): 0.5 h for mean or P90
  lead-time difference, 0.25 orders for mean WIP difference, 0.001 orders/h for throughput
  difference. Cost-per-unit precision derives from the throughput-difference CI (Fieller ratio, as
  in v1 `summarize_decision.py`).
- Relative precision is undefined at an exactly-zero or sign-changing mean difference; report the
  absolute-tolerance outcome instead, never a fabricated relative number.

## 5. Sample-size and stopping rule

1. Pilot n0 = 10 independent seeds for every family with a precision target (E1, E2, E6).
2. Compute each KPI's pilot relative half-width. If every target KPI is under 5% (or, for near-zero
   effects, under its absolute tolerance), stop at n0 = 10 for that family/scenario.
3. If not met, add a **fixed, independent, disjoint confirmation batch** (seeds start where the
   pilot ends, e.g. pilot 1–10 -> confirmation 11–40 or 11–50 per family's declared cap above).
   Do not pool the pilot with the confirmation; report both, labelled separately, exactly as v1 did.
4. No sequential/repeated peeking at the confirmation batch to decide on more runs: the confirmation
   batch size is fixed before it is launched and respected even if precision is still missed at the
   budget cap stated per experiment above (E2 cap 40/scenario, E4 no further runs, E5 fixed n=30,
   E6 cap 30). A missed target at the cap is reported as a missed target, not silently dropped.
5. Pre-specify this stopping rule in the run manifest before the confirmation batch launches.

## 6. Multiplicity plan

- **Primary confirmatory contrast** (the only claim entitled to a Holm-adjusted simultaneous
  reading): **Assembly+1 vs Test+1**, paired by seed, on (a) mean lead time and (b) P90 lead time,
  both from the **E2 confirmation** batch. Two tests, Holm-adjusted at family-wise alpha = 0.05
  (equivalent to Bonferroni for two tests: reject test 1 if p1 < 0.025, then test 2 at 0.05 if test 1
  rejected, else both at 0.025 — standard Holm step-down).
- **Everything else is exploratory**, reported with pointwise 95% CIs and explicitly labelled
  "pointwise, not simultaneous": the five-alternative-vs-baseline family (as in v1), E4's manifold
  outcomes, and every E5 sensitivity axis.
- The direct Assembly-vs-Test comparison (not vs baseline) is the one that answers the brief's
  central question; the five vs-baseline comparisons are retained for completeness and bottleneck
  narrative only.

## 7. Metric definitions for steady-state windows

- **Warm-up deletion.** Warm-up is a job-index cutoff W, estimated visually from a Welch plot of the
  replication-averaged lead time (and a WIP proxy) against job index, using the **pilot runs only**
  (`analysis/welch.py`, §B of the deliverable list). W is frozen in the run manifest before the
  confirmation batch is analyzed, and before confirmation data existed look at — i.e. the Welch read
  happens on pilot data, same as v1's unmet design intent, not on confirmation data.
- **Windowed lead-time cohort.** Jobs with index >= W only. Mean/P90 computed over those jobs'
  `(finish - release)` exactly as in v1.
- **Windowed throughput.** Completed jobs with index >= W, divided by `(final_time - release_time_of_job_W)`.
  This avoids diluting the rate estimate with the empty-start transient, unlike v1's
  `target / final_time` definition which explicitly included startup and drain.
- **Windowed time-weighted WIP.** Integral of in-system order count over `[release_time_of_job_W, final_time]`,
  divided by that window's length — computed from `P3_METRIC` integrals restricted to that time
  window, not from the job-level lead-time sum (that shortcut only holds for a fully-drained,
  zero-warm-up cohort, which the windowed case is not).
- **Windowed per-stage utilization/queue/starvation.** `busyArea`, `queueArea`,
  `starvedByUpstream` integrals restricted to `[release_time_of_job_W, final_time]`, each divided by
  the window length (utilization additionally divided by capacity).
- **Idle units.** `idleUnits[j]` integral (capacity_j minus busy_j) dt, windowed the same way; this
  is the per-resource-unit idle time, distinct from the v1 `empty_station_idle_fraction` identity
  metric for capacity-1 stages.
- **Cost per added station-hour.** Added station cost rate (currency/h, same illustrative rates as
  v1: Kitting 20, Assembly 35, Test 45, Quality 30, Handover 20) x windowed observation hours,
  divided by windowed observation hours = the rate itself; reported mainly as the numerator for the
  next metric.
- **Cost per order-lead-hour saved (windowed).** (added station cost rate x windowed hours) /
  (windowed completed orders x paired windowed mean-lead-time reduction), with a Fieller 95% interval
  under paired replication means, exactly as v1's `fieller_ratio` — but evaluated on the windowed
  (post-warm-up) cohort, not the whole finite campaign, so the denominator is a steady-state
  lead-hours-saved quantity, not a drain-timing artifact. Undefined if the paired throughput or
  lead-time-reduction CI includes zero or is non-positive — reported as undefined, not forced.

## 8. Pre-registered wording for E4 outcomes

Because (c, s) is not jointly identifiable from a single observed mean, the write-up commits now to
one of exactly two sentences depending on what E4 shows, decided before the runs:

- **If the Assembly+1-vs-Test+1 mean/P90 ranking is the same sign at all four manifold points:**
  "The Assembly-over-Test preference is stable across the explored (capacity, waiting-share)
  manifold that reproduces the observed end-to-end mean; it is not an artifact of one arbitrarily
  chosen calibration point."
- **If the ranking sign changes anywhere on the manifold:** "The Assembly-over-Test preference is
  NOT identifiable from the observed data alone: at least one (capacity, waiting-share) pair that
  reproduces the observed mean lead time reverses which station should get the added unit. The
  recommendation in this report is conditional on the specific (c, s) chosen for E2, and that choice
  is an assumption, not an inference from data."

No third option (e.g. softened language, selective reporting of only the convenient manifold points)
is permitted after seeing the results.

## 9. Regression test criteria (v2 defaults vs v1)

Implemented in `analysis/regress_vs_v1.py` (CLI takes two log directories). For every (seed,
scenario) pair in {1..10} x {0..5}:
- Per-job: `release`, `finish`, `lead` from `P3_ORDER` must match between the v2-default log and the
  matching v1 log to **max abs difference <= 1e-9 h**.
- Per-stage-record: `entered`, `started`, `finished`, `duration` from `P3_STAGE` (ignoring the new
  trailing `visit` field, which must be 0 for every record in a no-rework default run) must match to
  the same **1e-9 h** tolerance.
- Any mismatch, missing pair, or extra/missing job fails the whole regression with the offending
  seed/scenario/job named — no partial pass.

## 10. Cross-tool agreement criteria (Python replica vs native)

Where the v2 spec is fully deterministic given the CRN tapes (replay mode, and the first five
job-indexed draws logged by `P3_CRN` in finite mode), a from-scratch Python re-derivation of job
release/finish/lead times, per-stage entered/started/finished/duration, and the fitted-marginal
inverse-CDF draws (`inputMode=1`) must match the native log to **1e-9 h** per job and per stage
record. This is deterministic-tape agreement, not independent-random-stream distributional
agreement — the two are not conflated in the report. (Building the replica itself is out of scope
for this document; this section only states the acceptance bar it must clear when written.)

## 11. Figure list (Evidence Pack, numbered)

Per `lessons-from-grading.md` and `submission-checklist.md`, every experiment family gets a
parameter screenshot, a results screenshot, an animation screenshot, and (where blocks changed) a
flowchart screenshot. Numbering continues from v1's Figure 1–3 (source diagnostics, paired
confirmation effects, runtime replay) since those are retained unchanged.

| Figure | Content | Experiment |
|---|---|---|
| fig04_e0_regression_results | Console/analysis output showing 1e-9 h match, v2 vs v1, all seeds/scenarios | E0 |
| fig05_e1_params | Properties panel: capacities set to 50 at all five ResourcePools, meanInterarrival=5.0540201005 | E1 |
| fig06_e1_results | Bar chart of simulated vs observed mean/P90 per stage and end-to-end, console finished | E1 |
| fig07_e1_animation | 2D view with all five queue areas visibly empty (capacity never binds) | E1 |
| fig08_e2_params | Properties panel: baseline capacities [2,5,5,3,1], meanInterarrival=5.0540201005, target=5000, per-scenario +1 capacity | E2 |
| fig09_e2_flowchart | Full Process Modeling Library flowchart (unchanged structure, new parameter bindings visible) | E2 |
| fig10_e2_results_pilot | Welch plot (job-index trajectory) used to pick W, from `results/welch/` | E2 pilot / Part B |
| fig11_e2_results_confirmation | Utilization/queue bar charts, lead-time histograms, ResourcePool Inspect windows, console finished, for the windowed confirmation batch | E2 |
| fig12_e2_animation | 2D/3D view: queue areas and attractor counts matching [2,5,5,3,1] (+1 at swept stage) resource pool capacities | E2 |
| fig13_e3_contrast_table | Side-by-side table/plot of E2 (steady-state, observed rate) vs E3 (v1 scaled-down, read-only) headline numbers, explicitly labelled | E3 |
| fig14_e4_manifold | Plot of end-to-end mean vs serviceScale for each of the four capacity vectors, with the interpolated s* marked | E4 |
| fig15_e4_ranking_table | Table: (c_Assembly, c_Test, s*, Assembly+1 vs Test+1 mean/P90 ranking) for all four vectors | E4 |
| fig16_e5_params | Properties panels for each of the 8 axis-levels (capacities, serviceScale, inputMode, reworkProbability+maxRework, componentMode+componentMeanInterarrival) | E5 |
| fig17_e5_results | Paired-effect forest plot per axis-level (mean/P90 reduction, 95% CI), explicitly marked exploratory | E5 |
| fig18_e6_mmc_params | Properties panel: ResourcePool capacity=3, arrival/service rates for rho=0.7 | E6 |
| fig19_e6_mmc_results | Table of Erlang-C targets vs native CI, relative half-widths, pass/fail per metric | E6 |
| fig20_disclosure_timestamps | File-listing screenshot (or equivalent table) showing `results/diagnostics/first-truncated-sweep/` timestamps (16:49) vs `results/native/` pilot timestamps (16:59), 24 Oct 2026 | Disclosures |
| fig21_bottleneck_table | Baseline vs post-change (Assembly+1, Test+1) bottleneck table: utilization, upstream queue, starvedByUpstream per stage | E2 / E4 |

Seed and Stop option per row (for reproducibility of each screenshot): recorded in the run manifest
written alongside each family's logs (`P3_CONFIG` line is authoritative); Stop option is **Never**
for every family above — AnyLogic PLE's 50,000-agent cap is the bounded/unbounded signal, not a
model-side stop condition, consistent with the rest of the PMS team's standard.

## 12. Disclosures

- v1's `results/diagnostics/first-truncated-sweep/` directory contains **6 complete 600-order
  native finite logs**, timestamped **16:49 on 2026-10-24**, covering capacity scenarios 1–3 at
  seed 3 (plus baseline-equivalent seed-1/2/3 scenario-0 logs). These were not disclosed as a
  distinct experiment in v1's `design.md`/`experiments.md`/`report.md`.
- v1's main pilot logs in `results/native/` (top level, outside `diagnostics/`) are timestamped
  **16:59 on 2026-10-24** — ten minutes later than the diagnostics sweep.
- v1's `design.md` states "The finite amendment below preceded capacity-effect results." **That
  claim cannot be verified from file modification times alone.** File timestamps show the
  diagnostics sweep logs exist chronologically *before* the pilot logs, which is consistent with
  (but does not prove) the amendment having been decided first and the diagnostics sweep being an
  earlier, abandoned/truncated attempt at the same scenario grid — it is equally consistent with the
  amendment text having been written or edited after both batches existed. No git history, editor
  undo log, or independent timestamp on the `design.md` text itself was available to the agents who
  produced v1 to settle this. v2's report must state plainly that the sequencing claim is
  unverified, present both timestamp facts above, and not repeat v1's unqualified sentence.

## 13. Bottleneck evidence definition (restated for implementation)

A stage is bottleneck evidence only when all three hold together, computed over the same window
(finite whole-run for E0/E1/E3, Welch-windowed for E2/E4/E5):

1. **Utilization**: `busyArea / (capacity * window_h)` is the highest among the five stages.
2. **Upstream queue**: `queueArea / window_h` (mean queue immediately before that stage's service)
   is also elevated relative to the other stages — not required to be the single highest, but must
   be materially above zero and above its own post-change value.
3. **Starved downstream**: the next stage's `starvedByUpstream[j] / window_h` (time that downstream
   stage is idle with zero queue while stage j is busy or has a queue) is materially above zero,
   evidencing that the upstream stage is actually gating the downstream one — not the `1 -
   utilization` identity used in v1 for capacity-1 stages.

If utilization, queue and starvation do not agree, the report says **"ambiguous/moving bottleneck"**
rather than naming one. The required table (fig21) reports baseline vs the Assembly+1 and Test+1
post-change configurations side by side, explicitly answering whether the bottleneck moves (v1 found
it moves to Test after Assembly+1 — utilization 33.6% vs 58.8%, queue 0.042 vs 0.545 — and never said
so in the v1 report; v2 must say so if it recurs).
