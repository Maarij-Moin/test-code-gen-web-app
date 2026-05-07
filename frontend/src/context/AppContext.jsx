import { createContext, useCallback, useContext, useMemo, useState } from "react";

const AppContext = createContext(null);

export function AppContextProvider({ children }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activity, setActivity] = useState([]);

  const addActivity = useCallback((entry) => {
    const payload = {
      ...entry,
      time: entry?.time || new Date().toISOString()
    };
    setActivity((prev) => [payload, ...prev].slice(0, 8));
  }, []);

  const clearError = useCallback(() => setError(""), []);

  const value = useMemo(
    () => ({
      loading,
      setLoading,
      error,
      setError,
      clearError,
      activity,
      addActivity
    }),
    [loading, error, activity, addActivity, clearError]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppContext() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useAppContext must be used within AppContextProvider");
  }
  return context;
}
