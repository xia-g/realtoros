'use client'
import { createContext, useContext, useEffect } from 'react'
import { useAuthStore } from '@store/auth'

const AuthContext = createContext<ReturnType<typeof useAuthStore> | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { user, token, isAuthenticated, login, logout } = useAuthStore()
  return <AuthContext.Provider value={{ user, token, isAuthenticated, login, logout }}>
    {children}
  </AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext) as ReturnType<typeof useAuthStore>
