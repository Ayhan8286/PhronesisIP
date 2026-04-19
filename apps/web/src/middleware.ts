import { withAuth } from "next-auth/middleware";
import { NextResponse } from "next/server";

export default withAuth(
  function middleware(req) {
    // Already authenticated if this runs, just continue
    return NextResponse.next();
  },
  {
    callbacks: {
      authorized: ({ token }) => !!token,
    },
    pages: {
      signIn: "/login",
    },
  }
);

export const config = {
  matcher: [
    /*
     * Match all request paths except for:
     * - _next/static, _next/image, favicon.ico (static assets)
     * - public (root public assets)
     * - login (auth page)
     * - api/auth (NextAuth endpoints)
     * - api/v1/public (Unprotected public API)
     * - get-started (Public client intake)
     */
    "/((?!_next/static|_next/image|favicon.ico|public|login|api/auth|api/v1/public|get-started).*)",
  ],
};
