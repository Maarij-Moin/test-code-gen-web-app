import { useQuery } from "@tanstack/react-query";

import { prService } from "@/services/prService";

export function usePullRequests() {
  return useQuery({
    queryKey: ["pull-requests"],
    queryFn: prService.list,
    refetchInterval: 20_000,
  });
}
