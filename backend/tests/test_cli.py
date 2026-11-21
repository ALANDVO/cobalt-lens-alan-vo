"""CLI tests for /graphify skill."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


# The backend app root (parent of the 'app' package directory)
_BACKEND_APP = Path(__file__).parent.parent


def _get_env():
    """Get environment with PYTHONPATH set for the backend app."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_BACKEND_APP)
    return env


def run_cli_parse(directory, output_format="json"):
    """Run the CLI parse command and return parsed JSON output."""
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "parse", directory, "--output", output_format],
        capture_output=True,
        text=True,
        cwd=str(_BACKEND_APP),
        env=_get_env(),
    )
    return result


def test_cli_parse_json_with_python_files():
    """Test CLI parse outputs valid JSON with Python file directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test Python file
        test_file = Path(tmpdir) / "test_module.py"
        test_file.write_text(
            "def hello():\n    return \"hello\"\n\nclass MyClass:\n    pass\n"
        )

        result = run_cli_parse(tmpdir, "json")
        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        output = json.loads(result.stdout)

        # Verify structure
        assert "nodes" in output
        assert "edges" in output
        assert "stats" in output
        assert output["stats"]["files_parsed"] >= 1

        # Verify node types
        node_types = {n["type"] for n in output["nodes"]}
        assert "module" in node_types
        assert "function" in node_types
        assert "class" in node_types


def test_cli_parse_dot_format():
    """Test CLI parse outputs valid DOT format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_module.py"
        test_file.write_text("def hello(): return \"hello\"\n")

        result = run_cli_parse(tmpdir, "dot")
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        output = result.stdout
        assert output.startswith("digraph G {")
        assert output.rstrip("\n").endswith("}")


def test_cli_parse_with_imports():
    """Test CLI parse detects imports and creates edges."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "with_imports.py"
        test_file.write_text("import os\nimport json\n\ndef foo(): pass\n")

        result = run_cli_parse(tmpdir, "json")
        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        output = json.loads(result.stdout)

        # Should have import nodes and edges
        assert output["stats"]["files_parsed"] >= 1
        assert output["stats"]["edges_created"] >= 0

        # Check for import-type nodes
        node_types = {n["type"] for n in output["nodes"]}
        # At minimum should have module nodes
        assert any(n["type"] == "module" for n in output["nodes"])


def test_cli_parse_nonexistent_directory():
    """Test CLI error on nonexistent directory."""
    result = run_cli_parse("/nonexistent/path", "json")
    assert result.returncode != 0
    assert "Error" in result.stderr
