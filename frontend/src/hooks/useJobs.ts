import { useQuery } from "@tanstack/react-query";

import { jobService } from "@/services/jobService";

export function useJobs() {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: jobService.list,
    refetchInterval: 15_000,
  });
}

export function useJob(jobId?: string) {
  return useQuery({
    queryKey: ["jobs", jobId],
    queryFn: () => jobService.get(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: 5_000,
  });
}
