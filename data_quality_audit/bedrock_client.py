"""
Bedrock Client for generating data quality tests using Claude.
"""

import json
import logging
import boto3
from typing import Dict, List, Any, Optional
from config import BEDROCK_CONFIG

logger = logging.getLogger(__name__)


class BedrockClient:
    """Client for interacting with Amazon Bedrock to generate test queries."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Bedrock client.

        Args:
            config: Bedrock configuration. Uses BEDROCK_CONFIG if not provided.
        """
        self.config = config or BEDROCK_CONFIG
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=self.config["region"]
        )
        self.model_id = self.config["model_id"]

    def generate_tests(
        self,
        model_context: Dict[str, Any],
        table_metadata: List[Dict[str, Any]],
        table_stats: Dict[str, Any],
        sample_data: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Generate data quality tests using Bedrock/Claude.

        Args:
            model_context: dbt model context from DBTParser
            table_metadata: Column metadata from Redshift
            table_stats: Table statistics from Redshift
            sample_data: Sample rows from Redshift

        Returns:
            List of test definitions with test_name, test_category, test_description, test_query, severity
        """
        # Build the prompt
        prompt = self._build_prompt(model_context, table_metadata, table_stats, sample_data)

        logger.info(f"Generating tests for model: {model_context['model_name']}")

        try:
            # Call Bedrock API
            response = self._invoke_bedrock(prompt)

            # Parse the response
            tests = self._parse_response(response)

            logger.info(f"Generated {len(tests)} tests for {model_context['model_name']}")

            return tests

        except Exception as e:
            logger.error(f"Failed to generate tests: {e}")
            raise

    def _build_prompt(
        self,
        model_context: Dict[str, Any],
        table_metadata: List[Dict[str, Any]],
        table_stats: Dict[str, Any],
        sample_data: List[Dict[str, Any]],
    ) -> str:
        """Build the prompt for Claude to generate tests."""

        model_name = model_context["model_name"]
        sql_content = model_context["sql_content"]
        dependencies = model_context["dependencies"]
        column_descriptions = model_context["column_descriptions"]
        model_description = model_context["model_description"]

        # Format column metadata
        column_info = []
        for col in table_metadata:
            col_name = col["column_name"]
            col_type = col["data_type"]
            nullable = "NULL" if col["is_nullable"] else "NOT NULL"
            description = column_descriptions.get(col_name, "")

            null_count = table_stats["null_counts"].get(col_name, 0)
            distinct_count = table_stats["distinct_counts"].get(col_name, 0)

            col_info_str = f"  - {col_name} ({col_type}, {nullable})"
            if description:
                col_info_str += f" - {description}"
            col_info_str += f"\n    Stats: {null_count} nulls, {distinct_count} distinct values"

            column_info.append(col_info_str)

        column_metadata_str = "\n".join(column_info)

        # Format sample data
        sample_data_str = json.dumps(sample_data[:5], indent=2, default=str)

        # Format dependencies
        dependencies_str = ", ".join(dependencies) if dependencies else "None"

        # Build the prompt
        prompt = f"""You are a data quality expert reviewing a dbt mart model for a UAT audit. Your goal is to generate comprehensive SQL test queries that will identify data quality issues a business SME would care about.

CONTEXT:

Model Name: {model_name}
Model Description: {model_description or "No description provided"}

Model SQL:
```sql
{sql_content}
```

Schema:
{column_metadata_str}

Sample Data (first 5 rows):
{sample_data_str}

Statistics:
- Total rows: {table_stats['row_count']}

Dependencies:
This model references: {dependencies_str}

TASK:

Generate 10-15 data quality test queries covering these categories:
1. Uniqueness (primary keys, composite keys)
2. Nullability (required fields)
3. Referential Integrity (foreign keys to upstream models like {dependencies_str})
4. Date Validity (no future dates, valid ranges, logical order)
5. Business Logic (calculated fields match components, aggregations match details)
6. Value Range (no negatives where inappropriate, categorical values are valid)
7. Data Consistency (related fields are logically consistent)

For each test, return JSON in this format:
{{
  "test_name": "unique_snake_case_name",
  "test_category": "Uniqueness|Nullability|Referential Integrity|Date Validity|Business Logic|Value Range|Data Consistency",
  "test_description": "Clear human-readable description of what this test validates",
  "test_query": "SQL query that returns rows WHERE defects exist (empty result = pass). Use schema 'waffles' and LIMIT 5 for performance.",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW"
}}

IMPORTANT QUERY GUIDELINES:
- Queries should return ONLY defective records (so empty result = test passes)
- Include key identifiers in SELECT clause for defect examples
- Use LIMIT 5 to prevent huge result sets
- Queries should be read-only (SELECT only)
- Test queries should be self-contained (no temp tables)
- Use the schema 'waffles' when referencing tables (e.g., waffles.{model_name})
- For referential integrity tests with upstream models, reference them as waffles.model_name

Return ONLY a JSON array of test objects, no other text. Start your response with [ and end with ].
"""

        return prompt

    def _invoke_bedrock(self, prompt: str) -> str:
        """
        Invoke Bedrock API with the prompt.

        Args:
            prompt: The prompt to send to Claude

        Returns:
            Response text from Claude
        """
        # Prepare the request body for Claude 3.5 Sonnet
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "temperature": 0.2,  # Lower temperature for more consistent output
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        try:
            # Invoke the model
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            # Parse response
            response_body = json.loads(response["body"].read())

            # Extract text from Claude's response
            response_text = response_body["content"][0]["text"]

            return response_text

        except Exception as e:
            logger.error(f"Bedrock API call failed: {e}")
            raise

    def _parse_response(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Parse Claude's response into test definitions.

        Args:
            response_text: JSON response from Claude

        Returns:
            List of test definition dicts
        """
        try:
            # Claude should return a JSON array
            # Extract JSON from the response (in case there's extra text)
            json_start = response_text.find("[")
            json_end = response_text.rfind("]") + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON array found in response")

            json_str = response_text[json_start:json_end]

            tests = json.loads(json_str)

            # Validate test structure
            validated_tests = []
            required_fields = ["test_name", "test_category", "test_description", "test_query", "severity"]

            for test in tests:
                if all(field in test for field in required_fields):
                    validated_tests.append(test)
                else:
                    logger.warning(f"Skipping invalid test definition: {test}")

            return validated_tests

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}\nResponse: {response_text}")
            raise
        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
            raise
