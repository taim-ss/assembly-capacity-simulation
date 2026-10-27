# Source and verification register

**SYNTHETIC DATA â€” P3 learning project.** Research register checked 23 October; native evidence reconciled 24 October 2026. A documentation source supports an API/design claim; it does not prove that the local model compiled or ran. Native logs and their analysis provide separate execution evidence. No repository code was copied.

## Local governing inputs

| Source | How it is used |
|---|---|
| `../../prompts/P3-anylogic-assembly-flow.md` from project root | Numbered Steps1â€“8 define scope; optional Step9 deferred. Source location is PMS `prompts/`, outside the portable project. |
| PMS `knowledge/portfolio-playbook.md`, section0 | Synthetic labels, authorship tiers, local-only work, no commercial/company claims. |
| PMS `knowledge/kpi-definitions.md`, `submission-checklist.md`, `lessons-from-grading.md` | Queue/utilization/lead-time outputs, parameter/result/animation/flowchart screenshots and fresh extraction. The 70â€“90% utilization heuristic is not a mathematical stability proof. |
| PMS `knowledge/worked-example-bank-office.md`, `pml-block-reference.md` | Experiment table format and PML starting pattern; this portfolio's numbered requirements determine its actual experiment set. |
| PMS `knowledge/research-web-2026-10-23.md`, sections3.4,5,6,7 | Initial assembly, CRN, precision and validation research; original V/S/U labels are preserved rather than promoted into runtime claims. |
| PMS `knowledge/research-github-2026-10-23.md`, joe8606 row and section3 | Packaging examples and verification checklist; inspiration only. |
| Source KPI-case `README.md`, generator and workbook sheet `LeadTime_Analysis` | Synthetic source with200 records and five planted errors. Crucial interpretation: completion-stamp differences include waiting. Independent recalculation and source hashes are in calibration outputs. Source files remain unchanged. |

The source data live under `Documents/job-search-ops/applications/2026-10-21-career-packs/evidence/inventory-leadtime-kpi-case/`. This provenance path is documentation, not a runtime absolute-path dependency; packaged execution must consume local clean input copies/parameters.

## Primary technical sources checked this session

| Source | Current check and supported use | Limits |
|---|---|---|
| [AnyLogic Parameter Variation](https://anylogic.help/anylogic/experiments/parameter-variation.html) | Search-index article body read: top-level parameter range/freeform variation, fixed/variable replication options, multi-core execution and run actions. | Direct open returned403. Verify corresponding editor fields in installed8.9.10 before a native run. Explicit `repSeed` sweep is a design choice, not a claim that nested engine RNG automatically aligns jobs. |
| [AnyLogic Service](https://anylogic.help/library-reference-guides/process-modeling-library/service.html) | Search-index article body read: Service is equivalent to Seize/Delay/Release for a resource-held delay. | Direct open403; local implementation and event callbacks remain to be tested. |
| [AnyLogic Queue](https://anylogic.help/library-reference-guides/process-modeling-library/queue.html) | Search-index documentation checked for queue/time statistics. | Direct open403; use time integrals or confirm `statsSize.mean()` in installed help. Do not confuse event-sampled counts with time-weighted means. |
| [AnyLogic ResourcePool](https://anylogic.help/library-reference-guides/process-modeling-library/resourcepool.html) and [resource functions](https://www.anylogic.help/library-reference-guides/process-modeling-library/resource-api.html) | Official search-index text: utilization statistics are continuous-time busy-unit statistics; per-unit utilization API exists. | Scheduled availability changes denominators; this design assumes no shifts. Exact local readout and reset timing require native testing. |
| [AnyLogic Assembler](https://anylogic.help/library-reference-guides/process-modeling-library/assembler.html) | Official search-index text describes assembly from multiple input agents and processing/resources. | Direct open403. The implemented model uses one logical order token and a Kitting Service; no Assembler/component synchronization or BOM is claimed. |
| [AnyLogic reproducibility](https://anylogic.help/anylogic/stochastic/reproducible.html) | Official search-index body read: mutable static state, RNG reset and iteration settings affect reproducibility. | Fixed seed alone does not establish scenario CRN; job-index tape alignment must be checked. |
| [AnyLogic downloads](https://www.anylogic.com/downloads/) | Opened directly: official current version8.9.10 released24 September2026, PLE for evaluation/personal use, edition limits. | The installed executable/version and long-run exemption are separate runtime checks. No export/publishing action authorized. |
| [Stanford EE384X queueing handout](https://web.stanford.edu/class/ee384x/EE384X/handouts/H10.pdf), M/M/1 section | Opened24-page primary university teaching PDF. Poisson arrivals, independent exponential services, stability and steady-state relations support the analytic verification case. | Formula use is analytic; it is not evidence of AnyLogic reproduction. |

For exponential sampling the project uses explicit inverse transform `-mean*log1p(-u)` with u from `java.util.Random`, avoiding ambiguity between mean and rate conventions. The earlier research note's blanket claim about Source `exponential(10)` is not applied blindly: Source rate/interarrival mode must be visible in evidence.

## Validation literature and external examples

- [Sargent, Verification and Validation of Simulation Models, WSC2005](https://www.informs-sim.org/wsc05papers/014.pdf) and [Sargent/Goldsman/Yaacoub operational validation tutorial, WSC2016](https://www.informs-sim.org/wsc16papers/016.pdf): identified in the local research register. Retrieval failed/inaccessible or timed out this session; no new full-text verification claimed. Used as pointers to the purpose/accuracy-first validation principle, implemented here as an explicit project contract.
- [joe8606 job-shop example](https://github.com/joe8606/job-shop-simulation-anylogic-python): local research had inspected it; this session uses its reported CSV/figures/canvas/GIF organization only. Repository current state/license was not rechecked, and no source code was reused. Its utilization threshold is not adopted as proof of the bottleneck.
- [AnyLogic editions help](https://anylogic.help/anylogic/ui/editions.html): PML model-time exemption is an item to check in the installed application. A search statement about exemption is not proof that this project's experiment passes a5-hour boundary. The50,000 dynamically-created-agent limitation also needs its actual failure semantics recorded if reached; cumulative creations and live WIP are distinct counters.

## Native evidence and claims still outside scope

Actual native replay now completes all 195 clean orders and matches source timestamps within 3.64e-12 h. The six-scenario, ten-seed finite pilot produced 60 complete native exports and paired intervals; its native-derived plots are Python visualizations of those logs. The separate final confirmation, benchmark, sensitivity, visual and fresh-extract evidence is indexed in `docs/evidence-pack.md` and the report, with raw-file hashes in the corresponding analysis JSON. The canonical native model is `model/P3_Assembly_Flow.alp`; older generated drafts are not interchangeable runtime evidence.

The v2 decision uses finite post-cutoff performance with a frozen500-job cutoff and a disclosed final drain. Native M/M/1 and M/M/3 benchmarks are separate from source-process accuracy. An independently implemented Python event simulator agrees with native order/visit/kit timestamps on the declared deterministic tapes. Both empirical and fitted input modes, Combine synchronization, independent component supply and geometric rework are implemented and tested. Detailed component BOM quantities and physical replenishment transport are not modeled. Taim's own editor rebuild is a separate unverified hands-on skill demonstration; agent-produced native evidence does not establish it.

Historical service times, resource counts, rework probabilities, costs and an Airbus staffing recommendation are not identifiable from synthetic elapsed timestamps. Passing native queueing checks cannot repair that identification boundary. Black or blank captures are rejected; runtime screenshots do not prove a full editor canvas or resource inspector settings. Nothing was submitted or published.
