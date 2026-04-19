'use client';

import React from 'react';
import { SessionProvider, useSession, signIn, signOut } from 'next-auth/react';

interface User {
  id: string;
  email: string;
  role: string;
  firm_id: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (token: string, userData: User) => void; // Keeps backward compatibility
  logout: () => void;
  isLoading: boolean;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      {children}
    </SessionProvider>
  );
}

export function useAuth(): AuthContextType {
  const { data: session, status } = useSession();

  const user = session?.user ? {
    id: (session.user as any).id || '',
    email: session.user.email || '',
    role: (session.user as any).role || 'attorney',
    firm_id: (session.user as any).firmId || '',
  } : null;

  return {
    user,
    token: (session as any)?.accessToken || null,
    login: async () => {
      // Compatibility stub — normally we use signIn directly
    },
    logout: () => signOut({ callbackUrl: '/login' }),
    isLoading: status === 'loading',
  };
}
