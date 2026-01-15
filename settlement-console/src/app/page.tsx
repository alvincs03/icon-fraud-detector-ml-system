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
    <div className={[styles.pill, hasBeenOpened ? styles.pillVisited : ""].join(" ")}>
      <button
        type="button"
        className={styles.chevBtn}
        aria-expanded={isOpen}
        onClick={onToggle}
      >
        <span className={isOpen ? styles.chevOpen : styles.chevClosed}>▾</span>
      </button>

      <div className={styles.pillAmount}>${tx.amount.toFixed(2)}</div>

      <div className={styles.pillMerchant}>
        {tx.merchant?.trim() ? tx.merchant : "Unknown merchant"}
      </div>

      <div className={[styles.pillScore, styles[`score_${band}`]].join(" ")}>
        {tx.riskScore.toFixed(1)}
      </div>
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
                onClick={() =>
                  onExplain(
                    "Velocity",
                    "Velocity measures short-term transaction bursts (e.g., multiple purchases in a short window).",
                    "velocity"
                  )
                }
              >
                {tx.velocity}
              </button>
            </InfoCard>

            <InfoCard title="Risk Score">
              <button
                type="button"
                className={styles.explainBtn}
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
              </button>
            </InfoCard>
          </div>
        </section>
      </div>
    </div>
  );
}

export default function Home() {
  const { data: session} = useSession();
  const [modalOpen, setModalOpen] = useState(false);
  const { transactions } = useTransactions();

  const [openId, setOpenId] = useState<string | null>(null);
  const [openedIds, setOpenedIds] = useState<Set<string>>(() => new Set());

  const [searchTerm, setSearchTerm] = useState("");

  // Explain popup state
  const [explainOpen, setExplainOpen] = useState(false);
  const [explainTitle, setExplainTitle] = useState("");
  const [explainSubtitle, setExplainSubtitle] = useState("");
  const [explainReasons, setExplainReasons] = useState<Transaction["reasons"]>([]);
  const [explainMode, setExplainMode] = useState<"risk" | "velocity">("risk");

  const filtered = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    if (!q) return transactions;

    return transactions.filter((tx) => {
      const merchant = (tx.merchant ?? "").toLowerCase().trim();
      return merchant.length > 0 && merchant.includes(q);
    });
  }, [transactions, searchTerm]);

  const hasTx = transactions.length > 0;

  const openExplain = (tx: Transaction, title: string, subtitle: string, mode: "risk" | "velocity") => {
    setExplainTitle(title);
    setExplainSubtitle(subtitle);
    setExplainReasons(tx.reasons || []);
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
        onClose={() => setExplainOpen(false)}
      />

      <main className={styles.main}>
        <div className={styles.symbolRow}>
          <Image src="/symbol.png" alt="Symbol" width={120} height={120} />
        </div>

        <div className={styles.headerRow}>
          <div className={styles.headerLeft}>
            <h1 className={styles.h1}>HELLO {session?.user?.name || session?.user?.email|| "THERE"}!</h1>
            <div className={styles.checkboxRow}>
              <div className={styles.checkbox} />
            </div>
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

        <div className={styles.listWrap}>
          {!hasTx ? (
            <div className={styles.emptyTop}>No transactions yet. Add one from the sidebar.</div>
          ) : filtered.length === 0 ? (
            <div className={styles.noResults}>No results found.</div>
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
