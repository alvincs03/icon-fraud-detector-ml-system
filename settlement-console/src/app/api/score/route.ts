import { NextResponse } from "next/server";

const ML_BASE_URL = process.env.ML_BASE_URL ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  const body = await req.json();

  try {
    const resp = await fetch(`${ML_BASE_URL}/score`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(8000),
      cache: "no-store",
    });

    const text = await resp.text();

    let data: any = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        return NextResponse.json(
          { error: "ML returned non-JSON", status: resp.status, body: text },
          { status: 502 }
        );
      }
    }

    return NextResponse.json(data, { status: resp.status });
  } catch (err: any) {
    return NextResponse.json(
      {
        error: "Failed to reach ML service",
        detail: err?.message ?? String(err),
        target: `${ML_BASE_URL}/score`,
      },
      { status: 502 }
    );
  }
}

