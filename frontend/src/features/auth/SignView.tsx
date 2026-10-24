
"use client";

import Link from "next/link";
import { useState } from "react";
import { LogoMark } from "@/components/layout/Logo";
import { Notice } from "@/components/ui/States";

export function SignupView() {
  const [message, setMessage] = useState("");

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(
      "Account creation is not connected yet. Please use the demo or connect the authentication backend."
    );
  }

  return (
    <div className="login">
      <aside className="login-brand">
        <LogoMark size={44} />
        <h1>VERIFAI</h1>
        <p className="login-tag">Don’t just find it. Verify it.</p>
        <p className="muted-light">
          Create your account to organise opportunities,
          manage your profile, and keep track of verification.
        </p>
      </aside>

      <main className="login-card" id="main">
        <h2>Create your account</h2>
        <p className="muted">
          Join VERIFAI and keep your opportunities organised.
        </p>

        {message && (
          <Notice tone="info" title="Sign up unavailable">
            {message}
          </Notice>
        )}

        <form className="stack" onSubmit={handleSubmit}>
          <label className="field">
            <span className="label">Full name</span>
            <input
              className="input"
              name="name"
              type="text"
              placeholder="Your full name"
              autoComplete="name"
              required
            />
          </label>

          <label className="field">
            <span className="label">Email address</span>
            <input
              className="input"
              name="email"
              type="email"
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
          </label>

          <label className="field">
            <span className="label">Password</span>
            <input
              className="input"
              name="password"
              type="password"
              placeholder="Create a password"
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>

          <button className="btn btn-primary" type="submit">
            Create account
          </button>
        </form>

        <p className="small muted">
          Account creation is a preview until authentication is connected.
          Your details are not submitted or stored.
        </p>

        <p className="small">
          Already have an account?{" "}
          <Link href="/login">Sign in</Link>
        </p>

        <Link href="/explore" className="btn btn-ghost">
          Continue without signing in
        </Link>
      </main>
    </div>
  );
}
