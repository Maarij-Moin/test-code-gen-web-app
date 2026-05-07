import { useMutation, useQuery } from "@tanstack/react-query";

import { queryClient } from "@/lib/queryClient";
import { repoService } from "@/services/repoService";

export function useRepositories() {
  return useQuery({
    queryKey: ["repositories"],
    queryFn: repoService.list,
  });
}

export function useRepository(repoId?: string) {
  return useQuery({
    queryKey: ["repositories", repoId],
    queryFn: () => repoService.get(repoId as string),
    enabled: Boolean(repoId),
  });
}

export function useConnectRepository() {
  return useMutation({
    mutationFn: (repoUrl: string) => repoService.connect(repoUrl),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["repositories"] });
    },
  });
}
