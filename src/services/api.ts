const BASE = "http://localhost:8000";

export async function uploadCv(form: FormData) {
  const res = await fetch("http://localhost:8000/upload", { method: "POST", body: form });
  return res.json() as Promise<{ questions: string[] }>;
}