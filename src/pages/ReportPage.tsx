import { useInterview } from "../contexts/InterviewContext";

export default function ReportPage() {
  const { state, dispatch } = useInterview();

  function download() {
    const blob = new Blob([JSON.stringify(state.answers, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "interview-report.json";
    a.click();
  }

  return (
    <div className="max-w-3xl mx-auto p-8 space-y-6">
      <h1 className="text-3xl font-bold">Your Interview Report</h1>
      {state.answers.map((a, i) => (
        <div key={i} className="p-4 rounded bg-slate-800 space-y-2">
          <p className="font-bold">{a.q}</p>
          <p className="text-slate-300">{a.a}</p>
          <p className="text-sm text-green-400">Feedback: {a.f}</p>
        </div>
      ))}
      <div className="flex gap-4">
        <button onClick={download} className="btn bg-sky-600">
          Download Report
        </button>
        <button onClick={() => dispatch({ type: "RESET" })} className="btn bg-slate-600">
          Restart
        </button>
      </div>
    </div>
  );
}