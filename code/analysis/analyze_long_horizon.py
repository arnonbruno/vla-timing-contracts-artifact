#!/usr/bin/env python3
"""Long-horizon confirmation: primary J_bar = J/T; secondary raw J."""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "code"))

RAW = REPO / "data" / "study_c" / "sessions"
OUT = REPO / "results" / "long_horizon" / "LONG_HORIZON_SUMMARY.json"
ARM_MO = "model_only_deadline"
ARM_AR = "actuator_ready"
T_S = 15.0
# Preregistered for J_bar (mean |CTE|); not the 3s integrated-J SESOI
DELTA_EQ_JBAR = 0.005 / 3.0  # ~same mean-|CTE| scale as 3s δ_eq/T
BOOT_B = 5000
BOOT_SEED = 2026080706


def main() -> int:
    rows = []
    if RAW.exists():
        for d in sorted(RAW.iterdir()):
            rep_p = d / "session_report.json"
            if not rep_p.exists():
                continue
            rep = json.loads(rep_p.read_text(encoding="utf-8"))
            if rep.get("study") != "LONG_HORIZON" and int(rep.get("cycles") or 0) < 200:
                continue
            rows.append(rep)
    pairs: Dict[Any, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        pairs[r.get("scenario_seed")][r["arm"]] = r

    dJbar = []
    dJ = []
    for seed, arms in pairs.items():
        if ARM_MO not in arms or ARM_AR not in arms:
            continue
        Jmo = float(arms[ARM_MO].get("J_primary") or 0)
        Jar = float(arms[ARM_AR].get("J_primary") or 0)
        dJ.append(Jmo - Jar)
        dJbar.append((Jmo - Jar) / T_S)

    rng = random.Random(BOOT_SEED)
    boots = []
    n = len(dJbar)
    for _ in range(BOOT_B):
        if n == 0:
            break
        s = [dJbar[rng.randrange(n)] for _ in range(n)]
        boots.append(sum(s) / n)
    boots.sort()
    ci = [boots[int(0.05 * len(boots))], boots[int(0.95 * len(boots)) - 1]] if boots else [None, None]
    eq = ci[0] is not None and -DELTA_EQ_JBAR <= ci[0] and ci[1] <= DELTA_EQ_JBAR
    material_pos = ci[0] is not None and ci[0] > DELTA_EQ_JBAR
    material_neg = ci[1] is not None and ci[1] < -DELTA_EQ_JBAR
    if eq:
        verdict = "equivalence_established"
    elif material_pos or material_neg:
        verdict = "material_effect_CI_outside_band"
    else:
        verdict = "equivalence_inconclusive"
    out = {
        "schema": "analysis_long_horizon_v1",
        "primary": "J_bar=J/T",
        "T_s": T_S,
        "delta_eq_Jbar": DELTA_EQ_JBAR,
        "n_pairs": n,
        "delta_Jbar_mean": (sum(dJbar) / n) if n else None,
        "delta_Jbar_ci90": ci,
        "equivalence_CI_containment": bool(eq) if n else None,
        "verdict": verdict,
        "note": (
            "CI not contained in ±delta_eq does not alone demonstrate non-equivalence; "
            "if CI overlaps the band, report equivalence_inconclusive."
        ),
        "secondary_delta_J_mean": (sum(dJ) / n) if n else None,
        "secondary_note": "raw integrated Delta_J is not a 15s materiality claim without a 15s SESOI",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
