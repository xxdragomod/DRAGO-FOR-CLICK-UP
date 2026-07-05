import { getGameBySlug } from '@/app/actions/games'
import { notFound } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import type { Metadata } from 'next'

interface Props {
  params: Promise<{ slug: string }>
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params
  const game = await getGameBySlug(slug)
  if (!game) return { title: 'Game Not Found' }
  return {
    title: game.name,
    description: `Play ${game.name} now`,
  }
}

export default async function GamePage({ params }: Props) {
  const { slug } = await params
  const game = await getGameBySlug(slug)

  if (!game) notFound()

  return (
    <div className="flex flex-col min-h-screen bg-background">
      {/* Hero section with back button */}
      <header className="relative bg-primary px-4 py-4 flex items-center gap-3 min-h-[60px]">
        <Link
          href="/"
          className="flex items-center justify-center w-9 h-9 rounded-full bg-primary-foreground/20 hover:bg-primary-foreground/30 transition-colors shrink-0"
          aria-label="Go back to home"
        >
          <ArrowLeft className="w-5 h-5 text-primary-foreground" />
        </Link>
        <h1 className="text-lg font-bold text-primary-foreground font-heading truncate">
          {game.name}
        </h1>
        <span className="ml-auto text-xs font-semibold bg-primary-foreground/20 text-primary-foreground px-2 py-0.5 rounded-full shrink-0">
          {game.badge}
        </span>
      </header>

      {/* Iframe game embed */}
      <main className="flex-1 flex flex-col">
        <iframe
          src={game.link}
          title={game.name}
          className="flex-1 w-full border-0"
          style={{ minHeight: 'calc(100vh - 60px)' }}
          allow="fullscreen"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox"
        />
      </main>
    </div>
  )
}
