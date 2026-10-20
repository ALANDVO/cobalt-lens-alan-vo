import axios, { AxiosInstance } from 'axios';
import type {
  GraphNodesResponse,
  GraphEdgesResponse,
  GraphSummary,
  ParseRequest,
  ParseResponse,
  ParseJob,
  Node,
  Edge,
} from '@/types/api';

const API_BASE = '/api/v1';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000,
    });
  }

  async parseCodebase(request: ParseRequest): Promise<ParseResponse> {
    const response = await this.client.post<ParseResponse>('/parse', request);
    return response.data;
  }

  async getParseJobStatus(jobId: number): Promise<ParseJob> {
    const response = await this.client.get<ParseJob>(`/parse/${jobId}`);
    return response.data;
  }

  async getGraphSummary(jobId: number): Promise<GraphSummary> {
    const response = await this.client.get<GraphSummary>(`/graph/summary`, {
      params: { job_id: jobId },
    });
    return response.data;
  }

  async getNodes(
    jobId: number,
    options?: {
      node_type?: string;
      name?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<GraphNodesResponse> {
    const response = await this.client.get<GraphNodesResponse>('/graph/nodes', {
      params: { job_id: jobId, ...options },
    });
    return response.data;
  }

  async getEdges(
    jobId: number,
    options?: {
      source_id?: number;
      target_id?: number;
      edge_type?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<GraphEdgesResponse> {
    const response = await this.client.get<GraphEdgesResponse>('/graph/edges', {
      params: { job_id: jobId, ...options },
    });
    return response.data;
  }

  async exportJson(jobId: number): Promise<{ nodes: Node[]; edges: Edge[] }> {
    const response = await this.client.get(`/graph/export/json`, {
      params: { job_id: jobId },
    });
    return response.data;
  }

  async exportGraphml(jobId: number): Promise<string> {
    const response = await this.client.get(`/graph/export/graphml`, {
      params: { job_id: jobId },
      responseType: 'text',
    });
    return response.data;
  }

  async exportDot(jobId: number): Promise<string> {
    const response = await this.client.get(`/graph/export/dot`, {
      params: { job_id: jobId },
      responseType: 'text',
    });
    return response.data;
  }
}

export const apiClient = new ApiClient();