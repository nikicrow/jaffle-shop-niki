# AI Helper for dbt Test Generation - Implementation Guide

## Overview

This guide outlines how to build an AI-powered helper that analyzes your dbt project and Redshift tables to automatically generate data quality tests. We'll start with the simplest possible implementation using Amazon Bedrock and iterate from there.

## Architecture Overview

```
┌─────────────────┐
│   dbt Project   │
│   (Local/Git)   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│         Python Script/Agent             │
│  ┌───────────────────────────────────┐  │
│  │  1. Read dbt model files (.sql)   │  │
│  │  2. Query Redshift metadata       │  │
│  │  3. Send context to Bedrock       │  │
│  │  4. Generate test suggestions     │  │
│  │  5. Write tests to YAML files     │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐    ┌──────────────┐
│    Redshift     │    │Amazon Bedrock│
│    Database     │    │  (Claude 3)  │
└─────────────────┘    └──────────────┘
```

## Phase 1: Simplest Implementation

### What You'll Need

1. **AWS Credentials** with access to:
   - Amazon Bedrock (Claude 3 Sonnet or Haiku)
   - Redshift cluster

2. **Python Environment** with:
   - `boto3` (AWS SDK)
   - `psycopg2` or `redshift_connector` (Redshift connection)
   - `pyyaml` (for reading/writing dbt YAML files)

3. **dbt Project Structure** understanding:
   - Location of model files (`models/`)
   - Location of schema files (`models/**/*.yml`)

### Step-by-Step Approach

#### Step 1: Set Up Basic Connectivity

Create a simple Python script that can:
- Connect to your Redshift database
- Read files from your dbt project directory
- Call Amazon Bedrock API

```python
# Key components needed:
# - Redshift connection for metadata queries
# - File system access to dbt project
# - Boto3 client for Bedrock
```

#### Step 2: Extract Context for a Single Model

For one dbt model, gather:

**From dbt:**
- The SQL code that creates the model
- Any existing tests already defined
- Dependencies (other models it references)

**From Redshift:**
- Column names and data types
- Sample data (first 5-10 rows)
- Basic statistics (row count, null counts, distinct values)

#### Step 3: Create a Simple Prompt

Send this context to Bedrock with a prompt like:

```
I have a dbt model with the following details:

MODEL SQL:
[insert model SQL]

SCHEMA:
[insert column names and types]

SAMPLE DATA:
[insert sample rows]

EXISTING TESTS:
[insert any existing tests]

Please suggest 3-5 data quality tests for this model. Focus on:
- Not null constraints for important columns
- Unique constraints for ID columns
- Referential integrity checks
- Accepted value checks for categorical columns
- Relationship tests with upstream models

Format your response as dbt test YAML.
```

#### Step 4: Parse and Save the Response

Take Bedrock's response and:
1. Parse the suggested tests
2. Validate they're in correct dbt YAML format
3. Either append to existing schema.yml or create a new test file
4. Save to the appropriate location in your dbt project

### Minimal Script Structure

```
dbt_test_generator/
├── main.py              # Entry point
├── redshift_client.py   # Redshift connection and queries
├── dbt_parser.py        # Read dbt files
├── bedrock_client.py    # Bedrock API calls
├── test_writer.py       # Write YAML test files
└── config.yaml          # Configuration (connections, paths)
```

## Phase 2: Enhancements

Once the basic version works, consider these improvements:

### 2.1 Batch Processing
- Process multiple models at once
- Prioritize models by importance or data volume

### 2.2 Smarter Context Gathering
- Query actual data quality issues from Redshift:
  ```sql
  -- Find columns with high null rates
  -- Identify potential unique keys
  -- Detect foreign key relationships
  -- Find categorical columns with reasonable cardinality
  ```

### 2.3 Test Type Specialization
- Different prompts for different test categories:
  - Schema tests (not_null, unique, accepted_values)
  - Relationship tests (foreign keys)
  - Custom data tests (business logic)
  - Freshness checks

### 2.4 Interactive Mode
- Let user approve/reject suggested tests
- Allow customization of test parameters
- Preview tests before writing

### 2.5 Learning from Existing Tests
- Analyze patterns in existing tests across your project
- Use these patterns to make better suggestions
- Maintain consistency with team conventions

## Phase 3: Agent-like Capabilities

### 3.1 Autonomous Exploration
The agent could:
- Discover which tables lack tests
- Identify inconsistencies in testing coverage
- Suggest improvements to existing tests

### 3.2 Iterative Refinement
- Run suggested tests in a dev environment
- If tests fail, analyze failures
- Adjust test parameters or suggest data fixes

### 3.3 Documentation Generation
- Generate documentation for why tests were suggested
- Create data quality reports
- Suggest lineage or dependency improvements

## Implementation Recommendations

### Start Simple
1. **Pick one model** to test the entire flow
2. **Manually review** all generated tests initially
3. **Iterate quickly** based on what works

### Bedrock Model Choice
- **Claude 3.5 Sonnet**: Best for complex reasoning about data relationships
- **Claude 3 Haiku**: Faster and cheaper for simpler test generation
- Start with Sonnet, optimize to Haiku if needed

### Safety Considerations
- **Never auto-commit** generated tests without review
- **Version control** all changes
- **Test in dev environment** first
- **Validate YAML syntax** before writing files

### Prompt Engineering Tips
- Include examples of good tests from your project
- Be specific about your team's conventions
- Ask for explanations along with test suggestions
- Request tests in order of priority

## Sample Queries for Redshift Metadata

```sql
-- Get column information
SELECT 
    column_name,
    data_type,
    is_nullable,
    ordinal_position
FROM information_schema.columns
WHERE table_schema = 'your_schema'
    AND table_name = 'your_table';

-- Get row count and basic stats
SELECT 
    COUNT(*) as row_count,
    COUNT(DISTINCT your_key_column) as distinct_keys
FROM your_schema.your_table;

-- Find columns with nulls
SELECT 
    column_name,
    COUNT(*) as null_count,
    COUNT(*) * 100.0 / (SELECT COUNT(*) FROM your_schema.your_table) as null_percentage
FROM your_schema.your_table
WHERE column_value IS NULL
GROUP BY column_name;
```

## Expected Output Example

For a model called `dim_customers`, the agent might suggest:

```yaml
version: 2

models:
  - name: dim_customers
    description: "Customer dimension table"
    columns:
      - name: customer_id
        description: "Unique identifier for customer"
        tests:
          - unique
          - not_null
      
      - name: email
        description: "Customer email address"
        tests:
          - not_null
          - unique
      
      - name: customer_status
        description: "Current status of customer account"
        tests:
          - accepted_values:
              values: ['active', 'inactive', 'suspended', 'churned']
      
      - name: created_at
        description: "Timestamp when customer was created"
        tests:
          - not_null
          - dbt_utils.expression_is_true:
              expression: "created_at <= current_date"
```

## Next Steps

1. Set up AWS credentials and Bedrock access
2. Create basic Python script with Redshift connectivity
3. Test Bedrock API with a simple prompt
4. Implement the context gathering for one model
5. Generate and review your first test suggestions
6. Iterate based on results

Would you like me to help you with any specific part of this implementation?