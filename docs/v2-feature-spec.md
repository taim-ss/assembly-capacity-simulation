# P3 v2 feature spec (single source of truth for model, replica and analyzer)

SYNTHETIC. Time unit hours. `samples[r]` = {release, kitting, assembly, test, quality, handover} of clean row r (n = 195); stage k (0..4) duration uses `samples[r][k+1]`.
All v1 behaviour, stream seeds and log lines stay unchanged when every new parameter is at its default.

## New parameters (defaults reproduce v1 exactly)
| name | type | default | meaning |
|---|---|---|---|
| inputMode | int | 0 | 0 = empirical joint rows (v1). 1 = fitted marginals via inverse CDF on the per-stage uniform u = stageRng[k] (already drawn per job at release) |
| componentMode | int | 0 | 0 = ample stock: Combine passes immediately (zero kit wait). 1 = rate-limited components |
| componentMeanInterarrival | double | 5.0 | mean of exponential component interarrival (h), used when componentMode = 1 |
| maxRework | int | 5 | cap on rework loops per job |
| animationEnabled | boolean | false | gates the 3D animation hooks (no effect on logic) |
`reworkProbability` p in [0, 0.5] now allowed (v1 threw if != 0). `warmupHours` stays rejected (warm-up is applied in analysis, not in the model).

## New random streams (always consumed per job at release, independent of scenario/capacity)
- reworkRng = new java.util.Random(14001L + repSeed): at release, ALWAYS draw 2*maxRework uniforms r[0..2*maxRework-1] per job, in job order, after nothing else (own stream).
- componentRng = new java.util.Random(15001L + repSeed): component arrival process (componentMode = 1): interarrival_i = -ln(1-nextDouble()) * componentMeanInterarrival, one draw per component, first component at t = interarrival_1.
- v1 streams unchanged: arrival 11001, row 12001, quality 13001, stage k = 21001 + 1000k (+ repSeed).

## Geometric rework (finite mode only; replay mode never reworks)
- At release: u = j.qualityDraw (existing 13001 stream). N_j = (p <= 0) ? 0 : min(maxRework, floor(ln(max(u, 1e-300)) / ln(p))). So P(N >= k) = p^k.
- Rework loop = Test -> Assembly -> Test. After each Test visit: pass iff j.reworks >= N_j, otherwise j.reworks++ and the job goes back to Assembly.
- Visit durations for loop v (v = 1..N_j), scale = serviceScale: Assembly_v = scale * samples[floor(r[2(v-1)] * n)][2]; Test_v = scale * samples[floor(r[2(v-1)+1] * n)][3]. First visits use duration[1], duration[2] as in v1.
- Each Assembly/Test visit logs a P3_STAGE line with visit index v (first visit v = 0). `reworks` in P3_ORDER = N_j actually performed.

## Kitting with Combine (finite mode branch only)
- componentSource -> combine.in2; order agents (from chooseMode finite branch) -> combine.in1; combine output = the ORDER agent (component consumed, zero time), then kittingService as in v1. Kitting service duration unchanged (duration[0]).
- componentMode 0: every order finds a component at once (kit wait = 0): lead times identical to v1.
- componentMode 1: n-th order is matched with the n-th component FIFO. Kit wait = max(0, componentArrival_n - orderRelease_n) (unbounded wait queue). Lead time includes the kit wait.
- Log one line per job: `P3_KIT,seed,scenario,job,orderReleaseTime,kitReadyTime,kitWait`.

## Fitted marginals (inputMode = 1), u = stageRng[k] draw, scale = serviceScale
- k = 0 Kitting: empirical type-1 quantile of sorted kitting samples: sorted[min(n-1, floor(u*n))].
- k = 1 Assembly lognormal(shape 0.30435615867119564, loc 0, scale 19.265424718138505); k = 2 Test Weibull(c 1.697260159664356, loc 0, scale 19.912596407400642); k = 3 Quality lognormal(0.42675962852691607, 0, 7.957160535215475); k = 4 Handover lognormal(0.3613639262514972, 0, 2.7824739447886313). (Source: analysis/calibration/calibration_table.csv; re-read at generation time.)
- lognormal: scale * exp(shape * z(u)), z = standard normal quantile (Wichura AS241 PPND16 or equal-accuracy); Weibull: scale * (-ln(1-u))^(1/c). duration = scale_factor * that.
- Dependence between stages is dropped (observed Spearman ~ 0, see results/calibration/step_spearman_correlations.csv). The row index is still drawn from rowRng (consumption unchanged).

## Evidence metrics (per stage j, integrals over the whole run, written once at the sink like v1)
- starvedByUpstream[j]: time with busy_j == 0 AND queued_j == 0 AND upstreamQueued_j > 0, where upstreamQueued_j = queued[j-1] (j >= 1). j = 0 has no upstream: 0.
- idleUnits[j]: integral of (capacity_j - busy_j) dt.
- blockedFraction is not applicable (infinite buffers) and must be documented as such.

## Log schema (comma separated, appended fields only)
- `P3_CONFIG,seed,scenario,replay,target,interarrival,scale,joint,rework,warmup,capK,capA,capT,capQ,capH,inputMode,componentMode,componentMeanInterarrival,maxRework` (4 new trailing fields)
- `P3_STAGE,seed,scenario,job,stage,entered,started,finished,duration,visit` (new trailing visit)
- `P3_METRIC,seed,scenario,stage,time,areaBusy,areaQueue,emptyIdle,busy,queued,starvedByUpstream,idleUnits` (2 new trailing)
- `P3_KIT,...` new line type (finite mode only); P3_ORDER, P3_CRN, P3_IN, P3_STATE, P3_DONE, P3_META, P3_VERIFICATION_MODE unchanged.

## 3D animation hook contract (logic is unaffected; bodies empty when animationEnabled = false)
Main functions called from the existing stage hooks: `animRelease(Job j)` (Source onExit), `animStageEnter(Job j,int stage)` (service onEnter), `animStageStart(Job j,int stage)` (onEnterDelay), `animStageFinish(Job j,int stage)` (onExit), `animDone(Job j)` (Sink onEnter). Hooks only move/colour presentation objects; they must not read or write any logic variable, draw random numbers, or change time.
