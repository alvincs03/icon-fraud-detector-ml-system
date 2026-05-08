"use client";

import Image from "next/image";
import { useMemo, useState } from "react";
import styles from "./page.module.css";
import Sidebar from "@/components/Sidebar";
import AddTransactionModal from "@/components/AddTransactionModal";
import ExplainPopup from "@/components/ExplainPopup";
import { useTransactions } from "@/context/TransactionsContext";
import { Transaction } from "@/types/transaction";
import { useSession } from "next-auth/react";

type RiskFilter = "all" | "high" | "medium" | "low";

function riskBand(score: number): "low" | "medium" | "high" {
  if (score >= 7) return "high";
  if (score >= 4) return "medium";
  return "low";
}

function bandLabel(b: "low" | "medium" | "high") {
  if (b === "high") return "High Risk";
  if (b === "medium") return "Medium Risk";
  return "Low Risk";
}

function InfoCard({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className={styles.infoCard}>
      <div className={styles.infoTitle}>{title}</div>
      <div className={styles.infoBody}>{children ?? <span className={styles.placeholder}>—</span>}</div>
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: string | number; accent?: "high" | "medium" | "neutral" }) {
  return (
    <div className={[styles.statCard, accent ? styles[`statAccent_${accent}`] : ""].join(" ")}>
      <div className={styles.statValue}>{value}</div>
      <div className={styles.statLabel}>{label}</div>
    </div>
  );
}

function RiskMeter({ score }: { score: number }) {
  const band = riskBand(score);
  const pct = Math.min(100, (score / 10) * 100);
  return (
    <div className={styles.riskMeter}>
      <div className={styles.riskMeterTrack}>
        <div
          className={[styles.riskMeterFill, styles[`meterFill_${band}`]].join(" ")}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className={[styles.riskMeterLabel, styles[`scoreText_${band}`]].join(" ")}>
        {score.toFixed(1)} / 10
      </div>
    </div>
  );
}

function TransactionPill({
  tx,
  isOpen,
  hasBeenOpened,
  onToggle,
}: {
  tx: Transaction;
  isOpen: boolean;
  hasBeenOpened: boolean;
  onToggle: () => void;
}) {
  const band = riskBand(tx.riskScore);

  return (
    <div
      className={[
        styles.pill,
        styles[`pillBand_${band}`],
        hasBeenOpened ? styles.pillVisited : "",
      ].join(" ")}
      onClick={onToggle}
      role="button"
      tabIndex={0}
      aria-expanded={isOpen}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onToggle(); } }}
    >
      <div className={[styles.pillRiskBar, styles[`riskBar_${band}`]].join(" ")} />

      <span className={isOpen ? styles.chevOpen : styles.chevClosed}>▾</span>

      <div className={styles.pillAmount}>${tx.amount.toFixed(2)}</div>

      <div className={styles.pillMerchant}>
        {tx.merchant?.trim() ? tx.merchant : "Unknown merchant"}
      </div>

      <div className={styles.pillCategory}>
        {tx.category?.trim() && tx.category !== "Other" ? tx.category : ""}
      </div>

      <div className={[styles.pillScore, styles[`score_${band}`]].join(" ")}>
        {tx.riskScore.toFixed(1)}
      </div>

      <div className={styles.pillExpandHint}>{isOpen ? "collapse" : "expand ↓"}</div>
    </div>
  );
}

function ExpandedTransaction({
  tx,
  onExplain,
}: {
  tx: Transaction;
  onExplain: (title: string, subtitle: string, mode: "risk" | "velocity") => void;
}) {
  const band = riskBand(tx.riskScore);

  return (
    <div className={styles.expandedWrap}>
      <div className={styles.centerRow}>
        <section className={styles.selectedCard}>
          <div className={styles.selectedInner}>
            <div className={styles.selectedAmount}>${tx.amount.toFixed(2)}</div>

            <div className={styles.selectedMerchant}>
              {tx.merchant?.trim() ? tx.merchant : "Unknown merchant"}
            </div>

            <div className={[styles.riskBadge, styles[`badge_${band}`]].join(" ")}>
              {bandLabel(band)}
            </div>

            <RiskMeter score={tx.riskScore} />

            <div className={styles.selectedSub}>Flagged for Review</div>
          </div>
        </section>

        <section className={styles.gridWrap}>
          <div className={styles.infoGrid}>
            <InfoCard title="Timestamp">{new Date(tx.createdAt).toLocaleString()}</InfoCard>

            <InfoCard title="Merchant">
              {tx.merchant?.trim() ? tx.merchant : "Unknown merchant"}
            </InfoCard>

            <InfoCard title="Category">
              {tx.category?.trim() ? tx.category : "Other"}
            </InfoCard>

            <InfoCard title="Location">{tx.location}</InfoCard>

            <InfoCard title="Payment Channel">{tx.channel.toUpperCase()}</InfoCard>

            <InfoCard title="Velocity">
              <button
                type="button"
                className={styles.explainBtn}
                title="Click for details"
                onClick={() =>
                  onExplain(
                    "Velocity",
                    "Velocity measures short-term transaction bursts (e.g., multiple purchases in a short window).",
                    "velocity"
                  )
                }
              >
                {tx.velocity}
                <span className={styles.infoIcon}>ⓘ</span>
              </button>
            </InfoCard>

            <InfoCard title="Risk Score">
              <button
                type="button"
                className={styles.explainBtn}
                title="Click to see why"
                onClick={() =>
                  onExplain(
                    "Risk Score",
                    "Key factors that influenced this prediction (grouped by type).",
                    "risk"
                  )
                }
              >
                <span className={[styles.scoreBig, styles[`scoreText_${band}`]].join(" ")}>
                  {tx.riskScore.toFixed(1)}
                </span>
                <span className={styles.infoIcon}>ⓘ</span>
              </button>
            </InfoCard>
          </div>
        </section>
      </div>
    </div>
  );
}

