# Changelog

## 1.0.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-20

### Added
- Multi-language AST parser using tree-sitter (Python, JavaScript, TypeScript)
- Graph extraction: imports, function calls, class inheritance, interface implementation, containment
- SQLite-backed persistent graph storage with WAL mode and indexes
- FastAPI REST API with parse jobs, paginated queries, filtering
- Graph export to JSON, GraphML, DOT formats
- React + TypeScript + Vite frontend with Cytoscape.js visualization
- Interactive graph exploration: search, filter by type, node detail panel
- Comprehensive test suite (30 backend tests, frontend typecheck/build)
- Docker Compose with backend, frontend services

### Changed
- N/A (initial release)

### Fixed
- N/A (initial release)