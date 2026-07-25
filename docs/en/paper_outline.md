# ABI Paper Outline

## Working title

**ABI: Contract-Compiled Control for Private, Agent-Mediated Bioinformatics**

## Positioning and claim boundary

ABI is a systems/technique contribution, not a new biological learning algorithm and not a
single analysis plugin. It is a plugin-based control layer that compiles machine-readable
biological workflow contracts into inspectable, permission-gated execution and evidence. YAML
configuration and the declarative DAG are important sources of truth, but they do not execute or
interpret an analysis by themselves. Plugin code, tool and resource contracts, runtime adapters,
output assertions, standard tables, provenance, reports, and explicit limitations complete the
lifecycle.

The paper makes two separate empirical claims:

1. **Agent operability:** on a newly run, preregistered benchmark of locally deployable models,
   ABI improves reliable task completion relative to shell, generic tools, and
   information-matched static documentation.
2. **Biological validity:** on real public data, ABI completes auditable analyses and recovers
   preregistered biological endpoints. Airway and bacterial WGS form the paired running example;
   SCAPP is the flagship case study.

No pre-existing ABI-Bench score is evidence for the first claim. The canonical metric table marks
those cells `pending_new_run` until a clean, locally hosted confirmatory experiment passes
preflight.

## Introduction — six-paragraph draft

**1. Background and motivation.** Biological analyses increasingly combine many command-line
tools, reference databases, environment-specific dependencies, and study-specific statistical
choices. An AI agent can help operate this machinery, but sensitive genomic data often cannot be
sent to a hosted model, making locally deployable models the realistic setting for many
laboratories. Consider two public studies that we use throughout this paper. Reanalyzing the
Airway RNA-seq experiment requires the agent to preserve the paired donor design while comparing
dexamethasone with untreated samples. Reanalyzing six ST93 MRSA isolates requires a different
chain of quality control, assembly, annotation, sequence typing, and antimicrobial-resistance
analysis. The desired interaction is the same in both cases: a researcher states the biological
goal, reviews a concrete plan, authorizes execution, and receives traceable evidence rather than
an opaque sequence of shell commands.

**2. Limitations of existing interfaces.** Three capabilities are missing when a general-purpose
agent operates these analyses directly. First, repository documentation and shell access do not
provide an executable contract that prevents the agent from inventing parameters, paths, or
workflow branches. Second, generic tool-calling exposes individual actions without binding them
to dependency order, resource readiness, permission boundaries, and expected outputs. Third,
traditional workflow descriptions can schedule commands but do not necessarily expose a compact
agent-facing lifecycle for discovery, diagnosis, result inspection, biological interpretation,
and limitation disclosure. These gaps are especially consequential for smaller local models,
whose privacy advantage is useful only if constrained operation remains reliable.

**3. Problem essence and goal.** Our goal is to make heterogeneous bioinformatics analyses
operable by local AI agents without asking those agents to synthesize a new shell pipeline for
every study. The hard constraints are that biological choices remain plugin-specific, plans are
deterministic and reviewable before execution, real work requires explicit authorization,
software and database identities remain recoverable, and execution success is never conflated
with biological validity. We therefore treat an analysis as a contract-compiled lifecycle rather
than as free-form command generation.

**4. Key challenges.** This goal creates three challenges. First, analysis types differ in sample
models, conditional branches, tools, databases, outputs, and scientific assertions; a single
hard-coded planner cannot preserve this heterogeneity, while bespoke interfaces do not scale.
Second, a syntactically plausible plan can still fail because an executable, environment,
reference, permission, or intermediate artifact is missing; checking only YAML or DAG structure
does not close the plan-to-execution gap. Third, a completed run is not automatically a correct
scientific result; each endpoint needs an explicit comparator, denominator, evidence status, and
limitation, and some conclusions must remain not assessed.

**5. Solution overview.** ABI addresses these challenges with three corresponding mechanisms.
Analysis plugins declare biological identity, configuration and sample schemas, a DAG, tool and
resource contracts, output assertions, standard tables, and report metadata; the shared core
compiles these declarations into a backend-neutral execution plan. A common lifecycle—query,
plan, check, dry-run, authorize, run, inspect, and report—resolves environments and resources,
enforces permissions and step contracts, and records provenance across local, container,
Nextflow, HPC, and service adapters. Finally, ABI publishes claim-scoped evidence tables, figures,
methods, and limitations. In the paired running example this preserves the Airway donor-aware
design and the WGS MLST/AMR endpoints under the same control surface, while retaining their
different biological semantics.

**6. Contributions.** This paper makes four contributions. (1) It introduces ABI, a
contract-compiled, plugin-based control layer for private agent-mediated bioinformatics
(Sections 2–4). (2) It defines a permission-gated execution and evidence lifecycle that connects
declarative plans to runtime checks, standard outputs, provenance, and explicit claim boundaries
(Sections 3–4). (3) It introduces a preregistered evaluation for locally deployable model
families that separates interface effects from information volume and reports only new,
preflight-eligible runs (Section 5). (4) It validates the approach on the Airway and ST93 MRSA
running examples and uses the SCAPP plasmidome as a flagship case study with an independent-truth
gate for headline precision, recall, and F1 (Sections 6–7).

## System architecture

Explain the thick-core, thin-adapter architecture: plugin manifests, `pipeline_dag.yaml`, tool and
resource contracts, compiled plans, runtime locks, provenance writers, CLI/MCP/HTTP adapters,
standard tables, reports, and SciPlot figures. Make clear that the plugin owns biological choices
while the core owns reusable execution control.

## Evaluation design

Use locally hosted models as the primary deployment setting because raw genomic data may be
privacy-sensitive. The confirmatory design uses at least three model families, a matched small and
medium configuration within each family, identical serving precision/quantization within each
pair, frozen runtime attestations, and the G1/G2/G3/G4 comparison. Treat model family as the unit
of external generalization; repeated runs estimate within-configuration variability.

## Results and case studies

- Report new ABI-Bench results only after the clean-run preflight passes. Do not import historical
  pilot scores into the paper metric table.
- Use Airway and ST93 MRSA as a paired running example for cross-plugin execution and biological
  endpoint recovery.
- Use SCAPP as the flagship case study. Report completed execution and auxiliary plasmid evidence,
  but withhold paper-method precision, recall, and F1 until the independent K127 two-stage truth
  reconstruction is complete.

## Reproducibility appendix

The root `metrics.tsv` is the canonical claim-scoped metric registry. Supporting machine-readable
tables and FigureSpecs live in `docs/paper_examples/`. Every numeric claim records its evidence
track, status, numerator/denominator when applicable, source, and limitation.
