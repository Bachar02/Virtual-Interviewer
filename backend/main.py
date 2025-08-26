import os, io, json, asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PyPDF2 import PdfReader
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor()

def extract_text(pdf: bytes) -> str:
    return " ".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)

@app.post("/upload")
async def upload(file: UploadFile = File(...), job: str = Form("")):
    cv_text = extract_text(await file.read())
    prompt = f"Job: {job}\nCV: {cv_text}\n\nGenerate ONE starter interview question."
    question = model.generate_content(prompt).text.strip()
    return {"question": question, "cv": cv_text, "job": job}

@app.post("/step")
async def step(payload: dict):
    job   = payload.get("job", "")
    cv    = payload.get("cv", "")
    hist  = payload.get("history", [])
    last  = hist[-1].get("answer", "") if hist else ""
    turns_on_topic = len([h for h in hist if h["q"].startswith("Tell me more")])
    prompt = (
        f"Job: {job}\nCV: {cv}\n\n"
        f"History (turns on this topic = {turns_on_topic}):\n{json.dumps(hist)}\n\n"
        f"Last answer: {last}\n\n"
        "Rule:\n"
        "- If turns_on_topic >= 1 → close topic with short wrap-up and ask ONE brand-new question.\n"
        "- Otherwise ask ONE deeper follow-up on the same topic.\n"
        "Return JSON: {'text':'<question or closing>', 'advisor':'<tip>'}"
    )
    try:
        raw = await asyncio.get_event_loop().run_in_executor(
            executor, lambda: model.generate_content(prompt).text.strip()
        )
        return json.loads(raw)
    except Exception:
        return {"text": "Tell me more about yourself.", "advisor": "Stay concise."}