#!/usr/bin/env python3
"""Recompute primary letter claims from this archive (no hardware runs)."""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from replay.command_chain import (  # noqa: E402
    derive_u_active_from_applied,
    extract_command_applied,
    summarize_level3_plant_input,
)

ARM_MO = "model_only_deadline"
ARM_AR = "actuator_ready"
CORE = "REG-PIPE-CPU"
DELTA_EQ = 0.005
BOOT_B = 5000
BOOT_SEED = 2026080705


def _ff(joined):
    n = 0
    for r in joined:
        Lm, Ak, D = r.get("L_model_ns"), r.get("A_k_ns"), r.get("deadline_ns")
        if Lm is not None and Ak is not None and D is not None and Lm <= D < Ak:
            n += 1
    return n


def load_study(study: str):
    rows = []
    base = ROOT / "data/study_c/sessions"
    for d in sorted(base.iterdir()):
        rep_p, wsa_p, j_p = d / "session_report.json", d / "wsa_events.json", d / "joined_atomic_trace.jsonl"
        if not rep_p.exists():
            continue
        rep = json.loads(rep_p.read_text())
        if rep.get("study") != study:
            continue
        wsa = json.loads(wsa_p.read_text()) if wsa_p.exists() else {"events": [], "plant_steps": []}
        joined = [json.loads(l) for l in j_p.read_text().splitlines() if l.strip()] if j_p.exists() else []
        rep["_wsa"] = wsa
        rep["_joined"] = joined
        rows.append(rep)
    return rows


def check_c2(ok: bool) -> bool:
    rows = [r for r in load_study("C2") if r.get("regime_id") == CORE]
    blocks = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        blocks[(r.get("regime_id"), r.get("scenario_seed"))][str(r.get("deadline_label"))][r["arm"]] = r
    expect = {
        "D_loose": {"n": 40, "ff_tot": 2, "ff_mean": 0.05, "iu": 0.08208333333333333,
                    "dJ": -6.144242690142854e-05, "ci": [-0.0011546634112699268, 0.0009701738493562484]},
        "D_boundary": {"n": 40, "ff_tot": 0, "ff_mean": 0.0, "iu": 0.07125000000000001,
                       "dJ": -0.0007440053465263281, "ci": [-0.0020601696876516714, 0.00021863748382541516]},
        "D_tight": {"n": 40, "ff_tot": 37, "ff_mean": 0.925, "iu": 0.8108333333333333,
                    "dJ": 0.008183408729544121, "ci": [0.0049795488015016215, 0.011528351240414495]},
    }
    for lab, exp in expect.items():
        dJ, ff, iu = [], [], []
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
        n = len(dJ)
        ff_tot = sum(ff)
        ff_mean = ff_tot / n if n else None
        iu_mean = sum(iu) / len(iu) if iu else None
        dJ_mean = sum(dJ) / len(dJ) if dJ else None
        bids = [k for k, dmap in blocks.items() if lab in dmap and ARM_MO in dmap[lab] and ARM_AR in dmap[lab]]
        rng = random.Random(BOOT_SEED)
        boots = []
        for _ in range(BOOT_B):
            sample = [bids[rng.randrange(len(bids))] for _ in range(len(bids))]
            vals = []
            for key in sample:
                mo, ar = blocks[key][lab][ARM_MO], blocks[key][lab][ARM_AR]
                vals.append(float(mo.get("J_primary") or 0) - float(ar.get("J_primary") or 0))
            boots.append(sum(vals) / len(vals))
        boots = sorted(boots)
        lo, hi = boots[int(0.05 * len(boots))], boots[int(0.95 * len(boots)) - 1]
        print(f"C2 {lab}: n={n} FF={ff_mean} ({ff_tot}/40) Iu={iu_mean:.4f} dJ={dJ_mean:.6g} CI=[{lo:.6g},{hi:.6g}]")
        if n != exp["n"] or ff_tot != exp["ff_tot"] or abs(ff_mean - exp["ff_mean"]) > 1e-12:
            print(f"FAIL {lab} FF/n"); ok = False
        if iu_mean is None or abs(iu_mean - exp["iu"]) > 1e-9:
            print(f"FAIL {lab} I_u"); ok = False
        if dJ_mean is None or abs(dJ_mean - exp["dJ"]) > 1e-12:
            print(f"FAIL {lab} dJ mean"); ok = False
        if abs(lo - exp["ci"][0]) > 1e-9 or abs(hi - exp["ci"][1]) > 1e-9:
            print(f"FAIL {lab} CI"); ok = False
        if lab in ("D_loose", "D_boundary"):
            if not (-DELTA_EQ <= lo and hi <= DELTA_EQ):
                print(f"FAIL {lab} equivalence containment"); ok = False
        if lab == "D_tight":
            if -DELTA_EQ <= lo and hi <= DELTA_EQ:
                print("FAIL D_tight unexpectedly contained in +/-0.005"); ok = False
            if lo > DELTA_EQ:
                print("FAIL D_tight unexpectedly entirely above +0.005"); ok = False
    return ok


