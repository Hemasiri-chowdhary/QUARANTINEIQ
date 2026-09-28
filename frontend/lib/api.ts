import { CIRun, Decision, Outcome, Test } from '@/types';
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8001/api';

async function apiError(res: Response, fallback: string): Promise<never> {
  let detail = fallback;
  try { const body = await res.json(); if (body?.detail) detail = String(body.detail); } catch {}
  throw new Error(detail);
}

async function request<T>(path:string, init?:RequestInit):Promise<T>{
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`,{...init,cache:'no-store'});
  } catch {
    throw new Error('Unable to reach QuarantineIQ backend. Make sure FastAPI is running on port 8001.');
  }
  if(!res.ok) return apiError(res,'Request failed.');
  return res.json();
}

export const getTests=()=>request<Test[]>('/tests');
export const getTest=(id:string)=>request<Test>(`/tests/${id}`);
export const getTestHistory=(id:string)=>request<CIRun[]>(`/tests/${id}/history`);
export const getTestDecisions=(id:string)=>request<Decision[]>(`/tests/${id}/decisions`);
export const getTestOutcomes=(id:string)=>request<Outcome[]>(`/tests/${id}/outcomes`);
export const investigateTest=(id:string)=>request<InvestigationResult>(`/tests/${id}/investigate`,{method:'POST'});
export const submitDecision=(id:string,human_decision:string,human_reason:string,agent_recommendation?:string,agent_reason?:string,challenge_response?:string)=>request<any>(`/tests/${id}/decision`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({human_decision,human_reason,agent_recommendation,agent_reason,challenge_response})});
export const submitOutcome=(id:string,outcome:string,notes:string)=>request<any>(`/tests/${id}/outcome`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({outcome,notes})});
export const teachOutcome=(id:string,outcomeId:number)=>request<any>(`/tests/${id}/outcome/${outcomeId}/teach`,{method:'POST'});
export const getMemory=(query='QuarantineIQ engineering experience learned outcome decision regression flaky test')=>request<any>(`/memory?query=${encodeURIComponent(query)}`);
export const getSystemStatus=()=>request<any>('/status');
export const getPatterns=()=>request<any[]>('/patterns');
export const getActivity=()=>request<any[]>('/activity');
export const getDecisionChallenges=()=>request<any[]>('/decision-challenges');
export const getGithubStatus=()=>request<any>('/github/status');
export const syncGithub=()=>request<any>('/github/sync',{method:'POST'});
export const compareDemo=()=>request<any>('/demo/compare',{method:'POST'});
export const resetDemo=()=>request<any>('/demo/reset',{method:'POST'});
