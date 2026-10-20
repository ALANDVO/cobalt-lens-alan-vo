from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class NodeType(str, Enum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    IMPORT = "import"
    VARIABLE = "variable"
    DECORATOR = "decorator"
    INTERFACE = "interface"
    TYPE_ALIAS = "type_alias"
    ENUM = "enum"
    NAMESPACE = "namespace"


class EdgeType(str, Enum):
    IMPORTS = "imports"
    CALLS = "calls"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    CONTAINS = "contains"
    REFERENCES = "references"
    DECORATES = "decorates"
    OVERRIDES = "overrides"
    USES_TYPE = "uses_type"


class NodeBase(BaseModel):
    node_type: NodeType
    name: str
    qualified_name: Optional[str] = None
    file_path: str
    line_start: int
    line_end: int
    column_start: Optional[int] = None
    column_end: Optional[int] = None
    language: str
    metadata: Optional[dict] = None


class NodeCreate(NodeBase):
    pass


class Node(NodeBase):
    id: int
    job_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class EdgeBase(BaseModel):
    source_id: int
    target_id: int
    edge_type: EdgeType
    metadata: Optional[dict] = None


class EdgeCreate(EdgeBase):
    pass


class Edge(EdgeBase):
    id: int
    job_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ParseRequest(BaseModel):
    root_path: str = Field(..., description="Root directory to parse")
    include_patterns: Optional[list[str]] = Field(default=None)
    exclude_patterns: Optional[list[str]] = Field(default=None)
    languages: Optional[list[str]] = Field(default=None)


class ParseJobCreate(BaseModel):
    root_path: str
    status: str = "pending"


class ParseJob(BaseModel):
    id: int
    root_path: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    stats: Optional[dict] = None

    class Config:
        from_attributes = True


class GraphNodesResponse(BaseModel):
    nodes: list[Node]
    total: int
    limit: int
    offset: int


class GraphEdgesResponse(BaseModel):
    edges: list[Edge]
    total: int
    limit: int
    offset: int


class GraphSummary(BaseModel):
    job_id: int
    total_nodes: int
    total_edges: int
    node_types: dict[str, int]
    edge_types: dict[str, int]
    languages: dict[str, int]