"""CLI entry point: validate and summarize actual AnyLogic P3 logs (v1 and v2 schema).

SYNTHETIC educational data. Thin wrapper over the `analysis.native` package (split into
modules to stay under the ~800-line ceiling); re-exports the names other v2 scripts
(`summarize_decision.py`, tests) import, for drop-in compatibility with v1's single-file
`analyze_native.py`.
"""
from __future__ import annotations

import sys
import json
import numpy as np
import pandas as pd
from scipy import stats
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from native.outputs import plt, write_outputs
from native.cli import main  # noqa: E402
from native.comparisons import (ABS_TOLERANCES, compare_assembly_test, holm_adjust,  # noqa: E402,F401
                                paired_effects, precision, primary_contrast, summarize)
from native.metrics import confidence  # noqa: E402,F401
from native.mm1 import assess_mm1, assess_mmc, erlang_c, mmc_targets  # noqa: E402,F401
from native.parsing import (CONFIG_KEYS, LABEL, METRICS, MM1_TARGETS, SCENARIOS,  # noqa: E402,F401
                            STAGES, close, flag, integer, number, parse_log, require)
from native.validation import (scenario_capacities, validate_matrix,  # noqa: E402,F401
                               validate_replay_source, validate_run, validate_settings)

if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit(f"Native analysis rejected: {error}") from error
