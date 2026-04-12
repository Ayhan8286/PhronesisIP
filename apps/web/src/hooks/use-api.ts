import { useAuth } from "@clerk/nextjs";
import { createApi } from "@/lib/api";
import { useMemo, useState, useEffect } from "react";

export function useApi() {
  const { getToken } = useAuth();
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    async function fetchToken() {
      const t = await getToken();
      setToken(t);
    }
    fetchToken();
  }, [getToken]);

  const api = useMemo(() => {
    // If token is not yet loaded, we return a version of the API that will still work
    // but might fail if the backend requires authentication immediately.
    // However, most dashboard actions happen after the component has mounted and the token is fetched.
    return createApi(token || undefined);
  }, [token]);

  return api;
}
