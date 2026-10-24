import { HelpCircle } from "lucide-react";

export function UnresolvedList({ questions }: { questions: string[] }) {
  if (questions.length === 0) {
    return <p className="muted small">No unresolved questions were recorded for this report. That does not guarantee that nothing is missing — confirm critical details on the official page.</p>;
  }
  return (
    <ul className="unresolved">
      {questions.map((q) => (
        <li key={q}>
          <HelpCircle size={15} aria-hidden />
          <span>{q}</span>
        </li>
      ))}
    </ul>
  );
}
