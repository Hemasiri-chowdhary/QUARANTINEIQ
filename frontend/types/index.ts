export type TestStatus = 'active' | 'quarantined' | 'disabled' | 'needs_review';
export type DecisionType = 'quarantine' | 'investigate' | 'keep_active';
export type OutcomeType = 'genuinely_flaky' | 'infrastructure_issue' | 'real_regression' | 'still_uncertain';

export interface Test { id:number; name:string; service:string; repository:string; status:TestStatus; created_at:string; source?:string; external_key?:string|null }
export interface CIRun { id:number; test_id:number; commit_sha:string; status:string; failure_type?:string|null; error_message?:string|null; duration:number; retry_count:number; retry_success:boolean; timestamp:string; source?:string; workflow_run_id?:string|null; job_id?:string|null; workflow_name?:string|null; job_name?:string|null; log_excerpt?:string|null; html_url?:string|null; branch?:string|null; run_attempt?:number }
export interface Decision { id:number; test_id:number; agent_recommendation?:DecisionType|null; agent_reason?:string|null; human_decision?:DecisionType|null; human_reason?:string|null; timestamp:string; challenge_shown?:boolean; challenge_reason?:string|null }
export interface Outcome { id:number; decision_id:number; outcome:OutcomeType; notes?:string|null; timestamp:string }
export interface InvestigationResult { current_evidence:any; historical_evidence:any[]; attention_score:{score:number;breakdown:Record<string,number>}; recommendation:{level:string;message:string}; reasoning_summary:string; memory_status:string; decision_challenge:{triggered:boolean;message?:string|null;evidence_count:number}; root_cause?:{summary:string;signals:{signal:string;evidence:string;strength:string}[];caveat:string} }
