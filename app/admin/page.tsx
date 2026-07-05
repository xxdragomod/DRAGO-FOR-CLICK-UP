import { auth } from '@/lib/auth'
import { headers } from 'next/headers'
import { redirect } from 'next/navigation'
import { isAdminEmail } from '@/lib/admin'
import { getGames } from '@/app/actions/games'
import { AdminGamesTable } from '@/components/admin-games-table'
import { AdminSignOutButton } from '@/components/admin-sign-out-button'
import Link from 'next/link'
import { Home } from 'lucide-react'

export const metadata = {
  title: 'Admin Panel',
}

export default async function AdminPage() {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session?.user) redirect('/admin/sign-in')
  // Sirf allowlisted admin emails hi panel dekh sakte hain.
  if (!isAdminEmail(session.user.email)) redirect('/admin/sign-in')

  const games = await getGames()

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card border-b border-border px-4 py-3 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center justify-center w-8 h-8 rounded-lg border border-border hover:bg-muted transition-colors"
            aria-label="View site"
          >
            <Home className="w-4 h-4 text-foreground" />
          </Link>
          <div>
            <h1 className="text-base font-bold text-foreground font-heading leading-none">Admin Panel</h1>
            <p className="text-xs text-muted-foreground mt-0.5">{session.user.email}</p>
          </div>
        </div>
        <AdminSignOutButton />
      </header>

      {/* Content */}
      <main className="max-w-2xl mx-auto px-4 py-6">
        <AdminGamesTable games={games} />
      </main>
    </div>
  )
}
