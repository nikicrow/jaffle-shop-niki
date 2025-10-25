# Data Quality Audit System

AI-powered data quality audit system for dbt mart models using AWS Bedrock (Claude) and Redshift.

## Overview

This system analyzes dbt models, generates comprehensive data quality tests using AI, executes those tests against Redshift, and produces CSV reports with defect details.

## Project Structure

```
data_quality_audit/
├── config.py              # Configuration (Redshift, Bedrock, paths)
├── dbt_parser.py         # Parse dbt SQL and YAML files
├── redshift_client.py    # Redshift connection and queries
├── bedrock_client.py     # Bedrock/Claude API for test generation
├── test_executor.py      # Execute tests and capture defects
├── csv_writer.py         # Generate CSV reports
├── main.py               # Main orchestrator script
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Setup

### 1. Install Dependencies

```bash
cd data_quality_audit
pip install -r requirements.txt
```

### 2. Configure Connection Settings (Securely)

**⚠️ IMPORTANT: Never commit credentials to Git!**

The configuration uses environment variables to keep credentials safe.

#### Option A: Create a .env file (Recommended)

1. Copy the example file:
   ```bash
   cd data_quality_audit
   cp .env.example .env
   ```

2. Edit `.env` with your actual credentials:
   ```bash
   REDSHIFT_HOST=your-cluster.abc123.us-east-1.redshift.amazonaws.com
   REDSHIFT_PORT=5439
   REDSHIFT_DATABASE=dev
   REDSHIFT_USER=your_username
   REDSHIFT_PASSWORD=your_password
   REDSHIFT_SCHEMA=waffles
   ```

3. Load environment variables before running:
   ```bash
   # On Windows PowerShell:
   Get-Content .env | ForEach-Object {
       $name, $value = $_.split('=')
       Set-Item -Path env:$name -Value $value
   }

   # On Windows CMD:
   for /f "tokens=*" %i in (.env) do set %i

   # On Mac/Linux:
   export $(cat .env | xargs)
   ```

#### Option B: Set Environment Variables Manually

```bash
# On Windows PowerShell:
$env:REDSHIFT_HOST="your-cluster.redshift.amazonaws.com"
$env:REDSHIFT_USER="your_username"
$env:REDSHIFT_PASSWORD="your_password"

# On Mac/Linux:
export REDSHIFT_HOST=your-cluster.redshift.amazonaws.com
export REDSHIFT_USER=your_username
export REDSHIFT_PASSWORD=your_password
```

#### Update Bedrock Config (if needed)

Only edit `config.py` if you need to change the AWS region:
```python
{
"region": "ap-southeast-2",  # Change if your AWS region is different
"model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
}
```

### 3. Configure AWS Credentials

Ensure your AWS credentials are configured for Bedrock access:

```bash
aws configure
```

Or use environment variables:
```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

### 4. Verify Bedrock Access

Make sure you have:
- Bedrock enabled in your AWS account
- Access to Claude 3.5 Sonnet model
- IAM permissions for `bedrock:InvokeModel`

## Usage

### Audit All Mart Models

```bash
python main.py
```

### Audit Specific Model

```bash
python main.py customers
```

### Audit Multiple Models

```bash
python main.py customers orders order_items
```

## Output

### Individual Model Reports

CSV files are generated in `data_quality_reports/` directory:

```
data_quality_reports/
├── customers_data_quality_report_20251016_142345.csv
├── orders_data_quality_report_20251016_142512.csv
└── order_items_data_quality_report_20251016_142638.csv
```

Each CSV contains:
- `test_name`: Unique identifier for the test
- `test_category`: Category (Uniqueness, Nullability, etc.)
- `test_description`: Human-readable description
- `test_query`: Actual SQL query executed
- `defect_count`: Number of violations found
- `defect_examples`: Sample defective records
- `status`: PASS/FAIL/ERROR
- `severity`: CRITICAL/HIGH/MEDIUM/LOW
- `notes`: Additional context
- `execution_timestamp`: When test was run

### Summary Report

When auditing multiple models, a summary CSV is also generated:

```
data_quality_summary_20251016_142700.csv
```

Contains aggregate statistics across all models.

## Example Workflow

1. **Run audit on single model** (test setup):
   ```bash
   python main.py customers
   ```

2. **Review CSV report** in Excel/Google Sheets

3. **Iterate on failed tests** (fix data or adjust expectations)

4. **Run full audit** on all models:
   ```bash
   python main.py
   ```

5. **Share CSV reports** with business SMEs for UAT review

## Test Categories

The system generates tests across 7 categories:

1. **Uniqueness**: Primary keys, composite keys
2. **Nullability**: Required fields
3. **Referential Integrity**: Foreign keys to upstream models
4. **Date Validity**: No future dates, valid ranges
5. **Business Logic**: Calculated fields match components
6. **Value Range**: No negative values where inappropriate
7. **Data Consistency**: Related fields are logically consistent

## Troubleshooting

### Connection Errors

If you see connection errors:
```
Failed to connect to Redshift: ...
```

- Verify your Redshift host, port, database, user, password in `config.py`
- Check security groups allow your IP
- Test connection manually: `psql -h <host> -U <user> -d <database>`

### Bedrock Errors

If you see Bedrock errors:
```
Failed to invoke Bedrock: ...
```

- Verify AWS credentials: `aws sts get-caller-identity`
- Check Bedrock model access in AWS Console
- Ensure model ID is correct in `config.py`
- Verify IAM permissions for `bedrock:InvokeModel`

### Model Not Found

If you see:
```
Model SQL file not found: ...
```

- Verify model exists in `models/marts/`
- Check model name spelling (case-sensitive)
- Ensure `DBT_MODELS_PATH` in `config.py` points to correct directory

## Logs

Logs are written to:
- Console (stdout)
- `data_quality_audit.log` file

Check logs for detailed execution information and errors.

## Next Steps

Once this works locally, you can:

1. **Package for Lambda**: Zip the directory and deploy to AWS Lambda
2. **Add S3 Support**: Read dbt files from S3 instead of local filesystem
3. **Schedule with EventBridge**: Run audits automatically
4. **Add Notifications**: SNS alerts for critical failures
5. **Build Dashboard**: Visualize trends over time

See `bedrock_tester.md` for full implementation roadmap.
