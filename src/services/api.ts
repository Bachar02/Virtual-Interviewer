export async function uploadCv(form: FormData) {
  const res = await fetch("http://localhost:8000/upload", { 
    method: "POST", 
    body: form 
  });
  
  if (!res.ok) {
    throw new Error(`Upload failed: ${res.statusText}`);
  }
  
  return res.json();
}

export async function getNextQuestion(body: {
  job: string;
  cv: string;
  history: { question: string; answer: string; topic?: string; phase?: string }[];
}) {
  const res = await fetch("http://localhost:8000/step", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  
  if (!res.ok) {
    throw new Error(`API request failed: ${res.statusText}`);
  }
  
  return res.json();
}