import { useState } from 'react';
import { Dashboard } from '@/components/Dashboard';
import { GraphView } from '@/components/GraphView';
import { apiClient } from '@/api/client';
import type { ParseJob, GraphSummary } from '@/types/api';
import './App.css';

function App() {
  const [currentJob, setCurrentJob] = useState<ParseJob | null>(null);
  const [summary, setSummary] = useState<GraphSummary | null>(null);
  const [view, setView] = useState<'dashboard' | 'graph'>('dashboard');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleParse = async (rootPath: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiClient.parseCodebase({ root_path: rootPath });
      setCurrentJob({
        id: response.job_id,
        root_path: rootPath,
        status: response.status,
        started_at: new Date().toISOString(),
        completed_at: null,
        error_message: null,
        stats: null,
      } as ParseJob);
      pollJobStatus(response.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start parse job');
    } finally {
      setIsLoading(false);
    }
  };

  const pollJobStatus = async (jobId: number) => {
    const maxAttempts = 60;
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const { promise, resolve } = Promise.withResolvers<void>();
      setTimeout(resolve, 1000);
      await promise;
      try {
        const job = await apiClient.getParseJobStatus(jobId);
        setCurrentJob(job);
        if (job.status === 'completed') {
          const summary = await apiClient.getGraphSummary(jobId);
          setSummary(summary);
          setView('graph');
          break;
        } else if (job.status === 'failed') {
          setError(job.error_message || 'Parse job failed');
          break;
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Cobalt Lens</h1>
        <p className="subtitle">Codebase Knowledge Graph Explorer</p>
      </header>
      {error && <div className="error-banner">{error}</div>}
      {view === 'dashboard' && (
        <Dashboard onParse={handleParse} isLoading={isLoading} currentJob={currentJob} />
      )}
      {view === 'graph' && currentJob && summary && (
        <GraphView jobId={currentJob.id} summary={summary} onBack={() => setView('dashboard')} />
      )}
    </div>
  );
}

export default App;