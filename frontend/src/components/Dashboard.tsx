import { useState, FormEvent } from 'react';
import type { ParseJob } from '@/types/api';

interface DashboardProps {
  onParse: (rootPath: string) => void;
  isLoading: boolean;
  currentJob: ParseJob | null;
}

export function Dashboard({ onParse, isLoading, currentJob }: DashboardProps) {
  const [rootPath, setRootPath] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (rootPath.trim()) {
      onParse(rootPath.trim());
    }
  };

  return (
    <main className="dashboard">
      <section className="parse-form-section">
        <h2>Parse Codebase</h2>
        <form onSubmit={handleSubmit} className="parse-form">
          <div className="form-group">
            <label htmlFor="rootPath">Root Directory Path</label>
            <input
              type="text"
              id="rootPath"
              value={rootPath}
              onChange={(e) => setRootPath(e.target.value)}
              placeholder="/path/to/your/codebase"
              disabled={isLoading}
              required
            />
            <p className="form-hint">
              Enter the absolute path to the codebase you want to analyze.
              Supports Python (.py), JavaScript (.js), and TypeScript (.ts, .tsx) files.
            </p>
          </div>
          <button type="submit" className="btn btn-primary" disabled={isLoading || !rootPath.trim()}>
            {isLoading ? 'Starting...' : 'Start Analysis'}
          </button>
        </form>
      </section>

      {currentJob && (
        <section className="job-status-section">
          <h2>Job Status</h2>
          <div className="job-status-card">
            <div className="status-info">
              <span className="label">Job ID:</span>
              <span className="value">{currentJob.id}</span>
            </div>
            <div className="status-info">
              <span className="label">Status:</span>
              <span className={`value status-${currentJob.status}`}>{currentJob.status}</span>
            </div>
            <div className="status-info">
              <span className="label">Path:</span>
              <span className="value">{currentJob.root_path}</span>
            </div>
            {currentJob.completed_at && (
              <div className="status-info">
                <span className="label">Completed:</span>
                <span className="value">{new Date(currentJob.completed_at).toLocaleString()}</span>
              </div>
            )}
            {currentJob.error_message && (
              <div className="status-info error">
                <span className="label">Error:</span>
                <span className="value">{currentJob.error_message}</span>
              </div>
            )}
          </div>
        </section>
      )}
    </main>
  );
}