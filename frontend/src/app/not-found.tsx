import Link from "next/link";

export default function NotFound() {
  return (
    <main className="page" style={{ maxWidth: 560, margin: "15vh auto", padding: 24 }}>
      <h1>Page not found</h1>
      <p className="muted">That page doesn’t exist.</p>
      <Link className="btn btn-primary" href="/explore">Back to Discover</Link>
    </main>
  );
}
