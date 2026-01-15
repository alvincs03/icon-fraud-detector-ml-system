"use client";

import React from "react";
import styles from "./reasonPopup.module.css";
import { Transaction } from "@/types/transaction";

function riskBand(score: number) {
  if (score < 3.5) return "Low";
  if (score < 7.0) return "Medium";
  return "High";
}

export default function ReasonPopup({
  open,
  onClose,
  tx,
  mode,
}: {
  open: boolean;
  onClose: () => void;
  tx: Transaction | null;
  mode: "risk" | "velocity";
}) {
  if (!open || !tx) return null;

  const band = riskBand(tx.riskScore);

  const header =
    mode === "risk"
      ? `Risk Score (${tx.riskScore.toFixed(1)} / 10) — ${band} Risk`
      : `Velocity (${tx.velocity}) — Recent Activity`;

  const intro =
    mode === "risk"
      ? "This score is produced by the model based on signals extracted from the transaction and the recent transaction history."
      : "Velocity is computed from recent transactions (short time windows). Higher velocity often indicates automated or compromised activity.";

  const emptyReasons =
    !tx.reasons || tx.reasons.length === 0
      ? "No explanation signals were returned. This usually means the scoring service did not include reasons yet."
      : null;

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-label="Explanation">
      <div className={styles.modal}>
        <div className={styles.topRow}>
          <div className={styles.title}>{header}</div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className={styles.body}>
          <div className={styles.intro}>{intro}</div>

          {mode === "risk" && (
            <div className={styles.bandNote}>
              {band === "Low"
                ? "Low risk typically means the transaction matches the user’s normal pattern (amount, timing, merchant familiarity, and velocity)."
                : band === "Medium"
                ? "Medium risk usually indicates one or two signals deviated from normal behavior (e.g., unusual amount or elevated velocity)."
                : "High risk usually indicates multiple strong deviations (e.g., high amount + unusual location + burst activity)."}
            </div>
          )}

          <div className={styles.sectionTitle}>Top Drivers</div>

          {emptyReasons ? (
            <div className={styles.empty}>{emptyReasons}</div>
          ) : (
            <ul className={styles.list}>
              {tx.reasons.slice(0, 6).map((r, idx) => (
                <li key={`${r.feature}-${idx}`} className={styles.item}>
                  <div className={styles.itemTop}>
                    <span className={styles.feature}>{r.feature}</span>
                    <span className={styles.impact}>impact: {Number(r.impact).toFixed(3)}</span>
                  </div>
                  <div className={styles.note}>{r.note}</div>
                </li>
              ))}
            </ul>
          )}

          <div className={styles.footer}>
            This explanation is intended for transparency and review, not as a final decision.
          </div>
        </div>
      </div>
    </div>
  );
}
