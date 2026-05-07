import { useContext } from "react";
import { useMutation } from "@tanstack/react-query";

import { AuthContext } from "@/context/AuthContext";
import { queryClient } from "@/lib/queryClient";
import { authService, type LoginPayload, type RegisterPayload } from "@/services/authService";
import { useAuthStore } from "@/stores/authStore";

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }

  return context;
}

export function useLogin() {
  const setSession = useAuthStore((state) => state.setSession);

  return useMutation({
    mutationFn: (payload: LoginPayload) => authService.login(payload),
    onSuccess: async (token) => {
      setSession(token.access_token);
      await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: (payload: RegisterPayload) => authService.register(payload),
  });
}
