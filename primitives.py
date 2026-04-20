"""
primitives — Single Source of Truth for the Coverage Cube constants.

Nothing here is arbitrary. One rule forces every value: take a number,
double it, add one, starting from 2. That rule picks out V=3 as the only
positive integer where 2^V equals V^2 - 1 (8 = 9 - 1). V=3 then fixes
every other constant in the cube.

Formally:
    A1 (Origin)     — We start at 2.
    A2 (Operator)   — D = 2. Doubling is the fundamental operation.
    A3 (Evolution)  — f(n) = 2n + 1. The growth rule.
    A4-A7           — Injectivity / Foundation / Induction / Observer.

The V=3 lock rests on the Catalan/Mihailescu theorem (2002): 8 and 9 are
the only consecutive perfect powers. So V is forced, not chosen.

Usage:
    from primitives import V, D, FANO, Bott, S_V, C_V, N_VALUES
"""

# =============================================================================
# Axiomatic inputs
# =============================================================================

D = 2    # A2: doubling constant
N_0 = 2  # A1: origin


# =============================================================================
# V = 3 — the dimensional lock
# =============================================================================
# Only positive integer satisfying 2^V = V^2 - 1. Solved at import so this
# file defends its own thesis.

_V_CANDIDATES = [v for v in range(1, 50) if 2**v == v*v - 1]
assert _V_CANDIDATES == [3], (
    f"Forcing equation 2^V = V^2 - 1 has solutions {_V_CANDIDATES}, expected [3]"
)
V = _V_CANDIDATES[0]


# =============================================================================
# Constants forced by V = 3
# =============================================================================

FANO = D**V - 1        # = 7.  Points of the Fano plane / non-trivial 3-bit words.
Bott = D**V            # = 8.  All 3-bit states / corners of a cube.
S_V  = V + V**2        # = 12. Resolution: 3 axes + 9 planes = 12 measurement slots.
C_V  = FANO * (V + 1)  # = 28. Error-correction capacity: 7 directions x 4 vertices.

N_VALUES = D**2        # = 4.  States per crumb (the stalk Z / N_VALUES).


if __name__ == "__main__":
    print(f"D={D}  V={V}")
    print(f"FANO={FANO}  Bott={Bott}  S_V={S_V}  C_V={C_V}")
    print(f"N_VALUES={N_VALUES}")
    print("All constants forced by V=3. No free parameters.")
