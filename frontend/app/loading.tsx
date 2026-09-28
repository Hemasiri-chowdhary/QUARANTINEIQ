export default function Loading() {
  return (
    <div className="flex min-h-[70vh] items-center justify-center">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="h-3 w-24 animate-pulse rounded bg-slate-200" />
        <div className="mt-3 h-7 w-56 animate-pulse rounded bg-slate-200" />
        <div className="mt-4 h-3 w-full animate-pulse rounded bg-slate-100" />
        <div className="mt-2 h-3 w-5/6 animate-pulse rounded bg-slate-100" />
      </div>
    </div>
  );
}
