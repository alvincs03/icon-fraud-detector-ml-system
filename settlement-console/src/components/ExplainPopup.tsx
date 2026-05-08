"use client";

import React, { useEffect, useMemo, useRef } from "react";
import styles from "./explainPopup.module.css";
import { TxReason } from "@/types/transaction";

type GroupKey = "Behavior" | "Location" | "Merchant" | "Pricing" | "Time" | "Category" | "Other";

function groupForFeature(feature: string): GroupKey {
  const f = (feature || "").toLowerCase();

  if (f.includes("velocity")) return "Behavior";
  if (f.includes("distance") || f.includes("location")) return "Location";
  if (f.includes("merchant") || f.includes("freq")) return "Merchant";
  if (f.includes("price") || f.includes("amount")) return "Pricing";
  if (f.includes("hour") || f.includes("weekday") || f.includes("time")) return "Time";
  if (f.includes("category")) return "Category";
  return "Other";
}

const GROUP_ORDER: GroupKey[] = ["Behavior", "Location", "Merchant", "Pricing", "Time", "Category", "Other"];

export default function ExplainPopup({
  open,
  title,
  subtitle,
  mode,
  reasons,
  onClose,
}: {
  open: boolean;
  title: string;
  subtitle?: string;
  mode: "risk" | "velocity";
  reasons: TxReason[];
  onClose: () => void;
}) {
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Focus management + ESC close + basic focus trap
  useEffect(() => {
    if (!open) return;

    // focus close button when opened
    const t = setTimeout(() => closeBtnRef.current?.focus(), 0);

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();

      // simple focus trap
      if (e.key === "Tab") {
        const root = containerRef.current;
        if (!root) return;
        const focusables = Array.from(
          root.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
        ).filter((el) => !el.hasAttribute("disabled"));

        if (focusables.length === 0) return;

        const first = focusables[0];
        const last = focusables[focusables.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      clearTimeout(t);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  const grouped = useMemo(() => {
    const buckets: Record<GroupKey, TxReason[]> = {
      Behavior: [],
      Location: [],
      Merchant: [],
      Pricing: [],
      Time: [],
      Category: [],
      Other: [],
    };

    for (const r of reasons || []) {
      buckets[groupForFeature(r.feature)].push(r);
    }

    // For velocity mode, prioritize velocity groups first by filtering noise
    if (mode === "velocity") {
      // Keep Behavior + Time + Location; move the rest under Other
      const keep: GroupKey[] = ["Behavior", "Time", "Location"];
      for (const key of GROUP_ORDER) {
        if (!keep.includes(key) && buckets[key].length) {
          buckets.Other.push(...buckets[key]);
          buckets[key] = [];
        }
      }
    }

    // Sort each group by abs(impact) descending
    for (const key of GROUP_ORDER) {
      buckets[key].sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact));
    }

    return buckets;
  }, [reasons, mode]);

  if (!open) return null;

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-label={title} onMouseDown={onClose}>
      <div
        className={styles.modal}
        ref={containerRef}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className={styles.topRow}>
          <div>
            <div className={styles.title}>{title}</div>
            {subtitle && <div className={styles.subtitle}>{subtitle}</div>}
          </div>

          <button
            ref={closeBtnRef}
            className={styles.closeBtn}
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className={styles.body}>
          {(!reasons || reasons.length === 0) ? (
            <div className={styles.empty}>Scoring in progress — check back in a moment.</div>
          ) : (
            <div className={styles.groupStack}>
              {GROUP_ORDER.map((g) => {
                const items = grouped[g];
                if (!items || items.length === 0) return null;

                return (
                  <div key={g} className={styles.group}>
                    <div className={styles.groupTitle}>{g}</div>

                    <div className={styles.reasonList}>
                      {items.map((r, idx) => (
                        <div key={`${r.feature}-${idx}`} className={styles.reasonCard}>
                          <div className={styles.reasonHeader}>
                            <div className={styles.feature}>{r.feature}</div>
                            <div className={styles.impact}>
                              {r.impact > 0 ? `+${r.impact.toFixed(2)}` : r.impact.toFixed(2)}
                            </div>
                          </div>
                          <div className={styles.note}>{r.note}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className={styles.footer}>
          <button className={styles.okBtn} onClick={onClose}>
            OK
          </button>
        </div>
      </div>
    </div>
  );
}
