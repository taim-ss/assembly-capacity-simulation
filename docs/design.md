# P3 v2: sensor-module production and capacity

**SYNTHETIC. Educational AnyLogic PLE model. Tier B agent-produced work.**

## Story and decision

A hypothetical manufacturer produces industrial temperature-sensor modules. Each work order needs a housing, circuit board and sensing parts prepared, assembled, functionally tested, checked for quality and packed for shipment. Test failures return to Assembly for repair and then repeat Test.

The manager can add one processing resource. **Compare baseline, Assembly +1 and Test +1:** which reduces work-order completion time and waiting more? The product story explains the process; the synthetic timestamps do not become measured electronics-factory inputs.

| Model stage | Sensor-module story | What to observe |
|---|---|---|
| Kitting | Prepare the required parts | Orders waiting for a kit or a free preparation station |
| Assembly | Fit the board/sensor into its housing | Waiting work orders and occupied assembly resources |
| Test | Check that the assembled module functions | Test queues, occupied rigs and repeat visits |
| Quality | Inspect and approve the tested module | Inspection waiting and resource use |
| Handover | Pack the approved module | Packing work before completion |
| Sink | Ship the completed work order | Final completions and total lead time |

One moving token is one **work order**, not a claim about a physical single-unit batch size. Parts, equipment and cartons are explanatory graphics. The process does not simulate individual screws, an electronic circuit, test measurements or a detailed bill of materials.

## Process logic

Finite-mode orders wait in an unlimited FIFO order buffer; independent component tokens wait in a separate unlimited FIFO component buffer. Combine consumes one component token and keeps the order token. That component token represents an available kit, not separate housing/board/sensor inventories. Mode 0 supplies one kit immediately per order, adding zero kit wait. Mode 1 generates independent exponential supply, so missing kits can delay preparation.

Each of the five Service blocks seizes one unit from its corresponding static ResourcePool, holds it for the job duration and releases it. Waiting queues are unlimited. Test failures revisit Assembly and Test. Sink records final completion and checks complete drain.

| Blocks | Purpose |
|---|---|
| source, chooseMode | Create work orders; select deterministic replay or finite queueing |
| componentSource, componentBuffer, orderBuffer, combine | One-kit/one-order synchronization with unlimited arrival buffers |
| Five *Service and five *Pool objects | Capacity-constrained FCFS processing |
| Five *Elapsed Delay objects | Unlimited-concurrency source-timestamp replay |
| passTest | Continue to Quality or return to Assembly for assigned rework visits |
| sink | Final completion, conservation, metrics and terminal P3_DONE |

The canonical process has 3 agent types, 23 embedded PML objects and 19 connections. The two input Queue objects correct the native forced-push error found when independent arrivals fed Combine directly.

## Inputs and uncertainty

There are 200 synthetic source records, 195 retained. Three missing timestamps and two negative-duration records are excluded with IDs/reasons in calibration outputs. Mean end-to-end elapsed time is 55.4603 hours. Differences between completion timestamps contain waiting; measured service starts, staffing, shifts, costs and failure rates are absent.

Replay preserves original releases and durations to verify ingestion. Finite mode assumes those elapsed durations are service proxies. Whole-row empirical bootstrap preserves within-order dependence. Fitted marginal mode uses empirical Kitting, lognormal Assembly/Quality/Handover and Weibull Test. The fit-selection subset helped choose families and is not independent final validation.

E2 matches the observed 5.0540-hour mean release gap using an assumed exponential arrival process. The source generator placed a fixed count of releases uniformly over 42 days; it was not Poisson. Baseline capacities [2,5,5,3,1] are assumptions. Different capacity/service-scale combinations can reproduce one observed mean, so calibration alone cannot identify real capacities or establish a staffing recommendation.

## Randomness and measurement

Separate java.util.Random streams cover arrivals, rows, stage uniforms, rework counts/durations and component supply. Job-indexed service/rework tapes are drawn before scenario-specific waiting. Baseline and alternatives share the same tapes. Rework counts are geometric, truncated at maxRework (default 5), with probability 0..0.5. Repeat Assembly/Test durations use pre-drawn visit inputs. Presentation draws no random numbers.

Record order release/completion, stage-visit entry/start/finish/duration, kit readiness, busy/queue integrals and idle units. The analyzer reconciles transition counters with actual order events and checks visit chains, capacities, terminal drain and independently reconstructed integrals.

Warm-up cutoff W=500 was frozen from pilot evidence before confirmation. Lead-time cohorts use jobs 500 onward; WIP includes all orders overlapping the window; station integrals are clipped exactly. Final drain remains, so these are finite post-cutoff approximations, not proof of an uncensored steady state. Low-capacity and critically loaded supply cases stay explicitly finite-case results.

The starvation proxy measures an empty downstream stage while its immediately upstream queue is nonempty. It is distinct from 1-utilization. Unlimited buffers imply no blocking. Name a bottleneck only when utilization, queues and downstream starvation align; otherwise report ambiguity.

## Presentation and separation

The editor has two spatially separated areas: the presentation at the left, and PML blocks, variables and connectors at x=2300 and beyond. Logic elements are hidden from the runtime dashboard. The runtime places the story, active scenario, KPIs and legend above a real Window3D control; world geometry is rendered only in 3D. The flowchart does not overlap the factory scene.

Recognizable kit/board/housing/carton details show a work order's progress. Normal direction arrows connect stations; the red route explains failed-test return to Assembly and retesting. Separate display lists and wall-clock interpolation animate travel between actual process states. Visual travel adds no processing delay, simulation event or routing decision; the token's displayed travel is not measured physical transport. Fast playback can shorten or interrupt a visible transition when another real event occurs.

Display limits are 6 resource units and 8 waiting tokens per stage; overflow text reports additional waiting orders. The redesigned native scene was inspected after Taim approved running and recording it; results/visual-final contains authentic media and its specific acceptance scope.
