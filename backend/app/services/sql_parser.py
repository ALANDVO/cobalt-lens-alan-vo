"""
SQL Schema Parser

Parses SQL DDL statements to extract:
- Tables and their columns
- Foreign key relationships
- Data types and constraints
"""

import re
from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class ColumnInfo:
    """Information about a database column."""
    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False
    autoincrement: bool = False
    default: Optional[str] = None
    unique: bool = False


@dataclass
class TableInfo:
    """Information about a database table."""
    name: str
    columns: List[ColumnInfo] = field(default_factory=list)
    primary_key_columns: List[str] = field(default_factory=list)
    foreign_keys: List["ForeignKeyInfo"] = field(default_factory=list)


@dataclass
class ForeignKeyInfo:
    """Information about a foreign key relationship."""
    constraint_name: str
    source_column: str
    referent_table: str
    referent_column: str
    onupdate: str = ""
    ondelete: str = ""


@dataclass
class ParsedSQLResult:
    """Result of parsing SQL DDL."""
    tables: List[TableInfo] = field(default_factory=list)
    relationships: List[ForeignKeyInfo] = field(default_factory=list)


_SQL_TYPE_KEYWORDS = {
    "tinyint": "SMALLINT", "smallint": "SMALLINT", "mediumint": "INTEGER",
    "int": "INTEGER", "integer": "INTEGER", "bigint": "BIGINT",
    "bool": "BOOLEAN", "boolean": "BOOLEAN",
    "float": "FLOAT", "double": "DOUBLE PRECISION", "real": "REAL",
    "decimal": "DECIMAL", "numeric": "DECIMAL",
    "char": "CHAR", "varchar": "VARCHAR", "text": "TEXT",
    "tinytext": "TEXT", "mediumtext": "TEXT", "longtext": "TEXT",
    "tinyblob": "BLOB", "blob": "BLOB", "mediumblob": "BLOB",
    "date": "DATE", "datetime": "DATETIME", "timestamp": "TIMESTAMP",
    "time": "TIME", "year": "YEAR",
}


def _normalize_type(type_str: str) -> str:
    """Normalize a SQL type string to a canonical form."""
    if not type_str:
        return type_str
    
    type_lower = type_str.strip().lower()
    
    # First check for types with parentheses (e.g., VARCHAR(50), INT(11), TEXT)
    if "(" in type_lower:
        # Extract base type and parameters
        base_match = re.match(r"([a-z]+)(.*)", type_lower)
        if base_match:
            base = base_match.group(1)
            params = base_match.group(2)  # includes the opening parenthesis
            if base in _SQL_TYPE_KEYWORDS:
                return _SQL_TYPE_KEYWORDS[base] + params
    
    # Then check for plain type keywords (e.g., INT, BOOLEAN, TEXT without parens)
    if type_lower in _SQL_TYPE_KEYWORDS:
        return _SQL_TYPE_KEYWORDS[type_lower]
    
    # Return as-is (e.g., types we don't recognize)
    return type_str


def _parse_column_definition(col_def: str) -> Optional[ColumnInfo]:
    """Parse a single column definition from a CREATE TABLE statement."""
    if not col_def or not col_def.strip():
        return None
    
    col_def = col_def.strip()
    col_def = col_def.rstrip(", ").strip()
    
    # Check for PRIMARY KEY constraint on this column
    has_primary_key = bool(re.search(r"\bPRIMARY\s+KEY\b", col_def, re.IGNORECASE))
    
    # Check for UNIQUE constraint
    has_unique = bool(re.search(r"\bUNIQUE\b", col_def, re.IGNORECASE))
    
    # Determine nullability
    has_not_null = bool(re.search(r"\bNOT\s+NULL\b", col_def, re.IGNORECASE))
    nullable = not has_not_null
    
    # Check for DEFAULT value
    default_match = re.search(
        r"\bDEFAULT\s+([^\s,]+(?:\s+[^\s,]+)*)",
        col_def, re.IGNORECASE
    )
    default_val = None
    if default_match:
        default_val = default_match.group(1).strip()
        if (default_val.startswith("'") and default_val.endswith("'")) or \
           (default_val.startswith('"') and default_val.endswith('"')):
            default_val = default_val[1:-1]
    
    # Check for AUTO_INCREMENT / IDENTITY
    has_autoincrement = bool(
        re.search(r"\bAUTO_INCREMENT\b|\bGENERATED\s+ALWAYS\s+AS\s+IDENTITY\b",
                  col_def, re.IGNORECASE)
    )
    
    # Extract column name and type
    # After removing constraints, the first token is the type or the column name
    cleaned = col_def
    for keyword in ["PRIMARY KEY", "UNIQUE", "NOT NULL", "AUTO_INCREMENT",
                    "GENERATED ALWAYS AS IDENTITY", "DEFAULT"]:
        cleaned = re.sub(rf"\b{keyword}\b", "", cleaned, flags=re.IGNORECASE).strip()
    
    tokens = cleaned.split()
    if not tokens:
        return None
    
    type_keywords_set = set(_SQL_TYPE_KEYWORDS.keys())
    
    if tokens[0].lower() in type_keywords_set:
        # First token is type, second is column name
        if len(tokens) < 2:
            return None
        type_str = tokens[0]
        col_name = tokens[1]
    else:
        # First token is column name, second is type
        col_name = tokens[0]
        type_str = tokens[1] if len(tokens) > 1 else ""
    
    type_normalized = _normalize_type(type_str)
    
    return ColumnInfo(
        name=col_name,
        type=type_normalized,
        nullable=nullable,
        primary_key=has_primary_key,
        autoincrement=has_autoincrement,
        default=default_val,
        unique=has_unique,
    )


