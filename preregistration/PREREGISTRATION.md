# Study C preregistration (anonymous)

Topology: three physical machines (plant workstation, inference workstation, Pi gateway).
Author hostnames and addresses are omitted. Apparatus roles are retained.

Seed rule: s_i = H(master, policy, regime, T, i). Excludes admission arm and deadline.
Same scenario bank across D_L, D_B, D_T. Master seed: 2026080701.

## C1 (fixed Exit-3)

- D = 150 ms; NOM + CPU; n = 80 paired episodes each
- Primary L4: integrated J = integral |CTE| dt; delta_eq = 0.005; CI containment
- Level 3: plant-step I_u from COMMAND_APPLIED

## C2

- Core: CPU x {D_L, D_B, D_T}; n = 40 paired scenarios
- Sanity: NOM x D_B (not pooled into the core envelope)
- Primary L4: delta J (integrated)
- Scenario-block bootstrap
- Deadlines frozen from an independent latency-only calibration before any tracking analysis:
  D_L = 71 ms, D_B = 61 ms, D_T = 51 ms

## Long horizon

- D_long = D_B; T = 15 s; n = 40
- Primary: J_bar = J/T with its own equivalence margin

## Study A p95

- 1000 samples / session; 15 sessions for the two robot-policy artifacts
- Report r_95 and Delta_95 (ms)

## Out of scope

Physical-robot validation; hardware re-run from this artifact.
This file restates the preregistered design. It is not additional scientific argument.
