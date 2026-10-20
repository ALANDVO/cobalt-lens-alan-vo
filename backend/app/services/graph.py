import json
from typing import Optional
from datetime import datetime

from app.models.database import get_connection, transaction
from app.models.graph import NodeCreate, EdgeCreate, Node, Edge, ParseJob, GraphSummary
from app.core.config import settings


def create_parse_job(root_path: str) -> int:
    with transaction() as conn:
        cursor = conn.execute(
            "INSERT INTO parse_jobs (root_path, status) VALUES (?, ?)",
            (root_path, "pending")
        )
        return cursor.lastrowid


def update_parse_job(job_id: int, status: str, error_message: Optional[str] = None,
                     stats: Optional[dict] = None) -> None:
    with transaction() as conn:
        if status == "completed":
            conn.execute(
                "UPDATE parse_jobs SET status = ?, completed_at = datetime('now'), stats_json = ? WHERE id = ?",
                (status, json.dumps(stats) if stats else None, job_id)
            )
        elif status == "failed":
            conn.execute(
                "UPDATE parse_jobs SET status = ?, completed_at = datetime('now'), error_message = ? WHERE id = ?",
                (status, error_message, job_id)
            )
        else:
            conn.execute(
                "UPDATE parse_jobs SET status = ? WHERE id = ?",
                (status, job_id)
            )


def get_parse_job(job_id: int) -> Optional[ParseJob]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM parse_jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return None
        return ParseJob(
            id=row["id"],
            root_path=row["root_path"],
            status=row["status"],
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            error_message=row["error_message"],
            stats=json.loads(row["stats_json"]) if row["stats_json"] else None,
        )


