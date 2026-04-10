import { NextResponse } from "next/server";

export async function GET() {
  const backendUrl = process.env.CARE_BACKEND_URL ?? "http://localhost:9010";

  try {
    const response = await fetch(`${backendUrl}/health`, { cache: "no-store" });
    if (!response.ok) {
      return NextResponse.json(
        { status: "error", detail: `Backend devolvio HTTP ${response.status}` },
        { status: 502 }
      );
    }

    const body = (await response.json()) as { status?: string };
    return NextResponse.json({ status: body.status ?? "ok" });
  } catch (error: unknown) {
    return NextResponse.json(
      { status: "error", detail: String(error) },
      { status: 502 }
    );
  }
}
