import pytest
from pathlib import Path
from fastapi.testclient import TestClient
import tempfile
import json

from app.main import create_app
from app.models.database import init_db, get_connection
from app.services.graph import create_parse_job, store_nodes, store_edges
from app.services.parser import parse_directory
from app.models.graph import NodeCreate, EdgeCreate, NodeType, EdgeType


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def sample_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        (tmpdir / "main.py").write_text("""
import os
from utils import helper

class Service:
    def process(self):
        return helper()

def helper():
    return 42
""")
        (tmpdir / "utils.py").write_text("""
def helper():
    return 42

class Util:
    pass
""")
        yield str(tmpdir)


class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestParseEndpoint:
    def test_parse_creates_job(self, client, sample_repo):
        response = client.post("/api/v1/parse", json={"root_path": sample_repo})
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert data["job_id"] > 0

    def test_parse_invalid_path(self, client):
        response = client.post("/api/v1/parse", json={"root_path": "/nonexistent/path"})
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

    def test_parse_job_status(self, client, sample_repo):
        response = client.post("/api/v1/parse", json={"root_path": sample_repo})
        job_id = response.json()["job_id"]

        import time
        for _ in range(10):
            time.sleep(0.5)
            status_resp = client.get(f"/api/v1/parse/{job_id}")
            if status_resp.json()["status"] in ("completed", "failed"):
                break

        status_resp = client.get(f"/api/v1/parse/{job_id}")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["id"] == job_id
        assert data["status"] in ("completed", "failed")

    def test_parse_nonexistent_job(self, client):
        response = client.get("/api/v1/parse/99999")
        assert response.status_code == 404


class TestGraphEndpoints:
    @pytest.fixture
    def completed_job(self, sample_repo):
        job_id = create_parse_job(sample_repo)
        nodes, edges, stats = parse_directory(sample_repo, job_id)
        store_nodes(job_id, nodes)
        node_ids = {i: n for i, n in enumerate(nodes)}
        store_edges(job_id, edges)
        return job_id

    def test_graph_summary(self, client, completed_job):
        response = client.get(f"/api/v1/graph/summary?job_id={completed_job}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == completed_job
        assert data["total_nodes"] > 0
        assert data["total_edges"] > 0
        assert "node_types" in data
        assert "edge_types" in data
        assert "languages" in data

    def test_graph_summary_not_found(self, client):
        response = client.get("/api/v1/graph/summary?job_id=99999")
        assert response.status_code == 404

    def test_list_nodes(self, client, completed_job):
        response = client.get(f"/api/v1/graph/nodes?job_id={completed_job}&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "total" in data
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert len(data["nodes"]) <= 10

    def test_list_nodes_filter_by_type(self, client, completed_job):
        response = client.get(f"/api/v1/graph/nodes?job_id={completed_job}&node_type=class")
        assert response.status_code == 200
        data = response.json()
        for node in data["nodes"]:
            assert node["node_type"] == "class"

    def test_list_nodes_filter_by_name(self, client, completed_job):
        response = client.get(f"/api/v1/graph/nodes?job_id={completed_job}&name=helper")
        assert response.status_code == 200
        data = response.json()
        for node in data["nodes"]:
            assert "helper" in node["name"].lower()

    def test_list_edges(self, client, completed_job):
        response = client.get(f"/api/v1/graph/edges?job_id={completed_job}&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "edges" in data
        assert "total" in data

    def test_list_edges_filter_by_source(self, client, completed_job):
        nodes_resp = client.get(f"/api/v1/graph/nodes?job_id={completed_job}&limit=1")
        if nodes_resp.json()["nodes"]:
            node_id = nodes_resp.json()["nodes"][0]["id"]
            response = client.get(f"/api/v1/graph/edges?job_id={completed_job}&source_id={node_id}")
            assert response.status_code == 200

    def test_list_edges_filter_by_type(self, client, completed_job):
        response = client.get(f"/api/v1/graph/edges?job_id={completed_job}&edge_type=calls")
        assert response.status_code == 200
        data = response.json()
        for edge in data["edges"]:
            assert edge["edge_type"] == "calls"

    def test_pagination(self, client, completed_job):
        response = client.get(f"/api/v1/graph/nodes?job_id={completed_job}&limit=2&offset=0")
        page1 = response.json()
        response = client.get(f"/api/v1/graph/nodes?job_id={completed_job}&limit=2&offset=2")
        page2 = response.json()
        assert page1["offset"] == 0
        assert page2["offset"] == 2
        if page1["total"] > 2:
            assert len(page2["nodes"]) > 0


class TestGraphExports:
    @pytest.fixture
    def completed_job(self, sample_repo):
        job_id = create_parse_job(sample_repo)
        nodes, edges, stats = parse_directory(sample_repo, job_id)
        store_nodes(job_id, nodes)
        store_edges(job_id, edges)
        return job_id

    def test_export_json(self, client, completed_job):
        response = client.get(f"/api/v1/graph/export/json?job_id={completed_job}")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data

    def test_export_graphml(self, client, completed_job):
        response = client.get(f"/api/v1/graph/export/graphml?job_id={completed_job}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/xml"
        content = response.text
        assert "<graphml" in content
        assert "<node" in content
        assert "<edge" in content

    def test_export_dot(self, client, completed_job):
        response = client.get(f"/api/v1/graph/export/dot?job_id={completed_job}")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        content = response.text
        assert "digraph G" in content
        assert "->" in content


class TestDatabase:
    def test_init_db_creates_tables(self):
        init_db()
        with get_connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {t["name"] for t in tables}
            assert "parse_jobs" in table_names
            assert "nodes" in table_names
            assert "edges" in table_names