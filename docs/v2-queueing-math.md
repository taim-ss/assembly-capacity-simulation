# P3 v2 — queueing math

SYNTHETIC educational project. Elapsed durations include waiting (per `docs/design.md`); treating
them as "service times" below is an explicit, stated assumption, not a validated service-time
model. All numbers in this file are either (a) deterministic arithmetic on the stated inputs, or
(b) explicitly labelled approximations / bootstrap estimates that AnyLogic native runs must
confirm. Method follows `knowledge/resource-sizing-method.md`; KPI reading follows
`knowledge/kpi-definitions.md`.

Stage order and index: 0 Kitting, 1 Assembly, 2 Test, 3 Quality, 4 Handover.

## 0. Inputs

| Stage | Mean service `m_j` (h) | Elapsed CV `cs_j` | `cs_j^2` |
|---|---|---|---|
| Kitting | 5.9069 | 0.3494 | 0.1221 |
| Assembly | 20.1762 | 0.3101 | 0.0961 |
| Test | 17.6735 | 0.6302 | 0.3971 |
| Quality | 8.7367 | 0.4671 | 0.2182 |
| Handover | 2.9670 | 0.3647 | 0.1330 |

`cs_j = sd/mean` of the 195 clean `*_h` columns in `analysis/calibration/clean_orders.csv`
(population sd). Arrival gaps: 199 gaps, mean **5.0540201005 h**, sd 5.1228 h, so
`ca = 1.0136`, `ca^2 = 1.0274` — close enough to 1 that the exponential/Poisson arrival
approximation used below is defensible, but the raw generator is "fixed count of uniformly
positioned releases in 42 days" per `design.md`, not a true Poisson process. **Flag:** `ca`
is itself a point estimate off 199 gaps; treat Erlang-C/Kingman outputs as order-of-magnitude.

