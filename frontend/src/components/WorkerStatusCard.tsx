import React, { useEffect, useState } from 'react';
import { Clock, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import type { WorkerStatus } from '../types';
import { fetchWorkerStatus } from '../services/api';

const JOB_LABELS: Record<string, string> = {
  announcements: 'Announcements',
  prices: 'Prices (stock / broker / index)',
  screen: 'M&A / capital screen',
  dossiers: 'Deal dossiers',
};

const fmtTime = (iso?: string) => (iso ? iso.replace('T', ' ').slice(0, 16) : '—');

/** Scheduled worker status (GET /api/system/worker), refreshed every minute. */
export const WorkerStatusCard: React.FC = () => {
  const [status, setStatus] = useState<WorkerStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () =>
      fetchWorkerStatus(8)
        .then((s) => {
          setStatus(s);
          setError(null);
        })
        .catch((err) => setError(err.message));
    load();
    const id = window.setInterval(load, 60_000);
    return () => window.clearInterval(id);
  }, []);

  const names = Array.from(new Set([...Object.keys(status?.schedules ?? {}), ...Object.keys(status?.jobs ?? {})]));
  const alerts = names.filter((n) => status?.jobs[n]?.alert);

  return (
    <div
      style={{
        background: 'rgba(15, 23, 42, 0.65)',
        border: `1px solid ${alerts.length || status?.stale ? 'rgba(248, 113, 113, 0.45)' : 'rgba(255, 255, 255, 0.08)'}`,
        borderRadius: '16px',
        padding: '1.25rem 1.5rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.8rem', flexWrap: 'wrap' }}>
        <Clock size={20} style={{ color: '#38bdf8' }} />
        <h3 style={{ margin: 0, fontSize: '1.05rem' }}>Scheduled worker</h3>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
          Asia/Jakarta time · started {fmtTime(status?.started_at)} · last activity {fmtTime(status?.updated_at)}
        </span>
        {status?.stale && (
          <span style={{ marginLeft: 'auto', color: '#f87171', fontSize: '0.8rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 4 }}>
            <AlertTriangle size={14} /> No activity for over 2 h — is the worker container running?
          </span>
        )}
      </div>

      {error && <p style={{ color: '#f87171', fontSize: '0.85rem', margin: 0 }}>{error}</p>}
      {!error && names.length === 0 && (
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', margin: 0 }}>
          The worker has not run yet. Start it with <code>docker compose up -d worker</code>.
        </p>
      )}

      {names.length > 0 && (
        <div className="table-container" style={{ marginTop: 0 }}>
          <table style={{ fontSize: '0.8rem' }}>
            <thead>
              <tr>
                <th>Job</th>
                <th>Schedule</th>
                <th>Status</th>
                <th>Last run</th>
                <th>Last success</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {names.map((n) => {
                const j = status?.jobs[n] ?? {};
                const ok = j.status === 'ok';
                return (
                  <tr key={n}>
                    <td style={{ fontWeight: 600 }}>{JOB_LABELS[n] ?? n}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>{status?.schedules?.[n] ?? j.schedule ?? '—'}</td>
                    <td>
                      {j.status ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: ok ? '#34d399' : '#f87171', fontWeight: 700 }}>
                          {ok ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
                          {ok ? 'OK' : `FAILED ×${j.consecutive_failures ?? 1}`}
                          {j.alert && ' · ALERT'}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-secondary)' }}>waiting</span>
                      )}
                    </td>
                    <td className="numeric">
                      {fmtTime(j.last_run)}
                      {j.duration_s != null && <span style={{ color: 'var(--text-secondary)' }}> ({j.duration_s}s)</span>}
                    </td>
                    <td className="numeric">{fmtTime(j.last_ok)}</td>
                    <td style={{ color: 'var(--text-secondary)', maxWidth: 420, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={j.message}>
                      {j.message ?? '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
