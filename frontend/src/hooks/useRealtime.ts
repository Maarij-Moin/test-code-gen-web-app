import { useEffect, useState } from "react";

import { queryClient } from "@/lib/queryClient";
import { websocketBaseUrl } from "@/lib/apiClient";
import { useAuthStore } from "@/stores/authStore";
import type { SocketEvent } from "@/types";

export function useRealtime() {
  const token = useAuthStore((state) => state.token);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!token) {
      setConnected(false);
      return undefined;
    }

    const socket = new WebSocket(`${websocketBaseUrl}/ws?token=${encodeURIComponent(token)}`);

    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onerror = () => setConnected(false);
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as SocketEvent;
        if (message.type.startsWith("job.")) void queryClient.invalidateQueries({ queryKey: ["jobs"] });
        if (message.type.startsWith("repo.")) void queryClient.invalidateQueries({ queryKey: ["repositories"] });
        if (message.type.startsWith("pr.")) void queryClient.invalidateQueries({ queryKey: ["pull-requests"] });
      } catch {
        // Ignore malformed socket payloads; HTTP polling remains the fallback.
      }
    };

    return () => socket.close();
  }, [token]);

  return { connected };
}
