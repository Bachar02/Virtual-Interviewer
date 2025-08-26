export default function ReportCard({ q, a, f }: { q: string; a: string; f: string }) {
  return (
    <div className="p-4 rounded bg-slate-800 space-y-2">
      <p className="font-bold">{q}</p>
      <p className="text-slate-300">{a}</p>
      <p className="text-sm text-green-400">Feedback: {f}</p>
    </div>
  );
}