import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { User } from "@/types";

type AuthState = {
  token: string | null;
  user: User | null;
  setSession: (token: string, user?: User | null) => void;
  setUser: (user: User | null) => void;
  clearSession: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setSession: (token, user = null) => set({ token, user }),
      setUser: (user) => set({ user }),
      clearSession: () => set({ token: null, user: null }),
    }),
    {
      name: "autotest-auth",
      partialize: (state) => ({ token: state.token, user: state.user }),
    },
  ),
);
