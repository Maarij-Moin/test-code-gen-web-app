import { apiClient } from "@/lib/apiClient";

export type WebhookHealth = {
  status: string;
  webhook_path: string;
  secret_configured: boolean;
  supported_events: string[];
  replay_protection: string;
  signature_verification: string;
};

export type WebhookEvent = {
  id: string;
  event_type: string;
  delivery_id: string | null;
  status: string;
  commit_sha: string | null;
  branch: string | null;
  created_at: string;
  processed_at: string | null;
  error_message: string | null;
};

export const webhookService = {
  async health(): Promise<WebhookHealth> {
    const { data } = await apiClient.get<WebhookHealth>("/webhooks/health");
    return data;
  },
  async events(limit = 50): Promise<WebhookEvent[]> {
    try {
      const { data } = await apiClient.get<WebhookEvent[]>(`/webhooks/events?limit=${limit}`);
      return data;
    } catch {
      return [];
    }
  },
};
