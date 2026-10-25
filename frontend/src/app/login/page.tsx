import { Suspense } from "react";
import type { Metadata } from "next";
import { LoginView } from "@/features/auth/LoginView";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  // LoginView uses useSearchParams() to read ?error= from the OAuth callback.
  // Next.js requires a Suspense boundary around any component that calls
  // useSearchParams() to avoid a prerender error during static generation.
  return (
    <Suspense fallback={<div className="login" />}>
      <LoginView />
    </Suspense>
  );
}
