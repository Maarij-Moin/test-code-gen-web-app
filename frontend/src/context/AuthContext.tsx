import { createContext, useEffect, useMemo, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { authService } from "@/services/authService";
import { useAuthStore } from "@/stores/authStore";

type AuthContextValue = {
  isAuthenticated: boolean;
  isLoading: boolean;
  logout: () => void;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { token, setUser, clearSession } = useAuthStore();
  const profileQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: authService.me,
    enabled: Boolean(token),
  });

  useEffect(() => {
    if (profileQuery.data) {
      setUser(profileQuery.data);
    }
  }, [profileQuery.data, setUser]);

  const value = useMemo(
    () => ({
      isAuthenticated: Boolean(token),
      isLoading: profileQuery.isLoading,
      logout: clearSession,
    }),
    [clearSession, profileQuery.isLoading, token],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
