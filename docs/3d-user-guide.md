# Read the P3 sensor-module scene

**SYNTHETIC educational model. Produced by agents under Taim's direction (tier B).**

**Current status:** Taim approved running and recording the revised animation. The native80-order demonstration completed, its dashboard/equipment/flow separation was inspected, and actual PNG/GIF/MP4 evidence is in `results/visual-final`. The approximately32-second clip covers the final part of the run, ending at80 completed orders and zero WIP; it is not a full-campaign recording.

## What is happening?

A hypothetical small manufacturer assembles industrial temperature-sensor modules. Work orders arrive, wait for prepared kits, receive assembly and testing, pass quality inspection, and are packed for shipment. Failed tests return to Assembly for repair, then repeat Test.

**The question is where to put one extra processing resource: Assembly or Test.** The active scenario label distinguishes baseline, Assembly +1 and Test +1. Compare waiting, queues and total order completion time using matched replication seeds. A visibly long queue is a clue to investigate, not by itself proof of the best intervention.

## Read the scene from left to right

| Place | Meaning |
|---|---|
| Incoming trays | New work orders and the illustrative parts context |
| Prepare parts / Kitting | Make a kit available before assembly |
| Assembly benches | Fit the board and sensor into the housing |
| Functional-test rigs | Test the assembled module; failures require rework |
| Quality inspection | Approve the tested module |
| Packing | Pack an approved order |
| Shipping pallet | Completed work orders leave the system |

One moving product token represents one **work order**. PCB, housing and packed-carton details explain its stage; they do not simulate circuit behavior or individual parts. The actual Combine logic uses one available-kit token per order, not a detailed bill of materials.

**Blue = waiting; green = processing; red = a rework visit.** Direction arrows show forward progress. The red return route means Test â†’ Assembly â†’ Test. Resource markers represent processing capacity; each busy resource can handle one work order at a time. At most 6 units and 8 waiting tokens are drawn per stage; overflow text reports the additional queue. These graphical limits do not limit the process.

Products visibly travel between station positions using presentation-only wall-clock interpolation. Processing logic still transfers them at its actual event times. Travel adds no modeled transport time, service delay, event or random draw. At high playback speed, a later state update may interrupt an unfinished visual movement. The image illustrates flow; it is not a physical transport study.

## Separate presentation and flowchart

The runtime dashboard contains the story, scenario, completion/waiting indicators and legend above the 3D window. Factory furniture, route markings and product geometry are 3D-only. The editor's PML blocks, variables and connectors are placed in their own area at x=2300 and beyond and hidden from runtime. The process flowchart does not sit on top of the 3D factory or dashboard.

The dashboard reads actual model state: released/completed orders, WIP, completed-order mean lead time, clock time, and station capacity/queue/busy values. It must not show invented sensor readings or measured-factory claims. A completed-order average is not a prediction for an unfinished individual order.

## Open the native view

The portable file is `model/P3_Assembly_Flow.alp`, for AnyLogic 8.9 PLE. `Demo3D` is the presentation experiment; default `Simulation` is the deterministic 195-record replay. Demo parameters are set before a run; change a scenario or capacity, then restart. Mid-run edits do not constitute a matched statistical comparison. Scenario index 2 adds one Assembly resource and index 3 adds one Test resource.

Built-in extruded geometry requires no external DAE, GLB or image assets. `results/plans` records the exact executed numerical configurations. Static checks and numerical tests remain separate from visual proof: a native screenshot proves only its identified view and state. `docs/3d-layout-plan.png` is a design preview, not an AnyLogic capture.

Source timestamps include waiting and processing. The sensor-module story is illustrative, capacities and failure rates are assumptions, and no real factory is validated by the scene. No submission or publication has been performed.
