"""
Tests for the SQL Schema Parser.

Tests SQL DDL parsing for tables, columns, and foreign key relationships.
"""

import pytest
import tempfile
import os
import sys
from pathlib import Path


# The backend app root (parent of the 'app' package directory)
_BACKEND_APP = Path(__file__).parent.parent


def _get_env():
    """Get environment with PYTHONPATH set for the backend app."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_BACKEND_APP)
    return env


from app.services.sql_parser import (
    parse_ddl_statement,
    parse_sql_file,
    ColumnInfo,
    TableInfo,
    ForeignKeyInfo,
    ParsedSQLResult,
)


class TestColumnInfo:
    """Test ColumnInfo dataclass."""

    def test_column_with_pk_and_nullable(self):
        """Column with PRIMARY KEY and NOT NULL."""
        col = ColumnInfo(
            name="id",
            type="INTEGER",
            nullable=False,
            primary_key=True,
        )
        assert col.name == "id"
        assert col.type == "INTEGER"
        assert col.nullable is False
        assert col.primary_key is True

    def test_column_with_default(self):
        """Column with DEFAULT value."""
        col = ColumnInfo(
            name="created_at",
            type="DATETIME",
            default="CURRENT_TIMESTAMP",
        )
        assert col.default == "CURRENT_TIMESTAMP"


class TestTableInfo:
    """Test TableInfo dataclass."""

    def test_table_creation(self):
        """Basic table info creation."""
        table = TableInfo(name="users")
        assert table.name == "users"
        assert table.columns == []

    def test_table_with_columns(self):
        """Table with columns."""
        table = TableInfo(
            name="users",
            columns=[
                ColumnInfo(name="id", type="INTEGER", primary_key=True),
                ColumnInfo(name="username", type="VARCHAR(50)"),
            ],
        )
        assert table.name == "users"
        assert len(table.columns) == 2
        assert table.columns[0].primary_key is True


class TestForeignKeyInfo:
    """Test ForeignKeyInfo dataclass."""

    def test_fk_creation(self):
        """Basic foreign key info."""
        fk = ForeignKeyInfo(
            constraint_name="fk_user_posts",
            source_column="user_id",
            referent_table="users",
            referent_column="id",
            onupdate="CASCADE",
            ondelete="SET NULL",
        )
        assert fk.constraint_name == "fk_user_posts"
        assert fk.source_column == "user_id"
        assert fk.referent_table == "users"
        assert fk.referent_column == "id"
        assert fk.onupdate == "CASCADE"
        assert fk.ondelete == "SET NULL"


class TestParsedSQLResult:
    """Test ParsedSQLResult dataclass."""

    def test_empty_result(self):
        """Empty result by default."""
        result = ParsedSQLResult()
        assert result.tables == []
        assert result.relationships == []


class TestParseDDL:
    """Test parse_ddl_statement function."""

    def test_simple_create_table(self):
        """Parse a simple CREATE TABLE statement."""
        ddl = "CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(50));"
        result = parse_ddl_statement(ddl)
        
        assert len(result.tables) == 1
        assert result.tables[0].name == "users"
        assert len(result.tables[0].columns) == 2

    def test_create_table_with_fk(self):
        """Parse CREATE TABLE with foreign key."""
        ddl = (
            "CREATE TABLE posts ("
            "id INT PRIMARY KEY, "
            "title VARCHAR(200), "
            "user_id INT, "
            "FOREIGN KEY (user_id) REFERENCES users(id)"
            ");"
        )
        result = parse_ddl_statement(ddl)
        
        assert len(result.tables) == 1
        assert result.tables[0].name == "posts"
        assert len(result.tables[0].foreign_keys) == 1
        fk = result.tables[0].foreign_keys[0]
        assert fk.source_column == "user_id"
        assert fk.referent_table == "users"
        assert fk.referent_column == "id"

    def test_multiple_tables(self):
        """Parse DDL with multiple CREATE TABLE statements."""
        ddl = (
            "CREATE TABLE users (id INT PRIMARY KEY); "
            "CREATE TABLE posts (id INT, user_id INT, "
            "FOREIGN KEY (user_id) REFERENCES users(id));"
        )
        result = parse_ddl_statement(ddl)
        
        assert len(result.tables) == 2
        table_names = [t.name for t in result.tables]
        assert "users" in table_names
        assert "posts" in table_names

    def test_column_types(self):
        """Test various column type parsing."""
        ddl = "CREATE TABLE test (id INT PRIMARY KEY, name VARCHAR(100), email TEXT);"
        result = parse_ddl_statement(ddl)
        
        assert len(result.tables) == 1
        table = result.tables[0]
        assert len(table.columns) == 3
        
        # Check id column
        id_col = table.columns[0]
        assert id_col.name == "id"
        assert id_col.type == "INTEGER"  # int -> INTEGER
        assert id_col.primary_key is True
        
        # Check name column - type includes length parameter
        name_col = table.columns[1]
        assert name_col.name == "name"
        # VARCHAR with length is preserved
        assert "VARCHAR" in name_col.type
        
        # Check email column
        email_col = table.columns[2]
        assert email_col.name == "email"
        assert email_col.type == "TEXT"


class TestParseSQLFile:
    """Test parse_sql_file function."""

    def test_nonexistent_file(self):
        """Parsing a nonexistent file returns empty result."""
        result = parse_sql_file("/nonexistent/path/file.sql")
        assert result.tables == []
        assert result.relationships == []

    def test_empty_sql_file(self):
        """Parsing an empty SQL file returns empty result."""
        with tempfile.NamedTemporaryFile(suffix=".sql", mode="w", delete=False) as f:
            f.write("")
            tmp_path = f.name
        try:
            result = parse_sql_file(tmp_path)
            assert result.tables == []
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_sql_file_with_ddl(self):
        """Parsing a SQL file with CREATE TABLE statements."""
        with tempfile.NamedTemporaryFile(suffix=".sql", mode="w", delete=False) as f:
            f.write(
                "CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(50));"
            )
            tmp_path = f.name
        try:
            result = parse_sql_file(tmp_path)
            assert len(result.tables) == 1
            assert result.tables[0].name == "users"
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestEdgeCases:
    """Test edge cases."""

    def test_ddl_with_if_not_exists(self):
        """Parse DDL with IF NOT EXISTS clause."""
        ddl = "CREATE TABLE IF NOT EXISTS users (id INT PRIMARY KEY);"
        result = parse_ddl_statement(ddl)
        assert len(result.tables) == 1
        assert result.tables[0].name == "users"

    def test_ddl_without_parentheses(self):
        """Handle malformed DDL gracefully."""
        # DDL without CREATE TABLE structure
        ddl = "Just some random text"
        result = parse_ddl_statement(ddl)
        assert result.tables == []

    def test_case_insensitive(self):
        """Parser is case-insensitive."""
        ddl = "create table Users (id int primary key);"
        result = parse_ddl_statement(ddl)
        assert len(result.tables) == 1
        assert result.tables[0].name == "Users"  # preserves case
