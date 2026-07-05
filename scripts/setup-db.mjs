import { Pool } from 'pg'

const pool = new Pool({ connectionString: process.env.DATABASE_URL })

async function main() {
  // Better Auth tables
  await pool.query(`
    CREATE TABLE IF NOT EXISTS "user" (
      "id" text PRIMARY KEY,
      "name" text NOT NULL,
      "email" text NOT NULL UNIQUE,
      "emailVerified" boolean NOT NULL DEFAULT false,
      "image" text,
      "createdAt" timestamp NOT NULL DEFAULT now(),
      "updatedAt" timestamp NOT NULL DEFAULT now()
    );
  `)

  await pool.query(`
    CREATE TABLE IF NOT EXISTS "session" (
      "id" text PRIMARY KEY,
      "expiresAt" timestamp NOT NULL,
      "token" text NOT NULL UNIQUE,
      "createdAt" timestamp NOT NULL DEFAULT now(),
      "updatedAt" timestamp NOT NULL DEFAULT now(),
      "ipAddress" text,
      "userAgent" text,
      "userId" text NOT NULL REFERENCES "user"("id") ON DELETE CASCADE
    );
  `)

  await pool.query(`
    CREATE TABLE IF NOT EXISTS "account" (
      "id" text PRIMARY KEY,
      "accountId" text NOT NULL,
      "providerId" text NOT NULL,
      "userId" text NOT NULL REFERENCES "user"("id") ON DELETE CASCADE,
      "accessToken" text,
      "refreshToken" text,
      "idToken" text,
      "accessTokenExpiresAt" timestamp,
      "refreshTokenExpiresAt" timestamp,
      "scope" text,
      "password" text,
      "createdAt" timestamp NOT NULL DEFAULT now(),
      "updatedAt" timestamp NOT NULL DEFAULT now()
    );
  `)

  await pool.query(`
    CREATE TABLE IF NOT EXISTS "verification" (
      "id" text PRIMARY KEY,
      "identifier" text NOT NULL,
      "value" text NOT NULL,
      "expiresAt" timestamp NOT NULL,
      "createdAt" timestamp DEFAULT now(),
      "updatedAt" timestamp DEFAULT now()
    );
  `)

  // App table
  await pool.query(`
    CREATE TABLE IF NOT EXISTS "games" (
      "id" serial PRIMARY KEY,
      "name" text NOT NULL,
      "image" text NOT NULL,
      "link" text NOT NULL,
      "badge" text NOT NULL DEFAULT 'Free',
      "period" text NOT NULL DEFAULT 'both',
      "slug" text NOT NULL UNIQUE,
      "sortOrder" integer NOT NULL DEFAULT 0,
      "createdAt" timestamp NOT NULL DEFAULT now(),
      "updatedAt" timestamp NOT NULL DEFAULT now()
    );
  `)

  const { rows } = await pool.query('SELECT COUNT(*)::int AS count FROM "games"')
  if (rows[0].count === 0) {
    const seed = [
      ['Wingo 30s', '/games/wingo.png', 'https://example.com/wingo', 'Hot', '30s', 'wingo-30s', 1],
      ['Dice Roll', '/games/dice.png', 'https://example.com/dice', 'Free', '30s', 'dice-roll', 2],
      ['Lucky Spin', '/games/spin.png', 'https://example.com/spin', 'New', '30s', 'lucky-spin', 3],
      ['Color Trade', '/games/color.png', 'https://example.com/color', 'Free', '30s', 'color-trade', 4],
      ['K3 Lotto', '/games/k3.png', 'https://example.com/k3', 'Hot', '1min', 'k3-lotto', 5],
      ['Big Small', '/games/bigsmall.png', 'https://example.com/bigsmall', 'Free', '1min', 'big-small', 6],
      ['Number Up', '/games/numberup.png', 'https://example.com/numberup', 'New', '1min', 'number-up', 7],
      ['Aviator', '/games/aviator.png', 'https://example.com/aviator', 'Hot', 'both', 'aviator', 8],
    ]
    for (const g of seed) {
      await pool.query(
        `INSERT INTO "games" ("name","image","link","badge","period","slug","sortOrder")
         VALUES ($1,$2,$3,$4,$5,$6,$7)`,
        g,
      )
    }
    console.log(`Seeded ${seed.length} games`)
  } else {
    console.log(`Games table already has ${rows[0].count} rows, skipping seed`)
  }

  console.log('Database setup complete')
  await pool.end()
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
