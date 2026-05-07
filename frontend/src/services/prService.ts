import { apiClient } from "@/lib/apiClient";
import type { PullRequest } from "@/types";

const fallbackPullRequests: PullRequest[] = [
  {
    id: "pr-481",
    repo_id: "local-demo",
    title: "Add generated tests for payment retry flow",
    number: 481,
    url: "https://github.com/example/checkout-service/pull/481",
    author: "qa-automation",
    status: "open",
    checks: "passing",
    updated_at: new Date(Date.now() - 1000 * 60 * 22).toISOString(),
  },
  {
    id: "pr-214",
    repo_id: "local-demo",
    title: "Validate auth edge cases from latest diff",
    number: 214,
    url: "https://github.com/example/api-gateway/pull/214",
    author: "test-agent",
    status: "draft",
    checks: "pending",
    updated_at: new Date(Date.now() - 1000 * 60 * 94).toISOString(),
  },
];

export const prService = {
  async list() {
    try {
      const { data } = await apiClient.get<PullRequest[]>("/pull-requests");
      return data;
    } catch {
      return fallbackPullRequests;
    }
  },
};
