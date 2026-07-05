import { auth } from '@/lib/auth'
import { headers } from 'next/headers'
import { redirect } from 'next/navigation'
import { AdminSignInForm } from '@/components/admin-sign-in-form'

export default async function AdminSignInPage() {
  const session = await auth.api.getSession({ headers: await headers() })
  if (session?.user) redirect('/admin')

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-foreground font-heading">Admin Panel</h1>
          <p className="text-sm text-muted-foreground mt-1">Sign in to manage games</p>
        </div>
        <AdminSignInForm />
      </div>
    </div>
  )
}
