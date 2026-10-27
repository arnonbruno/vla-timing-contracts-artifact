Anonymous supplementary artifact
================================

The letter is self-contained. This archive is optional reproducibility
material. It is not an extra appendix.

What you can check
------------------
From frozen slim traces and summaries, recompute:

- Study C2 (CPU core, n=40 / deadline): MO false-feasible step counts
  2/0/37, plant-input I_u, delta-J, and 90% CIs
- Study C1 paired delta-J means (n=80 / regime)
- Study A robot-policy p95 headlines (15 sessions)
- Long-horizon frozen verdict (equivalence inconclusive)
- Study C2 envelope figure (Fig. 4 in the manuscript;
  internal reproduction filename fig8_deadline_envelope.pdf)

Tight-deadline check: delta-J = 0.00818, 90% CI [0.00498, 0.01153]
(equivalence not established; interval not entirely above +0.005).

This is not a three-machine hardware re-run. External policy weights
are not included.

Software
--------
- Python 3.10 or newer
- numpy >= 1.24
- matplotlib >= 3.7

Install with either:

  python3 -m pip install -r environment/requirements.txt

or:

  conda env create -f environment/environment.yml
  conda activate ral-anonymous-artifact

Directory structure
-------------------
ReadMe.txt             This file (IEEE multimedia user guide)
Summary.txt            One-paragraph contribution of the attachment
README.md              Short pointer to this file
LICENSE                Apache License 2.0 (no author name)
preregistration/       Frozen design notes and scenario manifests
code/analysis/         Claim check, C2/long-horizon analyzers, Fig. 4
code/replay/           Plant-command reconstruction (COMMAND_APPLIED -> I_u)
code/study_a|b|c/      Notes only; no extra measurement stacks
data/study_c/sessions/ Slim C1 (320), C2 (320),
                       long-horizon (80) records
data/study_a|b/        Notes; raw GPU/timing dumps omitted
results/c1/            Frozen C1 summary
results/c2/            Frozen C2 envelope + regenerated Fig. 4
results/long_horizon/  Frozen long-horizon summary
results/study_a_p95/   Frozen Study A p50/p95 summaries
results/study_b/       Frozen Study B summary
results/audits/        I_u / L_model audits and progressive-exit scope
scripts/reproduce_all.sh
environment/           requirements.txt and environment.yml
CORE_MANIFEST.sha256   Hashes of the core files listed inside, not all files

Reproduction
------------
From the unzipped ral_anonymous_artifact/ directory:

  bash scripts/reproduce_all.sh

Or the same steps without pip:

  python3 code/analysis/verify_paper_claims.py
  python3 code/analysis/analyze_c2_envelope.py
  python3 code/analysis/analyze_long_horizon.py
  python3 code/analysis/generate_fig8_envelope.py

verify_paper_claims.py must print PASS.

