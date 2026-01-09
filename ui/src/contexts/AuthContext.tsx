import { ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { client, getStoredAuthToken, setAuthToken } from '../services/api';

type AuthContextValue = {
  token: string | null;
  setToken: (token: string) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [token, setTokenState] = useState<string | null>(() => getStoredAuthToken());

  const applyToken = useCallback(
    (nextToken: string | null) => {
      setTokenState(nextToken);
      setAuthToken(nextToken);
      if (!nextToken) {
        queryClient.clear();
      }
    },
    [queryClient],
  );

  const logout = useCallback(() => {
    applyToken(null);
  }, [applyToken]);

  const setToken = useCallback(
    (nextToken: string) => {
      applyToken(nextToken);
    },
    [applyToken],
  );

  useEffect(() => {
    const interceptorId = client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          logout();
        }
        return Promise.reject(error);
      },
    );
    return () => {
      client.interceptors.response.eject(interceptorId);
    };
  }, [logout]);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      setToken,
      logout,
    }),
    [logout, setToken, token],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
}
