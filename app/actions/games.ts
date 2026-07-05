'use server'

import { auth } from '@/lib/auth'
import { db } from '@/lib/db'
import { games, type NewGame } from '@/lib/db/schema'
import { asc, eq } from 'drizzle-orm'
import { headers } from 'next/headers'
import { revalidatePath } from 'next/cache'
import { isAdminEmail } from '@/lib/admin'

async function requireAdmin() {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session?.user) throw new Error('Unauthorized')
  // Role check: sirf ADMIN_EMAILS allowlist wale users hi admin actions kar sakte hain.
  if (!isAdminEmail(session.user.email)) throw new Error('Forbidden: admin access required')
  return session.user
}

export async function getGames() {
  try {
    return db.select().from(games).orderBy(asc(games.sortOrder), asc(games.createdAt))
  } catch (e) {
    console.error('[getGames] Database error:', e)
    return []
  }
}

export async function getGamesByPeriod(period: '30s' | '1min') {
  const all = await db.select().from(games).orderBy(asc(games.sortOrder), asc(games.createdAt))
  return all.filter((g) => g.period === period || g.period === 'both')
}

export async function getGameBySlug(slug: string) {
  const result = await db.select().from(games).where(eq(games.slug, slug)).limit(1)
  return result[0] ?? null
}

export async function addGame(data: Omit<NewGame, 'id' | 'createdAt' | 'updatedAt'>) {
  await requireAdmin()
  await db.insert(games).values(data)
  revalidatePath('/')
  revalidatePath('/admin')
}

export async function updateGame(
  id: number,
  data: Partial<Omit<NewGame, 'id' | 'createdAt' | 'updatedAt'>>
) {
  await requireAdmin()
  await db
    .update(games)
    .set({ ...data, updatedAt: new Date() })
    .where(eq(games.id, id))
  revalidatePath('/')
  revalidatePath('/admin')
}

export async function deleteGame(id: number) {
  await requireAdmin()
  await db.delete(games).where(eq(games.id, id))
  revalidatePath('/')
  revalidatePath('/admin')
}
