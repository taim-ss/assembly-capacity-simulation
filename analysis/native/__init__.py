"""P3 v2 native-log analysis package. SYNTHETIC educational data.

Split from the v1 monolithic `analyze_native.py` / `summarize_decision.py` to stay under the
~700-line soft ceiling per module. Backward compatible with v1 logs: absent v2 trailing fields
(visit index, componentMode/inputMode config fields, starvedByUpstream/idleUnits metric fields)
default to the v1 values, so v1 logs analyze identically to v1's own `analyze_native.py` output.
"""
