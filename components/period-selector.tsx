'use client'

import { useState, useEffect } from 'react'
import type { Game } from '@/lib/db/schema'
import { GameGrid } from './game-grid'

interface PeriodSelectorProps {
  allGames: Game[]
}

type Period = '30s' | '1min'

export function PeriodSelector({ allGames }: PeriodSelectorProps) {
  const [selected, setSelected] = useState<Period>('1min')

  const filtered = allGames.filter(
    (g) => g.period === selected || g.period === 'both'
  )

  return (
    <div className="flex flex-col min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-background border-b border-border px-4 pt-4 pb-0">
        <div className="flex items-center justify-between mb-3">
          <h1 className="text-2xl font-bold text-foreground font-heading">Lottery:</h1>
        </div>
        <p className="text-sm text-muted-foreground mb-4 leading-relaxed">
          Try your luck in the POPI Lottery and win exciting rewards, premium benefits, and
          exclusive prizes. Participate regularly for more chances to win.
        </p>

        {/* Period tabs */}
        <div className="flex gap-2">
          {(['1min', '30s'] as Period[]).map((p) => (
            <button
              key={p}
              onClick={() => setSelected(p)}
              className={`flex-1 py-2.5 text-sm font-semibold rounded-t-lg border-b-2 transition-colors ${
                selected === p
                  ? 'border-primary text-primary bg-primary/5'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {p === '1min' ? '1 Minute' : '30 Seconds'}
            </button>
          ))}
        </div>
      </header>

      {/* Game grid */}
      <main className="flex-1 pt-4">
        <GameGrid games={filtered} />
      </main>
    </div>
  )
}
