import axios from "axios";
export default async function sendFeedback(text: string) {
  const form = new URLSearchParams({ text });
  const { data } = await axios.post("http://localhost:8000/feedback", form);
  return data as { interviewer: string; advisor: string };
}