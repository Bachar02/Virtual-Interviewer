import { useState } from "react";
import { useInterview } from "../contexts/InterviewContext";
import { uploadCv } from "../services/api";
import { useNavigate } from "react-router-dom";

export default function UploadPage() {
  const { dispatch } = useInterview();
  const nav = useNavigate();
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState("");

  async function handleFile() {
  if (!file || !job.trim()) return;
  setLoading(true);

  const form = new FormData();
  form.append("file", file);
  form.append("job", job);

  const res = await fetch("http://localhost:8000/upload", { method: "POST", body: form });
  const { question, cv, job: jobText } = await res.json();

  localStorage.setItem("job", jobText);
  localStorage.setItem("cv", cv); // **real text**
  dispatch({ type: "START", payload: { question, cv, job: jobText } });
  nav("/interview");
}

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="w-full max-w-md p-8 space-y-6 rounded bg-slate-800">
        <h1 className="text-3xl font-bold text-center">AI Interview Simulator</h1>
        <p className="text-center text-slate-400">
          Upload your résumé, get an instant voice mock interview.
        </p>

        <input
          type="file"
          accept=".pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-sky-600 file:text-white hover:file:bg-sky-700"
        />

        <textarea
          placeholder="Paste the job ad / role description here…"
          value={job}
          onChange={(e) => setJob(e.target.value)}
          className="w-full mt-4 p-2 rounded bg-slate-700"
          rows={3}
        />

        {loading ? (
          <div className="flex justify-center">
            <div className="w-8 h-8 border-4 border-slate-600 border-t-sky-400 rounded-full animate-spin"></div>
          </div>
        ) : (
          <button
            onClick={handleFile}
            disabled={!file || !job.trim()}
            className="w-full mt-2 py-2 bg-sky-600 rounded disabled:opacity-50"
          >
            Upload & Start
          </button>
        )}
      </div>
    </div>
  );
}