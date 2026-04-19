import { useAuth } from "@/hooks/useAuth";
import { createApi } from "@/lib/api";
import { useMemo } from "react";

/**
 * A hook that provides a pre-authenticated API client.
 * Uses TypeScript's ReturnType to preserve the interface of createApi
 * while injecting fresh tokens for every request.
 */
export function useApi() {
  const { token } = useAuth();

  const api = useMemo(() => {
    const staticApi = createApi();
    // Use the return type of createApi as the contract for our proxy
    type ApiInterface = ReturnType<typeof createApi>;
    const wrappedApi = {} as ApiInterface;

    (Object.keys(staticApi) as Array<keyof ApiInterface>).forEach((key) => {
      const originalMethod = staticApi[key];
      
      if (typeof originalMethod === "function") {
        // @ts-ignore - dynamic proxying requires some casting
        wrappedApi[key] = async (...args: any[]) => {
          // Create a fresh instance for the call with the new token
          const authenticatedApi = createApi(token || undefined);
          // @ts-ignore - dynamic method access
          return authenticatedApi[key](...args);
        };
      }
    });

    return wrappedApi;
  }, [token]);

  return api;
}
