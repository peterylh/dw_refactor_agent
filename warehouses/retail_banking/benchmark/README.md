# Retail Banking Semantic Cold-Start Benchmark Contract

This directory defines how `retail_banking` may be used as a model semantic
cold-start benchmark. The generated warehouse itself is a candidate dataset;
it is not the private gold bundle.

## Private gold boundary

The evaluator must build two physically separate artifacts:

- **Public input bundle:** only the files permitted by the selected track.
- **Private gold bundle:** adjudicated records conforming to
  `gold_schema.yaml`, label dictionaries, alias maps, and scoring code.

The public bundle must never contain model YAML, mappings, semantic specs,
business-process or semantic-subject catalogs, gold reports, or filenames that
encode expected labels. A model or agent being evaluated must not have read
access to the source checkout because the source checkout contains those
answers. Bundle manifests should record SHA-256 hashes, the Fineract commit,
the warehouse commit, the gold version, and the transformation seed.

`semantic_specs/dws_ads.yaml` is reviewer evidence used to prepare private gold;
it is explicitly forbidden from benchmark input.
`input_manifest.yaml` is the participant-bundle allow/deny contract.
Private gold is generated directly to evaluator-only storage and is never
written into or committed anywhere under this Git checkout.

Generate candidate gold to an access-controlled path, then build the physically
separated bundle outside the Git checkout:

```bash
python warehouses/retail_banking/tools/generate_assets.py generate-private-gold \
  --private-gold-output /secure/evaluator/retail_banking_private_gold.yaml
python warehouses/retail_banking/tools/build_benchmark_bundle.py \
  --track prefixless_role_blind \
  --private-gold /secure/evaluator/retail_banking_private_gold.yaml \
  --output /secure/path/retail_banking_bundle
```

Omit `--private-gold` to create a participant-only bundle. Every public bundle
contains `constraints.yaml`: source PK/UK/FK evidence for ODS mirrors plus the
Doris physical key for every asset. The role-blind track transforms referenced
table names with the same opaque alias map used for DDL and task SQL.
References to excluded control-plane tables remain visible as
`external_foreign_keys`; role-blind bundles replace those external names with
stable opaque aliases instead of silently dropping them.

Only `/secure/path/retail_banking_bundle/public/` may be given to a participant.
The sibling `evaluator/` directory contains the alias map and schema; it also
contains private gold only when the external `--private-gold` input is supplied.
It must remain evaluator-only.

## Tracks

### Named / taxonomy-assisted

Provides DDL, PK/UK/FK constraints, task SQL, business names, and the artificial
data-domain/business-area taxonomy. Models, mappings, process/subject catalogs,
and gold stay private. This is the development and diagnostic track. Results
must be labelled `taxonomy-assisted`, not zero-shot.

### Prefixless / role-blind

This is the primary test track. Remove `ods_`, `dim_`, `dwd_`, `dws_`, and
`ads_`; flatten ODS/MID/ADS directories; replace database names; remove SQL
comments and DDL comments. The same opaque asset role must be presented for all
tables. Business words, constraints, and SQL transformations remain because
they are legitimate semantic evidence.

ODS and ADS must be inferred and scored in this track. They must not be fixed
from the input directory as the existing generic benchmark runner does.

### Partially obfuscated

Apply deterministic aliases to table names and selected columns while retaining
types, PK/FK structure, SQL operations, and a limited description channel.
Because complete name removal makes business domain unidentifiable, this track
scores structural semantics, grain, metric behavior, and sensitivity, not
business process/domain unless enough evidence is deliberately retained.

### Template holdout

Use manually authored SQL involving windows, event expansion, state snapshots,
multi-source reconciliation, and SCD behavior. This prevents a model from
achieving a high score by recognizing only generated passthrough, `GROUP BY`,
and average-projection templates.

## Gold annotation

Each record follows `gold_schema.yaml`. Two reviewers independently annotate a
table, then an adjudicator resolves disagreement. Gold records retain reviewer
IDs, rationale, evidence paths, upstream commit, gold version, and any allowed
alternative answers.

Allowed alternatives are required for legitimate architecture choices. For
example, an account may be accepted as an entity dimension or accumulating
snapshot in a stated context; a loan-specific guarantor may be a participant
dimension or a factless relationship. Each alternative carries explicit credit
and rationale. They are not free-form aliases added after seeing model output.

Before publishing gold, every business-process code must belong to the frozen
canonical catalog. Domain IDs and codes are stored separately. Metric formulas
are normalized before comparison, but units, currency source, sign convention,
reversal policy, and aggregation behavior remain independently scored.

## Scoring

The benchmark reports layer accuracy, table-type and domain/process Macro-F1,
entity and grain set-F1, metric-class F1, normalized formula equivalence,
metric-behavior accuracy, sensitivity recall/F1, and hallucinated-field rate.
Both macro and micro aggregates are required.

The following are hard failures and are reported separately from weighted
accuracy:

- leaking a restricted field into an unrestricted output;
- summing currency amounts without a currency partition or conversion rule;
- marking balances fully additive over time;
- double-counting reversed transactions;
- fabricating a field or source table.

Exact weights and required fields are machine-readable in `gold_schema.yaml`.

## Release gates

A bundle may be called `gold_v1` only when:

1. every label is in a frozen catalog or explicitly nullable;
2. every record has two independent reviewers and adjudication;
3. allowed alternatives are frozen before model evaluation;
4. public/private manifests prove the forbidden files are absent;
5. role-blind transformations are deterministic and reversible only with the
   private alias map;
6. scorer tests cover all hard failures and formula normalization;
7. no test-table record is used to tune prompts or label dictionaries.
