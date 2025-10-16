# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a dbt (data build tool) project called "Jaffle Shop" - a fictional restaurant's e-commerce analytics platform. The project demonstrates dbt best practices for transforming raw data into analytics-ready models using SQL and Jinja templating.

**dbt Version Required**: >=1.5.0

## Common Commands

### Development Workflow

```bash
# Install dbt packages (run this first after cloning)
dbt deps

# Load sample data (1 year) into your warehouse
dbt seed --full-refresh --vars '{"load_source_data": true}'

# Build all models, tests, and snapshots
dbt build

# Build a specific model and its downstream dependencies
dbt build --select model_name+

# Run models only (no tests)
dbt run

# Run tests only
dbt test

# Run a specific model
dbt run --select model_name

# Compile models to see generated SQL without running
dbt compile
```

### Working with dbt Cloud CLI

If using dbt Cloud CLI (recommended for this project):
- The CLI automatically defers to production for unmodified models
- No need to manage `profiles.yml` for credentials

### Working with Larger Datasets

Generate synthetic data using `jafgen` (requires local setup):
```bash
jafgen 6  # Generate 6 years of data
rm -rf seeds/jaffle-data
mv jaffle-data seeds
dbt seed --full-refresh --vars '{"load_source_data": true}'
```

## Architecture

### Data Flow

```
Raw Sources (raw schema)
  → Staging Models (views)
    → Marts Models (tables)
```

### Layer Descriptions

**Sources** (`models/staging/__sources.yml`):
- Raw data tables in the `raw` schema under the `ecom` source
- Tables: `raw_customers`, `raw_orders`, `raw_items`, `raw_stores`, `raw_products`, `raw_supplies`

**Staging Layer** (`models/staging/`):
- Materialized as **views** (configured in `dbt_project.yml`)
- Purpose: Light transformations, renaming, type casting
- Naming convention: `stg_{entity_name}.sql`
- Pattern: Each staging model selects from one source table, renames columns with clear prefixes (e.g., `customer_id`, `order_id`)

**Marts Layer** (`models/marts/`):
- Materialized as **tables** (configured in `dbt_project.yml`)
- Purpose: Business logic, aggregations, joins across staging models
- Key models:
  - `customers.sql`: Customer lifetime metrics (orders, spend, customer type)
  - `orders.sql`: Order-level facts with food/drink classification and customer order sequence
  - `order_items.sql`: Line-item level detail
  - `products.sql`, `supplies.sql`, `locations.sql`: Dimension tables

### Model Relationships

- `customers` depends on `stg_customers` and `orders` (note the circular reference where marts reference each other)
- `orders` depends on `stg_orders` and `order_items`
- `order_items` depends on multiple staging models: `stg_order_items`, `stg_products`, `stg_supplies`

### Configuration Patterns

**Warehouse-Specific Settings**:
- Models use `dist` and `sort` keys for data warehouse optimization (e.g., Redshift)
- Example in `customers.sql`: `dist='customer_id'`
- Example in `orders.sql`: `dist='order_id', sort=['ordered_at', 'order_id']`

**Schema Override**:
- Seeds use `+schema: raw` to load into the raw schema
- Custom schema generation macro exists in `macros/generate_schema_name.sql`

## Macros

**`cents_to_dollars(column_name)`** (`macros/cents_to_dollars.sql`):
- Converts integer cent values to decimal dollar amounts
- Implements adapter-specific dispatch for different warehouses (default, postgres, bigquery, fabric)
- Example usage: `{{ cents_to_dollars('price') }}`

## Installed Packages

Defined in `packages.yml`:
- `dbt_utils` (1.1.1): Utility macros for common operations
- `dbt_date` (0.10.0): Date manipulation macros (timezone set to Australia/Sydney in vars)
- `audit_helper`: Data quality and comparison utilities
- `codegen` (0.13.1): Code generation helpers

## Variables

**Project Variables** (`dbt_project.yml`):
- `load_source_data`: Controls whether seed data is loaded (default: false)
  - Usage: `--vars '{"load_source_data": true}'`
- `dbt_date:time_zone`: Set to "Australia/Sydney" for date functions

## Testing & Data Quality

- Schema tests defined in YAML files alongside models (e.g., `stg_customers.yml`, `orders.yml`)
- Generic tests directory: `data-tests/`
- Freshness checks on source tables with `loaded_at_field` configured

## Important Notes

- This project uses dbt Cloud with project ID 275557 (configured in `dbt_project.yml`)
- Profile name is 'jaffle_shop'
- Seeds are **not** intended for production data loading - only for demo/tutorial purposes
- After loading data via seeds, remove `jaffle-data` from the seeds config in `dbt_project.yml`
- The project includes a MetricFlow time spine model (`metricflow_time_spine.sql`) for semantic layer usage
