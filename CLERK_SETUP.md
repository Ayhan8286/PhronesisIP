# Clerk Production Setup Guide

This guide explains how to properly configure Clerk authentication for production deployment of PatentIQ.

## Problem Symptoms

If you're seeing these errors:
- `Clerk has been loaded with development keys` warnings in browser
- `Missing required production environment variables: CLERK_JWKS_URL, CLERK_ISSUER` API errors
- 500 Internal Server Error when making API calls

## Solution: Configure Clerk Environment Variables

### Option 1: Free Clerk Domain (Recommended for now)

Clerk provides free subdomains that work for production without purchasing a custom domain:

1. Go to your [Clerk Dashboard](https://dashboard.clerk.com)
2. Select your application (or create a new one)
3. Navigate to **Domain & Keys** in the sidebar
4. Your free domain will be something like `your-app.clerk.accounts.dev` or `your-app.clerk.com`
5. Navigate to **API Keys** to get your keys

### Option 2: Use Development Mode (Temporary)

For testing without production keys, you can temporarily use development mode:

1. In your Vercel environment variables, add: `APP_ENV=development`
2. This will bypass the production validation and use the dev user bypass
3. Note: This is not secure for production use

### Step 2: Configure Environment Variables

**For Free Clerk Domain (Backend API):**
```bash
CLERK_SECRET_KEY=sk_test_your_secret_key_here  # Use test keys for free tier
CLERK_PUBLISHABLE_KEY=pk_test_your_publishable_key_here
CLERK_JWKS_URL=https://your-app.clerk.accounts.dev/.well-known/jwks.json
CLERK_ISSUER=https://your-app.clerk.accounts.dev
```

**For Development Mode (Backend API):**
```bash
APP_ENV=development
# No Clerk keys required - will use dev user bypass
```

**Where to find your Clerk domain:**
- In Clerk Dashboard, go to **Domain & Keys**
- Free domains use `.clerk.accounts.dev` for development
- Production free domains use `.clerk.com` (if available in your plan)

### Step 3: Configure Frontend Environment Variables

Add these to your Vercel deployment environment variables (Frontend):

**For Free Clerk Domain:**
```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_your_publishable_key_here  # Same as backend
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/dashboard
```

**For Development Mode:**
```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_your_publishable_key_here
# Other NEXT_PUBLIC_* variables can remain the same
```

### Step 4: Verify Configuration

After setting up the environment variables:

1. **Redeploy your application** on Vercel
2. Check browser console - the "development keys" warning should be gone
3. Test authentication flow - sign in/sign up should work
4. Make API calls - the 500 errors should be resolved

## Common Issues

### Using Development Keys in Production
- **Problem**: Using `.clerk.accounts.dev` domain or `sk_test_`/`pk_test_` keys
- **Solution**: Switch to production keys and `.clerk.com` domain
- **Why**: Development keys have strict rate limits and are not meant for production

### Missing JWKS/Issuer URLs
- **Problem**: `CLERK_JWKS_URL` or `CLERK_ISSUER` not set
- **Solution**: Set both to your production Clerk domain
- **Example**: `https://your-app.clerk.com/.well-known/jwks.json`

### Environment Variable Scope
- **Problem**: Variables set for wrong app (frontend vs backend)
- **Solution**: 
  - Backend API needs: `CLERK_SECRET_KEY`, `CLERK_PUBLISHABLE_KEY`, `CLERK_JWKS_URL`, `CLERK_ISSUER`
  - Frontend needs: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and other `NEXT_PUBLIC_*` variables

## Testing the Fix

1. After deployment, check the browser console for any Clerk warnings
2. Try signing in - should work without development key warnings
3. Make an API call that requires authentication - should not return 500 errors
4. Check the `/api/v1/health` endpoint - should return healthy status

## Support

If you still have issues:
1. Double-check all environment variables are set correctly
2. Ensure you're using production keys, not development keys
3. Verify your Clerk domain is correct (production uses `.clerk.com`)
4. Check Vercel deployment logs for any specific error messages
