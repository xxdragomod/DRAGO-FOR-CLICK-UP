'use client'

import { useState } from 'react'
import { addGame, updateGame } from '@/app/actions/games'
import type { Game } from '@/lib/db/schema'

interface AdminGameFormProps {
  game?: Game
  onClose: () => void
}

function toSlug(name: string) {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
}

export function AdminGameForm({ game, onClose }: AdminGameFormProps) {
  const [name, setName] = useState(game?.name ?? '')
  const [image, setImage] = useState(game?.image ?? '')
  const [link, setLink] = useState(game?.link ?? '')
  const [badge, setBadge] = useState(game?.badge ?? 'Free')
  const [period, setPeriod] = useState<string>(game?.period ?? 'both')
  const [slug, setSlug] = useState(game?.slug ?? '')
  const [sortOrder, setSortOrder] = useState<number>(game?.sortOrder ?? 0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  function handleNameChange(val: string) {
    setName(val)
    if (!game) setSlug(toSlug(val))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (game) {
        await updateGame(game.id, { name, image, link, badge, period, slug, sortOrder })
      } else {
        await addGame({ name, image, link, badge, period, slug, sortOrder })
      }
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save game')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Name */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Game Name</label>
          <input
            required
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
            placeholder="66 Lottery"
          />
        </div>

        {/* Slug */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Slug <span className="text-muted-foreground font-normal normal-case">(URL key)</span>
          </label>
          <input
            required
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring font-mono"
            placeholder="66-lottery"
          />
        </div>

        {/* Image URL */}
        <div className="flex flex-col gap-1.5 sm:col-span-2">
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Image URL</label>
          <input
            required
            value={image}
            onChange={(e) => setImage(e.target.value)}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
            placeholder="https://..."
          />
        </div>

        {/* Game Link */}
        <div className="flex flex-col gap-1.5 sm:col-span-2">
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Game Link (URL)</label>
          <input
            required
            value={link}
            onChange={(e) => setLink(e.target.value)}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
            placeholder="https://66lottery.com"
          />
        </div>

        {/* Badge */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Badge</label>
          <input
            value={badge}
            onChange={(e) => setBadge(e.target.value)}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
            placeholder="Free"
          />
        </div>

        {/* Sort Order */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Sort Order</label>
          <input
            type="number"
            value={sortOrder}
            onChange={(e) => setSortOrder(Number(e.target.value))}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        {/* Period */}
        <div className="flex flex-col gap-1.5 sm:col-span-2">
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Show In Period</label>
          <div className="flex gap-3">
            {([
              { value: 'both', label: 'Both (30s & 1 Min)' },
              { value: '30s', label: '30 Seconds only' },
              { value: '1min', label: '1 Minute only' },
            ] as const).map((opt) => (
              <label key={opt.value} className="flex items-center gap-2 cursor-pointer text-sm text-foreground">
                <input
                  type="radio"
                  name="period"
                  value={opt.value}
                  checked={period === opt.value}
                  onChange={() => setPeriod(opt.value)}
                  className="accent-primary"
                />
                {opt.label}
              </label>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">{error}</p>
      )}

      <div className="flex gap-3 justify-end pt-2">
        <button
          type="button"
          onClick={onClose}
          className="px-4 py-2 rounded-lg border border-border text-sm font-medium text-foreground hover:bg-muted transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={loading}
          className="px-6 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:opacity-90 disabled:opacity-60 transition-opacity"
        >
          {loading ? 'Saving...' : game ? 'Update Game' : 'Add Game'}
        </button>
      </div>
    </form>
  )
}
