import { Transaction } from "@/types/transaction";

type ScoreResponse = {
  riskScore: number;
  velocity: number;
  reasons: Array<{ feature: string; impact: number; note: string }>;
};

export async function fetchScore(tx: Transaction, history: Transaction[]): Promise<ScoreResponse> {
  const payload = {
    transaction: {
      id: tx.id,
      amount: tx.amount,
      merchant: tx.merchant ?? "",
      location: tx.location ?? "",
      channel: tx.channel,
      timestamp: tx.createdAt,            // IMPORTANT
      category: tx.category ?? "Other",
    },
    history: history.map((h) => ({
      id: h.id,
      amount: h.amount,
      merchant: h.merchant ?? "",
      location: h.location ?? "",
      channel: h.channel,
      timestamp: h.createdAt,             // IMPORTANT
      category: h.category ?? "Other",
    })),
  };

  const resp = await fetch("/api/score", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  if (!resp.ok) {
    const txt = await resp.text();
    throw new Error(`Score failed (${resp.status}): ${txt}`);
  }

  return resp.json();
}
