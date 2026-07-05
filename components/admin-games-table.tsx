'use client'

import { useState } from 'react'
import Image from 'next/image'
import { deleteGame } from '@/app/actions/games'
import { AdminGameForm } from './admin-game-form'
import type { Game } from '@/lib/db/schema'
import { Pencil, Trash2, Plus, X } from 'lucide-react'

interface AdminGamesTableProps {
  games: Game[]
}

export function AdminGamesTable({ games: initialGames }: AdminGamesTableProps) {
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingGame, setEditingGame] = useState<Game | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [games, setGames] = useState(initialGames)

  async function handleDelete(id: number) {
    if (!confirm('Delete this game? This cannot be undone.')) return
    setDeletingId(id)
    try {
      await deleteGame(id)
      setGames((prev) => prev.filter((g) => g.id !== id))
    } finally {
      setDeletingId(null)
    }
  }

  function handleCloseForm() {
    setShowAddForm(false)
    setEditingGame(null)
    // Reload to reflect DB changes
    window.location.reload()
  }

  const periodLabel = (p: string) =>
    p === 'both' ? 'Both' : p === '30s' ? '30 Sec' : '1 Min'

  return (
    <div className="flex flex-col gap-4">
      {/* Top bar */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-foreground font-heading">
          Games <span className="text-muted-foreground font-normal text-base">({games.length})</span>
        </h2>
        <button
          onClick={() => { setShowAddForm(true); setEditingGame(null) }}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-semibold hover:opacity-90 transition-opacity"
        >
          <Plus className="w-4 h-4" />
          Add Game
        </button>
      </div>

      {/* Add / Edit form modal */}
      {(showAddForm || editingGame) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="w-full max-w-xl bg-background rounded-2xl border border-border shadow-xl overflow-y-auto max-h-[90vh]">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
              <h3 className="font-bold text-foreground font-heading">
                {editingGame ? 'Edit Game' : 'Add New Game'}
              </h3>
              <button
                onClick={handleCloseForm}
                className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-muted transition-colors"
                aria-label="Close"
              >
                <X className="w-4 h-4 text-muted-foreground" />
              </button>
            </div>
            <div className="px-6 py-4">
              <AdminGameForm game={editingGame ?? undefined} onClose={handleCloseForm} />
            </div>
          </div>
        </div>
      )}

      {/* Games list */}
      {games.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground border border-dashed border-border rounded-xl">
          No games added yet. Click &quot;Add Game&quot; to get started.
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {games.map((game) => (
            <div
              key={game.id}
              className="flex items-center gap-4 bg-card border border-border rounded-xl px-4 py-3"
            >
              {/* Thumbnail */}
              <div className="relative w-12 h-16 rounded-lg overflow-hidden bg-muted shrink-0">
                <Image
                  src={game.image}
                  alt={game.name}
                  fill
                  className="object-cover"
                  sizes="48px"
                />
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-foreground text-sm truncate">{game.name}</p>
                <p className="text-xs text-muted-foreground truncate mt-0.5 font-mono">{game.slug}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs bg-secondary text-secondary-foreground px-2 py-0.5 rounded-md border border-border">
                    {game.badge}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {periodLabel(game.period)}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    Order: {game.sortOrder}
                  </span>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => { setEditingGame(game); setShowAddForm(false) }}
                  className="w-8 h-8 flex items-center justify-center rounded-lg border border-border hover:bg-muted transition-colors"
                  aria-label={`Edit ${game.name}`}
                >
                  <Pencil className="w-3.5 h-3.5 text-foreground" />
                </button>
                <button
                  onClick={() => handleDelete(game.id)}
                  disabled={deletingId === game.id}
                  className="w-8 h-8 flex items-center justify-center rounded-lg border border-destructive/30 hover:bg-destructive/10 transition-colors disabled:opacity-50"
                  aria-label={`Delete ${game.name}`}
                >
                  <Trash2 className="w-3.5 h-3.5 text-destructive" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
