"use client";

import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { Transaction } from "@/types/transaction";
import { enrichTransaction } from "@/lib/scoring";
import { fetchScore } from "@/lib/fetchScore";

type NewTransactionInput = {
  amount: number;
  merchant: string;
  location: string;
  channel: Transaction["channel"];
  category?: string;
  timestamp: string; // ISO string
};

type TransactionsContextValue = {
  transactions: Transaction[];
  addTransaction: (input: NewTransactionInput) => Promise<void>;
  clearAll: () => void;
  userKey: string; // helpful for debugging
  isAuthed: boolean;
};

const TransactionsContext = createContext<TransactionsContextValue | null>(null);

const STORAGE_PREFIX = "icon_transactions_v1__";

function safeParseTransactions(raw: string | null): Transaction[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((t) => t && typeof t === "object" && typeof t.id === "string") as Transaction[];
  } catch {
    return [];
  }
}

function normalizeEmail(email: string) {
  return email.trim().toLowerCase();
}

export function TransactionsProvider({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession();

  const isAuthed = status === "authenticated";
  const email = session?.user?.email ? normalizeEmail(session.user.email) : "";
  const userKey = isAuthed && email ? email : "anon";

  // Derived localStorage key
  const storageKey = `${STORAGE_PREFIX}${userKey}`;

  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const hydratedRef = useRef(false);
  const lastStorageKeyRef = useRef<string>("");

  // Load when auth state changes (storageKey changes)
  useEffect(() => {
    const prevKey = lastStorageKeyRef.current;
    lastStorageKeyRef.current = storageKey;

    const loaded = safeParseTransactions(localStorage.getItem(storageKey));
    setTransactions(loaded);

    hydratedRef.current = true;

    // Optional: If user just signed in, you may want to migrate anon transactions.
    // I am NOT auto-migrating to avoid surprising behavior.
    // If you want migration later, we can implement a one-time “Import anon transactions” action.
    void prevKey;
  }, [storageKey]);

  // Persist whenever transactions change
  useEffect(() => {
    if (!hydratedRef.current) return;
    localStorage.setItem(storageKey, JSON.stringify(transactions));
  }, [transactions, storageKey]);

  const clearAll = () => {
    setTransactions([]);
    localStorage.removeItem(storageKey);
  };

  const addTransaction = async (input: NewTransactionInput) => {
    // This is the “real auth information” being embedded:
    // If authed -> userId is the email (for now)
    // Later -> userId becomes DB id from Prisma adapter.
    const userId = isAuthed && email ? email : "anon";

    const base: Transaction = {
      id: `tx_${crypto.randomUUID()}`,
      createdAt: input.timestamp,
      userId,
      amount: Number(input.amount),
      merchant: input.merchant.trim(),
      location: input.location.trim(),
      channel: input.channel,
      category: (input.category ?? "Other").trim(),
      riskScore: 0,
      velocity: 0,
      reasons: [],
    };

    // Local fallback enrich (optional but makes UI feel responsive)
    const locallyEnriched = enrichTransaction(base);

    // History snapshot BEFORE insert (important for velocity/merchant_freq)
    const historySnapshot = transactions;

    // Insert immediately so it renders
    setTransactions((prev) => [locallyEnriched, ...prev]);

    // Score async and patch in-place
    try {
      const scored = await fetchScore(locallyEnriched, historySnapshot);

      setTransactions((prev) =>
        prev.map((tx) =>
          tx.id === locallyEnriched.id
            ? {
                ...tx,
                riskScore: Number(scored.riskScore),
                velocity: Number(scored.velocity),
                reasons: Array.isArray(scored.reasons) ? scored.reasons : [],
              }
            : tx
        )
      );
    } catch {
      // Keep local estimate, but annotate why ML wasn’t used
      setTransactions((prev) =>
        prev.map((tx) =>
          tx.id === locallyEnriched.id
            ? {
                ...tx,
                reasons: [
                  ...(Array.isArray(tx.reasons) ? tx.reasons : []),
                  { feature: "ml", impact: 0, note: "ML service unavailable; showing local estimate" },
                ],
              }
            : tx
        )
      );
    }
  };

  const value = useMemo(
    () => ({
      transactions,
      addTransaction,
      clearAll,
      userKey,
      isAuthed,
    }),
    [transactions, userKey, isAuthed]
  );

  return <TransactionsContext.Provider value={value}>{children}</TransactionsContext.Provider>;
}

export function useTransactions() {
  const ctx = useContext(TransactionsContext);
  if (!ctx) throw new Error("useTransactions must be used within TransactionsProvider");
  return ctx;
}
