import os
import json
from pathlib import Path
from typing import Optional
from tree_sitter import Language, Parser, Node as TSNode
from tree_sitter_python import language as python_language_fn
from tree_sitter_javascript import language as javascript_language_fn
from tree_sitter_typescript import language_typescript as typescript_language_fn, language_tsx as tsx_language_fn

from app.models.graph import NodeCreate, EdgeCreate, NodeType, EdgeType
from app.core.config import settings


PY_LANGUAGE = Language(python_language_fn())
JS_LANGUAGE = Language(javascript_language_fn())
TS_LANGUAGE = Language(typescript_language_fn())
TSX_LANGUAGE = Language(tsx_language_fn())


LANGUAGE_MAP = {
    ".py": (PY_LANGUAGE, "python"),
    ".js": (JS_LANGUAGE, "javascript"),
    ".jsx": (JS_LANGUAGE, "javascript"),
    ".ts": (TS_LANGUAGE, "typescript"),
    ".tsx": (TSX_LANGUAGE, "typescript"),
}


class ASTParser:
    def __init__(self):
        self.parsers: dict[str, Parser] = {}
        for ext, (lang, _) in LANGUAGE_MAP.items():
            parser = Parser(lang)
            self.parsers[ext] = parser

    def parse_file(self, file_path: Path, job_id: int) -> tuple[list[NodeCreate], list[EdgeCreate]]:
        ext = file_path.suffix
        if ext not in self.parsers:
            return [], []

        parser = self.parsers[ext]
        _, language_name = LANGUAGE_MAP[ext]

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return [], []

        if len(content) > settings.max_file_size_mb * 1024 * 1024:
            return [], []

        tree = parser.parse(content.encode("utf-8"))
        root_node = tree.root_node

        nodes: list[NodeCreate] = []
        edges: list[EdgeCreate] = []
        node_id_map: dict[int, int] = {}

        if language_name == "python":
            self._parse_python(root_node, content, file_path, job_id, nodes, edges, node_id_map)
        elif language_name in ("javascript", "typescript"):
            self._parse_js_ts(root_node, content, file_path, job_id, nodes, edges, node_id_map, language_name)

        return nodes, edges

    def _get_node_text(self, node: TSNode, content: str) -> str:
        return content[node.start_byte:node.end_byte]

    def _add_node(self, nodes: list, node_id_map: dict, ts_node: TSNode, node_type: NodeType,
                  name: str, qualified_name: Optional[str], file_path: Path, language: str,
                  metadata: Optional[dict] = None) -> int:
        node_create = NodeCreate(
            node_type=node_type,
            name=name,
            qualified_name=qualified_name,
            file_path=str(file_path),
            line_start=ts_node.start_point.row + 1,
            line_end=ts_node.end_point.row + 1,
            column_start=ts_node.start_point.column,
            column_end=ts_node.end_point.column,
            language=language,
            metadata=metadata,
        )
        nodes.append(node_create)
        node_id = len(nodes) - 1
        node_id_map[ts_node.id] = node_id
        return node_id

    def _parse_python(self, root: TSNode, content: str, file_path: Path, job_id: int,
                      nodes: list, edges: list, node_id_map: dict):
        module_name = file_path.stem
        self._add_node(nodes, node_id_map, root, NodeType.MODULE, module_name, module_name,
                       file_path, "python", {"docstring": self._get_module_docstring(root, content)})

        for child in root.children:
            self._walk_python(child, content, file_path, job_id, nodes, edges, node_id_map,
                              parent_qualified=module_name)

    def _get_module_docstring(self, root: TSNode, content: str) -> Optional[str]:
        for child in root.children:
            if child.type == "expression_statement":
                for grandchild in child.children:
                    if grandchild.type == "string":
                        return self._get_node_text(grandchild, content).strip('"\'')
        return None

    def _walk_python(self, node: TSNode, content: str, file_path: Path, job_id: int,
                     nodes: list, edges: list, node_id_map: dict, parent_qualified: str,
                     class_context: Optional[str] = None):
        if node.type == "function_definition":
            name = self._get_function_name(node, content)
            qualified = f"{parent_qualified}.{name}" if parent_qualified else name
            node_type = NodeType.METHOD if class_context else NodeType.FUNCTION
            node_idx = self._add_node(nodes, node_id_map, node, node_type, name, qualified,
                                      file_path, "python", {"decorators": self._get_decorators(node, content)})

            if class_context:
                parent_idx = self._find_parent_class(node, node_id_map)
                if parent_idx is not None:
                    edges.append(EdgeCreate(source_id=parent_idx, target_id=node_idx,
                                            edge_type=EdgeType.CONTAINS))

            self._extract_python_calls(node, content, node_idx, edges, node_id_map)

        elif node.type == "class_definition":
            name = self._get_class_name(node, content)
            qualified = f"{parent_qualified}.{name}" if parent_qualified else name
            node_idx = self._add_node(nodes, node_id_map, node, NodeType.CLASS, name, qualified,
                                      file_path, "python", {"bases": self._get_class_bases(node, content)})

            for base in self._get_class_bases(node, content):
                edges.append(EdgeCreate(source_id=node_idx, target_id=-1,
                                        edge_type=EdgeType.INHERITS,
                                        metadata={"base_class": base}))

            for child in node.children:
                if child.type == "block":
                    for grandchild in child.children:
                        self._walk_python(grandchild, content, file_path, job_id, nodes, edges,
                                          node_id_map, qualified, class_context=name)

        elif node.type == "import_statement" or node.type == "import_from_statement":
            imports = self._get_imports(node, content)
            for imp in imports:
                imp_name = imp["name"]
                qualified = f"{parent_qualified}.{imp_name}" if parent_qualified else imp_name
                node_idx = self._add_node(nodes, node_id_map, node, NodeType.IMPORT, imp_name, qualified,
                                          file_path, "python", {"module": imp.get("module"), "alias": imp.get("alias")})
                if imp.get("module"):
                    edges.append(EdgeCreate(source_id=node_idx, target_id=-1,
                                            edge_type=EdgeType.IMPORTS,
                                            metadata={"module": imp["module"]}))

        elif node.type == "decorator":
            pass

        for child in node.children:
            self._walk_python(child, content, file_path, job_id, nodes, edges, node_id_map,
                              parent_qualified, class_context)

    def _get_function_name(self, node: TSNode, content: str) -> str:
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text(child, content)
        return "<anonymous>"

    def _get_class_name(self, node: TSNode, content: str) -> str:
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text(child, content)
        return "<anonymous>"

    def _get_decorators(self, node: TSNode, content: str) -> list[str]:
        decorators = []
        for child in node.children:
            if child.type == "decorator":
                for grandchild in child.children:
                    if grandchild.type in ("identifier", "attribute", "call"):
                        decorators.append(self._get_node_text(grandchild, content))
        return decorators

    def _get_class_bases(self, node: TSNode, content: str) -> list[str]:
        bases = []
        for child in node.children:
            if child.type == "argument_list":
                for grandchild in child.children:
                    if grandchild.type in ("identifier", "attribute"):
                        bases.append(self._get_node_text(grandchild, content))
        return bases

    def _get_imports(self, node: TSNode, content: str) -> list[dict]:
        imports = []
        text = self._get_node_text(node, content)
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    name = self._get_node_text(child, content)
                    imports.append({"name": name.split(".")[-1], "module": name, "alias": None})
                elif child.type == "aliased_import":
                    for gc in child.children:
                        if gc.type == "dotted_name":
                            name = self._get_node_text(gc, content)
                        elif gc.type == "identifier":
                            alias = self._get_node_text(gc, content)
                            imports.append({"name": name.split(".")[-1], "module": name, "alias": alias})
        elif node.type == "import_from_statement":
            module = ""
            for child in node.children:
                if child.type == "dotted_name":
                    module = self._get_node_text(child, content)
                elif child.type == "wildcard_import":
                    imports.append({"name": "*", "module": module, "alias": None})
                elif child.type == "import_prefix":
                    for gc in child.children:
                        if gc.type == "identifier":
                            name = self._get_node_text(gc, content)
                            imports.append({"name": name, "module": module, "alias": None})
                        elif gc.type == "aliased_import":
                            imp_name = ""
                            alias = ""
                            for ggc in gc.children:
                                if ggc.type == "identifier":
                                    if not imp_name:
                                        imp_name = self._get_node_text(ggc, content)
                                    else:
                                        alias = self._get_node_text(ggc, content)
                            if imp_name:
                                imports.append({"name": imp_name, "module": module, "alias": alias})
        return imports

    def _extract_python_calls(self, node: TSNode, content: str, caller_idx: int,
                              edges: list, node_id_map: dict):
        for child in node.children:
            if child.type == "call":
                for gc in child.children:
                    if gc.type in ("identifier", "attribute"):
                        callee_name = self._get_node_text(gc, content)
                        edges.append(EdgeCreate(source_id=caller_idx, target_id=-1,
                                                edge_type=EdgeType.CALLS,
                                                metadata={"callee": callee_name}))
            self._extract_python_calls(child, content, caller_idx, edges, node_id_map)

    def _find_parent_class(self, node: TSNode, node_id_map: dict) -> Optional[int]:
        parent = node.parent
        while parent:
            if parent.id in node_id_map:
                return node_id_map[parent.id]
            parent = parent.parent
        return None

    def _parse_js_ts(self, root: TSNode, content: str, file_path: Path, job_id: int,
                     nodes: list, edges: list, node_id_map: dict, language: str):
        module_name = file_path.stem
        self._add_node(nodes, node_id_map, root, NodeType.MODULE, module_name, module_name,
                       file_path, language)

        for child in root.children:
            self._walk_js_ts(child, content, file_path, job_id, nodes, edges, node_id_map,
                             parent_qualified=module_name, language=language)

    def _walk_js_ts(self, node: TSNode, content: str, file_path: Path, job_id: int,
                    nodes: list, edges: list, node_id_map: dict, parent_qualified: str,
                    language: str, class_context: Optional[str] = None):
        if node.type in ("function_declaration", "function_expression", "arrow_function",
                         "method_definition", "generator_function_declaration"):
            name = self._get_js_function_name(node, content)
            qualified = f"{parent_qualified}.{name}" if parent_qualified else name
            node_type = NodeType.METHOD if class_context else NodeType.FUNCTION
            node_idx = self._add_node(nodes, node_id_map, node, node_type, name, qualified,
                                      file_path, language)

            if class_context:
                parent_idx = self._find_parent_class(node, node_id_map)
                if parent_idx is not None:
                    edges.append(EdgeCreate(source_id=parent_idx, target_id=node_idx,
                                            edge_type=EdgeType.CONTAINS))

            self._extract_js_calls(node, content, node_idx, edges, node_id_map)

        elif node.type in ("class_declaration", "class_expression"):
            name = self._get_js_class_name(node, content)
            qualified = f"{parent_qualified}.{name}" if parent_qualified else name
            node_idx = self._add_node(nodes, node_id_map, node, NodeType.CLASS, name, qualified,
                                      file_path, language, {"extends": self._get_js_extends(node, content)})

            extends = self._get_js_extends(node, content)
            if extends:
                edges.append(EdgeCreate(source_id=node_idx, target_id=-1,
                                        edge_type=EdgeType.INHERITS,
                                        metadata={"base_class": extends}))

            implements = self._get_js_implements(node, content)
            for impl in implements:
                edges.append(EdgeCreate(source_id=node_idx, target_id=-1,
                                        edge_type=EdgeType.IMPLEMENTS,
                                        metadata={"interface": impl}))

            for child in node.children:
                if child.type == "class_body":
                    for gc in child.children:
                        self._walk_js_ts(gc, content, file_path, job_id, nodes, edges,
                                         node_id_map, qualified, language, class_context=name)

        elif node.type in ("import_statement", "import_declaration", "export_statement"):
            imports = self._get_js_imports(node, content)
            for imp in imports:
                imp_name = imp["name"]
                qualified = f"{parent_qualified}.{imp_name}" if parent_qualified else imp_name
                node_idx = self._add_node(nodes, node_id_map, node, NodeType.IMPORT, imp_name, qualified,
                                          file_path, language, {"module": imp.get("module"), "alias": imp.get("alias")})
                if imp.get("module"):
                    edges.append(EdgeCreate(source_id=node_idx, target_id=-1,
                                            edge_type=EdgeType.IMPORTS,
                                            metadata={"module": imp["module"]}))

        elif node.type in ("interface_declaration", "type_alias_declaration"):
            name = self._get_js_interface_name(node, content)
            qualified = f"{parent_qualified}.{name}" if parent_qualified else name
            node_type = NodeType.INTERFACE if node.type == "interface_declaration" else NodeType.TYPE_ALIAS
            self._add_node(nodes, node_id_map, node, node_type, name, qualified,
                           file_path, language)

        elif node.type == "enum_declaration":
            name = self._get_js_enum_name(node, content)
            qualified = f"{parent_qualified}.{name}" if parent_qualified else name
            self._add_node(nodes, node_id_map, node, NodeType.ENUM, name, qualified,
                           file_path, language)

        elif node.type == "namespace_declaration":
            name = self._get_js_namespace_name(node, content)
            qualified = f"{parent_qualified}.{name}" if parent_qualified else name
            self._add_node(nodes, node_id_map, node, NodeType.NAMESPACE, name, qualified,
                           file_path, language)

        for child in node.children:
            self._walk_js_ts(child, content, file_path, job_id, nodes, edges, node_id_map,
                             parent_qualified, language, class_context)

    def _get_js_function_name(self, node: TSNode, content: str) -> str:
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text(child, content)
            if child.type == "property_identifier":
                return self._get_node_text(child, content)
        return "<anonymous>"

    def _get_js_class_name(self, node: TSNode, content: str) -> str:
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text(child, content)
        return "<anonymous>"

    def _get_js_extends(self, node: TSNode, content: str) -> Optional[str]:
        for child in node.children:
            if child.type == "class_heritage":
                for gc in child.children:
                    if gc.type == "extends_clause":
                        for ggc in gc.children:
                            if ggc.type == "identifier":
                                return self._get_node_text(ggc, content)
                    elif gc.type == "identifier" and not any(ggc.type == "implements" for ggc in gc.children if hasattr(gc, 'children')):
                        return self._get_node_text(gc, content)
                    elif gc.type == "member_expression":
                        return self._get_node_text(gc, content)
        return None

    def _get_js_implements(self, node: TSNode, content: str) -> list[str]:
        implements = []
        for child in node.children:
            if child.type == "class_heritage":
                for gc in child.children:
                    if gc.type == "implements_clause":
                        for ggc in gc.children:
                            if ggc.type == "type_identifier":
                                implements.append(self._get_node_text(ggc, content))
                    elif gc.type == "identifier" and gc.text.decode() != "implements":
                        implements.append(self._get_node_text(gc, content))
        return implements

    def _get_js_imports(self, node: TSNode, content: str) -> list[dict]:
        imports = []
        text = self._get_node_text(node, content)

        if "import" in text:
            if "from" in text:
                parts = text.split("from")
                if len(parts) == 2:
                    module = parts[1].strip().strip(";").strip('"\'')
                    imported = parts[0].replace("import", "").strip()
                    for name in imported.split(","):
                        name = name.strip().strip("{}").strip()
                        if " as " in name:
                            n, alias = name.split(" as ")
                            imports.append({"name": n.strip(), "module": module, "alias": alias.strip()})
                        else:
                            imports.append({"name": name, "module": module, "alias": None})
            else:
                imported = text.replace("import", "").strip().strip(";")
                for name in imported.split(","):
                    name = name.strip()
                    if " as " in name:
                        n, alias = name.split(" as ")
                        imports.append({"name": n.strip(), "module": "", "alias": alias.strip()})
                    else:
                        imports.append({"name": name, "module": "", "alias": None})
        return imports

    def _get_js_interface_name(self, node: TSNode, content: str) -> str:
        for child in node.children:
            if child.type == "type_identifier":
                return self._get_node_text(child, content)
        return "<anonymous>"

    def _get_js_enum_name(self, node: TSNode, content: str) -> str:
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text(child, content)
        return "<anonymous>"

    def _get_js_namespace_name(self, node: TSNode, content: str) -> str:
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text(child, content)
        return "<anonymous>"

    def _extract_js_calls(self, node: TSNode, content: str, caller_idx: int,
                          edges: list, node_id_map: dict):
        if node.type == "call_expression":
            for child in node.children:
                if child.type in ("identifier", "member_expression", "property_identifier"):
                    callee_name = self._get_node_text(child, content)
                    edges.append(EdgeCreate(source_id=caller_idx, target_id=-1,
                                            edge_type=EdgeType.CALLS,
                                            metadata={"callee": callee_name}))
        for child in node.children:
            self._extract_js_calls(child, content, caller_idx, edges, node_id_map)

    def _find_parent_class(self, node: TSNode, node_id_map: dict) -> Optional[int]:
        parent = node.parent
        while parent:
            if parent.id in node_id_map:
                return node_id_map[parent.id]
            parent = parent.parent
        return None


