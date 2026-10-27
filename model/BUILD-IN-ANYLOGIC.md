# P3 v2 model and parameter reference

**SYNTHETIC educational PLE project; agent-produced under Taim's direction.**

Taim approved the revised sensor-module native run and recording. The final demonstration completed80/80orders; the accepted actual scene/clip and provenance are in results/visual-final.

The portable model embeds195clean source rows. It needs no workbook connection, external database or 3D assets. Model time is hours. Keep this canonical file separate from private native test copies.

## Modes and blocks

`Simulation` defaults to deterministic source replay through five unlimited Delay blocks. It checks the original release/stage/finish timestamps without resource queues. Finite mode uses Source â†’ chooseMode â†’ orderBuffer â†’ Combine â†’ Kitting Service â†’ Assembly Service â†’ Test Service â†’ passTest â†’ Quality Service â†’ Handover Service â†’ Sink. A separate component Source and unlimited componentBuffer feed Combine's second port. Combine retains the order and consumes one component. Both input buffers are required for independent arrivals.

Test failures return to Assembly and then Test again. There are five static ResourcePools and unlimited Service waiting queues. All complete runs end with P3_DONE and released=completed=target. Launcher exit or a stopped clock is not proof of completion.

| Parameter | Meaning / supported values |
|---|---|
| replayMode | true: replay all195original records; false: finite queueing experiment |
| repSeed | Job-indexed replication seed shared by paired alternatives |
| scenarioIndex | 0baseline; 1Kitting+1; 2Assembly+1; 3Test+1; 4Quality+1; 5Handover+1 |
| scenarioOrders | Finite target1..10000; default600 |
| meanInterarrival | Positive exponential mean in hours; default30; E2 uses5.0540201005 |
| capKitting/Assembly/Test/Quality/Handover | Positive baseline capacities; selected scenario adds one at one stage |
| serviceScale | Positive multiplier on assumed service proxies; default1 |
| jointBootstrap | true samples a complete five-stage empirical row; false uses independent empirical stages |
| inputMode | 0empirical; 1fitted inverse-CDF marginals |
| reworkProbability | 0..0.5, default0; geometric number of repeat Assembly/Test visits |
| maxRework | Truncation cap0..10, default5 |
| componentMode | 0immediate one-per-order supply; 1independent exponential supply |
| componentMeanInterarrival | Positive mean component arrival gap, hours |
| animationEnabled | Presentation hooks only; defaultfalse |
| warmupHours | Must remain0; warm-up is performed by job index in analysis, not silently inside the engine |
| outputDirectory | Writable output folder, default relative results/native; isolated test copies use their own folders |
| verificationMode | Isolated exponential queue benchmark, separate from source-data experiments |
| verificationServers / verificationMeanService | Benchmark server count and exponential mean service |

`Demo3D` provides80finite orders, capacities[2,5,5,3,1], arrival mean5.054h, rework0.10and animation enabled. Set parameters before a run and restart for a new configuration. Mid-run capacity changes are not a matched statistical experiment.

## Executed plan versus GUI presets

FiniteCapacitySweep reproduces the v1-style default grid. ValidationSweep, SteadyStateSweep, ReworkSweep, ComponentSweep, InputModeSweep, MM1Verification and MMCVerification are convenient named presets. Exact executed matrices are the JSON plans in results/plans, not an assumption that every preset was launched unchanged.

`tools/native_batch.py` transforms a uniquely named private copy and records canonical/copy hashes. Native freeform parameters use the zero-based setup index. `tools/native_runtime.py` takes an exclusive OS mutex, launches in a private workspace, checks generated compiler error stubs and actual terminal logs, and cleans up only its owned Windows Job process tree.

The code tests run with Python/pytest. `tools/check_model.py` checks XML IDs, three agent types,23PMLobjects,19connections, real installed-library Java callbacks and dynamic shape expressions. Those are static checks. Native evidence is separate; preserve raw logs and their hashes when reproducing numerical results.

The analyzer accepts only declared complete seed/scenario cohorts, reconciles transition counters, stage chains, kit readiness, occupied-resource integrals and common random inputs. A Python replica is a verification aid and is never substituted for missing native output.

Source elapsed times include waiting, so finite results remain hypothetical. They do not reveal actual factory service times or staffing. Native visuals were inspected; package and fresh-extract evidence are indexed in docs/evidence-pack.md.