Observed arrival rate: `lambda_obs = 1/5.0540201005 = 0.19786229 /h`.
Assumed decision-experiment rate (design.md's stable baseline): `lambda_assumed = 1/30 = 0.03333 /h`.

## 1. Offered load `A_j = lambda * v_j * m_j`

### 1a. At the assumed rate (30 h mean interarrival, all `v_j=1`, capacity 1 baseline)

| Stage | A_j = rho_j (c=1) |
|---|---|
| Kitting | 0.1969 |
| Assembly | 0.6725 |
| Test | 0.5891 |
| Quality | 0.2912 |
| Handover | 0.0989 |

Matches `design.md`'s stated `[0.197, 0.673, 0.589, 0.291, 0.099]`. All stages under 0.9 at
capacity 1 — this is why the assumed rate was chosen as the stable +1 baseline (H1 fix note).

### 1b. At the observed rate (lambda_obs = 0.19786 /h, `v_j=1`)

| Stage | A_j = lambda_obs·m_j | min servers `ceil(A_j)` | practical `ceil(A_j/0.85)` |
|---|---|---|---|
| Kitting | 1.1688 | 2 | **2** |
| Assembly | 3.9921 | 4 | **5** |
| Test | 3.4969 | 4 | **5** |
| Quality | 1.7287 | 2 | **3** |
| Handover | 0.5871 | 1 | **1** |

Gives `c = [2,5,5,3,1]`, matching the brief's stated vector — this is the H1 "fix the observed
rate" sizing, using the 0.85-utilisation practical-server rule from
`resource-sizing-method.md`. All-capacity-1 at the observed rate is overloaded at Assembly,
Test and Quality (`A_j>1`), confirming `design.md`'s "overload demonstration" framing of H1.

## 2. Utilisation at `c=[2,5,5,3,1]` and the +1 variants (observed rate)

`rho_j = A_j/c_j`.

| Stage | c (base) | rho (base) | c+1 | rho (+1) |
|---|---|---|---|---|
| Kitting | 2 | 0.5844 | 3 | 0.3896 |
| Assembly | 5 | 0.7984 | 6 | 0.6654 |
| Test | 5 | 0.6994 | 6 | 0.5828 |
| Quality | 3 | 0.5762 | 4 | 0.4322 |
| Handover | 1 | 0.5871 | 2 | 0.2935 |

Assembly is the base-case bottleneck (highest rho, 0.798), Test second (0.699). Both are under
0.9, so `c=[2,5,5,3,1]` is a stable baseline per the 0.7–0.9 target band — Assembly sits inside
the band, the rest are below it (over-provisioned relative to the 0.85 target, by construction
of the `ceil(A/0.85)` rule rounding up). **Taim should confirm these with
`resourcePool.statsUtilization()` once the v2 native model runs** — these are deterministic
Erlang inputs, not simulated outputs; simulated utilisation will show sampling variance around
these numbers.

## 3. Erlang-C (M/M/c) indicative mean wait — explicitly an approximation

**This is NOT the real model.** Elapsed durations are not exponential (Assembly `cs=0.31`, Test
`cs=0.63` — both far from the exponential's `cs=1`), and the arrival process is a fixed-count
uniform release schedule, not Poisson (`ca=1.01`, close by luck of this one dataset, not by
mechanism). Erlang-C/M/M/c below is an order-of-magnitude sanity check on the capacity choice,
not a predictor of simulated Wq.

`C(c,a)` = Erlang-C formula, `a=A_j`; `Wq = C(c,a)·m_j/(c-a)`; `W = Wq + m_j`.

| Stage | c | Wq (h) | W (h) | c+1 | Wq+1 (h) | W+1 (h) |
|---|---|---|---|---|---|---|
| Kitting | 2 | 3.063 | 8.970 | 3 | 0.428 | 6.335 |
| Assembly | 5 | 11.032 | 31.208 | 6 | 2.842 | 23.018 |
| Test | 5 | 4.431 | 22.105 | 6 | 1.249 | 18.923 |
| Quality | 3 | 2.232 | 10.969 | 4 | 0.439 | 9.176 |
| Handover | 1 | 4.218 | 7.185 | 2 | 0.280 | 3.247 |
| **Sum** | | **24.976** | **80.436** | | | |

### 3a. Kingman/Allen-Cunneen correction using the observed CVs

`Wq_AC ≈ Wq_MMc · (ca^2+cs_j^2)/2` — the standard G/G/c correction that uses the actual
coefficient-of-variation instead of assuming exponential (`ca^2=cs^2=1`).

| Stage | cs_j^2 | Wq (M/M/c) | Wq (Allen-Cunneen) |
|---|---|---|---|
| Kitting | 0.1221 | 3.063 | 1.761 |
| Assembly | 0.0961 | 11.032 | 6.197 |
| Test | 0.3971 | 4.431 | 3.156 |
| Quality | 0.2182 | 2.232 | 1.390 |
| Handover | 0.1330 | 4.218 | 2.447 |
| **Sum** | | **24.976** | **14.951** |

Both are **indicative only** — AnyLogic's own FCFS multi-server simulation at `c=[2,5,5,3,1]`
is the number that counts; these bracket a plausible range (15–25 h of total expected queueing)
against which the simulated `queue.size()`/wait-time histograms can be sanity-checked.

## 4. Expected simulated end-to-end lead time vs the observed 55.46 h — the double-counting

- Sum of stage means (pure service, zero queueing) = 5.9069+20.1762+17.6735+8.7367+2.9670 =
  **55.4603 h** — this equals the observed mean end-to-end elapsed time (55.46 h) *by
  construction*, because the "service times" fed into the finite model **are** the historical
  elapsed durations, which already include whatever waiting happened in the source process.
- Adding Erlang-C queueing on top at `c=[2,5,5,3,1]`: expected `E[end-to-end] = sum(m_j) +
  sum(Wq_j) ≈ 55.46 + 24.98 = 80.44 h` (M/M/c), or `55.46 + 14.95 = 70.41 h` (Allen-Cunneen).
- **Both exceed the observed 55.46 h by 15–25 h.** That gap is the quantified double-counting:
  the finite capacity-constrained model adds a second layer of queueing delay on top of
  durations that already embed the source system's own (unmeasured) queueing. H1's fix does not
  remove the double-counting; it only makes the added layer stable/interpretable. **Report this
  gap explicitly in the submission** — a v2 finite run showing mean lead time near 80 h (not
  55 h) is expected behaviour, not a bug, given this input choice.

## 5. No-wait limit (c → ∞): per-stage and end-to-end sampling distribution

As capacity → ∞ at every stage, the finite model's per-job elapsed time at stage j converges to
a draw from the empirical distribution of that stage's historical duration (no queueing at all),
and total lead time converges to resampling whole clean rows (preserving within-order
dependence, since `jointBootstrap=true` by default — see feature spec). This is the right
baseline to bootstrap for E1 tolerance-setting: it is what the model produces with capacity
non-binding, so any departure from it when running `c=[2,5,5,3,1]` is attributable to queueing,
not to resampling noise.

Bootstrap method: resample `n` orders with replacement from the 195 clean rows (row-joint, i.e.
whole rows, not independent per-stage columns), compute the resample's mean/P90 per stage and
for the end-to-end total, repeat 2,000 times, take the standard deviation of the resample
statistic as its standard error (SE).

| Metric | Pop. mean/P90 | SE (n=600) | SE (n=5000) |
|---|---|---|---|
| Kitting mean | 5.9069 | 0.0853 | 0.0291 |
| Kitting P90 | 9.0167 | 0.1974 | 0.0651 |
| Assembly mean | 20.1762 | 0.2606 | 0.0865 |
| Assembly P90 | 27.3667 | 0.9286 | 0.2549 |
| Test mean | 17.6735 | 0.4496 | 0.1548 |
| Test P90 | 33.8667 | 0.9961 | 0.2539 |
| Quality mean | 8.7367 | 0.1661 | 0.0563 |
| Quality P90 | 13.5133 | 0.3837 | 0.1380 |
| Handover mean | 2.9670 | 0.0446 | 0.0154 |
| Handover P90 | 4.4267 | 0.1164 | 0.0643 |
| **End-to-end mean** | **55.4603** | **0.5775** | **0.2002** |
| **End-to-end P90** | **73.8633** | **1.6463** | **0.8465** |

**E1 tolerance recommendation:** set the no-wait-limit tolerance at roughly `2×SE` for the
campaign size actually run. At n=600 (the v1/v2 finite campaign size): end-to-end mean tolerance
≈ **±1.16 h**, end-to-end P90 tolerance ≈ **±3.29 h**. At n=5000 (larger confirmatory run):
≈ **±0.40 h** mean, **±1.69 h** P90. Going from 600 to 5000 orders shrinks SE by
`sqrt(600/5000)=0.346`, i.e. roughly a 3x tightening, consistent with `SE ∝ 1/sqrt(n)`.
Script: `analysis/python_replica/bootstrap_no_wait.py` (reproduces the table above;
`B=2000` resamples, `random.seed` fixed for reproducibility — this is a Python-side
descriptive bootstrap, independent of the java.util.Random streams used inside the model).

## 6. Analytic capacity bound: `min_j c_j/m_j` vs `lambda`

Stability requires `lambda < min_j (c_j/v_j)/m_j`. At `v_j=1`:

| Stage | c_j/m_j (base) | (c_j+1)/m_j (+1) |
|---|---|---|
| Kitting | 0.3386 | 0.5079 |
| Assembly | 0.2478 | 0.2974 |
| Test | 0.2829 | 0.3395 |
| Quality | 0.3434 | 0.4578 |
| Handover | 0.3370 | 0.6741 |

`min_j c_j/m_j = 0.2478` (Assembly, base), vs `lambda_obs = 0.1979`. **Feasible**:
`lambda_obs < bound` with margin `0.2478/0.1979 ≈ 1.25×`, i.e. the system can carry about 25%
more throughput than the observed rate before Assembly's base capacity saturates. Any +1
variant raises its own stage's bound but does not change the others'; Assembly stays the
tightest bound unless Assembly itself gets the extra unit (then Test, bound 0.2829, becomes
tightest).

## 7. Offered load with geometric rework (`p=0.05, 0.10`)

Per the v2 feature spec, rework is a Test→Assembly→Test loop; `v_Assembly = v_Test = 1/(1-p)`,
other stages unchanged (`v=1`). Offered load at the observed rate:

| p | v (Assembly, Test) | A_Assembly | A_Test | c85 (Assembly) | c85 (Test) | rho@c=5 (Assembly) | rho@c=5 (Test) |
|---|---|---|---|---|---|---|---|
| 0.00 (baseline) | 1.0000 | 3.9921 | 3.4969 | 5 | 5 | 0.7984 | 0.6994 |
| 0.05 | 1.0526 | 4.2022 | 3.6810 | 5 | 5 | 0.8404 | 0.7362 |
| 0.10 | 1.1111 | 4.4357 | 3.8855 | **6** | 5 | 0.8871 | 0.7771 |

Kitting, Quality, Handover are unaffected (`v=1` there; A unchanged at 1.1688/1.7287/0.5871,
c85 unchanged at 2/3/1). **At p=0.10 Assembly's practical-server count rises from 5 to 6** —
`c=[2,5,5,3,1]` stops being adequate (utilisation would hit 0.887 at c=5, inside but near the
top of the 0.7–0.9 band; `ceil(4.4357/0.85)=6` is the 0.85-target call). At p=0.05 both reworked
stages stay within `c=[2,5,5,3,1]`'s original sizing but Assembly's utilisation rises from 0.798
to 0.840 — worth flagging as "rework pushes Assembly toward the top of its target band" even
before resizing.

## 8. E4 identifiability stability table: `(c, serviceScale)` pairs with all `rho_j<0.95`

`serviceScale s` multiplies every stage mean (`m_j → s·m_j`), so `rho_j(s) = s·A_j(obs,s=1)/c_j`.
Max feasible `s` for a capacity vector = `min_j 0.95·c_j/A_j`.

| Candidate `c` | s_max (all rho<0.95) | rho at s=1 | Stable at s=1? |
|---|---|---|---|
| `[2,4,4,2,1]` (ceil-min) | 0.952 | K0.584 / A0.998 / T0.874 / Q0.864 / H0.587 | **No** (Assembly 0.998) |
| `[2,5,5,3,1]` (base, c85) | 1.190 | K0.584 / A0.798 / T0.699 / Q0.576 / H0.587 | Yes |
| `[3,5,5,3,1]` (+1 Kitting) | 1.190 | K0.390 / A0.798 / T0.699 / Q0.576 / H0.587 | Yes |
| `[2,6,5,3,1]` (+1 Assembly) | 1.358 | K0.584 / A0.665 / T0.699 / Q0.576 / H0.587 | Yes |
| `[2,5,6,3,1]` (+1 Test) | 1.190 | K0.584 / A0.798 / T0.583 / Q0.576 / H0.587 | Yes |
| `[2,5,5,4,1]` (+1 Quality) | 1.190 | K0.584 / A0.798 / T0.699 / Q0.432 / H0.587 | Yes |
| `[2,5,5,3,2]` (+1 Handover) | 1.190 | K0.584 / A0.798 / T0.699 / Q0.576 / H0.294 | Yes |
| `[3,6,6,4,2]` (generous) | 1.428 | all ≤0.665 | Yes |

For the E4 identifiability study, pick `(c, s)` pairs along this table's feasible region —
e.g. `([2,5,5,3,1], s∈{0.85,1.0,1.15})` stays stable throughout (`s_max=1.19`), giving three
genuinely different operating points (not the H2-flagged "same point rescaled" problem) without
crossing into instability. Do not pair `[2,4,4,2,1]` with `s≥0.95` — Assembly saturates.

## 9. M/M/c verification design (`c=3`, Kitting as the server) — extends `MM1Verification`

Following the existing `MM1Verification` pattern (`lambda=0.5/h, mu=1/h, c=1` single exponential
station, zero-duration downstream) but for `c=3`, so the native model can be run with
`capKitting=3` and all other capacities at a large number (effectively unconstrained) or the
downstream stages zeroed as `MM1Verification` already does for its single stage:

| Parameter | Value |
|---|---|
| `lambda` | 1.0 /h |
| `mu` | 0.4 /h (exponential service, mean 2.5 h) |
| `c` (capKitting) | 3 |
| `a = lambda/mu` | 2.5 Erlangs |
| **Erlang-C `C(3,2.5)`** | **0.702247** |
| rho (`a/c`) | 0.833333 |
| **Wq** | **3.511236 h** |
| **W** | **6.011236 h** |
| **Lq** | **3.511236** |
| **L** | **6.011236** |

Accuracy criteria (mirroring `design.md`'s M/M/1 benchmark table): point estimate error ≤5% on
each of `rho, Wq, W, Lq, L` against the native run's replication mean, CI half-width/mean <5%
on positive KPIs (same precision rule as the M/M/1 check), pilot n0=10 then confirm per the
existing precision protocol.

## 10. Summary — what native AnyLogic must confirm

| # | Deterministic/analytic here | Native run must produce |
|---|---|---|
| 1 | `A_j`, `c_min`, `c=[2,5,5,3,1]` (arithmetic, exact) | `resourcePool.statsUtilization()` per stage ≈ Section 2's rho |
| 2 | Erlang-C/Kingman Wq (indicative) | simulated queue wait histograms — expect simulated totals near 70–80 h, not near 55 h |
| 3 | No-wait-limit bootstrap SEs | a capacity-unconstrained (very large c) run should land within ~2×SE of the Section 5 table |
| 4 | Capacity bound feasibility | throughput should not be bounded below `lambda_obs` in a stable run |
| 5 | Rework offered-load shift | a p=0.10 run should show Assembly utilisation trending toward 0.887 at c=5, recommend c=6 |
| 6 | E4 stability table | chosen `(c,s)` pairs should show rho<0.95 at every stage once simulated |
| 7 | M/M/3 verification targets | native `MM1Verification`-style run at `capKitting=3` should match Wq/W/Lq/L within the stated 5% criteria |
