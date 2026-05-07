import { useQuery } from "@tanstack/react-query";
import { webhookService } from "@/services/webhookService";

export function useWebhookHealth() {
  return useQuery({
    queryKey: ["webhook", "health"],
    queryFn: webhookService.health,
    refetchInterval: 30_000,
    retry: false,
  });
}

export function useWebhookEvents(limit = 50) {
  return useQuery({
    queryKey: ["webhook", "events", limit],
    queryFn: () => webhookService.events(limit),
    refetchInterval: 10_000,
  });
}
