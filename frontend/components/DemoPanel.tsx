'use client';

import { useState } from 'react';
import { compareDemo, resetDemo } from '@/lib/api';
import StatusBadge from './StatusBadge';

function label(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function DemoPanel() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function run() {
    setLoading(true); setError(''); setMessage('');
    try { setData(await compareDemo()); }
    catch (e) { setError(e instanceof Error ? e.message : 'Unable to run the comparison.'); }
    finally { setLoading(false); }
  }

  async function reset() {
    setLoading(true); setError('');
    try { const response = await resetDemo(); setData(null); setMessage(response.status || 'Demo reset.'); }
    catch (e) { setError(e instanceof Error ? e.message : 'Unable to reset the demo.'); }
    finally { setLoading(false); }
  }

  const without = data?.without_memory;
  const withMemory = data?.with_memory;
  const scoreDelta = withMemory && without ? withMemory.attention_score.score - without.attention_score.score : null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-3"><button onClick={run} disabled={loading} className="primary-btn">{loading ? 'Running…' : 'Run memory comparison'}</button><button onClick={reset} disabled={loading} className="secondary-btn">Reset demo data</button></div>
      {message && <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div>}
      {error && <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
      {data && (
        <>
          <div className="grid gap-5 lg:grid-cols-2">
            {[['WITHOUT MEMORY', without, 'No organizational memory is consulted.'], ['WITH HINDSIGHT MEMORY', withMemory, 'The same current evidence is combined with retained engineering experience.']].map(([title, result, desc]) => (
              <section key={String(title)} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-start justify-between gap-3"><div><p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">{title}</p><p className="mt-2 text-sm text-slate-500">{desc}</p></div>{result && <StatusBadge value={result.recommendation.level} />}</div>
                <div className="mt-5 grid grid-cols-2 gap-3"><div className="rounded-xl bg-slate-50 p-4"><p className="text-[10px] uppercase tracking-widest text-slate-400">Attention score</p><p className="mt-1 text-3xl font-bold">{result.attention_score.score}</p></div><div className="rounded-xl bg-slate-50 p-4"><p className="text-[10px] uppercase tracking-widest text-slate-400">Memory</p><p className="mt-1 text-sm font-semibold">{result.memory_status}</p></div></div>
                <div className="mt-4 rounded-xl border border-slate-200 p-4"><p className="text-xs font-semibold">Recommendation</p><p className="mt-1 text-sm font-bold">{result.recommendation.message}</p><p className="mt-2 text-xs leading-5 text-slate-500">{result.reasoning_summary}</p></div>
                {result.historical_evidence?.length > 0 && <div className="mt-4"><p className="text-xs font-semibold">Historical experiences recalled: {result.historical_evidence.length}</p><p className="mt-1 text-xs leading-5 text-slate-500">These memories are what make the second investigation different.</p></div>}
              </section>
            ))}
          </div>
          <div className="rounded-2xl border border-blue-200 bg-blue-50 p-5"><p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-blue-600">Why memory matters</p><p className="mt-2 text-sm leading-6 text-blue-950">{scoreDelta !== null ? `The recalled organizational memory changed the attention score by ${scoreDelta} points.` : 'The memory-aware run uses real retained engineering experiences.'}</p></div>
        </>
      )}
    </div>
  );
}
