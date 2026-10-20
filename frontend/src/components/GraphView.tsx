import { useEffect, useRef, useState } from 'react';
import cytoscape, { Core, NodeSingular, EdgeSingular } from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import { apiClient } from '@/api/client';
import type { GraphSummary } from '@/types/api';
import './GraphView.css';

cytoscape.use(coseBilkent);

interface GraphViewProps {
  jobId: number;
  summary: GraphSummary;
  onBack: () => void;
}

interface CytoscapeNode {
  id: string;
  label: string;
  type: string;
  file: string;
  line: number;
  language: string;
}

interface CytoscapeEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}

export function GraphView({ jobId, summary, onBack }: GraphViewProps) {
  const cyRef = useRef<HTMLDivElement>(null);
  const [nodes, setNodes] = useState<CytoscapeNode[]>([]);
  const [edges, setEdges] = useState<CytoscapeEdge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<CytoscapeNode | null>(null);
  const [filterType, setFilterType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const nodeTypes = ['all', 'module', 'class', 'function', 'method', 'import', 'interface', 'type_alias', 'enum', 'namespace'];

  useEffect(() => {
    let cy: Core | null = null;

    const fetchGraphData = async () => {
      setLoading(true);
      try {
        const [nodesRes, edgesRes] = await Promise.all([
          apiClient.getNodes(jobId, { limit: 500 }),
          apiClient.getEdges(jobId, { limit: 1000 }),
        ]);

        const cyNodes: CytoscapeNode[] = nodesRes.nodes.map((n) => ({
          id: String(n.id),
          label: n.name,
          type: n.node_type,
          file: n.file_path,
          line: n.line_start,
          language: n.language,
        }));

        const cyEdges: CytoscapeEdge[] = edgesRes.edges.map((e) => ({
          id: `e${e.id}`,
          source: String(e.source_id),
          target: String(e.target_id),
          type: e.edge_type,
        }));

        setNodes(cyNodes);
        setEdges(cyEdges);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load graph');
      } finally {
        setLoading(false);
      }
    };

    fetchGraphData();

    if (cyRef.current) {
      cy = cytoscape({
        container: cyRef.current,
        elements: [],
        style: [
          {
            selector: 'node',
            style: {
              label: 'data(label)',
              'background-color': '#4a90d9',
              color: '#fff',
              'text-valign': 'center',
              'text-halign': 'center',
              'font-size': '10px',
              width: 'label',
              height: 'label',
              padding: '8px 12px',
              'text-max-width': '120px',
            } as cytoscape.Css.Node,
          },
          {
            selector: 'node[type="class"]',
            style: { 'background-color': '#e67e22', 'shape': 'rectangle' } as cytoscape.Css.Node,
          },
          {
            selector: 'node[type="function"], node[type="method"]',
            style: { 'background-color': '#27ae60', 'shape': 'ellipse' } as cytoscape.Css.Node,
          },
          {
            selector: 'node[type="import"]',
            style: { 'background-color': '#9b59b6', 'shape': 'triangle' } as cytoscape.Css.Node,
          },
          {
            selector: 'node[type="module"]',
            style: { 'background-color': '#34495e', 'shape': 'rectangle', width: 150 } as cytoscape.Css.Node,
          },
          {
            selector: 'node[type="interface"]',
            style: { 'background-color': '#1abc9c', 'shape': 'diamond' } as cytoscape.Css.Node,
          },
          {
            selector: 'node[type="type_alias"]',
            style: { 'background-color': '#16a085', 'shape': 'diamond' } as cytoscape.Css.Node,
          },
          {
            selector: 'node[type="enum"]',
            style: { 'background-color': '#f39c12', 'shape': 'hexagon' } as cytoscape.Css.Node,
          },
          {
            selector: 'node[type="namespace"]',
            style: { 'background-color': '#8e44ad', 'shape': 'tag' } as cytoscape.Css.Node,
          },
          {
            selector: 'node:selected',
            style: {
              'border-width': 3,
              'border-color': '#f39c12',
              'background-color': '#f1c40f',
              color: '#000',
            } as cytoscape.Css.Node,
          },
          {
            selector: 'edge',
            style: {
              width: 1.5,
              'line-color': '#95a5a6',
              'target-arrow-color': '#95a5a6',
              'target-arrow-shape': 'triangle',
              'curve-style': 'bezier',
              'font-size': '8px',
              label: 'data(type)',
              'text-background-color': '#fff',
              'text-background-opacity': 0.8,
              'text-background-padding': '2px',
            } as cytoscape.Css.Edge,
          },
          {
            selector: 'edge[type="inherits"]',
            style: { 'line-color': '#e67e22', 'target-arrow-color': '#e67e22' } as cytoscape.Css.Edge,
          },
          {
            selector: 'edge[type="calls"]',
            style: { 'line-color': '#27ae60', 'target-arrow-color': '#27ae60' } as cytoscape.Css.Edge,
          },
          {
            selector: 'edge[type="imports"]',
            style: { 'line-color': '#9b59b6', 'target-arrow-color': '#9b59b6' } as cytoscape.Css.Edge,
          },
          {
            selector: 'edge[type="contains"]',
            style: { 'line-color': '#3498db', 'target-arrow-color': '#3498db', 'line-style': 'dashed' } as cytoscape.Css.Edge,
          },
          {
            selector: 'edge[type="implements"]',
            style: { 'line-color': '#1abc9c', 'target-arrow-color': '#1abc9c', 'line-style': 'dotted' } as cytoscape.Css.Edge,
          },
        ],
        layout: {
          name: 'cose-bilkent',
          fit: true,
          padding: 50,
          randomize: false,
          nodeRepulsion: 4000,
          nodeOverlap: 20,
          idealEdgeLength: 100,
          edgeElasticity: 0.45,
          nestingFactor: 0.1,
          gravity: 0.25,
          numIter: 2500,
          tile: true,
        } as cytoscape.LayoutOptions,
      });

      cy.on('tap', 'node', (evt: { target: NodeSingular }) => {
        const node = evt.target;
        const nodeData = nodes.find((n) => n.id === node.id());
        if (nodeData) {
          setSelectedNode(nodeData);
        }
      });

      cy.on('tap', (evt: { target: Core | NodeSingular | EdgeSingular }) => {
        if (evt.target === cy) {
          setSelectedNode(null);
        }
      });
      const updateElements = () => {
        if (!cy) return;
        const filteredNodes = filterType === 'all'
          ? nodes
          : nodes.filter((n) => n.type === filterType);
        const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
        const filteredEdges = edges.filter(
          (e) => filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target)
        );

        const nodeElements = filteredNodes.map((n) => ({
          data: n,
          group: 'nodes' as const,
        }));
        const edgeElements = filteredEdges.map((e) => ({
          data: e,
          group: 'edges' as const,
        }));

        if (searchQuery) {
          const query = searchQuery.toLowerCase();
          const matchingNodes = nodes.filter(
            (n) => n.label.toLowerCase().includes(query) || n.file.toLowerCase().includes(query)
          );
          const matchingIds = new Set(matchingNodes.map((n) => n.id));
          const matchingEdges = edges.filter(
            (e) => matchingIds.has(e.source) || matchingIds.has(e.target)
          );
          const searchNodeElements = matchingNodes.map((n) => ({
            data: n,
            group: 'nodes' as const,
          }));
          const searchEdgeElements = matchingEdges.map((e) => ({
            data: e,
            group: 'edges' as const,
          }));
          cy.elements().remove();
          cy.add([...searchNodeElements, ...searchEdgeElements]);
        } else {
          cy.elements().remove();
          cy.add([...nodeElements, ...edgeElements]);
        }
        cy.layout({ name: 'cose-bilkent', fit: true, padding: 50 } as cytoscape.LayoutOptions).run();
      };

      updateElements();

      return () => {
        if (cy) {
          cy.destroy();
        }
      };
    }
  }, [nodes, edges, filterType, searchQuery, jobId]);

  const typeCounts = nodes.reduce((acc, n) => {
    acc[n.type] = (acc[n.type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  if (loading) {
    return (
      <div className="graph-view loading">
        <div className="loading-spinner"></div>
        <p>Loading graph...</p>
      </div>
    );
  }

  return (
    <div className="graph-view">
      <div className="graph-header">
        <button className="btn btn-secondary" onClick={onBack}>
          ← Back to Dashboard
        </button>
        <div className="graph-stats">
          <span>Nodes: {summary.total_nodes}</span>
          <span>Edges: {summary.total_edges}</span>
          <span>Languages: {Object.keys(summary.languages).join(', ')}</span>
        </div>
      </div>

      <div className="graph-toolbar">
        <div className="search-box">
          <input
            type="text"
            placeholder="Search nodes by name or file..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="filter-group">
          <label>Filter by type:</label>
          <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
            {nodeTypes.map((type) => (
              <option key={type} value={type}>
                {type === 'all' ? 'All Types' : type.charAt(0).toUpperCase() + type.slice(1)}
                {type !== 'all' && typeCounts[type] && ` (${typeCounts[type]})`}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="graph-container">
        <div className="graph-main">
          <div ref={cyRef} className="cytoscape-container" />
        </div>
        {selectedNode && (
          <div className="node-detail-panel">
            <h3>Node Details</h3>
            <button className="close-btn" onClick={() => setSelectedNode(null)}>×</button>
            <dl>
              <dt>Name</dt>
              <dd>{selectedNode.label}</dd>
              <dt>Type</dt>
              <dd>{selectedNode.type}</dd>
              <dt>File</dt>
              <dd>{selectedNode.file}</dd>
              <dt>Line</dt>
              <dd>{selectedNode.line}</dd>
              <dt>Language</dt>
              <dd>{selectedNode.language}</dd>
            </dl>
          </div>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}
    </div>
  );
}