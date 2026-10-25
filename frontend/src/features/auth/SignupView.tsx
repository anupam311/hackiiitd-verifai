"use client";

import Link from "next/link";
import { Github } from "lucide-react";
import { LogoMark } from "@/components/layout/Logo";
import { Notice } from "@/components/ui/States";
import { authUrls } from "@/lib/api-client";
import { useApiHealth } from "@/hooks/useApiHealth";
import { useDemo } from "@/providers/DemoProvider";

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

/**
 * Sign-up page. Because VERIFAI uses OAuth-only registration,
 * sign-up and sign-in are the same flow: the backend creates a new
 * account automatically on the first successful OAuth callback
 * (find_or_create_user). No password is ever stored.
 */
export function SignupView() {
  const { demo } = useDemo();
  const health = useApiHealth(!demo);
  const disabled = demo || health === "down";

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
        <p className="login-tag">Don&apos;t just find it. Verify it.</p>
        <p className="muted-light">
          Create your account to save opportunities, manage your profile,
          and keep track of verification history across devices.
        </p>
      </aside>

      <main className="login-card" id="main">
        <h2>Create your account</h2>
        <p className="muted">
          Choose a provider below — your account is created automatically
          the first time you sign in. No password needed.
        </p>

        <div className="stack">
          {demo && (
            <Notice tone="info" title="Sample data is on">
              Sign-in is disabled in sample mode. Switch sample data off in
              the sidebar to use the real backend.
            </Notice>
          )}
          {!demo && health === "down" && (
            <Notice tone="warn" title="API unreachable">
              The VERIFAI API did not respond, so sign-up cannot start.
              Check that the backend is running.
            </Notice>
          )}

          {providerBtn(authUrls.google, "Sign up with Google", <GoogleMark />)}
          {providerBtn(authUrls.github, "Sign up with GitHub", <Github size={18} aria-hidden />)}

          <Link href="/explore" className="btn btn-ghost">
            Continue without an account
          </Link>
        </div>

        <details className="disclosure">
          <summary>How account creation works</summary>
          <div className="disclosure-body small">
            <p>
              VERIFAI uses OAuth &mdash; you sign in with Google or GitHub and we
              create your account automatically on the first sign-in.
              No email or password is collected or stored by VERIFAI.
            </p>
            <p>
              If you later sign in with a second provider that has the same
              <strong> verified</strong> email, both accounts are linked into one.
            </p>
            <p>
              You can log out at any time from the profile menu.
            </p>
          </div>
        </details>

        <p className="small muted" style={{ textAlign: "center", marginTop: "0.5rem" }}>
          Already have an account?{" "}
          <Link href="/login">Sign in</Link>
        </p>
      </main>
    </div>
  );
}
