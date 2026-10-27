#!/usr/bin/env python3
"""C2 envelope table + scenario-block bootstrap (shared scenarios across D).

Preregistered core: CPU regime × {D_L, D_B, D_T}, n=40 paired scenarios.
NOM × D_B is a sanity cell and is NOT pooled into the core envelope
(pooling produced the spurious D_B FF/episode=0.0125 = 1/80 artifact).
"""
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

from replay.command_chain import (  # noqa: E402
    derive_u_active_from_applied,
    extract_command_applied,
    summarize_level3_plant_input,
)

RAW = REPO / "data" / "study_c" / "sessions"
OUT = REPO / "results" / "c2"
ARM_MO = "model_only_deadline"
ARM_AR = "actuator_ready"
CORE_REGIME = "REG-PIPE-CPU"
BOOT_B = 5000
BOOT_SEED = 2026080705
DELTA_EQ = 0.005


def _ff(joined: List[Dict[str, Any]]) -> int:
    """Count MO-carrier false-feasible steps in one MO episode."""
    n = 0
    for r in joined:
        Lm, Ak, D = r.get("L_model_ns"), r.get("A_k_ns"), r.get("deadline_ns")
        if Lm is not None and Ak is not None and D is not None and Lm <= D < Ak:
            n += 1
    return n


def load() -> List[Dict[str, Any]]:
    rows = []
    if not RAW.exists():
        return rows
    for d in sorted(RAW.iterdir()):
        rep_p, wsa_p, j_p = d / "session_report.json", d / "wsa_events.json", d / "joined_atomic_trace.jsonl"
        if not rep_p.exists() or not wsa_p.exists():
            continue
        rep = json.loads(rep_p.read_text(encoding="utf-8"))
        wsa = json.loads(wsa_p.read_text(encoding="utf-8"))
        joined = [json.loads(l) for l in j_p.read_text(encoding="utf-8").splitlines() if l.strip()] if j_p.exists() else []
        rep["_wsa"] = wsa
        rep["_joined"] = joined
        rows.append(rep)
    return rows


def _build_blocks(
    rows: List[Dict[str, Any]], regime: str | None
) -> Dict[Tuple[Any, Any], Dict[str, Dict[str, Dict[str, Any]]]]:
    blocks: Dict[Tuple[Any, Any], Dict[str, Dict[str, Dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for r in rows:
        if regime is not None and r.get("regime_id") != regime:
            continue
        blocks[(r.get("regime_id"), r.get("scenario_seed"))][str(r.get("deadline_label", "?"))][
            r["arm"]
        ] = r
    return blocks


def analyze_blocks(
    blocks: Dict[Tuple[Any, Any], Dict[str, Dict[str, Dict[str, Any]]]]
) -> Dict[str, Any]:
    deadlines = sorted({lab for b in blocks.values() for lab in b if str(lab).startswith("D_")})
    point: Dict[str, Any] = {}
    for lab in deadlines:
        dJ, ff, iu, hold = [], [], [], []
        for (_reg, _seed), dmap in blocks.items():
            if lab not in dmap or ARM_MO not in dmap[lab] or ARM_AR not in dmap[lab]:
                continue
            mo, ar = dmap[lab][ARM_MO], dmap[lab][ARM_AR]
            dJ.append(float(mo.get("J_primary") or 0) - float(ar.get("J_primary") or 0))
            ff.append(_ff(mo["_joined"]))
            l3 = summarize_level3_plant_input(
                derive_u_active_from_applied(
                    extract_command_applied(mo["_wsa"].get("events") or []),
                    mo["_wsa"].get("plant_steps") or [],
                ),
                derive_u_active_from_applied(
                    extract_command_applied(ar["_wsa"].get("events") or []),
                    ar["_wsa"].get("plant_steps") or [],
                ),
            )
            iu.append(l3["frac_mismatch"])
            mo_adm = {r.get("observation_id"): r.get("admission_outcome") for r in mo["_joined"]}
            ar_adm = {r.get("observation_id"): r.get("admission_outcome") for r in ar["_joined"]}
            keys = set(mo_adm) & set(ar_adm)
            if keys:
                hold.append(sum(1 for k in keys if mo_adm[k] != ar_adm[k]) / len(keys))

        # Bootstrap only over scenarios that complete this deadline (avoids mixing NOM sanity).
        block_ids = [
            k
            for k, dmap in blocks.items()
            if lab in dmap and ARM_MO in dmap[lab] and ARM_AR in dmap[lab]
        ]
        rng = random.Random(BOOT_SEED)
        boots: List[float] = []
        for _ in range(BOOT_B):
            if not block_ids:
                break
            sample = [block_ids[rng.randrange(len(block_ids))] for _ in range(len(block_ids))]
            vals = []
            for key in sample:
                mo, ar = blocks[key][lab][ARM_MO], blocks[key][lab][ARM_AR]
                vals.append(float(mo.get("J_primary") or 0) - float(ar.get("J_primary") or 0))
            boots.append(sum(vals) / len(vals))
        boots_sorted = sorted(boots)
        if boots_sorted:
            lo = boots_sorted[int(0.05 * len(boots_sorted))]
            hi = boots_sorted[int(0.95 * len(boots_sorted)) - 1]
        else:
            lo = hi = None

        n = len(dJ)
        ff_total = sum(ff)
        ff_mean = (ff_total / n) if n else None
        point[lab] = {
            "n_scenarios": n,
            "L2_FF_total_events": ff_total,
            "L2_FF_mean_per_MO_episode": ff_mean,
            # Back-compat alias used by older docs
            "L2_FF_mean": ff_mean,
            "L3_I_u_frac": (sum(iu) / len(iu)) if iu else None,
            "hold_mismatch_frac": (sum(hold) / len(hold)) if hold else None,
            "L4_delta_J_mean": (sum(dJ) / len(dJ)) if dJ else None,
            "L4_delta_J_ci90": [lo, hi],
            "equivalence_CI_containment": (
                lo is not None and hi is not None and -DELTA_EQ <= lo and hi <= DELTA_EQ
            ),
            "ci_entirely_above_plus_delta_eq": lo is not None and lo > DELTA_EQ,
        }
    return {
        "schema": "analysis_c2_envelope_v2",
        "primary_L4": "delta_J_integrated",
        "bootstrap": "scenario_block_per_deadline",
        "core_regime": CORE_REGIME,
        "ff_estimand": "mean MO-carrier false-feasible step count per MO episode",
        "envelope_table": point,
        "n_blocks": len(
            {
                k
                for k, dmap in blocks.items()
                if any(ARM_MO in dmap[lab] and ARM_AR in dmap[lab] for lab in dmap)
            }
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--json-out", type=Path, default=OUT / "C2_ENVELOPE.json")
    p.add_argument(
        "--pool-nom",
        action="store_true",
        help="Debug only: pool NOM+CPU (creates inhomogeneous n; not for primary claims).",
    )
    args = p.parse_args()
    rows = [r for r in load() if r.get("study") == "C2"]
    if not rows:
        rows = [
            r
            for r in load()
            if str(r.get("deadline_label", "")).startswith("D_")
            and r.get("deadline_label") != "D150"
        ]
    regime = None if args.pool_nom else CORE_REGIME
    blocks = _build_blocks(rows, regime=regime)
    out = analyze_blocks(blocks)
    if not args.pool_nom:
        # Attach NOM×D_B sanity separately (prereg), not pooled.
        nom_blocks = _build_blocks(rows, regime="REG-PIPE-NOM")
        nom = analyze_blocks(nom_blocks)
        out["nom_sanity_D_boundary"] = nom.get("envelope_table", {}).get("D_boundary")
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
