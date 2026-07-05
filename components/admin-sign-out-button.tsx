'use client'

import { authClient } from '@/lib/auth-client'
import { useRouter } from 'next/navigation'
import { LogOut } from 'lucide-react'

export function AdminSignOutButton() {
  const router = useRouter()

  async function handleSignOut() {
    await authClient.signOut()
    router.push('/admin/sign-in')
    router.refresh()
  }

  return (
    <button
      onClick={handleSignOut}
      className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors px-3 py-1.5 rounded-lg hover:bg-muted"
    >
      <LogOut className="w-4 h-4" />
      Sign out
    </button>
  )
}
