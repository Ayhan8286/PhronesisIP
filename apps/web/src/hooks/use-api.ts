import { useAuth } from "@clerk/nextjs";
import { createApi } from "@/lib/api";
import { useMemo } from "react";

/**
 * A hook that provides a pre-authenticated API client.
 * Refactored to fetch the latest session token for EVERY request.
 * This ensures that if the user switches organizations, the very next
 * API call will use the correct organization ID in its JWT.
 */
export function useApi() {
  const { getToken } = useAuth();

  const api = useMemo(() => {
    const staticApi = createApi();
    const wrappedApi: any = {};

    Object.keys(staticApi).forEach((key) => {
      const originalMethod = (staticApi as any)[key];
      
      if (typeof originalMethod === "function") {
        wrappedApi[key] = async (...args: any[]) => {
          // Fetch a fresh token RIGHT BEFORE the request
          const token = await getToken();
          
          if (!token) {
            console.warn(`useApi: No token available for ${key}. Request might fail if auth is required.`);
          }

          // Create a temporary API instance with the fresh token
          const authenticatedApi = createApi(token || undefined) as any;
          return authenticatedApi[key](...args);
        };
      }
    });

    return wrappedApi;
  }, [getToken]);

  return api;
}
