import { apiClient } from "@/lib/apiClient";
import type { Job } from "@/types";

const fallbackJobs: Job[] = [
  {
    id: "job-live-001",
    repo_id: "local-demo",
    repo_name: "checkout-service",
    type: "generate",
    status: "running",
    progress: 68,
    started_at: new Date(Date.now() - 1000 * 60 * 18).toISOString(),
    message: "Generating regression tests from latest diff",
    steps: [
      { name: "Fetch diff", status: "succeeded", duration_ms: 3120 },
      { name: "Retrieve context", status: "succeeded", duration_ms: 8440 },
      { name: "Generate tests", status: "running" },
      { name: "Validate assertions", status: "queued" },
    ],
  },
  {
    id: "job-live-002",
    repo_id: "local-demo",
    repo_name: "billing-api",
    type: "validate",
    status: "succeeded",
    progress: 100,
    started_at: new Date(Date.now() - 1000 * 60 * 72).toISOString(),
    finished_at: new Date(Date.now() - 1000 * 60 * 61).toISOString(),
    message: "Validation report published",
    steps: [
      { name: "Install test runtime", status: "succeeded", duration_ms: 18900 },
      { name: "Run generated tests", status: "succeeded", duration_ms: 43100 },
      { name: "Summarize coverage", status: "succeeded", duration_ms: 7400 },
    ],
  },
];

export const jobService = {
  async list() {
    try {
      const { data } = await apiClient.get<Job[]>("/jobs");
      return data;
    } catch {
      return fallbackJobs;
    }
  },
  async get(jobId: string) {
    try {
      const { data } = await apiClient.get<Job>(`/jobs/${jobId}`);
      return data;
    } catch {
      return fallbackJobs.find((job) => job.id === jobId) ?? fallbackJobs[0];
    }
  },
};
