export type VelocityLevel = "low" | "medium" | "high";


export type TxReason = {
  feature: string;
  impact: number;
  note: string;
};

export type Transaction = {
  id: string;
  userId: string;
  createdAt: string; // ISO timestamp
  amount: number;
  merchant: string;
  location: string;
  channel: "card" | "ach" | "wire" | "wallet" | "cash";

  // NEW
  category: string;

  // scoring outputs
  riskScore: number;
  velocity: number;
  reasons: TxReason[];
};



