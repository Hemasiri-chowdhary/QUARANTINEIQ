export default function EmptyState({ title, message, description }: { title: string; message?: string; description?: string }) {
  const text = message ?? description ?? '';
  return <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/60 px-5 py-8 text-center"><p className="text-sm font-semibold text-slate-700">{title}</p><p className="mx-auto mt-1 max-w-md text-xs leading-5 text-slate-500">{text}</p></div>;
}
