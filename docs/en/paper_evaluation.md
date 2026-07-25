# Paper Evaluation Protocol

## Evidence tracks

The ABI paper keeps agent operability and biological validity as separate evidence tracks.
ABI-Bench measures whether an agent can discover, plan, diagnose, authorize, execute, and inspect
bioinformatics workflows. Real-data case studies measure whether completed workflows recover
preregistered biological endpoints. A dry-run score cannot support a biological-validity claim,
and a successful case study cannot by itself establish that ABI helps an agent relative to a
baseline.

## Privacy-grounded local-model benchmark

The primary benchmark population is **locally deployable, self-hosted language models**. This
matches laboratories and clinical environments where raw genomic data, sample identifiers, paths,
and intermediate results cannot be sent to a hosted API. The paper's claim is therefore scoped to
the exact model checkpoints, serving configuration, quantization, and hardware that are measured;
it does not claim universal performance across all local or frontier models.

All pre-existing ABI-Bench outcomes are excluded from the analysis. A new study must begin from a
clean benchmark commit and a frozen study manifest.

### Confirmatory model design

- Select at least three independent model families before collecting outcomes.
- Within each family, evaluate a small and a medium configuration under matched precision or the
  same quantization method. Do not infer a parameter-scale effect from a native-versus-4-bit pair.
- Record checkpoint revision and hash, tokenizer, context length, temperature, maximum output
  tokens, inference engine and version, quantization, GPU model and VRAM, concurrency, timeout, and
  retry policy in a runtime attestation.
- Keep the same system prompt, task prompt, tool implementation, fixture, and serving policy across
  G1/G2/G3/G4 within each model configuration.
- Randomize or block the group order and hold concurrency constant to prevent thermal, memory, or
  queueing drift from becoming a treatment effect.
- Use repeated runs to estimate within-configuration variability. Treat model family—not the
  number of runs or tasks—as the unit for claims that generalize across models.

### Groups and estimands

| Group | Surface | Purpose |
| --- | --- | --- |
| G1 | README plus shell | Documentation-and-shell baseline |
| G2 | Generic tool calling | Tests whether unconstrained tools are sufficient |
| G3 | ABI lifecycle | Full contract-guided control layer |
| G4 | Information-matched static docs | Isolates callable lifecycle control from information volume |

The primary estimands are paired `G3−G1`, `G3−G2`, and `G3−G4` differences on the
`causal_core_v0_8` suite. Hidden diagnostic robustness is reported separately on
`hidden_robustness_v0_9`. ABI-native mechanism probes and real-execution tasks are descriptive and
must not be pooled into the primary causal score.

### Privacy and isolation controls

- Run the model server and benchmark harness inside the controlled local network.
- Disable outbound network access during scored tasks.
- Mount only the task fixture and required documentation; do not expose unrelated study data.
- Do not retain prompts or model traces outside the approved benchmark artifact root.
- Publish synthetic/public fixtures and aggregate scores, not protected sample content.

### Preflight gate

The score table may be populated only when all of the following are true:

1. the benchmark repository is clean and its commit is frozen;
2. task, fixture, scorer, group-profile, model-registry, and runtime-attestation hashes are frozen;
3. every required model × group × task × replicate cell is present;
4. G1/G2/G4 traces contain no ABI lifecycle leakage;
5. the public causal suite and hidden robustness suite pass their matching preflight checks;
6. exclusions and retry rules were fixed before outcomes were inspected.

Until then, the agent-operability rows in `metrics.tsv` remain `pending_new_run` with empty
estimates.

## Biological validation

Airway and ST93 MRSA are the paired running example. SCAPP is the flagship case study. Their
machine-readable endpoints, methods, and limitations live in `docs/paper_examples/`; their numeric
results are independent of the discarded ABI-Bench outcomes.

## Canonical metric table

`metrics.tsv` is long-form and claim-scoped. Every row records an evidence track, claim role,
status, workflow or model, dataset or suite, metric, estimate, interval when available,
numerator/denominator, unit, source, and limitation. Blank values are meaningful only when status
is `pending_new_run`, `pending_independent_truth`, or `not_assessed`.
