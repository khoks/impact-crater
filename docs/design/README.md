# Design artefacts

Raw outputs of the multi-agent design passes that preceded the E-2.10 / E-2.11 / E-2.12 build sessions (June 2026). They were produced under `.scratch/` and promoted here on 2026-10-24 (S-2.13.6) because the tracker cites them. They are historical working material, not maintained documents: the shipped design is described in the ADRs (ADR-0017 to ADR-0020) and in `docs/architecture/PIPELINE_DATAFLOW.md`.

| File | Date | What it is |
|---|---|---|
| `designs.json` | 2026-06-29 | Per-subsystem design proposals for the feedback-driven curation-quality pass (E-2.10): confirmed mechanisms, proposed changes, affected files, from a parallel agent workflow. |
| `critique.md` | 2026-06-29 | The adversarial critique of those proposals — verified corrections, conflicts between designs, and what was already true in the code. |
| `refinement_design.json` | 2026-06-30 | The six-agent design + synthesis for open-ended refinement and the shared curation levers (PlanDirective, ReservationSet, agentic refinement loop) that became E-2.12 (ADR-0019 / ADR-0020). |
