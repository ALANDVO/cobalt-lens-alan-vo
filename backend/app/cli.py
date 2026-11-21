#!/usr/bin/env python3
"""CLI entry for /graphify skill."""
import sys
from pathlib import Path
from app.services.parser import parse_directory
from app.models.graph import NodeType, EdgeType


def cmd_parse(args):
    """Parse a directory and output graph nodes/edges."""
    import argparse
    parser = argparse.ArgumentParser(
        prog="graphify parse",
        description="Parse a directory of code and output graph nodes/edges",
    )
    parser.add_argument("directory", help="Directory to parse")
    parser.add_argument(
        "--output", "-o", choices=["json", "dot"], default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--include", "-i", action="append", default=[],
        help="Include pattern (can be specified multiple times)",
    )
    parser.add_argument(
        "--exclude", "-e", action="append", default=[],
        help="Exclude pattern (can be specified multiple times)",
    )
    parsed = parser.parse_args(args)

    directory = parsed.directory
    output_format = parsed.output
    include_patterns = parsed.include
    exclude_patterns = parsed.exclude

    try:
        nodes, edges, stats = parse_directory(
            directory,
            job_id=1,
            include_patterns=include_patterns if include_patterns else None,
            exclude_patterns=exclude_patterns if exclude_patterns else None,
            languages=None,
        )
    except ValueError as ve:
        print(f"Error: {ve}", file=sys.stderr)
        sys.exit(1)

    if output_format == "json":
        import json
        output = {
            "nodes": [
                {
                    "id": n.node_type + ":" + n.name if n.name else n.node_type,
                    "type": n.node_type,
                    "name": n.name,
                    "qualified": n.qualified_name or "",
                    "file": n.file_path,
                    "language": n.language,
                    "metadata": n.metadata or {},
                }
                for n in nodes
            ],
            "edges": [
                {
                    "source": e.source_id,
                    "target": e.target_id,
                    "type": e.edge_type,
                    "metadata": e.metadata or {},
                }
                for e in edges
            ],
            "stats": stats,
        }
        print(json.dumps(output, indent=2))
    elif output_format == "dot":
        lines = ["digraph G {"]
        for e in edges:
            src = e.source_id
            tgt = e.target_id
            etype = e.edge_type
            lines.append(f'  {src} -> {tgt} [label="{etype}"];')
        lines.append("}")
        print("\n".join(lines))


def main():
    if len(sys.argv) < 2:
        print("Usage: graphify parse <directory> [options]", file=sys.stderr)
        print("       graphify parse --help", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    remaining = sys.argv[2:]

    if command == "parse":
        cmd_parse(remaining)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
