export type User = {
  id: string;
  email: string;
  full_name?: string | null;
  is_active: boolean;
};

export type AuthToken = {
  access_token: string;
  token_type: string;
};

export type Repository = {
  id: string;
  repo_id: string;
  name: string;
  repo_url: string;
  repo_path: string;
  branch?: string;
  status: "connected" | "indexing" | "failed" | "idle";
  last_indexed_at?: string;
  language?: string;
  coverage_delta?: number;
  open_prs?: number;
};

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export type Job = {
  id: string;
  repo_id: string;
  repo_name: string;
  type: "index" | "generate" | "validate" | "pr";
  status: JobStatus;
  progress: number;
  started_at: string;
  finished_at?: string;
  message?: string;
  steps: Array<{ name: string; status: JobStatus; duration_ms?: number }>;
};

export type GeneratedTest = {
  id: string;
  repo_id: string;
  file: string;
  function_name: string;
  old_code: string;
  new_code: string;
  prompt: string;
  validation?: ValidationReport;
};

export type ValidationReport = {
  status: "passed" | "warning" | "failed";
  score: number;
  assertions: number;
  risks: string[];
  summary: string;
};

export type PullRequest = {
  id: string;
  repo_id: string;
  title: string;
  number: number;
  url: string;
  author: string;
  status: "open" | "merged" | "closed" | "draft";
  checks: "pending" | "passing" | "failing";
  updated_at: string;
};

export type SocketEvent =
  | { type: "job.updated"; payload: Job }
  | { type: "repo.updated"; payload: Repository }
  | { type: "test.generated"; payload: GeneratedTest }
  | { type: "pr.updated"; payload: PullRequest };
