"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./addTransactionModal.module.css";
import { useTransactions } from "@/context/TransactionsContext";
import { Transaction } from "@/types/transaction";

type Props = {
  open: boolean;
  onClose: () => void;
};

const TIMEZONES = [
  { label: "US Pacific (−08:00)", value: "-08:00" },
  { label: "US Mountain (−07:00)", value: "-07:00" },
  { label: "US Central (−06:00)", value: "-06:00" },
  { label: "US Eastern (−05:00)", value: "-05:00" },
  { label: "UTC (+00:00)", value: "+00:00" },
];

const CHANNELS: Transaction["channel"][] = ["card", "ach", "wire", "wallet", "cash"];

const CATEGORIES = [
  "Other",
  "Groceries",
  "Dining",
  "Gas",
  "Retail",
  "Electronics",
  "Entertainment",
  "Travel",
  "Hotels",
  "Transport",
  "Healthcare",
  "Pharmacy",
  "Subscriptions",
  "Utilities",
  "Rent/Mortgage",
  "Insurance",
  "Education",
  "Gifts/Donations",
  "ATM/Cash",
  "Fees/Charges",
];

function isValidTimeHHMMSS(s: string) {
  // Accept exactly HH:MM:SS (24h)
  if (!/^\d{2}:\d{2}:\d{2}$/.test(s)) return false;
  const [hh, mm, ss] = s.split(":").map((x) => Number(x));
  if ([hh, mm, ss].some((n) => Number.isNaN(n))) return false;
  return hh >= 0 && hh <= 23 && mm >= 0 && mm <= 59 && ss >= 0 && ss <= 59;
}

function buildIsoTimestamp(dateYYYYMMDD: string, timeHHMMSS: string, tzOffset: string) {
  // date: "2026-01-14"
  // time: "21:32:00"
  // tz: "-06:00"
  return `${dateYYYYMMDD}T${timeHHMMSS}${tzOffset}`;
}

export default function AddTransactionModal({ open, onClose }: Props) {
  const { addTransaction } = useTransactions();

  const [amount, setAmount] = useState<string>("");
  const [merchant, setMerchant] = useState<string>("");
  const [location, setLocation] = useState<string>("");
  const [channel, setChannel] = useState<Transaction["channel"]>("card");
  const [category, setCategory] = useState<string>("Other");
  const [userId, setUserId] = useState<string>("demo_user");

  // Date + time + tz controls
  const [date, setDate] = useState<string>(() => {
    // default to today in local date format YYYY-MM-DD
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  });
  const [time, setTime] = useState<string>("12:00:00");
  const [tz, setTz] = useState<string>("-06:00");

  // Reset form when opening
  useEffect(() => {
    if (!open) return;
    setAmount("");
    setMerchant("");
    setLocation("");
    setChannel("card");
    setCategory("Other");
    setUserId("demo_user");

    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    setDate(`${yyyy}-${mm}-${dd}`);
    setTime("12:00:00");
    setTz("-06:00");
  }, [open]);

  const errors = useMemo(() => {
    const e: string[] = [];

    const amt = Number(amount);
    if (!amount.trim()) e.push("Amount is required.");
    else if (!Number.isFinite(amt)) e.push("Amount must be a number.");
    else if (amt <= 0) e.push("Amount must be greater than 0.");

    if (!merchant.trim()) e.push("Merchant is required.");
    if (!location.trim()) e.push("Location is required.");
    if (!userId.trim()) e.push("User ID is required.");

    if (!date.trim()) e.push("Date is required.");
    // basic YYYY-MM-DD check
    if (date.trim() && !/^\d{4}-\d{2}-\d{2}$/.test(date.trim())) e.push("Date must be YYYY-MM-DD.");

    if (!time.trim()) e.push("Time is required.");
    else if (!isValidTimeHHMMSS(time.trim())) e.push("Time must be HH:MM:SS in 24-hour format.");

    if (!tz.trim() || !/^[+-]\d{2}:\d{2}$/.test(tz.trim())) e.push("Timezone must be an offset like -06:00.");

    return e;
  }, [amount, merchant, location, userId, date, time, tz]);

  const canSubmit = errors.length === 0;

  const onSubmit = (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!canSubmit) return;

    const iso = buildIsoTimestamp(date.trim(), time.trim(), tz.trim());

    addTransaction({
      userId: userId.trim(),
      amount: Number(amount),
      merchant: merchant.trim(),
      location: location.trim(),
      channel,
      category: category.trim() || "Other",
      timestamp: iso,
    });

    onClose();
  };

  if (!open) return null;

  return (
    <div className={styles.backdrop} onClick={onClose} role="presentation">
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-label="Add Transaction"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.header}>
          <h2 className={styles.title}>Add Transaction</h2>
          <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className={styles.body}>
          <form className={styles.form} onSubmit={onSubmit}>
            <div className={styles.row}>
              <label className={styles.label}>Amount</label>
              <input
                className={styles.input}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="47.91"
                inputMode="decimal"
              />
            </div>

            <div className={styles.row}>
              <label className={styles.label}>Merchant</label>
              <input
                className={styles.input}
                value={merchant}
                onChange={(e) => setMerchant(e.target.value)}
                placeholder="Target"
              />
            </div>

            <div className={styles.row}>
              <label className={styles.label}>Location</label>
              <input
                className={styles.input}
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Providence, RI  (or 41.88,-87.62)"
              />
              <div className={styles.helper}>
                Tip: distance only works automatically if you enter <b>lat,lon</b>. You can upgrade city mapping later.
              </div>
            </div>

            <div className={styles.row}>
              <label className={styles.label}>Payment Channel</label>
              <select className={styles.select} value={channel} onChange={(e) => setChannel(e.target.value as any)}>
                {CHANNELS.map((c) => (
                  <option key={c} value={c}>
                    {c.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>

            <div className={styles.row}>
              <label className={styles.label}>Category</label>
              <select className={styles.select} value={category} onChange={(e) => setCategory(e.target.value)}>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            <div className={styles.row}>
              <label className={styles.label}>User ID (temp)</label>
              <input
                className={styles.input}
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder="demo_user"
              />
            </div>

            <div className={styles.row}>
              <label className={styles.label}>Date</label>
              <input className={styles.input} type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>

            <div className={styles.row}>
              <label className={styles.label}>Time (HH:MM:SS)</label>
              <input
                className={styles.input}
                value={time}
                onChange={(e) => setTime(e.target.value)}
                placeholder="21:32:00"
              />
              <div className={styles.helper}>24-hour format, down to seconds.</div>
            </div>

            <div className={styles.row}>
              <label className={styles.label}>Timezone</label>
              <select className={styles.select} value={tz} onChange={(e) => setTz(e.target.value)}>
                {TIMEZONES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>

            {errors.length > 0 && (
              <div className={styles.errors} role="alert">
                <p className={styles.errorsTitle}>Fix these before submitting:</p>
                <ul className={styles.errorList}>
                  {errors.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className={styles.footer}>
              <button type="button" className={styles.btn} onClick={onClose}>
                Cancel
              </button>
              <button
                type="submit"
                className={[styles.btn, styles.btnPrimary, !canSubmit ? styles.btnDisabled : ""].join(" ")}
                disabled={!canSubmit}
              >
                Add
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
