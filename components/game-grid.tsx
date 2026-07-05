'use client'

import Link from 'next/link'
import Image from 'next/image'
import type { Game } from '@/lib/db/schema'

interface GameGridProps {
  games: Game[]
}

export function GameGrid({ games }: GameGridProps) {
  if (games.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <p className="text-lg">No games available yet.</p>
        <p className="text-sm mt-1">Check back soon!</p>
      </div>
    )
  }

  return (
    <div className="pb-8">
      {/* Horizontal slider: 2 rows, scroll right to reveal more games */}
      <div className="hide-scrollbar overflow-x-auto overscroll-x-contain px-4 [scroll-snap-type:x_proximity]">
        <div className="grid grid-flow-col grid-rows-2 auto-cols-[42%] gap-3 sm:auto-cols-[28%] lg:auto-cols-[20%]">
          {games.map((game) => (
            <Link
              key={game.id}
              href={`/game/${game.slug}`}
              className="group flex flex-col items-center rounded-2xl bg-card border border-border overflow-hidden transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5 active:scale-[0.98] [scroll-snap-align:start]"
            >
              {/* Phone mockup image */}
              <div className="w-full aspect-[9/16] relative overflow-hidden bg-muted">
                <Image
                  src={game.image}
                  alt={game.name}
                  fill
                  className="object-cover group-hover:scale-105 transition-transform duration-300"
                  sizes="(max-width: 640px) 42vw, (max-width: 1024px) 28vw, 20vw"
                />
              </div>

              {/* Name + badge */}
              <div className="w-full px-2 py-2 flex flex-col items-center gap-1">
                <span className="font-bold text-sm text-center text-foreground leading-tight line-clamp-1 font-heading">
                  {game.name}
                </span>
                <span className="bg-secondary text-secondary-foreground text-xs font-semibold px-3 py-0.5 rounded-md border border-border">
                  {game.badge}
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
