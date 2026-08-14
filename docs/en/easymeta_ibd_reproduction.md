# EasyMeta IBD formal reproduction gates

The 30-sample manifest is an engineering stress test only. Formal biological conclusions use the
single-project SRP131166 cohort frozen from supplementary Table 1: all 13 NC, the first 20 CD runs
in accession sort order, and all 20 UC. Every row must contain paired ENA HTTPS URLs, MD5 values,
and positive byte counts.

Formal execution uses PlusPF 20240605 (about 64 GB compressed and 83 GB indexed) and the frozen
GRCh37/hg19 KneadData Bowtie2 index. The publisher exposes a per-file MD5 manifest, not an archive
SHA-256. ABI therefore records the publisher MD5-manifest URL, an ABI-computed archive SHA-256, and
a deterministic extracted content-tree SHA-256 without mislabeling the computed value as official.
The host index records the same source/archive/content identity chain.

The formal configuration rejects uncaptured tool versions, a dirty or missing Git identity, a
missing strict runtime lock, resource-content mismatch, and any manifest that differs from the
frozen Table 1 selection. Deleted intermediates are hashed before deletion; cleanup receipts link to
separate tombstone manifests. Run the independent machine audit with:

```bash
abi audit-result --result-dir RESULT --output RESULT/provenance/compliance_matrix.json
```

E1-E5 are written to `05_statistics/ibd_core53_endpoint_scores.json`. Any endpoint that misses its
preregistered threshold remains explicitly `divergent`; the workflow never converts divergence into
pass by interpretation.

The currently deployed cloud stack is KneadData 0.12.4, Trimmomatic 0.40, and Bowtie2 2.5.5 rather
than the literature stack 0.6.1/0.39/2.3.5.1. ABI captures the commands' actual versions and marks
the overall result and `method_compatibility` as `divergent`; individual E1-E5 outcomes remain
reported against their preregistered thresholds.
