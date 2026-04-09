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

export function Providers({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    // Manually capture pageview on mount and navigation
    if (typeof window !== 'undefined') {
      posthog.capture('$pageview');
    }
  }, []);

  return (
    <PostHogProvider client={posthog}>
      {children}
    </PostHogProvider>
  );
}
