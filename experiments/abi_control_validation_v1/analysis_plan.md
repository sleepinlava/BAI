# ABI Control-Layer Validation v1 — Analysis Plan

## 1. Estimands

### Primary

For each of the 18 tasks, estimate the mean CVC across five frozen replicates in:

- ABI full;
- matched advisory control.

The primary estimand is the mean task-level paired risk difference:

```text
mean_task(CVC_abi_full − CVC_matched_advisory)
```

The task, not the replicate, is the unit of generalization.

### Key mechanism estimand

Within T3 preflight and T5 output-acceptance tasks:

```text
mean_task(CVC_abi_full − CVC_abi_no_runtime_contracts)
```

Interpret this only as the contribution of pre/post runtime contracts in the affected
tasks. Do not call it the total contribution of all ABI components.

## 2. Secondary outcomes

Report by applicable denominator:

- workflow-selection accuracy for T1;
- valid-plan rate for T2;
- pre-execution fault detection and external-tool calls before block for T3;
- unauthorized attempts and realized side effects for T4;
- false acceptance for T5;
- root-cause accuracy and recovery success for T6;
- cross-verifiable provenance completeness;
- wall time, token use, tool calls, and retries.

Never use all trials as the denominator for a category-specific metric.

## 3. Uncertainty

Use a task-level paired nonparametric bootstrap:

1. sample 18 tasks with replacement;
2. retain all conditions and replicates belonging to each sampled task;
3. recompute the mean task-level paired difference;
4. use a frozen bootstrap seed and at least 10,000 draws;
5. report the percentile 95% confidence interval.

For the contract ablation, resample only the six applicable T3/T5 tasks.

Report raw numerators and denominators alongside intervals. A mixed-effects logistic
model with condition as a fixed effect and task as a random intercept is supplementary
sensitivity analysis, not the primary result.

## 4. Repeated reliability

For every task and condition, report:

- successes out of five;
- all-five-success indicator;
- distribution of 0–5 successes.

Do not report best-of-five as reliability evidence.

## 5. Robustness model

The second model is a supplementary sensitivity analysis on the frozen six-task subset.
Report its results separately. With two checkpoints, do not claim universal model-family
generalization or a model-size interaction.

## 6. Exclusions

Allowed trial-level exclusions:

- container failed before the prompt was delivered;
- model service was unavailable before receiving task context;
- artifact storage failed and no complete transcript/event/workspace record exists;
- a condition-independent fixture corruption is proven by its hash.

Not allowed:

- model produced an invalid tool call;
- model timed out after receiving the task;
- model exhausted token/tool/retry budget;
- ABI or advisory interface returned an error during normal use;
- outcome was unfavorable;
- Agent chose a wrong workflow or recovery action.

Excluded cells are rerun only under a rule frozen before confirmation. Every exclusion
and rerun keeps the original record and reason.

## 7. Missing cells

Do not silently average incomplete blocks. Report:

- planned trials;
- completed trials;
- excluded trials;
- valid analysis trials;
- missing cells by condition and reason.

The primary analysis requires complete paired task-condition data or a preregistered
paired missing-data rule.

## 8. Multiple outcomes

CVC is the sole primary outcome. Secondary metrics explain failure modes and are
reported with intervals without selecting them by statistical significance. If formal
hypothesis tests are added for the three mechanism outcomes, apply Holm correction and
retain all estimates regardless of p-value.

## 9. Manuscript reporting

Main text should contain at most:

1. ABI full versus advisory CVC paired difference and 95% CI;
2. pre-execution fault detection and false-acceptance results;
3. the runtime-contract ablation difference;
4. median control overhead;
5. one short real-data example from the separate biological-validation track.

Supplementary Information contains:

- all 18 task results;
- the robustness model;
- raw counts and repeated-reliability distributions;
- every prompt and condition descriptor;
- semantic coverage audit;
- grader audit;
- model, image, runtime-lock, resource, and contract identities;
- exclusions and deviations.

## 10. Claim boundaries

Permitted:

> In the frozen model and task configurations, ABI increased controlled valid
> completion relative to an information-matched advisory interface.

If supported:

> Removing runtime contracts reduced fault blocking and output rejection in the
> targeted preflight and output-acceptance tasks.

Not permitted:

- ABI guarantees biologically correct conclusions;
- ABI improves every model or workflow;
- ABI makes small models equivalent to frontier models;
- mock/dry-run success proves biological validity;
- one model's results establish general Agent behavior.
