# AI-Powered Data Quality Audit System - Implementation Guide

## Overview

This guide outlines how to build an AI-powered system that analyzes dbt mart models and generates comprehensive **CSV-based data quality audit reports**. The system uses AWS Lambda, Amazon Bedrock (Claude), and Redshift to act as a UAT validator that business SMEs can review.

**Key Difference from Traditional dbt Tests**: Instead of generating dbt YAML tests, we generate actionable CSV reports with test queries, defect counts, and real examples of data quality issues.

## Architecture Overview

```
┌─────────────────┐
│   dbt Project   │
│   (Git/S3)      │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│          AWS Lambda Function(s)              │
│  ┌────────────────────────────────────────┐  │
│  │  1. Read dbt mart model files (.sql)  │  │
│  │  2. Query Redshift for metadata        │  │
│  │  3. Send context to Bedrock Agent      │  │
│  │  4. Generate test queries              │  │
│  │  5. Execute tests against Redshift     │  │
│  │  6. Capture defects with examples      │  │
│  │  7. Write CSV reports to S3            │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐    ┌──────────────────────┐
│    Redshift     │    │  Amazon Bedrock      │
│    Database     │    │  Agents (Claude 3.5) │
└─────────────────┘    └──────────────────────┘
         │
         ▼
┌─────────────────┐
│   S3 Bucket     │
│  (CSV Reports)  │
└─────────────────┘
```

## Output Format: CSV Data Quality Reports

For each mart model (e.g., `customers`, `orders`, `order_items`), generate a CSV file: `{model_name}_data_quality_report.csv`

### CSV Schema

