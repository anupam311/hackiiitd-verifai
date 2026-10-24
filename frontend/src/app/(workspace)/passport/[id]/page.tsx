"use client";

import { PassportView } from "@/features/passport/PassportView";

export default function PassportPage({ params }: { params: { id: string } }) {
  return <PassportView id={decodeURIComponent(params.id)} />;
}
