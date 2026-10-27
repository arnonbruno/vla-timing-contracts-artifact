#!/usr/bin/env python3
"""Generate Study C2 operating-contract envelope figure from corrected CPU-only C2_ENVELOPE.json."""
from __future__ import annotations

import json
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

FIG = Path(__file__).resolve().parents[2] / "results" / "c2"
ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / "results/c2/C2_ENVELOPE.json"

plt.rcParams.update(
    {
        "font.size": 9,
        "axes.titlesize": 9.5,
        "axes.labelsize": 9,
        "legend.fontsize": 7.5,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)


def main() -> None:
    data = json.loads(ENV.read_text(encoding="utf-8"))
    table = data["envelope_table"]
    order = ["D_loose", "D_boundary", "D_tight"]
    labels = [r"$D_L{=}71$", r"$D_B{=}61$", r"$D_T{=}51$"]
    ff = [table[k]["L2_FF_mean_per_MO_episode"] for k in order]
    ff_tot = [int(table[k]["L2_FF_total_events"]) for k in order]
    iu = [table[k]["L3_I_u_frac"] for k in order]
    dj = [table[k]["L4_delta_J_mean"] for k in order]
    lo = [table[k]["L4_delta_J_ci90"][0] for k in order]
    hi = [table[k]["L4_delta_J_ci90"][1] for k in order]
    colors = ["#2e7d32", "#2e7d32", "#b71c1c"]
    verdicts = ["equivalent", "equivalent", "equiv. not established\npositive point est."]

    x = np.arange(3)
    fig, (ax0, ax1) = plt.subplots(
        2, 1, figsize=(7.1, 3.75), dpi=200, sharex=True, constrained_layout=True
    )

    w = 0.36
    b0 = ax0.bar(
        x - w / 2,
        ff,
        width=w,
        color="#1f4e79",
        label="MO FF: mean steps / MO episode",
    )
    b1 = ax0.bar(
        x + w / 2,
        iu,
        width=w,
        color="#b85c38",
        label=r"plant-step $I_u$ fraction",
    )
    # No generic unit label: legend defines each series.
    ax0.set_ylabel("")
    ax0.set_ylim(0, 1.18)
    ax0.grid(True, axis="y", alpha=0.3)
    ax0.legend(loc="upper left", framealpha=0.92)
    ax0.set_title(r"A. Classification and plant-input disagreement (CPU core, $n{=}40$)")
    for bar, tot in zip(b0, ff_tot):
        h = bar.get_height()
        ax0.text(
            bar.get_x() + bar.get_width() / 2,
            h + 0.02,
            f"{tot} steps / 40 ep.",
            ha="center",
            va="bottom",
            fontsize=6.5,
            color="#1f4e79",
        )
    for bar in b1:
        h = bar.get_height()
        ax0.text(
            bar.get_x() + bar.get_width() / 2,
            h + 0.02,
            f"{h:.3g}",
            ha="center",
            va="bottom",
            fontsize=7,
            color="#b85c38",
        )

    yerr = np.vstack([np.array(dj) - np.array(lo), np.array(hi) - np.array(dj)])
    ax1.axhspan(-0.005, 0.005, color="#c6e2c6", alpha=0.55, label=r"equiv. band $\pm0.005$")
    ax1.axhline(0.0, color="#444", lw=0.8)
    ax1.axhline(0.005, color="#2e7d32", lw=0.7, ls="--", alpha=0.7)
    ax1.errorbar(
        x, dj, yerr=yerr, fmt="o", color="#1a1a1a", ecolor="#1a1a1a", capsize=4, markersize=6, zorder=3
    )
    for xi, yi, c, lab in zip(x, dj, colors, verdicts):
        ax1.scatter([xi], [yi], s=55, color=c, zorder=4, edgecolors="#111", linewidths=0.4)
        ax1.text(
            xi,
            hi[xi] + 0.0005,
            lab,
            ha="center",
            va="bottom",
            fontsize=6.8,
            color=c,
            fontweight="bold",
            linespacing=1.15,
        )
    ax1.set_ylabel(r"$\Delta J$ (m$\cdot$s)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.set_ylim(-0.0035, 0.0150)
    ax1.grid(True, axis="y", alpha=0.3)
    ax1.legend(loc="upper left", framealpha=0.92)
    ax1.set_title(r"B. Tracking consequence ($\Delta J$ mean $\pm$ 90\% equivalence-decision CI)")

    fig.savefig(
        FIG / "fig8_deadline_envelope.pdf",
        metadata={"Author": "", "Creator": "", "Producer": "", "Title": "Study C2 envelope"},
    )
    plt.close(fig)
    print("wrote", FIG / "fig8_deadline_envelope.pdf")


if __name__ == "__main__":
    main()