export default function Home() {
  const { data: session } = useSession();
  const [modalOpen, setModalOpen] = useState(false);
  const { transactions } = useTransactions();

  const [openId, setOpenId] = useState<string | null>(null);
  const [openedIds, setOpenedIds] = useState<Set<string>>(() => new Set());
  const [searchTerm, setSearchTerm] = useState("");
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("all");

  const [explainOpen, setExplainOpen] = useState(false);
  const [explainTitle, setExplainTitle] = useState("");
  const [explainSubtitle, setExplainSubtitle] = useState("");
  const [explainTxId, setExplainTxId] = useState<string | null>(null);
  const [explainMode, setExplainMode] = useState<"risk" | "velocity">("risk");

  // Derived live from transactions so popup auto-updates when async scoring finishes
  const explainReasons = useMemo(
    () => transactions.find((t) => t.id === explainTxId)?.reasons ?? [],
    [transactions, explainTxId]
  );

  // Stats derived from all transactions
  const stats = useMemo(() => {
    const total = transactions.length;
    const highRisk = transactions.filter((tx) => riskBand(tx.riskScore) === "high").length;
    const avgScore =
      total === 0 ? 0 : transactions.reduce((s, tx) => s + tx.riskScore, 0) / total;
    return { total, highRisk, avgScore };
  }, [transactions]);

  const filtered = useMemo(() => {
    let result = transactions;

    const q = searchTerm.trim().toLowerCase();
    if (q) {
      result = result.filter((tx) => {
        const merchant = (tx.merchant ?? "").toLowerCase().trim();
        return merchant.length > 0 && merchant.includes(q);
      });
    }

    if (riskFilter !== "all") {
      result = result.filter((tx) => riskBand(tx.riskScore) === riskFilter);
    }

    return result;
  }, [transactions, searchTerm, riskFilter]);

  const hasTx = transactions.length > 0;

  const openExplain = (tx: Transaction, title: string, subtitle: string, mode: "risk" | "velocity") => {
    setExplainTitle(title);
    setExplainSubtitle(subtitle);
    setExplainTxId(tx.id);
    setExplainMode(mode);
    setExplainOpen(true);
  };

  return (
    <div className={styles.shell}>
      <Sidebar onAddClick={() => setModalOpen(true)} />
      <AddTransactionModal open={modalOpen} onClose={() => setModalOpen(false)} />

      <ExplainPopup
        open={explainOpen}
        title={explainTitle}
        subtitle={explainSubtitle}
        mode={explainMode}
        reasons={explainReasons}
        onClose={() => { setExplainOpen(false); setExplainTxId(null); }}
      />

      <main className={styles.main}>
        <div className={styles.symbolRow}>
          <Image src="/symbol.png" alt="Symbol" width={120} height={120} />
        </div>

        <div className={styles.headerRow}>
          <div className={styles.headerLeft}>
            <h1 className={styles.h1}>
              HELLO {session?.user?.name?.split(" ")[0].toUpperCase() || session?.user?.email?.split("@")[0].toUpperCase() || "THERE"}!
            </h1>
          </div>

          <div className={styles.searchWrap}>
            <input
              className={styles.searchInput}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search merchants..."
              aria-label="Search merchants"
            />
          </div>
        </div>

        {hasTx && (
          <div className={styles.statsRow}>
            <StatCard label="Total Transactions" value={stats.total} accent="neutral" />
            <StatCard label="High Risk" value={stats.highRisk} accent={stats.highRisk > 0 ? "high" : "neutral"} />
            <StatCard label="Avg Risk Score" value={stats.avgScore.toFixed(1)} accent={stats.avgScore >= 7 ? "high" : stats.avgScore >= 4 ? "medium" : "neutral"} />
          </div>
        )}

        {hasTx && (
          <div className={styles.filterRow}>
            {(["all", "high", "medium", "low"] as RiskFilter[]).map((f) => (
              <button
                key={f}
                type="button"
                className={[
                  styles.filterBtn,
                  riskFilter === f ? styles.filterBtnActive : "",
                  f !== "all" ? styles[`filterBtn_${f}`] : "",
                ].join(" ")}
                onClick={() => setRiskFilter(f)}
              >
                {f === "all" ? "All" : f === "high" ? "High Risk" : f === "medium" ? "Medium Risk" : "Low Risk"}
              </button>
            ))}
          </div>
        )}

        <div className={styles.listWrap}>
          {!hasTx ? (
            <div className={styles.emptyState}>
              <div className={styles.emptyTitle}>No transactions yet</div>
              <div className={styles.emptyHint}>← Click <strong>+ Add Transaction</strong> in the sidebar to get started</div>
            </div>
          ) : filtered.length === 0 ? (
            <div className={styles.noResults}>No results for this filter.</div>
          ) : (
            <div className={styles.listStack}>
              {filtered.map((tx) => {
                const isOpen = openId === tx.id;
                const hasBeenOpened = openedIds.has(tx.id);

                return (
                  <div key={tx.id} className={styles.listItem}>
                    <TransactionPill
                      tx={tx}
                      isOpen={isOpen}
                      hasBeenOpened={hasBeenOpened}
                      onToggle={() => {
                        setOpenId(isOpen ? null : tx.id);
                        if (!hasBeenOpened) {
                          setOpenedIds((prev) => {
                            const next = new Set(prev);
                            next.add(tx.id);
                            return next;
                          });
                        }
                      }}
                    />

                    {isOpen && (
                      <ExpandedTransaction
                        tx={tx}
                        onExplain={(title, subtitle, mode) => openExplain(tx, title, subtitle, mode)}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
