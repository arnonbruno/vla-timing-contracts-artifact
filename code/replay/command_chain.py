"""Command-chain helpers: COMMAND_APPLIED → u_active[k] → Level-3 I_u / Δu.

Replay must use raw COMMAND_APPLIED events; u_active is a derived analysis quantity.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# Frozen F1TENTH-ish scales: steer rad, accel m/s^2 (engineering diagonals).
U_TOL_STEER = 1e-6
U_TOL_ACCEL = 1e-6
W_STEER = 1.0 / 0.4
W_ACCEL = 1.0 / 3.0


def actions_approx_equal(
    a: Optional[Sequence[float]],
    b: Optional[Sequence[float]],
    *,
    tol_steer: float = U_TOL_STEER,
    tol_accel: float = U_TOL_ACCEL,
) -> bool:
    if a is None or b is None or len(a) < 2 or len(b) < 2:
        return a is None and b is None
    return abs(float(a[0]) - float(b[0])) <= tol_steer and abs(float(a[1]) - float(b[1])) <= tol_accel


def delta_u_norm(
    a: Sequence[float],
    b: Sequence[float],
    *,
    w_steer: float = W_STEER,
    w_accel: float = W_ACCEL,
) -> float:
    d0 = w_steer * (float(a[0]) - float(b[0]))
    d1 = w_accel * (float(a[1]) - float(b[1]))
    return float((d0 * d0 + d1 * d1) ** 0.5)


def extract_command_applied(events: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Raw plant application stream: {(t_apply, u_applied)}_j."""
    out: List[Dict[str, Any]] = []
    for ev in events:
        if ev.get("event") != "COMMAND_APPLIED":
            continue
        u = ev.get("u_applied") or ev.get("action")
        if u is None:
            continue
        out.append(
            {
                "t_apply_ns": int(ev.get("t_apply_ns") or ev.get("t_ns") or 0),
                "u_applied": [float(u[0]), float(u[1])],
                "observation_id": ev.get("observation_id"),
                "exit_id": ev.get("exit_id"),
                "outcome": ev.get("outcome"),
                "arm": ev.get("arm"),
                "A_k_ns": ev.get("A_k_ns"),
                "sequence_id": ev.get("sequence_id"),
            }
        )
    out.sort(key=lambda r: int(r["t_apply_ns"]))
    return out


def derive_u_active_from_applied(
    command_applied: Sequence[Dict[str, Any]],
    plant_steps: Sequence[Dict[str, Any]],
    *,
    fallback: Sequence[float] = (0.0, 0.0),
) -> List[Dict[str, Any]]:
    """Derive u_active[k] on plant intervals from COMMAND_APPLIED + step times.

    For each plant advance at t_advance, the active command is the last applied
    command with t_apply <= t_advance (hold-last-valid). If plant_steps already
    logged u_active, prefer that as ground truth for live runs.
    """
    if plant_steps and all("u_active" in s for s in plant_steps):
        return [
            {
                "plant_k": int(s.get("plant_k", i)),
                "t_advance_ns": int(s.get("t_advance_ns", 0)),
                "u_active": [float(s["u_active"][0]), float(s["u_active"][1])],
                "action_source": s.get("action_source"),
                "cte_m": s.get("cte_m"),
            }
            for i, s in enumerate(plant_steps)
        ]

    applied = sorted(command_applied, key=lambda r: int(r["t_apply_ns"]))
    j = 0
    cur = [float(fallback[0]), float(fallback[1])]
    out: List[Dict[str, Any]] = []
    for i, step in enumerate(plant_steps):
        t_adv = int(step.get("t_advance_ns", 0))
        while j < len(applied) and int(applied[j]["t_apply_ns"]) <= t_adv:
            cur = list(applied[j]["u_applied"])
            j += 1
        out.append(
            {
                "plant_k": int(step.get("plant_k", i)),
                "t_advance_ns": t_adv,
                "u_active": list(cur),
                "action_source": "derived_from_COMMAND_APPLIED",
                "cte_m": step.get("cte_m"),
            }
        )
    return out


def I_u_series(
    u_mo: Sequence[Dict[str, Any]],
    u_ar: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    n = min(len(u_mo), len(u_ar))
    rows: List[Dict[str, Any]] = []
    for k in range(n):
        a = u_mo[k]["u_active"]
        b = u_ar[k]["u_active"]
        mismatch = not actions_approx_equal(a, b)
        rows.append(
            {
                "plant_k": k,
                "I_u": int(mismatch),
                "delta_u_norm": delta_u_norm(a, b),
                "abs_delta_steer": abs(float(a[0]) - float(b[0])),
                "abs_delta_accel": abs(float(a[1]) - float(b[1])),
                "u_active_mo": list(a),
                "u_active_ar": list(b),
            }
        )
    return rows


def consecutive_hold_runs(I_u: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Run lengths of consecutive plant steps with I_u=1."""
    runs: List[int] = []
    cur = 0
    for row in I_u:
        if int(row["I_u"]) == 1:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    return {
        "n_mismatch_steps": int(sum(int(r["I_u"]) for r in I_u)),
        "n_steps": len(I_u),
        "frac_mismatch": (float(sum(int(r["I_u"]) for r in I_u)) / len(I_u)) if I_u else None,
        "n_runs": len(runs),
        "max_run": max(runs) if runs else 0,
        "mean_run": (sum(runs) / len(runs)) if runs else 0.0,
        "runs": runs,
    }


def summarize_level3_plant_input(
    u_mo: Sequence[Dict[str, Any]],
    u_ar: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    series = I_u_series(u_mo, u_ar)
    holds = consecutive_hold_runs(series)
    norms = [float(r["delta_u_norm"]) for r in series]
    return {
        **holds,
        "mean_delta_u_norm": (sum(norms) / len(norms)) if norms else None,
        "max_delta_u_norm": max(norms) if norms else None,
        "mean_abs_delta_steer": (
            sum(float(r["abs_delta_steer"]) for r in series) / len(series) if series else None
        ),
        "mean_abs_delta_accel": (
            sum(float(r["abs_delta_accel"]) for r in series) / len(series) if series else None
        ),
        "tolerances": {"steer": U_TOL_STEER, "accel": U_TOL_ACCEL},
        "W": {"steer": W_STEER, "accel": W_ACCEL},
    }
