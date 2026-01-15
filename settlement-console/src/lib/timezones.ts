// src/lib/timezones.ts

export type TimezoneOption = {
  label: string;  // user-friendly
  value: string;  // ISO suffix: "Z" or "-06:00"
};

// You can add more later. Keep it small and relevant.
export const TIMEZONES: TimezoneOption[] = [
  { label: "Local (America/Chicago)  -06:00", value: "-06:00" },
  { label: "UTC (Z)", value: "Z" },
  { label: "America/New_York        -05:00", value: "-05:00" },
  { label: "America/Los_Angeles     -08:00", value: "-08:00" },
  { label: "Europe/London           +00:00", value: "+00:00" },
  { label: "Asia/Tokyo              +09:00", value: "+09:00" },
  { label: "Asia/Seoul              +09:00", value: "+09:00" },
];
