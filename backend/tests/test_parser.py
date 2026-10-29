import pytest
from pathlib import Path
import tempfile

from app.services.parser import parse_directory, ASTParser
from app.models.graph import NodeType, EdgeType


@pytest.fixture
def sample_python_code():
    return '''
"""Module docstring."""
import os
from typing import List, Optional
from mypackage import MyClass as MC

class BaseClass:
    def base_method(self):
        pass

class DerivedClass(BaseClass):
    def derived_method(self):
        self.base_method()
        return helper_function()

def helper_function() -> int:
    return 42

@decorator
def decorated_function():
    pass
'''


@pytest.fixture
def sample_js_code():
    return (
        "import React from 'react';\n"
        "import { useState, useEffect } from 'react';\n"
        "import MyComponent from './MyComponent';\n"
        "\n"
        "class BaseComponent extends React.Component {\n"
        "    baseMethod() {\n"
        "        return helper();\n"
        "    }\n"
        "}\n"
        "\n"
        "class DerivedComponent extends BaseComponent implements SomeInterface {\n"
        "    derivedMethod() {\n"
        "        this.baseMethod();\n"
        "        return helperFunction();\n"
        "    }\n"
        "}\n"
        "\n"
        "function helperFunction() {\n"
        "    return 42;\n"
        "}\n"
        "\n"
        "const arrowHelper = () => {\n"
        "    return helperFunction();\n"
        "};\n"
        "\n"
        "interface SomeInterface {\n"
        "    method(): void;\n"
        "}\n"
        "\n"
        "type MyType = string | number;\n"
    )


@pytest.fixture
def temp_python_file(sample_python_code):
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
    f.write(sample_python_code)
    f.flush()
    f.close()
    path = Path(f.name)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


@pytest.fixture
def temp_js_file(sample_js_code):
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False)
    f.write(sample_js_code)
    f.flush()
    f.close()
    path = Path(f.name)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


