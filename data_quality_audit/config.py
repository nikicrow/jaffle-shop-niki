"""
Configuration for the Data Quality Audit System.

TODO: Update these values with your actual AWS and Redshift details.
"""

import os

# Redshift Connection Settings
# IMPORTANT: Never commit credentials to Git!
# Use environment variables for sensitive data
REDSHIFT_CONFIG = {
    "host": os.environ.get("REDSHIFT_HOST"),
    "port": int(os.environ.get("REDSHIFT_PORT", "5439")),
    "database": os.environ.get("REDSHIFT_DATABASE", "dev"),
    "user": os.environ.get("REDSHIFT_USER"),
    "password": os.environ.get("REDSHIFT_PASSWORD"),
    "schema": os.environ.get("REDSHIFT_SCHEMA", "waffles"),
}

# dbt Project Paths (local development)
DBT_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DBT_MODELS_PATH = os.path.join(DBT_PROJECT_ROOT, "models", "marts")

# AWS Bedrock Settings
# TODO: Update with your AWS region and preferred model
BEDROCK_CONFIG = {
    "region": "ap-southeast-2",  # Your AWS region
    "model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",  # Claude 3.5 Sonnet
}

# S3 Settings (for future Lambda deployment)
# TODO: Update when you create S3 buckets
S3_CONFIG = {
    "dbt_models_bucket": "YOUR-DBT-MODELS-BUCKET",
    "dbt_models_prefix": "marts/",
    "reports_bucket": "YOUR-REPORTS-BUCKET",
    "reports_prefix": "data_quality_reports/",
}

# Output Settings
OUTPUT_DIR = os.path.join(DBT_PROJECT_ROOT, "data_quality_reports")

# Test Execution Settings
MAX_DEFECT_EXAMPLES = 5  # Number of example defects to capture per test
TEST_QUERY_TIMEOUT = 300  # Query timeout in seconds (5 minutes)

# Mart Models to Audit
MART_MODELS = [
    "customers",
    "orders",
    "order_items",
    "products",
    "supplies",
    "locations",
]