def _extract_create_table_blocks(ddl: str) -> List[str]:
    """Extract individual CREATE TABLE blocks from a DDL string."""
    normalized = re.sub(r"\s+", " ", ddl).strip()
    statements = [s.strip() for s in normalized.split(";") if s.strip()]
    
    create_blocks = []
    for stmt in statements:
        upper = stmt.upper().lstrip()
        if upper.startswith("CREATE TABLE"):
            create_blocks.append(stmt)
    
    return create_blocks


def _split_column_defs(column_defs: str) -> List[str]:
    """Split column definitions by comma, respecting nested parentheses."""
    parts = []
    depth = 0
    current = []
    
    for char in column_defs:
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    
    if current:
        parts.append("".join(current).strip())
    
    return [p for p in parts if p]


def _find_last_paren_content(ddl_snippet: str) -> str:
    """
    Extract content between the first '(' and the last ')' in a string.
    This handles cases like CREATE TABLE table (col1, col2, ...).
    """
    # Find first (
    first_paren = ddl_snippet.find("(")
    if first_paren == -1:
        return ""
    
    # Find last )
    last_paren = ddl_snippet.rfind(")")
    if last_paren == -1 or last_paren <= first_paren:
        return ""
    
    return ddl_snippet[first_paren + 1:last_paren]


def _parse_foreign_keys_from_block(block: str) -> List["ForeignKeyInfo"]:
    """Extract foreign key definitions from a CREATE TABLE block."""
    fks = []
    
    # Pattern: [CONSTRAINT name] FOREIGN KEY (cols) REFERENCES table (cols)
    fk_pattern = re.compile(
        r"(?:CONSTRAINT\s+(\w+)\s+)?FOREIGN\s+KEY\s*\((.+?)\)\s+"
        r"REFERENCES\s+(\w+)\s*\((.+?)\)",
        re.IGNORECASE
    )
    
    for match in fk_pattern.finditer(block):
        constraint_name = match.group(1) or ""
        fk_columns = [c.strip() for c in match.group(2).split(",")]
        ref_table = match.group(3).strip()
        ref_columns = [c.strip() for c in match.group(4).split(",")]
        
        for fk_col in fk_columns:
            for ref_col in ref_columns:
                fk = ForeignKeyInfo(
                    constraint_name=constraint_name,
                    source_column=fk_col,
                    referent_table=ref_table,
                    referent_column=ref_col,
                )
                fks.append(fk)
    
    return fks


def parse_ddl_statement(ddl: str) -> ParsedSQLResult:
    """
    Parse a SQL DDL statement and extract tables, columns, and foreign keys.
    
    Args:
        ddl: A SQL DDL statement (CREATE TABLE, etc.)
    
    Returns:
        ParsedSQLResult containing tables and relationships
    """
    result = ParsedSQLResult()
    
    if not ddl or not ddl.strip():
        return result
    
    table_blocks = _extract_create_table_blocks(ddl)
    
    for block in table_blocks:
        create_match = re.search(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)",
            block, re.IGNORECASE
        )
        
        if not create_match:
            continue
        
        table_name = create_match.group(1)
        table_info = TableInfo(name=table_name)
        
        # Extract column definitions using last ) approach
        # Find content between first ( and last )
        column_content = _find_last_paren_content(block)
        
        if column_content:
            columns = _split_column_defs(column_content)
            
            for col_def in columns:
                col_info = _parse_column_definition(col_def)
                if col_info and col_info.name:
                    table_info.columns.append(col_info)
        
        # Extract primary key columns
        pk_match = re.search(
            r"PRIMARY\s+KEY\s*\((.+?)\)",
            block, re.IGNORECASE
        )
        if pk_match:
            table_info.primary_key_columns = [
                c.strip() for c in pk_match.group(1).split(",")
            ]
        
        # Extract foreign key definitions
        fks = _parse_foreign_keys_from_block(block)
        table_info.foreign_keys.extend(fks)
        
        result.tables.append(table_info)
    
    return result


def parse_sql_file(filepath: str) -> ParsedSQLResult:
    """
    Parse a SQL file and extract schema information.
    
    Args:
        filepath: Path to a .sql file
    
    Returns:
        ParsedSQLResult with tables and relationships
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (FileNotFoundError, UnicodeDecodeError):
        return ParsedSQLResult()
    
    return parse_ddl_statement(content)


def example_usage():
    """Example usage of the SQL DDL parser."""
    ddl = """
    CREATE TABLE users (
        id INT PRIMARY KEY,
        username VARCHAR(50) NOT NULL UNIQUE,
        email VARCHAR(100) NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP
    );
    
    CREATE TABLE posts (
        id INT PRIMARY KEY,
        title VARCHAR(200) NOT NULL,
        user_id INT,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """
    
    result = parse_ddl_statement(ddl)
    
    print(f"Parsed {len(result.tables)} table(s):")
    for table in result.tables:
        print(f"  Table: {table.name}")
        print(f"    Columns: {len(table.columns)}")
        for col in table.columns:
            pk = " PK" if col.primary_key else ""
            uk = " UK" if col.unique else ""
            nl = "" if col.nullable else " NOT NULL"
            df = f" DEFAULT {col.default}" if col.default else ""
            print(f"      - {col.name} ({col.type}{nl}{df}{pk}{uk})")
        
        print(f"    FK constraints: {len(table.foreign_keys)}")
        for fk in table.foreign_keys:
            print(f"      - {fk.source_column} -> {fk.referent_table}.{fk.referent_column} "
                  f"(onupdate={fk.onupdate}, ondelete={fk.ondelete})")


if __name__ == "__main__":
    example_usage()
