import { useEffect } from "react";
import { useInterview } from "../contexts/InterviewContext";
import QuestionCard from "../components/QuestionCard";
import { useNavigate } from "react-router-dom";

export default function InterviewPage() {
  const { state } = useInterview();
  const nav = useNavigate();

  useEffect(() => {
    if (state.step !== 1) nav("/");
  }, [state.step, nav]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <QuestionCard />
    </div>
  );
}