def parse_directory(root_path: str, job_id: int,
                    include_patterns: Optional[list[str]] = None,
                    exclude_patterns: Optional[list[str]] = None,
                    languages: Optional[list[str]] = None) -> tuple[list[NodeCreate], list[EdgeCreate], dict]:
    parser = ASTParser()
    all_nodes: list[NodeCreate] = []
    all_edges: list[EdgeCreate] = []
    stats = {"files_parsed": 0, "nodes_created": 0, "edges_created": 0, "languages": {}}

    root = Path(root_path).resolve()
    if not root.exists():
        raise ValueError(f"Root path does not exist: {root_path}")

    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix not in LANGUAGE_MAP:
            continue

        lang = LANGUAGE_MAP[file_path.suffix][1]
        if languages and lang not in languages:
            continue

        if include_patterns:
            if not any(file_path.match(p) for p in include_patterns):
                continue
        if exclude_patterns:
            if any(file_path.match(p) for p in exclude_patterns):
                continue

        try:
            nodes, edges = parser.parse_file(file_path, job_id)
            if nodes or edges:
                stats["files_parsed"] += 1
                stats["nodes_created"] += len(nodes)
                stats["edges_created"] += len(edges)
                stats["languages"][lang] = stats["languages"].get(lang, 0) + 1
                all_nodes.extend(nodes)
                all_edges.extend(edges)
        except Exception as e:
            continue

    return all_nodes, all_edges, stats