| Column Name | Description | Example |
|------------|-------------|---------|
| `test_name` | Unique identifier for the test | `unique_customer_id` |
| `test_category` | Category of test | `Uniqueness`, `Nullability`, `Date Validity`, `Business Logic`, `Referential Integrity`, `Value Range` |
| `test_description` | Human-readable description | "Verifies that customer_id is unique across all rows" |
| `test_query` | Actual SQL query executed | `SELECT customer_id, COUNT(*) as dup_count FROM prod.customers GROUP BY 1 HAVING COUNT(*) > 1` |
| `defect_count` | Number of violations found | `3` or `0` |
| `defect_examples` | Sample records showing violations (limit 5-10) | `customer_id=123, dup_count=2; customer_id=456, dup_count=3` |
| `status` | Test result | `PASS`, `FAIL`, `WARNING` |
| `severity` | Impact level | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` |
| `notes` | Additional context | "Found 3 duplicate customer IDs - investigate data load process" |
| `execution_timestamp` | When test was run | `2025-10-16 14:23:45 UTC` |

### Example CSV Output for `customers_data_quality_report.csv`

```csv
test_name,test_category,test_description,test_query,defect_count,defect_examples,status,severity,notes,execution_timestamp
unique_customer_id,Uniqueness,Verifies customer_id is unique across all rows,"SELECT customer_id, COUNT(*) FROM prod.customers GROUP BY 1 HAVING COUNT(*) > 1",0,,PASS,CRITICAL,No duplicate customer_ids found,2025-10-16 14:23:45
no_null_customer_id,Nullability,Ensures customer_id is never NULL,SELECT COUNT(*) FROM prod.customers WHERE customer_id IS NULL,0,,PASS,CRITICAL,All customer records have valid IDs,2025-10-16 14:23:45
no_future_orders,Date Validity,Checks for orders dated in the future,"SELECT customer_id, first_ordered_at FROM prod.customers WHERE first_ordered_at > CURRENT_DATE LIMIT 5",3,"customer_id=123, first_ordered_at=2026-01-15; customer_id=456, first_ordered_at=2026-02-20; customer_id=789, first_ordered_at=2026-03-10",FAIL,HIGH,Found 3 customers with future order dates - likely data entry errors,2025-10-16 14:23:46
no_negative_spend,Business Logic,Validates that lifetime spend is never negative,SELECT customer_id FROM prod.customers WHERE lifetime_spend < 0 LIMIT 5,0,,PASS,HIGH,All spend amounts are non-negative,2025-10-16 14:23:46
referential_integrity_orders,Referential Integrity,Ensures all customers exist in orders table,"SELECT c.customer_id FROM prod.customers c LEFT JOIN prod.orders o ON c.customer_id = o.customer_id WHERE o.customer_id IS NULL AND c.count_lifetime_orders > 0 LIMIT 5",12,"customer_id=234; customer_id=567; customer_id=890; customer_id=1234; customer_id=5678",FAIL,MEDIUM,12 customers show order count > 0 but have no matching orders,2025-10-16 14:23:47
lifetime_spend_matches_orders,Business Logic,Verifies lifetime_spend equals sum of orders,"SELECT c.customer_id, c.lifetime_spend, SUM(o.order_total) as actual_spend FROM prod.customers c JOIN prod.orders o ON c.customer_id = o.customer_id GROUP BY 1, 2 HAVING ABS(c.lifetime_spend - SUM(o.order_total)) > 0.01 LIMIT 5",5,"customer_id=111, expected=500.00, actual=499.50; customer_id=222, expected=1000.00, actual=1001.00",FAIL,HIGH,5 customers have mismatched lifetime spend calculations,2025-10-16 14:23:48
customer_type_valid_values,Value Range,Ensures customer_type contains only valid values,"SELECT DISTINCT customer_type FROM prod.customers WHERE customer_type NOT IN ('new', 'returning')",0,,PASS,MEDIUM,All customer_type values are valid,2025-10-16 14:23:48
```

## Test Categories to Generate

The Bedrock agent should suggest tests across these categories:

### 1. Uniqueness Tests
- Primary key columns are unique
- Composite key uniqueness
- Natural key uniqueness

### 2. Nullability Tests
- Required fields are not NULL
- Expected NULL patterns (e.g., "last_ordered_at can be NULL for customers with no orders")

### 3. Referential Integrity Tests
- Foreign keys exist in parent tables
- Child records exist for parent records (when expected)
- Orphaned records detection

### 4. Date Validity Tests
- No future dates (where not expected)
- Dates are not before business start date
- Created_at <= updated_at relationships
- Date ranges make sense (e.g., order_date <= delivery_date)

### 5. Business Logic Tests
- Calculated fields match their components (e.g., order_total = subtotal + tax)
- Aggregations match detail records
- Status transitions are valid
- Counts match (e.g., count_orders matches actual order records)

### 6. Value Range Tests
- Numeric fields within expected ranges (no negative prices, reasonable quantities)
- Categorical fields contain only valid values
- Percentages between 0 and 100
- Monetary amounts are reasonable

### 7. Data Consistency Tests
- Related fields are consistent (e.g., if is_repeat_buyer = true, count_orders > 1)
- Status fields match underlying data
- Aggregation fields match granular data

## Phase 1: Single Lambda MVP

### What You'll Need to Set Up (YOUR TASKS)

#### 1.1 AWS Resources
- [ ] **Redshift Cluster**: Ensure Jaffle Shop data is loaded in `prod` schema
- [ ] **S3 Bucket**: Create bucket for CSV reports (e.g., `jaffle-shop-data-quality-reports`)
- [ ] **IAM Role for Lambda**: Create role with permissions for:
  - Redshift Data API access
  - Bedrock InvokeModel access
  - S3 PutObject access
  - CloudWatch Logs access
- [ ] **Bedrock Access**: Enable Claude 3.5 Sonnet model in your AWS region
- [ ] **Lambda Function**: Create Python 3.11+ Lambda with 512MB memory, 5 minute timeout

#### 1.2 Redshift Setup
- [ ] Ensure dbt models are built in `prod` schema: `customers`, `orders`, `order_items`, `products`, `supplies`, `locations`
- [ ] Create Redshift user for Lambda with SELECT permissions on `prod` schema
- [ ] Note Redshift cluster identifier, database name, and workgroup for Lambda configuration

#### 1.3 Store dbt Project Files in S3
- [ ] Upload `models/marts/*.sql` files to S3 bucket (e.g., `s3://jaffle-shop-dbt-models/marts/`)
- [ ] Upload `models/marts/*.yml` files to S3 for schema documentation
- [ ] Set up S3 path that Lambda can read from

### What We'll Build Together (CLAUDE CODE TASKS)

#### 1.4 Lambda Function Structure
```
lambda_function/
├── lambda_function.py          # Main handler
├── dbt_parser.py              # Parse dbt SQL and YAML files from S3
├── redshift_client.py         # Redshift Data API queries
├── bedrock_client.py          # Bedrock API calls for test generation
├── test_executor.py           # Execute tests and capture defects
├── csv_writer.py              # Generate CSV reports
├── requirements.txt           # Dependencies
└── config.py                  # Configuration constants
```

#### 1.5 Core Components to Build

**Component 1: dbt_parser.py**
- [ ] Read model SQL from S3
- [ ] Parse model YAML for column descriptions
- [ ] Extract referenced models (dependencies)
- [ ] Extract model configuration (materialization, dist, sort keys)

**Component 2: redshift_client.py**
- [ ] Connect using Redshift Data API (boto3)
- [ ] Query table metadata from `information_schema`
- [ ] Get row counts, distinct counts, null counts
- [ ] Sample data retrieval (first 10 rows)
- [ ] Execute test queries and return results
- [ ] Format defect examples from query results

**Component 3: bedrock_client.py**
- [ ] Invoke Claude 3.5 Sonnet via Bedrock
- [ ] Format prompts with dbt context + Redshift metadata
- [ ] Parse Claude's response (structured JSON with test definitions)
- [ ] Handle retries and error cases

**Component 4: test_executor.py**
- [ ] Execute each generated test query against Redshift
- [ ] Count defects
- [ ] Extract example records (limit 5-10)
- [ ] Format defect examples as semicolon-delimited strings
- [ ] Determine status (PASS/FAIL/WARNING)
- [ ] Assign severity based on test category

**Component 5: csv_writer.py**
- [ ] Create CSV with proper headers
- [ ] Write test results to rows
- [ ] Upload CSV to S3
- [ ] Handle special characters in defect examples

**Component 6: lambda_function.py (Handler)**
- [ ] Parse Lambda event (which mart model to audit)
- [ ] Orchestrate the flow: parse → analyze → generate tests → execute → report
- [ ] Error handling and logging
- [ ] Return S3 path to generated CSV

### Step-by-Step Implementation Plan

#### STEP 1: Local Development Setup (CLAUDE CODE)
- [ ] Create project structure in `lambda_function/` directory
- [ ] Set up `requirements.txt` with: `boto3`, `pandas`, `python-dateutil`
- [ ] Create `config.py` with placeholder values for S3 paths, Redshift details
- [ ] Set up basic logging

#### STEP 2: Build Redshift Client (CLAUDE CODE)
- [ ] Implement connection using Redshift Data API
- [ ] Create method: `get_table_metadata(schema, table_name)`
  - Returns: column names, data types, nullability
- [ ] Create method: `get_table_stats(schema, table_name)`
  - Returns: row count, null counts per column, distinct counts
- [ ] Create method: `get_sample_data(schema, table_name, limit=10)`
  - Returns: sample rows as list of dicts
- [ ] Create method: `execute_query(sql)`
  - Returns: query results as list of dicts
- [ ] Create method: `format_defect_examples(query_results, limit=5)`
  - Returns: semicolon-delimited string of defect examples

#### STEP 3: Build dbt Parser (CLAUDE CODE)
- [ ] Implement S3 file reader using boto3
- [ ] Parse SQL file to extract model definition
- [ ] Parse YAML file to extract descriptions and existing tests
- [ ] Extract `ref()` calls to understand dependencies
- [ ] Return structured dict with model context

#### STEP 4: Build Bedrock Client with Prompt Engineering (CLAUDE CODE)
- [ ] Create prompt template for test generation
- [ ] Include in prompt:
  - Model SQL code
  - Column metadata (names, types, nullability)
  - Sample data (first 10 rows)
  - Existing descriptions from YAML
  - Dependencies on other models
- [ ] Request Claude to return JSON array of test definitions:
  ```json
  [
    {
      "test_name": "unique_customer_id",
      "test_category": "Uniqueness",
      "test_description": "...",
      "test_query": "SELECT ...",
      "severity": "CRITICAL"
    }
  ]
  ```
- [ ] Parse Claude's JSON response
- [ ] Validate test queries for SQL injection risks (basic sanitation)

#### STEP 5: Build Test Executor (CLAUDE CODE)
- [ ] For each test definition from Bedrock:
  - [ ] Execute `test_query` against Redshift
  - [ ] Count rows returned (defect_count)
  - [ ] If defects > 0, format first 5 examples
  - [ ] Determine status: `PASS` if defect_count=0, else `FAIL`
  - [ ] Add execution timestamp
- [ ] Return list of test results

#### STEP 6: Build CSV Writer (CLAUDE CODE)
- [ ] Use `pandas` to create DataFrame from test results
- [ ] Write to CSV with proper escaping
- [ ] Upload CSV to S3 bucket
- [ ] Return S3 URI

#### STEP 7: Wire Up Lambda Handler (CLAUDE CODE)
- [ ] Create handler that accepts event: `{"model_name": "customers"}`
- [ ] Orchestrate full flow
- [ ] Add comprehensive error handling
- [ ] Log each step for debugging
- [ ] Return success response with S3 path to CSV

#### STEP 8: Package and Deploy (YOUR TASK)
- [ ] Zip Lambda function with dependencies
- [ ] Upload to AWS Lambda
- [ ] Configure environment variables:
  - `REDSHIFT_CLUSTER_ID`
  - `REDSHIFT_DATABASE`
  - `REDSHIFT_WORKGROUP`
  - `REDSHIFT_SCHEMA` (e.g., `prod`)
  - `S3_DBT_MODELS_BUCKET`
  - `S3_DBT_MODELS_PREFIX`
  - `S3_REPORTS_BUCKET`
  - `S3_REPORTS_PREFIX`
  - `BEDROCK_MODEL_ID` (e.g., `anthropic.claude-3-5-sonnet-20241022-v2:0`)
- [ ] Test with a single model: `{"model_name": "customers"}`

#### STEP 9: Test and Iterate (YOUR TASK + CLAUDE CODE)
- [ ] YOU: Invoke Lambda with test event
- [ ] YOU: Download CSV from S3 and review
- [ ] CLAUDE CODE: Fix bugs, improve prompts, refine test queries based on your feedback
- [ ] Iterate until results are satisfactory

## Phase 2: Multi-Model Batch Processing

### Enhancements

#### 2.1 Lambda Orchestrator (YOUR TASK + CLAUDE CODE)
- [ ] CLAUDE CODE: Create second Lambda that triggers the test Lambda for all mart models
- [ ] CLAUDE CODE: Read list of models from `models/marts/` in S3
- [ ] CLAUDE CODE: Invoke test Lambda for each model (parallel or sequential)
- [ ] YOU: Deploy orchestrator Lambda
- [ ] YOU: Test full batch run

#### 2.2 Enhanced Context Gathering (CLAUDE CODE)
- [ ] Add queries to detect actual data issues:
  ```sql
  -- Find columns with high null rates
  -- Identify potential composite unique keys
  -- Detect de facto foreign key relationships
  -- Find categorical columns (low cardinality)
  -- Identify date columns
  -- Find numeric columns
  ```
- [ ] Pass this enriched context to Bedrock for smarter test suggestions

#### 2.3 Test Prioritization (CLAUDE CODE)
- [ ] Ask Claude to rank tests by importance
- [ ] Execute critical tests first
- [ ] If critical tests fail, flag in CSV with higher severity

## Phase 3: Bedrock Agents (Advanced)

### 3.1 Multi-Agent Architecture

Instead of single Bedrock invocation, use Bedrock Agents with specialized capabilities:

**Agent 1: Schema Analyzer Agent** (YOUR TASK to configure + CLAUDE CODE to define)
- Role: Analyzes table schema and metadata
- Tools:
  - Query Redshift metadata
  - Read dbt YAML
- Output: Structured analysis of table (primary keys, foreign keys, data types, business entities)

**Agent 2: Test Generator Agent** (YOUR TASK to configure + CLAUDE CODE to define)
- Role: Generates specific test queries based on schema analysis
- Input: Schema analysis from Agent 1
- Output: JSON array of test definitions with queries

**Agent 3: Defect Analyzer Agent** (YOUR TASK to configure + CLAUDE CODE to define)
- Role: Analyzes failed tests and provides recommendations
- Input: Test results with failures
- Output: Root cause analysis and suggested fixes

#### 3.2 Implementation Steps for Agents

**YOUR TASKS:**
- [ ] Create Bedrock Agent in AWS Console for each agent above
- [ ] Define action groups for each agent
- [ ] Configure agent instructions (we'll write these together)
- [ ] Set up agent IAM roles

**CLAUDE CODE TASKS:**
- [ ] Define OpenAPI specs for agent action groups
- [ ] Create Lambda functions that agents call for tools
- [ ] Write agent instruction prompts
- [ ] Update main Lambda to orchestrate agent calls

### 3.3 Iterative Refinement Agent (Phase 3+)

**Advanced Capability:**
- Agent automatically re-runs tests after suggesting data fixes
- Learns from false positives and adjusts test queries
- Maintains a knowledge base of test patterns per model type

## Phase 4: Productionization

### 4.1 Scheduling (YOUR TASK)
- [ ] Create EventBridge rule to trigger Lambda daily/weekly
- [ ] Run after dbt production job completes

### 4.2 Notifications (YOUR TASK + CLAUDE CODE)
- [ ] CLAUDE CODE: Add SNS notification when critical failures are found
- [ ] CLAUDE CODE: Generate summary email with failure counts
- [ ] YOU: Configure SNS topic and subscriptions

### 4.3 Historical Tracking (CLAUDE CODE)
- [ ] Store CSV reports with timestamps
- [ ] Create trend analysis: track defect counts over time
- [ ] Alert when defect counts spike

### 4.4 Web Dashboard (Optional - YOUR TASK)
- [ ] Build simple web UI to view latest reports
- [ ] S3 static site or API Gateway + Lambda
- [ ] Display CSVs in interactive tables

## Prompt Engineering for Test Generation

### Effective Prompt Structure

```
You are a data quality expert reviewing a dbt mart model for a UAT audit. Your goal is to generate comprehensive SQL test queries that will identify data quality issues a business SME would care about.

CONTEXT:

Model Name: {model_name}
Model SQL:
{model_sql}

Schema:
{column_metadata}

Sample Data (first 10 rows):
{sample_data}

Business Descriptions:
{yaml_descriptions}

Statistics:
- Total rows: {row_count}
- Null counts: {null_counts}
- Distinct value counts: {distinct_counts}

Dependencies:
This model references: {upstream_models}

TASK:

Generate 10-15 data quality test queries covering these categories:
1. Uniqueness (primary keys, composite keys)
2. Nullability (required fields)
3. Referential Integrity (foreign keys to upstream models)
4. Date Validity (no future dates, valid ranges, logical order)
5. Business Logic (calculated fields match components, aggregations match details)
6. Value Range (no negatives where inappropriate, categorical values are valid)
7. Data Consistency (related fields are logically consistent)

For each test, return JSON in this format:
{
  "test_name": "unique_snake_case_name",
  "test_category": "Uniqueness|Nullability|Referential Integrity|Date Validity|Business Logic|Value Range|Data Consistency",
  "test_description": "Clear human-readable description of what this test validates",
  "test_query": "SQL query that returns rows WHERE defects exist (empty result = pass). LIMIT 5 for performance.",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW"
}

IMPORTANT QUERY GUIDELINES:
- Queries should return ONLY defective records (so empty result = test passes)
- Include key identifiers in SELECT clause for defect examples
- Use LIMIT 5 to prevent huge result sets
- Queries should be read-only (SELECT only)
- Test queries should be self-contained (no temp tables)

Return ONLY a JSON array of test objects, no other text.
```

### Example Claude Response

```json
[
  {
    "test_name": "unique_customer_id",
    "test_category": "Uniqueness",
    "test_description": "Verifies that customer_id is unique across all rows with no duplicates",
    "test_query": "SELECT customer_id, COUNT(*) as dup_count FROM prod.customers GROUP BY customer_id HAVING COUNT(*) > 1 LIMIT 5",
    "severity": "CRITICAL"
  },
  {
    "test_name": "no_null_customer_id",
    "test_category": "Nullability",
    "test_description": "Ensures customer_id is never NULL as it is the primary key",
    "test_query": "SELECT 'null_customer_id' as defect_type, COUNT(*) as null_count FROM prod.customers WHERE customer_id IS NULL LIMIT 5",
    "severity": "CRITICAL"
  },
  {
    "test_name": "no_future_first_ordered_at",
    "test_category": "Date Validity",
    "test_description": "Checks that first_ordered_at is not in the future",
    "test_query": "SELECT customer_id, first_ordered_at FROM prod.customers WHERE first_ordered_at > CURRENT_DATE LIMIT 5",
    "severity": "HIGH"
  },
  {
    "test_name": "lifetime_spend_non_negative",
    "test_category": "Value Range",
    "test_description": "Validates that lifetime_spend is never negative",
    "test_query": "SELECT customer_id, lifetime_spend FROM prod.customers WHERE lifetime_spend < 0 LIMIT 5",
    "severity": "HIGH"
  },
  {
    "test_name": "customer_orders_exist_in_orders_table",
    "test_category": "Referential Integrity",
    "test_description": "Ensures customers with count_lifetime_orders > 0 have matching records in orders table",
    "test_query": "SELECT c.customer_id, c.count_lifetime_orders FROM prod.customers c LEFT JOIN prod.orders o ON c.customer_id = o.customer_id WHERE c.count_lifetime_orders > 0 AND o.customer_id IS NULL GROUP BY c.customer_id, c.count_lifetime_orders LIMIT 5",
    "severity": "MEDIUM"
  },
  {
    "test_name": "lifetime_spend_matches_order_totals",
    "test_category": "Business Logic",
    "test_description": "Verifies that lifetime_spend equals the sum of order_total from the orders table",
    "test_query": "SELECT c.customer_id, c.lifetime_spend as expected_spend, SUM(o.order_total) as actual_spend, ABS(c.lifetime_spend - SUM(o.order_total)) as difference FROM prod.customers c LEFT JOIN prod.orders o ON c.customer_id = o.customer_id GROUP BY c.customer_id, c.lifetime_spend HAVING ABS(c.lifetime_spend - COALESCE(SUM(o.order_total), 0)) > 0.01 LIMIT 5",
    "severity": "HIGH"
  },
  {
    "test_name": "customer_type_valid_values",
    "test_category": "Value Range",
    "test_description": "Ensures customer_type only contains expected values: 'new' or 'returning'",
    "test_query": "SELECT customer_id, customer_type FROM prod.customers WHERE customer_type NOT IN ('new', 'returning') LIMIT 5",
    "severity": "MEDIUM"
  },
  {
    "test_name": "customer_type_matches_order_count",
    "test_category": "Data Consistency",
    "test_description": "Validates that customer_type='returning' only when count_lifetime_orders > 1",
    "test_query": "SELECT customer_id, customer_type, count_lifetime_orders FROM prod.customers WHERE (customer_type = 'returning' AND count_lifetime_orders <= 1) OR (customer_type = 'new' AND count_lifetime_orders > 1) LIMIT 5",
    "severity": "HIGH"
  }
]
```

## Success Metrics

### Phase 1 Success Criteria
- [ ] Lambda successfully processes `customers` model
- [ ] CSV report is generated with 10-15 relevant tests
- [ ] At least 3 tests execute and return results (pass or fail)
- [ ] CSV is properly formatted and readable in Excel
- [ ] Defect examples are clear and actionable

### Phase 2 Success Criteria
- [ ] All 6 mart models are processed automatically
- [ ] Reports are generated in under 5 minutes total
- [ ] 90%+ of generated tests are relevant and useful
- [ ] False positive rate < 10%

### Phase 3 Success Criteria
- [ ] Bedrock Agents autonomously generate, execute, and analyze tests
- [ ] Agents provide root cause analysis for failures
- [ ] System suggests specific data fixes

## Next Steps

### Immediate Actions (YOUR TASKS)
1. [ ] Set up Redshift cluster and load Jaffle Shop data into `prod` schema
2. [ ] Create S3 buckets for dbt models and reports
3. [ ] Upload `models/marts/*.sql` files to S3
4. [ ] Create IAM role for Lambda with necessary permissions
5. [ ] Enable Bedrock access and Claude 3.5 Sonnet in your AWS account
6. [ ] Create Lambda function (empty shell for now)
7. [ ] Provide Claude Code with:
   - Redshift connection details (cluster ID, database, schema)
   - S3 bucket names and paths
   - IAM role ARN
   - Bedrock model ID

### Immediate Actions (CLAUDE CODE TASKS)
1. [ ] Create `lambda_function/` directory structure
2. [ ] Build `requirements.txt`
3. [ ] Implement `redshift_client.py` with data API
4. [ ] Implement `dbt_parser.py` for reading S3 files
5. [ ] Implement `bedrock_client.py` with prompt template
6. [ ] Implement `test_executor.py`
7. [ ] Implement `csv_writer.py`
8. [ ] Implement `lambda_function.py` handler
9. [ ] Create deployment package instructions

Let me know when you've completed your setup tasks and we'll start building the Lambda function!
