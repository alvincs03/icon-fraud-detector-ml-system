import { Transaction, VelocityLevel } from "@/types/transaction";

export function computeVelocity(amount: number): VelocityLevel {
  if (amount >= 800) return "high";
  if (amount >= 200) return "elevated";
  return "normal";
}

/**
 * Placeholder "ML" scorer.
 * Returns a 0-10 score to match your design (like 7.8).
 * Replace this later with your actual model output.
 */
export function computeRiskScore(tx: Omit<Transaction, "riskScore" | "velocity">): number {
  let score = 1.5;

  // Amount-based bumps
  if (tx.amount >= 100) score += 1.2;
  if (tx.amount >= 250) score += 2.0;
  if (tx.amount >= 800) score += 2.8;

  // Simple “risky merchant keyword” bump (placeholder)
  const m = tx.merchant.toLowerCase();
  if (m.includes("gift") || m.includes("crypto") || m.includes("luxury")) score += 1.4;

  // “Unfamiliar location” placeholder bump
  const loc = tx.location.toLowerCase();
  if (loc.includes("international") || loc.includes("unknown")) score += 1.2;

  // clamp to [0, 10] and round to 1 decimal
  score = Math.max(0, Math.min(10, score));
  return Math.round(score * 10) / 10;
}

export function enrichTransaction(
  tx: Omit<Transaction, "riskScore" | "velocity">
): Transaction {
  const riskScore = computeRiskScore(tx);
  const velocity = computeVelocity(tx.amount);
  return { ...tx, riskScore, velocity };
}
