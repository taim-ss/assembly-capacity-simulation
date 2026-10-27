# P3 v2 experiment register

**SYNTHETIC educational project.** The frozen contract is v2-preregistration.md. Pre-confirmation amendments are recorded separately in results/plans/director-decisions.json. Native numerical runs are distinct from Python plots, static checks and visual acceptance.

| Family | Exact scope | Status |
|---|---|---|
| E0 | 60default-regression cases, seeds1..10Ã—6scenarios; replay195orders | Completed; default native timestamps agree with read-only v1 within1e-9hours |
| E1 | 10seeds,600orders, capacities50each, observed mean release gap | Completed low-wait consistency check; does not identify real service times |
| E2pilot | 10seedsÃ—6scenarios,5000orders, capacities[2,5,5,3,1], arrival5.0540201005h | Completed; pilot retained separately |
| E2confirmation | 200fresh seeds11..210Ã—6scenarios,5000orders | Completed; strict aggregate analysis accepted |
| E3 | Reanalyze v1 confirmation,1140logs | Completed; different capacity/load assumptions, not pooled with v2 |
| E4grid | Assembly capacities4/5/6/8, matched Test4/4/5/7, eight service scales0.5..1.2,5seeds,2000orders | 160native runs complete; four interpolated points tested |
| E4contrast | Four interpolated mean-matching pointsÃ—10seedsÃ—baseline/Assembly+1/Test+1 | 120native runs completed and strictly accepted; ranking reverses |
| E5 | Eight levels over capacity, service haircut, input family, rework, component supply;30seedsÃ—3scenariosÃ—600orders | 720native runs complete; component family required a buffer fix and90reruns |
| E6 | M/M/3:lambda2.1,mu1,c3;10pilot and30fresh confirmation seeds,10000orders | Completed; six benchmark targets accepted |

E1/E2/E6 use pilot-driven fixed confirmation sizes, with no pooling. E2's original40-per-scenario cap was amended to200before confirmation data were inspected; this deviation remains explicit. The500-job cutoff was frozen from pilot visual review; the automated4971suggestion was rejected and preserved. Cutoff250/1000sensitivity is exported in results/warmup-sensitivity.

Only the E2 direct Assembly-versus-Test mean/P90 contrast is primary, with Holm adjustment across those two tests. Other intervals are exploratory pointwise intervals. Show relative half-widths and near-zero absolute tolerances; unmet targets remain visible.

Post-cutoff WIP and station statistics use exact interval overlap. Finite campaigns still drain, so the window is not a perpetual stationary observation. E5 low-capacity and critical-rate component cases require finite-campaign interpretation. Cost rates are assumptions; sustained-throughput and lead-saving gates remain explicit, with undefined ratios retained rather than forced.

The final canonical245-case native batch completed. Taim subsequently approved the revised native3D run and recording:80orders completed and the final approximately32seconds are preserved in results/visual-final. Canonical regression, package/fresh-extract evidence and disclosed evidence-plan deviations are indexed in docs/evidence-pack.md.
