"""
**Purpose**: Generates CSV reports from test results
**Key Features**:
 - write_report(): Creates individual model CSV report with columns:
   - test_name, test_category, test_description, test_query
   - defect_count, defect_examples, status, severity, notes, execution_timestamp
 - write_summary_report(): Creates aggregate summary CSV across all models with:
   - model_name, total_tests, passed, failed, errors
   - total_defects, critical_failures, high_failures
 - Adds timestamps to filenames for versioning
 - Creates output directory if it doesn't exist
 - Handles CSV escaping for special characters in defect examples
"""

import os
import csv
import logging
from typing import List, Dict, Any
from datetime import datetime
from config import OUTPUT_DIR

logger = logging.getLogger(__name__)


class CSVWriter:
    """Writer for data quality CSV reports."""

    def __init__(self, output_dir: str = OUTPUT_DIR):
        """
        Initialize CSV writer.

        Args:
            output_dir: Directory to write CSV files to
        """
        self.output_dir = output_dir

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

    def write_report(
        self, test_results: List[Dict[str, Any]], model_name: str
    ) -> str:
        """
        Write test results to CSV file.

        Args:
            test_results: List of test result dicts from TestExecutor
            model_name: Name of the model

        Returns:
            Path to the generated CSV file
        """
        # Generate filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{model_name}_data_quality_report_{timestamp}.csv"
        filepath = os.path.join(self.output_dir, filename)

        logger.info(f"Writing data quality report to: {filepath}")

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
                # Define CSV columns
                fieldnames = [
                    "test_name",
                    "test_category",
                    "test_description",
                    "test_query",
                    "defect_count",
                    "defect_examples",
                    "status",
                    "severity",
                    "notes",
                    "execution_timestamp",
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                # Write header
                writer.writeheader()

                # Write test results
                for result in test_results:
                    # Extract only the fields we need for CSV
                    row = {
                        "test_name": result["test_name"],
                        "test_category": result["test_category"],
                        "test_description": result["test_description"],
                        "test_query": result["test_query"],
                        "defect_count": result["defect_count"],
                        "defect_examples": result["defect_examples"],
                        "status": result["status"],
                        "severity": result["severity"],
                        "notes": result["notes"],
                        "execution_timestamp": result["execution_timestamp"],
                    }
                    writer.writerow(row)

            logger.info(f"Successfully wrote {len(test_results)} test results to {filepath}")

            return filepath

        except Exception as e:
            logger.error(f"Failed to write CSV report: {e}")
            raise

    def write_summary_report(
        self, all_results: Dict[str, List[Dict[str, Any]]]
    ) -> str:
        """
        Write a summary report across all models.

        Args:
            all_results: Dict mapping model_name to list of test results

        Returns:
            Path to the generated summary CSV file
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"data_quality_summary_{timestamp}.csv"
        filepath = os.path.join(self.output_dir, filename)

        logger.info(f"Writing summary report to: {filepath}")

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = [
                    "model_name",
                    "total_tests",
                    "passed",
                    "failed",
                    "errors",
                    "total_defects",
                    "critical_failures",
                    "high_failures",
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for model_name, test_results in all_results.items():
                    # Calculate summary stats
                    total_tests = len(test_results)
                    passed = sum(1 for r in test_results if r["status"] == "PASS")
                    failed = sum(1 for r in test_results if r["status"] == "FAIL")
                    errors = sum(1 for r in test_results if r["status"] == "ERROR")
                    total_defects = sum(
                        r["defect_count"] for r in test_results if r["defect_count"] > 0
                    )
                    critical_failures = sum(
                        1 for r in test_results
                        if r["status"] == "FAIL" and r["severity"] == "CRITICAL"
                    )
                    high_failures = sum(
                        1 for r in test_results
                        if r["status"] == "FAIL" and r["severity"] == "HIGH"
                    )

                    row = {
                        "model_name": model_name,
                        "total_tests": total_tests,
                        "passed": passed,
                        "failed": failed,
                        "errors": errors,
                        "total_defects": total_defects,
                        "critical_failures": critical_failures,
                        "high_failures": high_failures,
                    }
                    writer.writerow(row)

            logger.info(f"Successfully wrote summary report to {filepath}")

            return filepath

        except Exception as e:
            logger.error(f"Failed to write summary report: {e}")
            raise
