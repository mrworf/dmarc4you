import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { AggregateExplorerState } from "@/lib/aggregate-explorer-state";

type StateUpdater<T> = T | ((current: T) => T);

function resolveUpdater<T>(updater: StateUpdater<T>, current: T): T {
  return typeof updater === "function" ? (updater as (current: T) => T)(current) : updater;
}

type UseAggregateExplorerStateOptions<T extends AggregateExplorerState> = {
  buildParams: (state: T) => string;
  debounceMs?: number;
  initialState: T;
  parseState: (searchParams: URLSearchParams) => T;
  pathname: string;
  resetKey: string;
};

export function useAggregateExplorerState<T extends AggregateExplorerState>({
  buildParams,
  debounceMs = 300,
  initialState,
  parseState,
  pathname,
  resetKey,
}: UseAggregateExplorerStateOptions<T>) {
  const [appliedState, setAppliedState] = useState<T>(initialState);
  const [draftState, setDraftState] = useState<T>(initialState);
  const draftStateRef = useRef(draftState);
  const debounceTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    draftStateRef.current = draftState;
  }, [draftState]);

  const clearPendingCommit = useCallback(() => {
    if (debounceTimeoutRef.current !== null) {
      window.clearTimeout(debounceTimeoutRef.current);
      debounceTimeoutRef.current = null;
    }
  }, []);

  const replaceUrl = useCallback(
    (state: T) => {
      const nextParams = buildParams(state);
      const nextUrl = nextParams ? `${pathname}?${nextParams}` : pathname;
      const currentUrl = `${window.location.pathname}${window.location.search}`;

      if (currentUrl !== nextUrl) {
        window.history.replaceState(window.history.state, "", nextUrl);
      }
    },
    [buildParams, pathname],
  );

  const syncFromUrl = useCallback(() => {
    const nextState = parseState(new URLSearchParams(window.location.search));
    clearPendingCommit();
    draftStateRef.current = nextState;
    setAppliedState(nextState);
    setDraftState(nextState);
  }, [clearPendingCommit, parseState]);

  const commitState = useCallback(
    (updater: StateUpdater<T>) => {
      const nextState = resolveUpdater(updater, draftStateRef.current);
      clearPendingCommit();
      draftStateRef.current = nextState;
      setDraftState(nextState);
      setAppliedState(nextState);
      replaceUrl(nextState);
      return nextState;
    },
    [clearPendingCommit, replaceUrl],
  );

  const setDraftOnly = useCallback((updater: StateUpdater<T>) => {
    const nextState = resolveUpdater(updater, draftStateRef.current);
    draftStateRef.current = nextState;
    setDraftState(nextState);
    return nextState;
  }, []);

  const updateDraftState = useCallback(
    (updater: StateUpdater<T>, mode: "immediate" | "debounced" = "immediate") => {
      const nextState = resolveUpdater(updater, draftStateRef.current);
      draftStateRef.current = nextState;
      setDraftState(nextState);

      if (mode === "debounced") {
        clearPendingCommit();
        debounceTimeoutRef.current = window.setTimeout(() => {
          setAppliedState(nextState);
          replaceUrl(nextState);
          debounceTimeoutRef.current = null;
        }, debounceMs);
        return nextState;
      }

      clearPendingCommit();
      setAppliedState(nextState);
      replaceUrl(nextState);
      return nextState;
    },
    [clearPendingCommit, debounceMs, replaceUrl],
  );

  const resetState = useCallback(
    (nextState: T) => {
      clearPendingCommit();
      draftStateRef.current = nextState;
      setDraftState(nextState);
      setAppliedState(nextState);
      replaceUrl(nextState);
    },
    [clearPendingCommit, replaceUrl],
  );

  useEffect(() => {
    draftStateRef.current = initialState;
    setAppliedState(initialState);
    setDraftState(initialState);
    clearPendingCommit();
  }, [clearPendingCommit, initialState, resetKey]);

  useEffect(() => {
    const handlePopState = () => {
      syncFromUrl();
    };

    window.addEventListener("popstate", handlePopState);
    return () => {
      window.removeEventListener("popstate", handlePopState);
    };
  }, [syncFromUrl]);

  useEffect(() => {
    return () => {
      clearPendingCommit();
    };
  }, [clearPendingCommit]);

  return useMemo(
    () => ({
      appliedState,
      commitState,
      draftState,
      resetState,
      setDraftOnly,
      syncFromUrl,
      updateDraftState,
    }),
    [appliedState, commitState, draftState, resetState, setDraftOnly, syncFromUrl, updateDraftState],
  );
}
