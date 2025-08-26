import { useState, useRef, useEffect } from "react";
import { useInterview } from "../contexts/InterviewContext";

const BACKEND = "http://localhost:8000";

export default function QuestionCard() {
  const { state } = useInterview();
  const [question, setQuestion]   = useState("");
  const [advisor, setAdvisor]     = useState("");
  const [history, setHistory]     = useState<{q:string;a:string;advisor:string}[]>([]);
  const [recording, setRecording] = useState(false);
  const synth = useRef<SpeechSynthesis | null>(null);
  const rec   = useRef<SpeechRecognition | null>(null);

  /* --- helpers --- */
  function speak(text: string, onEnd?: () => void) {
  if (!synth.current) synth.current = window.speechSynthesis;
  synth.current.cancel();                 // stop previous speech
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en-US";
  u.onend = onEnd;
  synth.current.speak(u);
}

  /* --- fetch next --- */
  async function nextStep(answer?: string) {
    const body = { job: state.job, cv: state.cv, history: history };    if (answer) body.history = [...history, { q: question, a: answer, advisor }];
    const res  = await fetch(BACKEND + "/step", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body) });
    const { text, advisor: a } = await res.json();
    setQuestion(text);
    setAdvisor(a);
    speak(text);
  }

  /* --- first question after upload --- */
  useEffect(() => {
  if (state.current) speak(state.current);
}, [state.current]);

  /* --- record answer --- */
  function recordAnswer() {
    setRecording(true);
    rec.current = new (window as any).webkitSpeechRecognition();
    rec.current.lang = "en-US";
    rec.current.continuous = false;
    rec.current.onresult = (e) => {
      const text = e.results[0][0].transcript;
      nextStep(text);
    };
    rec.current.onend = () => setRecording(false);
    rec.current.start();
  }

  return (
    <div className="w-full max-w-lg p-6 space-y-4 rounded bg-slate-800">
      <h2 className="text-xl">{question}</h2>
      {advisor && (
        <>
          <p className="font-bold text-green-400 mt-2">Advisor:</p>
          <p className="text-white">{advisor}</p>
        </>
      )}

      <button onClick={recordAnswer} disabled={recording}
        className={`w-full py-2 rounded ${recording ? "bg-red-600" : "bg-sky-600"}`}>
        {recording ? "Listening…" : "Answer"}
      </button>

      <button onClick={() => nextStep()} className="w-full py-2 rounded bg-slate-600">
        Next Question
      </button>
    </div>
  );
}