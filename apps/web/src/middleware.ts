import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isPublicRoute = createRouteMatcher([
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/",
]);

// Routes that should bypass Clerk middleware entirely (handled by FastAPI backend)
const isBackendRoute = createRouteMatcher([
  "/api/v1(.*)",
  "/api/inngest(.*)",
]);

export default clerkMiddleware(async (auth, request) => {
  // Skip Clerk auth for backend API routes — they have their own JWT verification
  if (isBackendRoute(request)) {
    return;
  }

  if (!isPublicRoute(request)) {
    await auth.protect();
  }
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
