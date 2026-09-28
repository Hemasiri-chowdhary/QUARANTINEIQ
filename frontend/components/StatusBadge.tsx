export default function StatusBadge({ value }: { value: string }) {
  const normalized = String(value).toLowerCase();
  const styles = normalized === 'quarantined' || normalized === 'needs_review'
    ? 'bg-amber-50 text-amber-700 ring-amber-200'
    : normalized === 'active' || normalized === 'passed' || normalized === 'available' || normalized === 'retained'
      ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
      : normalized === 'failed' || normalized === 'high' || normalized.includes('unavailable')
        ? 'bg-rose-50 text-rose-700 ring-rose-200'
        : 'bg-slate-100 text-slate-600 ring-slate-200';
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ring-1 ${styles}`}><span className="h-1.5 w-1.5 rounded-full bg-current" />{normalized.replaceAll('_', ' ')}</span>;
}