def check_c1(ok: bool) -> bool:
    frozen = json.loads((ROOT / "results/c1/C1_SUMMARY.json").read_text())
    rows = load_study("C1")
    by = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        by[r.get("regime_id")][(r.get("scenario_seed"))][r["arm"]] = r
    for reg in ("REG-PIPE-NOM", "REG-PIPE-CPU"):
        pairs = []
        for seed, arms in by[reg].items():
            if ARM_MO in arms and ARM_AR in arms:
                pairs.append(float(arms[ARM_MO]["J_primary"]) - float(arms[ARM_AR]["J_primary"]))
        mean = sum(pairs) / len(pairs)
        exp = frozen["regimes"][reg]["delta_J"]["mean"]
        print(f"C1 {reg}: n={len(pairs)} mean_dJ={mean:+.6g}")
        if len(pairs) != 80 or abs(mean - exp) > 1e-12:
            print(f"FAIL C1 {reg}"); ok = False
        if not frozen["regimes"][reg]["equivalence_CI_containment"]:
            print(f"FAIL C1 {reg} frozen equivalence flag"); ok = False
    return ok


def check_study_a(ok: bool) -> bool:
    p95 = json.loads((ROOT / "results/study_a_p95/STUDY_A_P95.json").read_text())
    arts = {a["artifact_id"]: a for a in p95["artifacts"]}
    for aid, r95, d95 in (
        ("sdp_streaming_diffusion_policy", 1.007580867204435, 3.662968503333334),
        ("rd_vla_recurrent_depth", 1.0030095457132648, 0.22737436999999883),
    ):
        a = arts[aid]
        print(f"A {aid}: n={a['n_sessions']} r95={a['r_95']['mean']} d95={a['Delta_95_ms']['mean']}")
        if a["n_sessions"] != 15:
            print(f"FAIL {aid} sessions"); ok = False
        if abs(a["r_95"]["mean"] - r95) > 1e-12:
            print(f"FAIL {aid} r95"); ok = False
        if abs(a["Delta_95_ms"]["mean"] - d95) > 1e-9:
            print(f"FAIL {aid} d95"); ok = False
    p50 = json.loads((ROOT / "results/study_a_p95/SUMMARY_p50.json").read_text())
    if len(p50.get("per_artifact", [])) < 4:
        print("FAIL Study A p50 SUMMARY"); ok = False
    else:
        print(f"study_a_p50_artifacts={len(p50['per_artifact'])}")
    return ok


def main() -> int:
    ok = True
    ok = check_c2(ok)
    ok = check_c1(ok)
    ok = check_study_a(ok)
    env = json.loads((ROOT / "results/c2/C2_ENVELOPE.json").read_text())
    if env.get("core_regime") != CORE:
        print("FAIL envelope core_regime"); ok = False
    for lab in ("D_loose", "D_boundary", "D_tight"):
        if env["envelope_table"][lab]["n_scenarios"] != 40:
            print(f"FAIL frozen {lab} n"); ok = False
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
