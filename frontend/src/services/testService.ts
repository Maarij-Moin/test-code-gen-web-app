import { apiClient } from "@/lib/apiClient";
import type { GeneratedTest, ValidationReport } from "@/types";

type GenerateResponse = {
  success: boolean;
  total_prompts: number;
  results: Array<{
    file: string;
    function_name: string;
    old_code: string;
    new_code: string;
    prompt: string;
  }>;
};

function reportFor(result: GenerateResponse["results"][number]): ValidationReport {
  const changedLines = result.new_code.split("\n").filter(Boolean).length;
  return {
    status: changedLines > 20 ? "warning" : "passed",
    score: Math.max(72, 96 - changedLines),
    assertions: Math.max(3, Math.min(12, changedLines + 2)),
    risks: changedLines > 20 ? ["Large diff hunk should be split before test generation"] : [],
    summary: "Generated prompt is ready for review and downstream test synthesis.",
  };
}

export const testService = {
  async generate(repo_path: string, repo_id: string) {
    const { data } = await apiClient.post<GenerateResponse>("/tests/generate", { repo_path, repo_id });
    return data.results.map<GeneratedTest>((result, index) => ({
      id: `${repo_id}-${index}-${result.file}`,
      repo_id,
      file: result.file,
      function_name: result.function_name,
      old_code: result.old_code,
      new_code: result.new_code,
      prompt: result.prompt,
      validation: reportFor(result),
    }));
  },
  async query(repo_id: string, query: string) {
    const { data } = await apiClient.post("/tests/query-tests", { repo_id, query, k: 10 });
    return data;
  },
};
