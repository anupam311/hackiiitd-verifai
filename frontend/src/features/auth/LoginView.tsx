"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Github, LogOut } from "lucide-react";
import { LogoMark } from "@/components/layout/Logo";
import { Notice } from "@/components/ui/States";
import { Button, LinkButton } from "@/components/ui/Button";
import { authUrls } from "@/lib/api-client";
import { useApiHealth } from "@/hooks/useApiHealth";
import { useDemo } from "@/providers/DemoProvider";
import { useSession } from "./SessionProvider";

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden focusable="false">
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.4 5.7c4.3-4 6.8-9.9 6.8-17.4z" />
      <path fill="#FBBC05" d="M10.5 28.7A14.5 14.5 0 0 1 9.5 24c0-1.6.3-3.2.9-4.7l-7.9-6.1A24 24 0 0 0 0 24c0 3.9.9 7.5 2.6 10.8l7.9-6.1z" />
      <path fill="#34A853" d="M24 48c6.3 0 11.7-2.1 15.6-5.7l-7.4-5.7c-2.1 1.4-4.8 2.3-8.2 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z" />
    </svg>
  );
}

export function LoginView() {
  const { demo } = useDemo();
  const { user, status, logout } = useSession();
  const health = useApiHealth(!demo);
  const disabled = demo || health === "down";
  const params = useSearchParams();
  const authError = params.get("error");

  const errorMessages: Record<string, string> = {
    invalid_state: "The sign-in session expired or was opened in a different browser tab. Please try again.",
    access_denied: "You cancelled the sign-in. Try again whenever you're ready.",
    oauth_failed: "Something went wrong with the sign-in provider. Please try again.",
  };

  const providerBtn = (href: string, label: string, icon: React.ReactNode) =>
    disabled ? (
      <button className="btn btn-secondary provider-btn" disabled>{icon} {label}</button>
    ) : (
      <a className="btn btn-secondary provider-btn" href={href}>{icon} {label}</a>
    );

  return (
    <div className="login">
      <aside className="login-brand">
        <LogoMark size={44} />
        <h1>VERIFAI</h1>
        <p className="login-tag">Don’t just find it. Verify it.</p>
        <p className="muted-light">Opportunities, claim by claim, with the evidence beside every answer.</p>
      </aside>
      <main className="login-card" id="main">
        <h2>Sign in</h2>
        <p className="muted">Sign in to sync saved opportunities, your profile and recheck history across devices.</p>

        {status === "authenticated" && !demo && user ? (
          <div className="stack">
            <Notice tone="success" title={`Signed in as ${user.displayName}`}>{user.email ?? "No email on file."}</Notice>
            <LinkButton href="/explore" variant="primary">Continue to Discover</LinkButton>
            <Button icon={<LogOut size={15} aria-hidden />} onClick={() => logout()}>Log out</Button>
          </div>
        ) : (
          <div className="stack">
            {authError && (
              <Notice tone="warn" title="Sign-in failed">
                {errorMessages[authError] ?? "An unexpected error occurred. Please try again."}
              </Notice>
            )}
            {demo && <Notice tone="info" title="Sample data is on">Sign-in is disabled in sample mode. Switch sample data off in the sidebar to use the real backend.</Notice>}
            {!demo && health === "down" && <Notice tone="warn" title="API unreachable">The VERIFAI API did not respond, so sign-in cannot start. Check that the backend is running.</Notice>}
            {providerBtn(authUrls.google, "Continue with Google", <GoogleMark />)}
            {providerBtn(authUrls.github, "Continue with GitHub", <Github size={18} aria-hidden />)}
            <Link href="/explore" className="btn btn-ghost">Continue without signing in</Link>
            <p className="small muted" style={{ textAlign: "center" }}>
              New here?{" "}
              <Link href="/signup">Create your account</Link>
            </p>
          </div>
        )}

        <details className="disclosure">
          <summary>How sign-in and account linking work</summary>
          <div className="disclosure-body small">
            <p>Sign-in happens on the VERIFAI server; your browser never receives provider tokens or secrets. A secure, HttpOnly session cookie keeps you signed in.</p>
            <p>If you use both providers, accounts are linked only when both report the same <b>verified</b> email. GitHub emails can be private or unverified; in that case linking requires signing in and linking deliberately.</p>
            <p>You can log out at any time from the profile menu.</p>
            <p className="muted">Sign-in works only once the backend has provider credentials configured.</p>
          </div>
        </details>
      </main>
    </div>
  );
}
