import { apiClient } from "@/lib/apiClient";
import type { AuthToken, User } from "@/types";

export type LoginPayload = { email: string; password: string };
export type RegisterPayload = LoginPayload & { full_name?: string };

export const authService = {
  async login(payload: LoginPayload) {
    const { data } = await apiClient.post<AuthToken>("/auth/login", payload);
    return data;
  },
  async register(payload: RegisterPayload) {
    const { data } = await apiClient.post<User>("/auth/register", payload);
    return data;
  },
  async me() {
    const { data } = await apiClient.get<User>("/auth/me");
    return data;
  },
};
