import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const BLOCKED_HTML = [
  '/home.html',
  '/game.html',
  '/payment.html',
  '/profile.html',
  '/game-link.html',
  '/telegram-verify.html',
  '/index.html',
]

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Block direct .html access — redirect to home
  if (BLOCKED_HTML.some(p => pathname === p)) {
    return NextResponse.redirect(new URL('/', request.url), 301)
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|images|api).*)',
  ],
}
