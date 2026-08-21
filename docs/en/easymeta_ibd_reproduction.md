# EasyMetagenome auditable validation and optional strict certification

The paper's EasyMetagenome evidence level is an **auditable real run**. The cohort contains 30 real
metagenomic samples: 10 NC, 10 CD, and 10 UC. Its frozen operational manifest is
`configs/case3_ibd_p0_technical_pilot_samples.tsv`.

The canonical run preserves 277 successful commands, step logs, standard tables, checksums, cleanup
receipts, and reports. These artifacts support execution audit and input-to-output lineage.

The run does not validate a causal IBD effect. All CD samples are from ERP017091 in China, whereas
all NC and UC samples are from PRJNA737472 in the USA. Disease label is completely confounded with
project, country, and likely laboratory batch for comparisons involving CD.

The original run did not capture complete tool versions, Git identity, a strict runtime lock, or
complete database identities. These fields remain disclosed as audit findings. Later evidence must
not be represented as run-local evidence for the original execution.

Run the independent machine audit with:

```bash
abi audit-result --result-dir RESULT --output RESULT/provenance/compliance_matrix.json
```

Acceptance as an auditable real run requires 30 unique runs with NC=10, CD=10, and UC=10; complete
step states; commands; logs; standard tables; checksum or tombstone coverage; machine validation;
and descriptive figures carrying the source-confounding limitation.

Strict certification is optional. Its configuration is
`configs/case3_ibd_real30_validation_pluspf_20240605_16cpu_120gb.yaml`. It adds mandatory tool
versions, a clean Git identity, a strict runtime lock, and verified host and Kraken2 identities.

The previously frozen single-project SRP131166 core53 workflow remains in the repository as a
historical and optional publication-reproduction track. Its 53-sample manifest and E1-E5 endpoints
must not be deleted, relabelled as the current validation cohort, or mixed into the 30-sample
evidence chain. When that track is run, ABI continues to report actual software versions, method
substitutions, and every E1-E5 divergence against the original preregistered thresholds.