def store_nodes(job_id: int, nodes: list[NodeCreate]) -> list[int]:
    stored_ids = []
    with transaction() as conn:
        for node in nodes:
            cursor = conn.execute(
                """INSERT INTO nodes (job_id, node_type, name, qualified_name, file_path,
                   line_start, line_end, column_start, column_end, language, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (job_id, node.node_type.value, node.name, node.qualified_name, node.file_path,
                 node.line_start, node.line_end, node.column_start, node.column_end,
                 node.language, json.dumps(node.metadata) if node.metadata else None)
            )
            stored_ids.append(cursor.lastrowid)
    return stored_ids


def store_edges(job_id: int, edges: list[EdgeCreate], node_id_offset: int = 0) -> list[int]:
    stored_ids = []
    with transaction() as conn:
        for edge in edges:
            source_id = edge.source_id + node_id_offset if edge.source_id >= 0 else edge.source_id
            target_id = edge.target_id + node_id_offset if edge.target_id >= 0 else edge.target_id

            if source_id < 0 or target_id < 0:
                continue

            cursor = conn.execute(
                """INSERT INTO edges (job_id, source_id, target_id, edge_type, metadata_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (job_id, source_id, target_id, edge.edge_type.value,
                 json.dumps(edge.metadata) if edge.metadata else None)
            )
            stored_ids.append(cursor.lastrowid)
    return stored_ids


def get_nodes(job_id: int, node_type: Optional[str] = None, name: Optional[str] = None,
              limit: int = 50, offset: int = 0) -> tuple[list[Node], int]:
    with get_connection() as conn:
        where = ["job_id = ?"]
        params = [job_id]
        if node_type:
            where.append("node_type = ?")
            params.append(node_type)
        if name:
            where.append("name LIKE ?")
            params.append(f"%{name}%")

        where_clause = " AND ".join(where)

        total = conn.execute(f"SELECT COUNT(*) FROM nodes WHERE {where_clause}", params).fetchone()[0]

        params.extend([limit, offset])
        rows = conn.execute(
            f"SELECT * FROM nodes WHERE {where_clause} ORDER BY id LIMIT ? OFFSET ?", params
        ).fetchall()

        nodes = []
        for row in rows:
            nodes.append(Node(
                id=row["id"],
                job_id=row["job_id"],
                node_type=row["node_type"],
                name=row["name"],
                qualified_name=row["qualified_name"],
                file_path=row["file_path"],
                line_start=row["line_start"],
                line_end=row["line_end"],
                column_start=row["column_start"],
                column_end=row["column_end"],
                language=row["language"],
                metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else None,
                created_at=datetime.fromisoformat(row["created_at"]),
            ))
        return nodes, total


def get_edges(job_id: int, source_id: Optional[int] = None, target_id: Optional[int] = None,
              edge_type: Optional[str] = None, limit: int = 50, offset: int = 0) -> tuple[list[Edge], int]:
    with get_connection() as conn:
        where = ["job_id = ?"]
        params = [job_id]
        if source_id:
            where.append("source_id = ?")
            params.append(source_id)
        if target_id:
            where.append("target_id = ?")
            params.append(target_id)
        if edge_type:
            where.append("edge_type = ?")
            params.append(edge_type)

        where_clause = " AND ".join(where)

        total = conn.execute(f"SELECT COUNT(*) FROM edges WHERE {where_clause}", params).fetchone()[0]

        params.extend([limit, offset])
        rows = conn.execute(
            f"SELECT * FROM edges WHERE {where_clause} ORDER BY id LIMIT ? OFFSET ?", params
        ).fetchall()

        edges = []
        for row in rows:
            edges.append(Edge(
                id=row["id"],
                job_id=row["job_id"],
                source_id=row["source_id"],
                target_id=row["target_id"],
                edge_type=row["edge_type"],
                metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else None,
                created_at=datetime.fromisoformat(row["created_at"]),
            ))
        return edges, total


def get_graph_summary(job_id: int) -> Optional[GraphSummary]:
    with get_connection() as conn:
        job = conn.execute("SELECT * FROM parse_jobs WHERE id = ?", (job_id,)).fetchone()
        if not job:
            return None

        total_nodes = conn.execute("SELECT COUNT(*) FROM nodes WHERE job_id = ?", (job_id,)).fetchone()[0]
        total_edges = conn.execute("SELECT COUNT(*) FROM edges WHERE job_id = ?", (job_id,)).fetchone()[0]

        node_types_rows = conn.execute(
            "SELECT node_type, COUNT(*) as count FROM nodes WHERE job_id = ? GROUP BY node_type", (job_id,)
        ).fetchall()
        node_types = {row["node_type"]: row["count"] for row in node_types_rows}

        edge_types_rows = conn.execute(
            "SELECT edge_type, COUNT(*) as count FROM edges WHERE job_id = ? GROUP BY edge_type", (job_id,)
        ).fetchall()
        edge_types = {row["edge_type"]: row["count"] for row in edge_types_rows}

        languages_rows = conn.execute(
            "SELECT language, COUNT(*) as count FROM nodes WHERE job_id = ? GROUP BY language", (job_id,)
        ).fetchall()
        languages = {row["language"]: row["count"] for row in languages_rows}

        return GraphSummary(
            job_id=job_id,
            total_nodes=total_nodes,
            total_edges=total_edges,
            node_types=node_types,
            edge_types=edge_types,
            languages=languages,
        )


def export_graph_json(job_id: int) -> dict:
    nodes, _ = get_nodes(job_id, limit=10000, offset=0)
    edges, _ = get_edges(job_id, limit=10000, offset=0)

    return {
        "nodes": [n.model_dump() for n in nodes],
        "edges": [e.model_dump() for e in edges],
    }


def export_graph_graphml(job_id: int) -> str:
    nodes, _ = get_nodes(job_id, limit=10000, offset=0)
    edges, _ = get_edges(job_id, limit=10000, offset=0)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns '
        'http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">',
        '  <key id="label" for="node" attr.name="label" attr.type="string"/>',
        '  <key id="type" for="node" attr.name="type" attr.type="string"/>',
        '  <key id="file" for="node" attr.name="file" attr.type="string"/>',
        '  <key id="line" for="node" attr.name="line" attr.type="int"/>',
        '  <key id="language" for="node" attr.name="language" attr.type="string"/>',
        '  <key id="edge_type" for="edge" attr.name="type" attr.type="string"/>',
        '  <graph id="G" edgedefault="directed">',
    ]

    for node in nodes:
        lines.append(f'    <node id="n{node.id}">')
        lines.append(f'      <data key="label">{node.name}</data>')
        lines.append(f'      <data key="type">{node.node_type}</data>')
        lines.append(f'      <data key="file">{node.file_path}</data>')
        lines.append(f'      <data key="line">{node.line_start}</data>')
        lines.append(f'      <data key="language">{node.language}</data>')
        lines.append('    </node>')

    for edge in edges:
        lines.append(f'    <edge id="e{edge.id}" source="n{edge.source_id}" target="n{edge.target_id}">')
        lines.append(f'      <data key="edge_type">{edge.edge_type}</data>')
        lines.append('    </edge>')

    lines.append('  </graph>')
    lines.append('</graphml>')

    return "\n".join(lines)


def export_graph_dot(job_id: int) -> str:
    nodes, _ = get_nodes(job_id, limit=10000, offset=0)
    edges, _ = get_edges(job_id, limit=10000, offset=0)

    lines = ['digraph G {', '  rankdir=LR;', '  node [shape=box, fontname="Arial"];']

    for node in nodes:
        label = f'{node.name}\\n({node.node_type})'
        lines.append(f'  n{node.id} [label="{label}", tooltip="{node.file_path}:{node.line_start}"];')

    for edge in edges:
        lines.append(f'  n{edge.source_id} -> n{edge.target_id} [label="{edge.edge_type}"];')

    lines.append('}')
    return "\n".join(lines)