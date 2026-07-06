'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { api, endpoints } from '@lib/api-client'
import { useAuthStore } from '@store/auth'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const router = useRouter()
  const login = useAuthStore((s) => s.login)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const res: any = await api.post(endpoints.login, { email, password })
      login(res.token, res.user)
      router.push('/')
    } catch (err: any) {
      setError(err.message || 'Login failed')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4 p-8 bg-white rounded-xl shadow-sm">
        <h1 className="text-2xl font-bold text-center">RealtorOS</h1>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)}
          className="w-full px-3 py-2 border rounded-lg" required />
        <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)}
          className="w-full px-3 py-2 border rounded-lg" required />
        <button type="submit" className="w-full py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700">
          Sign In
        </button>
      </form>
    </div>
  )
}