import { createContext, useContext, useMemo, useState } from "react";

const RepoContext = createContext(null);

const initialRepoState = {
  repoId: "",
  repoPath: "",
  status: "idle",
  lastUpdated: null
};

export function RepoContextProvider({ children }) {
  const [repoState, setRepoState] = useState(initialRepoState);

  const value = useMemo(
    () => ({
      repoState,
      setRepoState
    }),
    [repoState]
  );

  return <RepoContext.Provider value={value}>{children}</RepoContext.Provider>;
}

export function useRepoContext() {
  const context = useContext(RepoContext);
  if (!context) {
    throw new Error("useRepoContext must be used within RepoContextProvider");
  }
  return context;
}
