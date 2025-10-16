"""
Test Executor for running data quality tests and capturing defects.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any
from redshift_client import RedshiftClient

logger = logging.getLogger(__name__)


class TestExecutor:
    """Executes data quality tests and captures results."""

    def __init__(self, redshift_client: RedshiftClient):
        """
        Initialize test executor.

        Args:
            redshift_client: Connected RedshiftClient instance
        """
        self.redshift_client = redshift_client

    def execute_tests(
        self, test_definitions: List[Dict[str, Any]], model_name: str
    ) -> List[Dict[str, Any]]:
        """
        Execute all tests and return results.

        Args:
            test_definitions: List of test definitions from BedrockClient
            model_name: Name of the model being tested

        Returns:
            List of test results with defect counts and examples
        """
        logger.info(f"Executing {len(test_definitions)} tests for {model_name}")

        test_results = []

        for test_def in test_definitions:
            result = self._execute_single_test(test_def, model_name)
            test_results.append(result)

        logger.info(
            f"Completed {len(test_results)} tests for {model_name}. "
            f"Passed: {sum(1 for r in test_results if r['status'] == 'PASS')}, "
            f"Failed: {sum(1 for r in test_results if r['status'] == 'FAIL')}"
        )

        return test_results

    def _execute_single_test(
        self, test_def: Dict[str, Any], model_name: str
    ) -> Dict[str, Any]:
        """
        Execute a single test and return result.

        Args:
            test_def: Test definition with test_query, test_name, etc.
            model_name: Name of the model being tested

        Returns:
            Dict with test result including status, defect_count, defect_examples
        """
        test_name = test_def["test_name"]
        test_query = test_def["test_query"]

        logger.debug(f"Executing test: {test_name}")

        execution_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        try:
            # Execute the test query
            query_results = self.redshift_client.execute_query(test_query)

            # Count defects (number of rows returned)
            defect_count = len(query_results)

            # Format defect examples
            defect_examples = ""
            if defect_count > 0:
                defect_examples = self.redshift_client.format_defect_examples(query_results)

            # Determine status
            status = "PASS" if defect_count == 0 else "FAIL"

            # Generate notes
            notes = self._generate_notes(test_def, status, defect_count)

            # Build result
            result = {
                "test_name": test_name,
                "test_category": test_def["test_category"],
                "test_description": test_def["test_description"],
                "test_query": test_query,
                "defect_count": defect_count,
                "defect_examples": defect_examples,
                "status": status,
                "severity": test_def["severity"],
                "notes": notes,
                "execution_timestamp": execution_timestamp,
                "model_name": model_name,
            }

            return result

        except Exception as e:
            logger.error(f"Failed to execute test {test_name}: {e}")

            # Return error result
            return {
                "test_name": test_name,
                "test_category": test_def["test_category"],
                "test_description": test_def["test_description"],
                "test_query": test_query,
                "defect_count": -1,
                "defect_examples": "",
                "status": "ERROR",
                "severity": test_def["severity"],
                "notes": f"Test execution failed: {str(e)}",
                "execution_timestamp": execution_timestamp,
                "model_name": model_name,
            }

    def _generate_notes(
        self, test_def: Dict[str, Any], status: str, defect_count: int
    ) -> str:
        """
        Generate human-readable notes for test result.

        Args:
            test_def: Test definition
            status: Test status (PASS/FAIL)
            defect_count: Number of defects found

        Returns:
            Notes string
        """
        test_name = test_def["test_name"]
        test_category = test_def["test_category"]

        if status == "PASS":
            return f"No issues found - {test_def['test_description'].lower()}"

        # Failed test - generate specific notes based on category
        if test_category == "Uniqueness":
            return f"Found {defect_count} duplicate record(s) - investigate data load process"
        elif test_category == "Nullability":
            return f"Found {defect_count} record(s) with unexpected NULL values"
        elif test_category == "Referential Integrity":
            return f"Found {defect_count} record(s) with referential integrity issues"
        elif test_category == "Date Validity":
            return f"Found {defect_count} record(s) with invalid dates"
        elif test_category == "Business Logic":
            return f"Found {defect_count} record(s) with business logic violations"
        elif test_category == "Value Range":
            return f"Found {defect_count} record(s) with values outside expected range"
        elif test_category == "Data Consistency":
            return f"Found {defect_count} record(s) with data consistency issues"
        else:
            return f"Found {defect_count} defect(s)"

    def get_summary(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary statistics for test results.

        Args:
            test_results: List of test result dicts

        Returns:
            Dict with summary statistics
        """
        total_tests = len(test_results)
        passed = sum(1 for r in test_results if r["status"] == "PASS")
        failed = sum(1 for r in test_results if r["status"] == "FAIL")
        errors = sum(1 for r in test_results if r["status"] == "ERROR")

        total_defects = sum(r["defect_count"] for r in test_results if r["defect_count"] > 0)

        critical_failures = sum(
            1 for r in test_results if r["status"] == "FAIL" and r["severity"] == "CRITICAL"
        )
        high_failures = sum(
            1 for r in test_results if r["status"] == "FAIL" and r["severity"] == "HIGH"
        )

        return {
            "total_tests": total_tests,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "total_defects": total_defects,
            "critical_failures": critical_failures,
            "high_failures": high_failures,
        }
