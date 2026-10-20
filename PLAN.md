# Product development plan

Each round completes one feature or repair. Future items are planned, not implemented claims.

## Current round

core-ast-parser

## Roadmap

### core-ast-parser — Core AST Parser with Language Plugins

Status: done

Acceptance:
- Parse Python, JavaScript, TypeScript files into AST nodes
- Extract imports, functions, classes, and their relationships
- Output deterministic graph edges (calls, imports, inheritance)
- No LLM required - fully offline deterministic parsing

Implementation: `backend/app/services/parser.py`, `backend/app/models/graph.py`, `backend/app/models/database.py`

Tests: `backend/tests/test_parser.py`, `backend/tests/test_graph_api.py`

### graph-storage — Graph Storage & Query API

Status: done

Acceptance:
- SQLite-backed persistent graph storage
- REST API for querying nodes/edges with pagination/filtering
- Export to GraphML, JSON, DOT formats

Implementation: `backend/app/services/graph.py`, `backend/app/api/graph.py`, `backend/app/api/parse.py`

Tests: `backend/tests/test_graph_api.py`

### web-ui — React Web UI for Graph Exploration

Status: done

Acceptance:
- Dashboard showing codebase overview stats
- Interactive graph visualization (cytoscape.js)
- Search/filter nodes by type, name, file
- Node detail panel with source location

Implementation: `frontend/src/App.tsx`, `frontend/src/components/Dashboard.tsx`, `frontend/src/components/GraphView.tsx`, `frontend/src/api/client.ts`

Tests: `frontend/typecheck via tsc`

### cli-skill — CLI /graphify Skill Integration

Status: planned

Acceptance:
- CLI command to parse a directory and output graph
- Integration with Claude Code, Cursor, Codex, Gemini CLI
- Configurable output formats

### sql-config-parsers — SQL Schema & Config File Parsers

Status: planned

Acceptance:
- Parse SQL DDL for tables, columns, FK relationships
- Parse YAML/JSON/TOML configs as structured nodes
- Extract relationships from config references

### pdf-doc-parser — PDF Documentation Parser

Status: planned

Acceptance:
- Extract text/structure from PDF docs
- Link doc sections to code symbols
- Output as graph nodes with source references

