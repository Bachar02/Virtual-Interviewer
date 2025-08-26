import axios from "axios";
export default async function sendFeedback(text: string) {
  const { data } = await axios.post("http://127.0.0.1:8000/feedback", { text });
  return data.feedback as string;
}