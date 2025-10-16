"""
Redshift Client for querying metadata and executing test queries.
"""

import logging
import psycopg2
from typing import Dict, List, Any, Optional
from config import REDSHIFT_CONFIG, MAX_DEFECT_EXAMPLES

logger = logging.getLogger(__name__)


class RedshiftClient:
    """Client for interacting with Redshift database."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Redshift client.

        Args:
            config: Redshift connection configuration. Uses REDSHIFT_CONFIG if not provided.
        """
        self.config = config or REDSHIFT_CONFIG
        self.connection = None
        self.schema = self.config.get("schema", "waffles")

    def connect(self):
        """Establish connection to Redshift."""
        try:
            self.connection = psycopg2.connect(
                host=self.config["host"],
                port=self.config["port"],
                database=self.config["database"],
                user=self.config["user"],
                password=self.config["password"],
            )
            logger.info(f"Connected to Redshift: {self.config['host']}/{self.config['database']}")
        except Exception as e:
            logger.error(f"Failed to connect to Redshift: {e}")
            raise

    def close(self):
        """Close connection to Redshift."""
        if self.connection:
            self.connection.close()
            logger.info("Redshift connection closed")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def get_table_metadata(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get column metadata for a table.

        Args:
            table_name: Name of the table

        Returns:
            List of dicts with column information (name, type, nullable, position)
        """
        query = f"""
        SELECT
            column_name,
            data_type,
            is_nullable,
            ordinal_position
        FROM information_schema.columns
        WHERE table_schema = %s
            AND table_name = %s
        ORDER BY ordinal_position
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, (self.schema, table_name))
                columns = cursor.fetchall()

                return [
                    {
                        "column_name": col[0],
                        "data_type": col[1],
                        "is_nullable": col[2] == "YES",
                        "ordinal_position": col[3],
                    }
                    for col in columns
                ]
        except Exception as e:
            logger.error(f"Failed to get table metadata for {table_name}: {e}")
            raise

    def get_table_stats(self, table_name: str) -> Dict[str, Any]:
        """
        Get basic statistics for a table.

        Args:
            table_name: Name of the table

        Returns:
            Dict with row_count, null_counts, and distinct_counts
        """
        # Get row count
        row_count_query = f"SELECT COUNT(*) FROM {self.schema}.{table_name}"

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(row_count_query)
                row_count = cursor.fetchone()[0]

            # Get column metadata to build null count queries
            metadata = self.get_table_metadata(table_name)

            null_counts = {}
            distinct_counts = {}

            # Build and execute queries for null counts and distinct counts
            for col in metadata:
                col_name = col["column_name"]

                # Null count query
                null_query = f"""
                SELECT COUNT(*)
                FROM {self.schema}.{table_name}
                WHERE {col_name} IS NULL
                """

                # Distinct count query (with limit for performance)
                distinct_query = f"""
                SELECT COUNT(DISTINCT {col_name})
                FROM {self.schema}.{table_name}
                """

                with self.connection.cursor() as cursor:
                    cursor.execute(null_query)
                    null_counts[col_name] = cursor.fetchone()[0]

                    cursor.execute(distinct_query)
                    distinct_counts[col_name] = cursor.fetchone()[0]

            return {
                "row_count": row_count,
                "null_counts": null_counts,
                "distinct_counts": distinct_counts,
            }

        except Exception as e:
            logger.error(f"Failed to get table stats for {table_name}: {e}")
            raise

    def get_sample_data(self, table_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get sample rows from a table.

        Args:
            table_name: Name of the table
            limit: Number of rows to return

        Returns:
            List of dicts representing rows
        """
        query = f"SELECT * FROM {self.schema}.{table_name} LIMIT {limit}"

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query)
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get sample data for {table_name}: {e}")
            raise

    def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """
        Execute a SQL query and return results.

        Args:
            sql: SQL query to execute

        Returns:
            List of dicts representing result rows
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql)

                # If no results (e.g., no columns returned), return empty list
                if cursor.description is None:
                    return []

                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error(f"Failed to execute query: {e}\nSQL: {sql}")
            raise

    def format_defect_examples(
        self, query_results: List[Dict[str, Any]], limit: int = MAX_DEFECT_EXAMPLES
    ) -> str:
        """
        Format query results into a semicolon-delimited string of defect examples.

        Args:
            query_results: List of dicts from execute_query
            limit: Maximum number of examples to include

        Returns:
            Formatted string like "col1=val1, col2=val2; col1=val3, col2=val4"
        """
        if not query_results:
            return ""

        examples = []
        for row in query_results[:limit]:
            # Format each row as "col1=val1, col2=val2"
            row_str = ", ".join([f"{k}={v}" for k, v in row.items()])
            examples.append(row_str)

        return "; ".join(examples)

    def test_connection(self) -> bool:
        """
        Test the connection to Redshift.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return result[0] == 1
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
