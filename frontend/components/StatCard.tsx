export default function StatCard({ label, value, detail, tone = 'neutral' }: { label: string; value: string | number; detail: string; tone?: 'neutral' | 'warning' | 'success' | 'danger' }) {
  const toneClass = tone === 'warning' ? 'border-amber-200 bg-amber-50/60' : tone === 'success' ? 'border-emerald-200 bg-emerald-50/60' : tone === 'danger' ? 'border-rose-200 bg-rose-50/60' : 'border-slate-200 bg-white';
  return (
    <div className={`rounded-2xl border p-5 shadow-[0_1px_2px_rgba(15,23,42,0.03)] ${toneClass}`}>
      <p className="text-xs font-semibold uppercase tracking-[0.13em] text-slate-500">{label}</p>
      <p className="mt-3 text-3xl font-bold tracking-tight text-slate-950">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{detail}</p>
    </div>
  );
}
