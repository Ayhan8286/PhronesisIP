'use client';

import { useEffect } from 'react';
import posthog from 'posthog-js';
import { PostHogProvider } from 'posthog-js/react';

if (typeof window !== 'undefined') {
  const posthogKey = process.env.NEXT_PUBLIC_POSTHOG_KEY;
  const posthogHost = process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://app.posthog.com';

  if (posthogKey) {
    posthog.init(posthogKey, {
      api_host: posthogHost,
      person_profiles: 'always', 
      capture_pageview: false, // We handle this manually to ensure it works with SPA navigation
    });
  }
}

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';

export function Providers({ children }: { children: React.ReactNode }) {
  // Initialize QueryClient within the component to ensure each user gets their own cache in SSR
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            retry: 2, // Automatically retry failing queries up to 2 times
            retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000), // Exponential backoff
            refetchOnWindowFocus: false, // Prevents excessive refetching on tab switch
          },
        },
      })
  );

  useEffect(() => {
    // Manually capture pageview on mount and navigation
    if (typeof window !== 'undefined') {
      posthog.capture('$pageview');
    }
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <PostHogProvider client={posthog}>
        {children}
      </PostHogProvider>
    </QueryClientProvider>
  );
}
