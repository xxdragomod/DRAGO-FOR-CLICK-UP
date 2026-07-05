import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

// Same Firebase Realtime DB the admin panel writes games to.
const FIREBASE_GAMES_URL =
  'https://quantum-anlyzer-default-rtdb.firebaseio.com/games.json'

// Public endpoint: returns games (added via the admin panel) for the static
// game.html page. Optional ?period=30s | 1min filter; games whose category is
// "all" appear under every period.
export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    const period = searchParams.get('period')

    const res = await fetch(FIREBASE_GAMES_URL, { cache: 'no-store' })
    const data = (await res.json()) as Record<
      string,
      { name?: string; image?: string; link?: string; category?: string; slug?: string; created_at?: number }
    > | null

    // Firebase returns null when there are no games.
    const entries = data ? Object.entries(data) : []

    let list = entries.map(([id, g]) => ({
      id,
      name: g?.name || 'Untitled',
      image: g?.image || '',
      slug: g?.slug || '',
      link: g?.link || '',
      category: g?.category || 'all',
      created_at: g?.created_at || 0,
    }))

    // Filter by period — "all" category games always show.
    if (period === '30s' || period === '1min') {
      list = list.filter((g) => g.category === period || g.category === 'all')
    }

    // Newest first (matches admin panel ordering).
    list.sort((a, b) => b.created_at - a.created_at)

    const result = list.map((g) => ({
      name: g.name,
      image: g.image,
      slug: g.slug,
      link: g.link,
    }))

    return NextResponse.json(
      { games: result },
      { headers: { 'Access-Control-Allow-Origin': '*' } }
    )
  } catch (e) {
    console.error('[api/games] error:', e)
    return NextResponse.json({ games: [] }, { status: 200 })
  }
}
