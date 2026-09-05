"use client";

import { useEffect, useState, type DependencyList } from "react";

/**
 * Reads repository data that may include browser-only (localStorage) content
 * alongside the static demo dataset.
 *
 * Server Components can never see localStorage, and computing it directly
 * during a Client Component's render would make the server-rendered HTML
 * (no local data) disagree with the client's hydrated render (local data
 * present) -- a real hydration mismatch, not a hypothetical one, for any
 * page reading `getAssessments()`/submissions after a user has created
 * something via the local assessment workflow.
 *
 * The fix used throughout this app: start at `undefined` (rendered
 * identically on server and first client pass), then resolve the real value
 * in an effect after mount. Callers show a small loading state for that one
 * frame; the deps array lets a page force a re-read (e.g. after saving).
 */
export function useClientData<T>(compute: () => T, deps: DependencyList = []): T | undefined {
  const [data, setData] = useState<T | undefined>(undefined);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- see file docblock: this is the intentional client-only-data resolution pattern, not a derivable-in-render value.
    setData(compute());
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `compute` is intentionally excluded; callers pass an inline closure and list their own deps.
  }, deps);

  return data;
}
