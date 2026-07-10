# Managed DDL Schema Identity Design

## Goal

Give every managed Doris table and column a persistent UUID identity so DDL
changes can distinguish rename, modification, addition, and replacement without
guessing from names or comments.

The first migration covers the `shop` and `finance_analytics` projects.

## Managed DDL Scope

Managed DDL files are all `*.sql` files returned by the project's configured
ODS, MID, and ADS `ddl` asset directories. For the first migration this means:

- `warehouses/shop/{ods,mid,ads}/ddl/**/*.sql`
- `warehouses/finance_analytics/{ods,mid,ads}/ddl/**/*.sql`

Fixture projects and generated artifacts are outside this migration.

## Metadata Format

Each managed DDL file has one UUID4 `table_id` near its header. Every column
definition has one UUID4 `column_id` comment immediately before it:

```sql
-- DWD order detail fact
-- table_id: 91ed8f6a-736d-4896-888e-f9225741b7fa
CREATE TABLE shop_dm.dwd_order_detail (
    -- column_id: 6bfa89c0-1e30-4f92-a25e-b5a39ab94880
    unit_price DECIMAL(12,2) NOT NULL COMMENT 'Unit price',
    -- column_id: 77eb791d-9856-4cc2-a77c-89f46ee626b2
    tax_amount DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT 'Tax amount'
);
```

IDs are identity metadata, not business metadata. They must not be embedded in
the Doris `COMMENT` value.

## Identity Lifecycle

- Creating a table generates a new `table_id` and new IDs for every column.
- Renaming a table preserves its `table_id` and all `column_id` values.
- Adding a column generates one new `column_id`.
- Renaming or modifying a column preserves its `column_id`.
- Copying a table or column creates new IDs; IDs do not represent cross-table
  business semantics.
- Split, merge, and replacement outputs receive new IDs.
- Reusing a deleted name does not permit reusing its old ID.

Table IDs and column IDs are globally unique across managed projects.

## Authoring Commands

Identity generation belongs to a dedicated authoring module:

```bash
python -m dw_refactor_agent.ddl_deriver.schema_ids init-project --project shop
python -m dw_refactor_agent.ddl_deriver.schema_ids init-file --file path/to/new.sql
python -m dw_refactor_agent.ddl_deriver.schema_ids assign-column --file path/to/table.sql --column new_name
python -m dw_refactor_agent.ddl_deriver.schema_ids validate --project shop
```

`init-project` is the explicit migration command. It fills only missing IDs,
preserves existing valid IDs, processes files in stable path/column order, and
is idempotent after the first successful write.

`init-file` is the new-table authoring command. It assigns a missing table ID
and IDs to all missing columns in one file.

`assign-column` is the normal existing-table command. It targets explicitly
named new columns and refuses to replace an existing ID.

`validate` is read-only and reports every error with a file and, when
applicable, column name.

The authoring commands use UUID4 and preserve DDL text except for inserted
identity comment lines. The deriver and refactor analyzer never generate IDs.

## Validation Rules

Strict validation rejects:

- a managed table with no `table_id`;
- a managed column with no `column_id`;
- malformed or non-UUID4 values;
- duplicate table IDs;
- duplicate column IDs, including duplicates across tables or projects;
- multiple ID markers attached to one table or column;
- an ID marker that is not associated with a parsed table or column;
- a DDL file that cannot be parsed.

Validation scans all configured managed projects when checking global
uniqueness, even when the requested report is for one project. Missing-ID and
parse-completeness checks apply to the requested project; other projects only
contribute IDs that are already present until they are migrated.

## Deriver Behavior

`ColumnDef` carries `column_id`. The parser reads the marker attached to the
column identifier by sqlglot.

For tables and columns with IDs, identity matching is exact:

- same ID and same name: compare mutable attributes;
- same ID and different name: emit rename;
- same ID, different name, and changed attributes: emit rename followed by
  modify using the final name;
- different IDs: emit drop/add rather than rename.

The `table_id` match remains the authoritative table rename signal. Jaccard
table matching and semantic column matching remain available only in explicit
legacy mode for external or historical DDL without IDs.

Project refactor workflows run in strict mode. Missing or conflicting IDs block
analysis before SQL is produced.

The existing behavior that generates a table UUID inside
`derive_ddl_changes()` is removed. Derivation is deterministic and read-only.

## Output Compatibility

Existing SQL ordering remains:

1. drop columns;
2. rename columns;
3. add and modify columns.

Rename JSON entries retain `old` and `new` and add audit fields when an ID is
available:

```json
{
  "old": "unit_price",
  "new": "price_unit",
  "column_id": "6bfa89c0-1e30-4f92-a25e-b5a39ab94880",
  "matched_by": "column_id"
}
```

Consumers that read only `old` and `new` remain compatible.

## Refactor Integration

`derive_project_ddl_changes()` validates the working-tree project DDL before
derivation and validates the parsed baseline identities. `refactor run analyze`
therefore fails closed with an actionable identity error instead of applying a
heuristic rename.

After the bulk migration lands, existing refactor runs must be restarted so the
baseline and working tree contain the same identity metadata generation.

## Lineage Boundary

The DDL UUID is a stable schema identity. Existing lineage `column_info.id` and
lineage edge column IDs are snapshot-local integer surrogate keys and remain
unchanged in this implementation. Internal names and documentation distinguish
the DDL value as `stable_column_id` when both concepts are present.

Persisting the stable UUID in lineage storage is a separate future change.

## Testing

Tests cover:

- parsing table and column UUID comments;
- project/file/column identity generation and idempotence;
- validation of missing, malformed, duplicate, and orphan IDs;
- exact table and column rename matching by ID;
- no rename for different IDs even when structures match;
- rename plus type, nullable, default, or comment modification;
- strict project derivation failure when IDs are missing;
- legacy behavior remaining explicitly available;
- successful validation of the migrated `shop` and `finance_analytics` assets.

## Migration

The migration is metadata-only:

1. Run `init-project` for `shop` and `finance_analytics`.
2. Validate both projects and global uniqueness.
3. Confirm no DDL content changed except inserted identity comments.
4. Run focused deriver/refactor tests and the full non-API suite.
5. Review generated IDs, parser boundaries, compatibility, and migration diff.
