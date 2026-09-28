'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';

function ShieldIcon(){return <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5"><path d="M12 3 5 6v5c0 4.7 2.9 8.6 7 10 4.1-1.4 7-5.3 7-10V6l-7-3Z" fill="none" stroke="currentColor" strokeWidth="1.8"/><path d="m9.6 12 1.7 1.7 3.4-3.8" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8"/></svg>}
function BrainIcon(){return <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5"><path d="M9 4.2a3 3 0 0 0-4.8 2.4c0 .5.1.9.3 1.3A3.4 3.4 0 0 0 5 14.4a3.1 3.1 0 0 0 3.5 4.2M15 4.2a3 3 0 0 1 4.8 2.4c0 .5-.1.9-.3 1.3A3.4 3.4 0 0 1 19 14.4a3.1 3.1 0 0 1-3.5 4.2M9 4.5v15M15 4.5v15M9 8.5h3M12 15.5h3" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7"/></svg>}

const links = [
  ['/', 'Overview'],['/tests','Tests'],['/activity','Activity'],['/memory','Memory'],['/patterns','Patterns'],['/challenges','Challenges'],['/github','GitHub / CI'],['/demo','Demo'],
];

export default function AppShell({children}:{children:ReactNode}){
  const pathname=usePathname();
  return <div className="min-h-screen bg-[#f6f8fb] text-slate-950">
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-[242px] border-r border-slate-200 bg-white lg:flex lg:flex-col">
      <div className="border-b border-slate-200 px-5 py-5"><Link href="/" className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-slate-950 text-white"><ShieldIcon/></span><span><span className="block text-[15px] font-bold">Quarantine<span className="text-blue-600">IQ</span></span><span className="block text-[11px] text-slate-500">CI decision intelligence</span></span></Link></div>
      <nav className="flex-1 px-3 py-4 text-sm"><p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Workspace</p>{links.map(([href,label])=><Link key={href} href={href} className={`shell-link ${pathname===href || (href!=='/' && pathname.startsWith(href))?'!bg-slate-100 !text-slate-950':''}`}>{label==='Memory'?<BrainIcon/>:null}{label}</Link>)}</nav>
      <div className="border-t border-slate-200 p-4"><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs font-semibold">Learning loop</p><p className="mt-1 text-[11px] leading-4 text-slate-500">Detect → investigate → decide → learn → remember</p></div></div>
    </aside>
    <div className="lg:pl-[242px]">
      <header className="sticky top-0 z-30 border-b border-slate-200/90 bg-white/95 backdrop-blur lg:hidden"><div className="flex items-center justify-between gap-4 px-4 py-3"><Link href="/" className="text-sm font-bold">Quarantine<span className="text-blue-600">IQ</span></Link><nav className="flex gap-3 overflow-x-auto text-xs font-medium text-slate-600">{links.map(([href,label])=><Link key={href} href={href}>{label}</Link>)}</nav></div></header>
      <main className="mx-auto min-h-screen max-w-[1380px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</main>
    </div>
  </div>
}
