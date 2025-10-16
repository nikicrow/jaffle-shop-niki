"""
Main script for running data quality audits on dbt mart models.

Usage:
    python main.py                    # Audit all mart models
    python main.py customers          # Audit single model
    python main.py customers orders   # Audit specific models
"""

import sys
import logging
from typing import List, Optional

from config import MART_MODELS
from dbt_parser import DBTParser
from redshift_client import RedshiftClient
from bedrock_client import BedrockClient
from test_executor import TestExecutor
from csv_writer import CSVWriter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data_quality_audit.log"),
    ],
)

logger = logging.getLogger(__name__)


def audit_model(
    model_name: str,
    dbt_parser: DBTParser,
    redshift_client: RedshiftClient,
    bedrock_client: BedrockClient,
    csv_writer: CSVWriter,
) -> List[dict]:
    """
    Audit a single dbt model.

    Args:
        model_name: Name of the model to audit
        dbt_parser: DBTParser instance
        redshift_client: RedshiftClient instance
        bedrock_client: BedrockClient instance
        csv_writer: CSVWriter instance

    Returns:
        List of test results
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Starting audit for model: {model_name}")
    logger.info(f"{'='*80}")

    try:
        # Step 1: Parse dbt model
        logger.info("Step 1: Parsing dbt model...")
        model_context = dbt_parser.parse_model(model_name)

        # Step 2: Get Redshift metadata
        logger.info("Step 2: Fetching Redshift metadata...")
        table_metadata = redshift_client.get_table_metadata(model_name)

        # Step 3: Get Redshift statistics
        logger.info("Step 3: Fetching Redshift statistics...")
        table_stats = redshift_client.get_table_stats(model_name)

        # Step 4: Get sample data
        logger.info("Step 4: Fetching sample data...")
        sample_data = redshift_client.get_sample_data(model_name, limit=10)

        # Step 5: Generate tests using Bedrock
        logger.info("Step 5: Generating tests with Bedrock/Claude...")
        test_definitions = bedrock_client.generate_tests(
            model_context, table_metadata, table_stats, sample_data
        )

        # Step 6: Execute tests
        logger.info("Step 6: Executing tests...")
        test_executor = TestExecutor(redshift_client)
        test_results = test_executor.execute_tests(test_definitions, model_name)

        # Get summary
        summary = test_executor.get_summary(test_results)
        logger.info(f"    - Passed: {summary['passed']}")
        logger.info(f"    - Failed: {summary['failed']}")
        logger.info(f"    - Errors: {summary['errors']}")
        logger.info(f"    - Total defects: {summary['total_defects']}")
        if summary['critical_failures'] > 0:
            logger.warning(f"    - Critical failures: {summary['critical_failures']}")
        if summary['high_failures'] > 0:
            logger.warning(f"    - High failures: {summary['high_failures']}")

        # Step 7: Write CSV report
        logger.info("Step 7: Writing CSV report...")
        report_path = csv_writer.write_report(test_results, model_name)

        logger.info(f"{'='*80}")
        logger.info(f"Audit complete for model: {model_name}")
        logger.info(f"{'='*80}\n")

        return test_results

    except Exception as e:
        logger.error(f"Failed to audit model {model_name}: {e}", exc_info=True)
        raise


def main(model_names: Optional[List[str]] = None):
    """
    Main entry point for data quality audit.

    Args:
        model_names: List of model names to audit. If None, audits all mart models.
    """
    # Determine which models to audit
    if model_names:
        models_to_audit = model_names
    else:
        models_to_audit = MART_MODELS

    logger.info(f"Starting Data Quality Audit")
    logger.info(f"Models to audit: {', '.join(models_to_audit)}")
    logger.info("")

    # Initialize clients
    logger.info("Initializing clients...")
    dbt_parser = DBTParser()
    bedrock_client = BedrockClient()
    csv_writer = CSVWriter()

    all_results = {}

    # Connect to Redshift and run audits
    with RedshiftClient() as redshift_client:
        logger.info("Connected to Redshift")
        logger.info("")

        # Test connection
        if not redshift_client.test_connection():
            logger.error("Redshift connection test failed")
            return

        # Audit each model
        for model_name in models_to_audit:
            try:
                test_results = audit_model(
                    model_name,
                    dbt_parser,
                    redshift_client,
                    bedrock_client,
                    csv_writer,
                )
                all_results[model_name] = test_results

            except Exception as e:
                logger.error(f"Skipping model {model_name} due to error: {e}")
                continue

    # Write summary report if multiple models
    if len(all_results) > 1:
        logger.info("\n" + "="*80)
        logger.info("Writing summary report...")
        summary_path = csv_writer.write_summary_report(all_results)
        logger.info(f"Summary report written to: {summary_path}")
        logger.info("="*80)

    # Final summary
    logger.info("\n" + "="*80)
    logger.info("Data Quality Audit Complete!")
    logger.info(f"Total models audited: {len(all_results)}")
    logger.info("="*80)


if __name__ == "__main__":
    # Parse command line arguments
    if len(sys.argv) > 1:
        # Specific models provided
        model_names = sys.argv[1:]
        main(model_names)
    else:
        # Audit all models
        main()