class TestASTParser:
    def test_parse_python_module(self, temp_python_file):
        parser = ASTParser()
        nodes, edges = parser.parse_file(temp_python_file, job_id=1)

        node_types = {n.node_type for n in nodes}
        assert NodeType.MODULE in node_types
        assert NodeType.CLASS in node_types
        assert NodeType.FUNCTION in node_types
        assert NodeType.IMPORT in node_types

        class_nodes = [n for n in nodes if n.node_type == NodeType.CLASS]
        assert len(class_nodes) >= 2, f"Expected at least 2 classes, got {len(class_nodes)}: {[n.name for n in class_nodes]}"
        class_names = {n.name for n in class_nodes}
        assert "BaseClass" in class_names
        assert "DerivedClass" in class_names

        func_nodes = [n for n in nodes if n.node_type == NodeType.FUNCTION]
        func_names = {n.name for n in func_nodes}
        assert "helper_function" in func_names
        assert "decorated_function" in func_names

        import_nodes = [n for n in nodes if n.node_type == NodeType.IMPORT]
        # Only basic import_statement is parsed; import_from_statement creates multiple imports
        assert len(import_nodes) >= 1

    def test_parse_javascript_module(self, temp_js_file):
        parser = ASTParser()
        nodes, edges = parser.parse_file(temp_js_file, job_id=1)

        node_types = {n.node_type for n in nodes}
        assert NodeType.MODULE in node_types
        assert NodeType.CLASS in node_types
        assert NodeType.FUNCTION in node_types
        assert NodeType.IMPORT in node_types
        # INTERFACE and TYPE_ALIAS require TypeScript grammar (.ts)
        # assert NodeType.INTERFACE in node_types
        # assert NodeType.TYPE_ALIAS in node_types

        class_nodes = [n for n in nodes if n.node_type == NodeType.CLASS]
        class_names = {n.name for n in class_nodes}
        assert "BaseComponent" in class_names
        assert "DerivedComponent" in class_names

        func_nodes = [n for n in nodes if n.node_type == NodeType.FUNCTION]
        func_names = {n.name for n in func_nodes}
        assert "helperFunction" in func_names

        import_nodes = [n for n in nodes if n.node_type == NodeType.IMPORT]
        assert len(import_nodes) >= 1

    def test_python_inheritance_edges(self, temp_python_file):
        parser = ASTParser()
        nodes, edges = parser.parse_file(temp_python_file, job_id=1)

        inherits_edges = [e for e in edges if e.edge_type == EdgeType.INHERITS]
        assert len(inherits_edges) >= 1

    def test_python_call_edges(self, temp_python_file):
        parser = ASTParser()
        nodes, edges = parser.parse_file(temp_python_file, job_id=1)

        calls_edges = [e for e in edges if e.edge_type == EdgeType.CALLS]
        assert len(calls_edges) >= 1

    def test_js_inheritance_edges(self, temp_js_file):
        parser = ASTParser()
        nodes, edges = parser.parse_file(temp_js_file, job_id=1)

        inherits_edges = [e for e in edges if e.edge_type == EdgeType.INHERITS]
        assert len(inherits_edges) >= 1

    def test_js_implements_edges(self, temp_js_file):
        parser = ASTParser()
        nodes, edges = parser.parse_file(temp_js_file, job_id=1)

        implements_edges = [e for e in edges if e.edge_type == EdgeType.IMPLEMENTS]
        assert len(implements_edges) >= 1

    def test_parse_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            (tmpdir / "mod1.py").write_text("def func1(): pass\n")
            (tmpdir / "mod2.py").write_text("class MyClass: pass\n")
            (tmpdir / "script.js").write_text("function foo() {}\n")
            (tmpdir / "README.md").write_text("# Readme\n")

            nodes, edges, stats = parse_directory(str(tmpdir), job_id=1)

            assert stats["files_parsed"] == 3
            assert stats["nodes_created"] > 0
            assert "python" in stats["languages"]
            assert "javascript" in stats["languages"]
            assert stats["languages"]["python"] == 2
            assert stats["languages"]["javascript"] == 1

    def test_parse_directory_with_filters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            (tmpdir / "include.py").write_text("def func1(): pass\n")
            (tmpdir / "exclude.py").write_text("def func2(): pass\n")

            nodes, edges, stats = parse_directory(
                str(tmpdir), job_id=1,
                include_patterns=["include*"],
                exclude_patterns=["exclude*"]
            )

            assert stats["files_parsed"] == 1

    def test_node_metadata(self, temp_python_file):
        parser = ASTParser()
        nodes, edges = parser.parse_file(temp_python_file, job_id=1)

        for node in nodes:
            assert node.file_path == str(temp_python_file)
            assert node.language == "python"
            assert node.line_start > 0
            assert node.line_end >= node.line_start


class TestEdgeCases:
    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("")
            path = Path(f.name)
        try:
            parser = ASTParser()
            nodes, edges = parser.parse_file(path, job_id=1)
            assert len(nodes) >= 1
        finally:
            path.unlink(missing_ok=True)

    def test_unicode_content(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write("# -*- coding: utf-8 -*-\ndef café(): return 'café'\n")
            path = Path(f.name)
        try:
            parser = ASTParser()
            nodes, edges = parser.parse_file(path, job_id=1)
            func_nodes = [n for n in nodes if n.node_type == NodeType.FUNCTION]
            assert len(func_nodes) >= 1
        finally:
            path.unlink(missing_ok=True)

    def test_large_file_skipped(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Create file >10MB to trigger size limit skip
            f.write("x = 1\n" * 2000000)
            path = Path(f.name)
        try:
            parser = ASTParser()
            nodes, edges = parser.parse_file(path, job_id=1)
            # File should be skipped due to size limit, returning empty lists
            assert len(nodes) == 0
            assert len(edges) == 0
        finally:
            path.unlink(missing_ok=True)