export type NodeType =
  | 'module'
  | 'class'
  | 'function'
  | 'method'
  | 'import'
  | 'variable'
  | 'decorator'
  | 'interface'
  | 'type_alias'
  | 'enum'
  | 'namespace';

export type EdgeType =
  | 'imports'
  | 'calls'
  | 'inherits'
  | 'implements'
  | 'contains'
  | 'references'
  | 'decorates'
  | 'overrides'
  | 'uses_type';

export interface Node {
  id: number;
  job_id: number;
  node_type: NodeType;
  name: string;
  qualified_name: string | null;
  file_path: string;
  line_start: number;
  line_end: number;
  column_start: number | null;
  column_end: number | null;
  language: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface Edge {
  id: number;
  job_id: number;
  source_id: number;
  target_id: number;
  edge_type: EdgeType;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface GraphNodesResponse {
  nodes: Node[];
  total: number;
  limit: number;
  offset: number;
}

export interface GraphEdgesResponse {
  edges: Edge[];
  total: number;
  limit: number;
  offset: number;
}

export interface GraphSummary {
  job_id: number;
  total_nodes: number;
  total_edges: number;
  node_types: Record<string, number>;
  edge_types: Record<string, number>;
  languages: Record<string, number>;
}

export interface ParseRequest {
  root_path: string;
  include_patterns?: string[];
  exclude_patterns?: string[];
  languages?: string[];
}

export interface ParseResponse {
  job_id: number;
  status: string;
  message: string;
}

export interface ParseJob {
  id: number;
  root_path: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
  stats: Record<string, unknown> | null;
}