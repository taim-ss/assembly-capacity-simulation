"""Standard-normal quantile (inverse CDF) and the two fitted-marginal families used by
inputMode=1 (lognormal for Assembly/Quality/Handover, Weibull for Test).

Implements Wichura's AS 241 algorithm (the same "equal accuracy" rational-approximation method
AnyLogic/Java environments commonly use for ppnd16), cross-checked against
``scipy.stats.norm.ppf`` in tests/test_quantiles.py to within 1e-9.
"""
from __future__ import annotations

import math

# AS 241 rational approximation coefficients (Wichura, 1988), "ppnd16".
_A = (
    3.3871328727963666080e0, 1.3314166789178437745e2, 1.9715909503065514427e3,
    1.3731693765509461125e4, 4.5921953931549871457e4, 6.7265770927008700853e4,
    3.3430575583588128105e4, 2.5090809287301226727e3,
)
_B = (
    4.2313330701600911252e1, 6.8718700749205790830e2, 5.3941960214247511077e3,
    2.1213794301586595867e4, 3.9307895800092710610e4, 2.8729085735721942674e4,
    5.2264952788528545610e3,
)
_C = (
    1.42343711074968357734e0, 4.63033784615654529590e0, 5.76949722146069140550e0,
    3.64784832476320460504e0, 1.27045825245236838258e0, 2.41780725177450611770e-1,
    2.27238449892691845833e-2, 7.74545014278341640590e-4,
)
_D = (
    2.05319162663775882187e0, 1.67638483018380384940e0, 6.89767334985100004550e-1,
    1.48103976427480074590e-1, 1.51986665636164571966e-2, 5.47593808499534494600e-4,
    1.05075007164441684324e-9,
)
_E = (
    6.65790464350110377720e0, 5.46378491116411436990e0, 1.78482653991729133580e0,
    2.96560571828504891230e-1, 2.65321895265761230930e-2, 1.24266094738807843860e-3,
    2.71155556874348757815e-5, 2.01033439929228813265e-7,
)
_F = (
    5.99832206555887937690e-1, 1.36929880922735805310e-1, 1.48753612908506148525e-2,
    7.86869131145613259100e-4, 1.84631831751005468180e-5, 1.42151175831644588870e-7,
    2.04426310338993978564e-15,
)


def _poly(coeffs: tuple[float, ...], r: float) -> float:
    num = coeffs[7] if len(coeffs) == 8 else 0.0
    den = 1.0
    cs = coeffs[:-1] if len(coeffs) == 8 else coeffs
    num = cs[-1]
    for c in reversed(cs[:-1]):
        num = num * r + c
    return num


def normal_ppf(p: float) -> float:
    """Inverse CDF of the standard normal, AS 241 (Wichura 1988) full double precision."""
    if p <= 0.0:
        return float("-inf")
    if p >= 1.0:
        return float("inf")
    q = p - 0.5
    if abs(q) <= 0.425:
        r = 0.180625 - q * q
        num = (((((((_A[7] * r + _A[6]) * r + _A[5]) * r + _A[4]) * r + _A[3]) * r + _A[2]) * r + _A[1]) * r + _A[0])
        den = (((((((_B[6] * r + _B[5]) * r + _B[4]) * r + _B[3]) * r + _B[2]) * r + _B[1]) * r + _B[0]) * r + 1.0)
        return q * num / den
    r = p if q < 0 else 1 - p
    r = math.sqrt(-math.log(r))
    if r <= 5.0:
        r -= 1.6
        num = (((((((_C[7] * r + _C[6]) * r + _C[5]) * r + _C[4]) * r + _C[3]) * r + _C[2]) * r + _C[1]) * r + _C[0])
        den = (((((((_D[6] * r + _D[5]) * r + _D[4]) * r + _D[3]) * r + _D[2]) * r + _D[1]) * r + _D[0]) * r + 1.0)
    else:
        r -= 5.0
        num = (((((((_E[7] * r + _E[6]) * r + _E[5]) * r + _E[4]) * r + _E[3]) * r + _E[2]) * r + _E[1]) * r + _E[0])
        den = (((((((_F[6] * r + _F[5]) * r + _F[4]) * r + _F[3]) * r + _F[2]) * r + _F[1]) * r + _F[0]) * r + 1.0)
    val = num / den
    return -val if q < 0 else val


def lognormal_from_u(u: float, shape: float, scale: float) -> float:
    """scale * exp(shape * z(u)); loc is always 0 for the calibrated v2 marginals."""
    return scale * math.exp(shape * normal_ppf(u))


def weibull_from_u(u: float, shape_c: float, scale: float) -> float:
    """scale * (-ln(1-u))^(1/c); loc is always 0 for the calibrated v2 marginal."""
    return scale * ((-math.log(1.0 - u)) ** (1.0 / shape_c))


def empirical_quantile(u: float, sorted_values: list[float]) -> float:
    """Type-1 (step) empirical quantile: sorted[min(n-1, floor(u*n))], per the v2 feature spec."""
    n = len(sorted_values)
    idx = min(n - 1, int(u * n))
    return sorted_values[idx]
