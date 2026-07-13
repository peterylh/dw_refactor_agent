# retail_banking

`retail_banking` is a Doris warehouse baseline derived from the Apache Fineract
tenant schema. The source inventory is pinned to Fineract commit
`45d8e24f82c9c42c46a6762b24e102ad2c723824` so regeneration is reproducible.

## Asset coverage

| Layer | Tables | Purpose |
|---|---:|---|
| ODS | 277 | One mirror for each analytical tenant application table |
| DIM | 36 | Human-reviewed durable entities, reference data, and bridges |
| DWD | 68 | Human-reviewed events, relations, balances, and account snapshots |
| DWS | 18 | Contract-driven aggregates with explicit grain and metric behavior |
| ADS | 13 | KPI, reconciliation, schedule, and posting-monitor applications |
| Total | 412 | Physical warehouse tables |

The complete source disposition is documented in
[`docs/fineract_table_mapping.md`](docs/fineract_table_mapping.md) and is also
available as machine-readable YAML and CSV under `mappings/`.
`mappings/fineract_layer_mapping.yaml` expands each source through all generated
ODS/DIM/DWD/DWS/ADS targets. Every analytical source table has an ODS table and
a documented disposition. A source creates a direct DIM or DWD table only when
the mapping is marked `confidence: human_reviewed`;
candidate component, rule, bridge, security, and operational sources remain
available in ODS without pretending that every operational table is an
independent analytical fact.

All managed DDL columns and tables have persistent UUID4 schema identities.
Most generated tasks use deterministic full replay/replace-all semantics. Six
current-state snapshot captures append or replace only the actual execution-day
slice and explicitly reject historical replay. Four mutable account entities are
split into stable DIM attributes and dated DWD snapshots; the mapping does not
claim SCD2 behavior that is not implemented.

## Regeneration

From the repository root:

```bash
python warehouses/retail_banking/tools/build_assets.py inventory \
  --fineract-root /path/to/apache-fineract \
  --unresolved-overrides \
  warehouses/retail_banking/mappings/liquibase_unresolved_overrides.yaml
python warehouses/retail_banking/tools/generate_assets.py generate
python warehouses/retail_banking/generate_ods_data.py
```

Private benchmark gold is intentionally not stored in this repository. Generate
it only to an access-controlled path outside the entire Git checkout when
preparing an evaluator:

```bash
python warehouses/retail_banking/tools/generate_assets.py generate-private-gold \
  --private-gold-output /secure/evaluator/retail_banking_private_gold.yaml
```

`build_assets.py` recursively reconstructs the PostgreSQL clean-install tenant
schema from Fineract Liquibase changelogs, including PK/UK/FK, nullable and
default metadata. Unsupported raw SQL fails closed unless its exact source and
rationale are recorded in the override file. `generate_assets.py` consumes the
pinned snapshot plus the adjudicated contracts under `semantic_specs/`,
preserving IDs through `mappings/schema_identities.yaml`.
`generate_ods_data.py` creates deterministic,
synthetic smoke rows for all 277 ODS tables. These rows are test fixtures, not a
production-scale or statistically representative banking dataset.

The 277-table ODS scope deliberately excludes six Spring Batch scheduler tables.
Fineract's separate tenant-store database contributes another four control-plane
tables. Therefore Fineract owns 287 physical tables in this pinned scope, while
277 are bank-application tables materialized here; all ten exclusions are listed
in `mappings/excluded_control_tables.yaml`.

Validate the generated project with:

```bash
python -m dw_refactor_agent.ddl_deriver.schema_ids validate \
  --project retail_banking
python -m dw_refactor_agent.lineage.lineage_extractor \
  --project retail_banking --parallel 4 --no-cache
python -m dw_refactor_agent.execution.reinit_project \
  --project retail_banking --etl-dates 2025-01-15
```

After loading, every query in `quality/core_reconciliation.sql` must return zero
rows. It covers GL debit/credit balance, loan/deposit/GL referential integrity,
and reversal-safe loan aggregation.

## Scope boundary

This project models capabilities present in Apache Fineract: customers, loans,
deposits, accounting, cashiers, standing instructions, collateral, guarantors,
shares, surveys, and optional working-capital/investor modules. Pure Fineract
does not provide complete card acquiring, external payment-network settlement,
enterprise AML case management, market risk, or regulatory-capital source data;
those subjects are intentionally not fabricated as if Fineract supplied them.
