"""Java source fragments for inputMode=1 fitted marginals (v2 feature spec section
"Fitted marginals"). Everything here is plain strings embedded into the generated
.alp by build_model.py; nothing here touches AnyLogic itself.

Normal quantile: Wichura (1988) AS 241 algorithm 2 (PPND16), full double precision,
reproduced from the well-known public-domain C port of the original Fortran (the same
rational-approximation constants appear in numerous open statistics libraries). Chosen
over the shorter Acklam approximation (~1.15e-9 max error) because the spec's
check_model probe compares against known qnorm values to 1e-9 and AS241 is accurate to
machine precision, with no refinement step needed.
"""
import csv
import json
from pathlib import Path

# AS241 is implemented as a Java lambda (java.util.function.DoubleUnaryOperator) rather
# than an AnyLogic "Function" element: this codebase (see P2's tools/build_model.py) has
# no established XML schema for custom Function elements, but Variable fields holding a
# lambda are already used here for firstArrivalTime/recordLog, so this follows the same
# proven pattern instead of guessing at untested XML.
NORMAL_QUANTILE_JAVA = """(java.util.function.DoubleUnaryOperator)(p) -> {
 double q = p - 0.5; double r; double val;
 if (Math.abs(q) <= 0.425) {
  r = 0.180625 - q*q;
  val = q*(((((((r*2509.0809287301226727+33430.575583588128105)*r+67265.770927008700853)*r+45921.953931549871457)*r+13731.693765509461125)*r+1971.5909503065514427)*r+133.14166789178437745)*r+3.387132872796366608)
      /(((((((r*5226.495278852854561+28729.085735721942674)*r+39307.89580009271061)*r+21213.794301586595867)*r+5394.1960214247511077)*r+687.1870074920579083)*r+42.313330701600911252)*r+1.0);
 } else {
  r = (q < 0) ? p : 1 - p;
  r = Math.sqrt(-Math.log(r));
  if (r <= 5.0) {
   r -= 1.6;
   val = (((((((r*7.7454501427834140764e-4+0.0227238449892691845833)*r+0.24178072517745061177)*r+1.27045825245236838258)*r+3.64784832476320460504)*r+5.7694972214606914055)*r+4.6303378461565452959)*r+1.42343711074968357734)
       /(((((((r*1.05075007164441684324e-9+5.475938084995344946e-4)*r+0.0151986665636164571966)*r+0.14810397642748007459)*r+0.68976733498510000455)*r+1.6763848301838038494)*r+2.05319162663775882187)*r+1.0);
  } else {
   r -= 5.0;
   val = (((((((r*2.01033439929228813265e-7+2.71155556874348757815e-5)*r+0.0012426609473880784386)*r+0.026532189526576123093)*r+0.29656057182850489123)*r+1.7848265399172913358)*r+5.4637849111641143699)*r+6.6579046435011037772)
       /(((((((r*2.04426310338993978564e-15+1.4215117583164458887e-7)*r+1.8463183175100546818e-5)*r+7.868691311456132591e-4)*r+0.0148753612908506148525)*r+0.13692988092273580531)*r+0.59983220655588793769)*r+1.0);
  }
  if (q < 0.0) val = -val;
 }
 return val;
}"""

STAGE_STEP_NAMES = {0: "kitting", 1: "assembly", 2: "test", 3: "quality_release", 4: "handover"}


def load_fit_params(root: Path) -> dict:
    """Read analysis/calibration/calibration_table.csv at generation time (never
    hand-typed) and return {stage_index: (family, [params...])} for stages 1..4
    (stage 0, kitting, uses the empirical type-1 quantile instead, see
    sorted_kitting_literal)."""
    path = root / "analysis/calibration/calibration_table.csv"
    out = {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            step = row["step"]
            idx = {v: k for k, v in STAGE_STEP_NAMES.items()}.get(step)
            if idx is None or idx == 0:
                continue
            out[idx] = (row["family"], json.loads(row["params_scipy_json"]))
    missing = {1, 2, 3, 4} - set(out)
    if missing:
        raise ValueError(f"calibration_table.csv missing fitted rows for stages {missing}")
    return out


def sorted_kitting_literal(rows) -> str:
    """double[] literal of the retained kitting_h column, ascending, for the
    empirical type-1 quantile sortedKitting[floor(u*n)] used at inputMode=1, k=0."""
    values = sorted(float(r["kitting_h"]) for r in rows)
    return "new double[]{" + ",".join(format(v, ".17g") for v in values) + "}"


def fitted_duration_java(fit: dict) -> str:
    """BiFunction<Integer,Double,Double> implementing the four fitted marginals
    (lognormal k=1,3,4 / weibull k=2) via inverse CDF on normalQuantile, using the
    exact shape/loc/scale floats read from calibration_table.csv. k=0 (kitting) is
    handled by sortedKitting directly in the caller, not here."""
    lines = []
    for k in (1, 2, 3, 4):
        family, params = fit[k]
        if family == "lognormal":
            shape, _loc, scale = params
            expr = f"{format(scale, '.17g')}*Math.exp({format(shape, '.17g')}*normalQuantile.applyAsDouble(u))"
        elif family == "weibull":
            c, _loc, scale = params
            expr = f"{format(scale, '.17g')}*Math.pow(-Math.log(1-u),1.0/{format(c, '.17g')})"
        else:
            raise ValueError(f"Unsupported fitted family for stage {k}: {family}")
        lines.append(f" if (k=={k}) return {expr};")
    # k==0 never reaches here (caller routes it to sortedKitting), but keep the
    # BiFunction total so a stray call does not throw inside a lambda.
    body = "(k,u) -> {\n if (k==0) return sortedKitting[Math.min(sortedKitting.length-1,(int)Math.floor(u*sortedKitting.length))];\n" \
           + "\n".join(lines) + "\n return 0.0;\n}"
    return body
