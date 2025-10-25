"""
**Purpose**: Reads and analyzes dbt model files (both SQL and YAML)
**Key Features**:
 - get_model_sql(): Reads the SQL file for a model
 - get_model_yaml(): Reads the YAML schema file
 - extract_ref_models(): Uses regex to find {{ ref('model_name') }} dependencies
 - extract_config(): Parses {{ config(...) }} blocks for materialization settings
 - get_column_descriptions(): Extracts column descriptions from YAML
 - get_existing_tests(): Extracts existing dbt tests from YAML
 - parse_model(): Main method that combines all the above into comprehensive model context
 - list_mart_models(): Lists all SQL models in the marts directory
"""

import os
import re
import yaml
import logging
from typing import Dict, List, Any, Optional
from config import DBT_MODELS_PATH

logger = logging.getLogger(__name__)


class DBTParser:
    """Parser for dbt model files (SQL and YAML)."""

    def __init__(self, models_path: Optional[str] = None):
        """
        Initialize dbt parser.

        Args:
            models_path: Path to dbt models directory. Uses DBT_MODELS_PATH if not provided.
        """
        self.models_path = models_path or DBT_MODELS_PATH

    def get_model_sql(self, model_name: str) -> str:
        """
        Read the SQL file for a dbt model.

        Args:
            model_name: Name of the model (without .sql extension)

        Returns:
            SQL content as string
        """
        sql_path = os.path.join(self.models_path, f"{model_name}.sql")

        if not os.path.exists(sql_path):
            raise FileNotFoundError(f"Model SQL file not found: {sql_path}")

        try:
            with open(sql_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read model SQL for {model_name}: {e}")
            raise

    def get_model_yaml(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Read the YAML schema file for a dbt model.

        Args:
            model_name: Name of the model

        Returns:
            Dict with YAML content, or None if not found
        """
        yaml_path = os.path.join(self.models_path, f"{model_name}.yml")

        if not os.path.exists(yaml_path):
            logger.warning(f"Model YAML file not found: {yaml_path}")
            return None

        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                yaml_content = yaml.safe_load(f)
                return yaml_content
        except Exception as e:
            logger.error(f"Failed to read model YAML for {model_name}: {e}")
            return None

    def extract_ref_models(self, sql_content: str) -> List[str]:
        """
        Extract referenced models from SQL using ref() function.

        Args:
            sql_content: SQL content as string

        Returns:
            List of referenced model names
        """
        # Pattern to match {{ ref('model_name') }} or {{ ref("model_name") }}
        pattern = r"{{\s*ref\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\s*}}"
        matches = re.findall(pattern, sql_content)

        return list(set(matches))  # Return unique model names

    def extract_config(self, sql_content: str) -> Dict[str, Any]:
        """
        Extract config() block from SQL.

        Args:
            sql_content: SQL content as string

        Returns:
            Dict with config settings (materialized, dist, sort, etc.)
        """
        # Pattern to match {{ config(...) }}
        pattern = r"{{\s*config\s*\((.*?)\)\s*}}"
        match = re.search(pattern, sql_content, re.DOTALL)

        if not match:
            return {}

        config_str = match.group(1)

        # Parse simple key=value pairs
        config = {}
        # Match key='value' or key="value"
        kv_pattern = r"(\w+)\s*=\s*['\"]([^'\"]+)['\"]"
        for key, value in re.findall(kv_pattern, config_str):
            config[key] = value

        return config

    def get_column_descriptions(self, yaml_content: Optional[Dict[str, Any]], model_name: str) -> Dict[str, str]:
        """
        Extract column descriptions from YAML content.

        Args:
            yaml_content: Parsed YAML content
            model_name: Name of the model

        Returns:
            Dict mapping column names to descriptions
        """
        if not yaml_content or "models" not in yaml_content:
            return {}

        descriptions = {}

        for model in yaml_content.get("models", []):
            if model.get("name") == model_name:
                for column in model.get("columns", []):
                    col_name = column.get("name")
                    col_desc = column.get("description", "")
                    if col_name:
                        descriptions[col_name] = col_desc

        return descriptions

    def get_existing_tests(self, yaml_content: Optional[Dict[str, Any]], model_name: str) -> List[Dict[str, Any]]:
        """
        Extract existing tests from YAML content.

        Args:
            yaml_content: Parsed YAML content
            model_name: Name of the model

        Returns:
            List of test definitions
        """
        if not yaml_content or "models" not in yaml_content:
            return []

        tests = []

        for model in yaml_content.get("models", []):
            if model.get("name") == model_name:
                # Model-level tests
                for test in model.get("tests", []):
                    tests.append({"level": "model", "test": test})

                # Column-level tests
                for column in model.get("columns", []):
                    col_name = column.get("name")
                    for test in column.get("tests", []):
                        tests.append({
                            "level": "column",
                            "column": col_name,
                            "test": test
                        })

        return tests

    def parse_model(self, model_name: str) -> Dict[str, Any]:
        """
        Parse a dbt model and return comprehensive context.

        Args:
            model_name: Name of the model

        Returns:
            Dict with model SQL, config, dependencies, descriptions, and tests
        """
        logger.info(f"Parsing model: {model_name}")

        # Read SQL
        sql_content = self.get_model_sql(model_name)

        # Read YAML (optional)
        yaml_content = self.get_model_yaml(model_name)

        # Extract information
        ref_models = self.extract_ref_models(sql_content)
        config = self.extract_config(sql_content)
        descriptions = self.get_column_descriptions(yaml_content, model_name)
        existing_tests = self.get_existing_tests(yaml_content, model_name)

        # Get model description
        model_description = ""
        if yaml_content and "models" in yaml_content:
            for model in yaml_content["models"]:
                if model.get("name") == model_name:
                    model_description = model.get("description", "")
                    break

        return {
            "model_name": model_name,
            "sql_content": sql_content,
            "config": config,
            "dependencies": ref_models,
            "model_description": model_description,
            "column_descriptions": descriptions,
            "existing_tests": existing_tests,
        }

    def list_mart_models(self) -> List[str]:
        """
        List all SQL models in the marts directory.

        Returns:
            List of model names (without .sql extension)
        """
        if not os.path.exists(self.models_path):
            raise FileNotFoundError(f"Models path not found: {self.models_path}")

        models = []
        for filename in os.listdir(self.models_path):
            if filename.endswith(".sql"):
                model_name = filename[:-4]  # Remove .sql extension
                models.append(model_name)

        return sorted(models)
