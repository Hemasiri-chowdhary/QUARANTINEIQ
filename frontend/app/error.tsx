'use client';

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto flex min-h-[70vh] max-w-xl items-center justify-center p-6">
      <div className="w-full rounded-2xl border border-rose-200 bg-white p-6 text-center shadow-sm">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-rose-600">Something went wrong</p>
        <h1 className="mt-2 text-xl font-bold text-slate-950">QuarantineIQ could not load this view.</h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">Check that the backend is running on port 8001, then try again.</p>
        <button onClick={() => reset()} className="primary-btn mt-5">Try again</button>
      </div>
    </div>
  );
}
