# test_server.py - Simple version for debugging
import os
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PyPDF2 import PdfReader
import io

app = FastAPI(title="Test Interview Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + " "
        return text.strip()
    except Exception as e:
        raise Exception(f"Error reading PDF: {str(e)}")

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/upload")
async def upload_cv(file: UploadFile = File(...), job: str = Form("")):
    """Simple upload endpoint for testing."""
    try:
        print(f"Received file: {file.filename}")
        print(f"Content type: {file.content_type}")
        print(f"Job length: {len(job)}")
        
        # Basic validation
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
            
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files supported")
        
        if not job.strip():
            raise HTTPException(status_code=400, detail="Job description required")
        
        # Read and process PDF
        print("Reading PDF content...")
        pdf_content = await file.read()
        print(f"PDF size: {len(pdf_content)} bytes")
        
        print("Extracting text...")
        cv_text = extract_text_from_pdf(pdf_content)
        print(f"Extracted {len(cv_text)} characters")
        
        if len(cv_text) < 10:
            raise HTTPException(status_code=400, detail="Could not extract meaningful text from PDF")
        
        # Return simple response without AI
        return {
            "question": "Thank you for uploading your CV! Can you tell me a bit about yourself?",
            "advisor_tip": "Keep your answer concise and highlight your key strengths.",
            "cv": cv_text,
            "job": job,
            "phase": "introduction",
            "topic": "introduction"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in upload: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.post("/step")
async def simple_step(request: dict):
    """Simple step endpoint for testing."""
    try:
        print(f"Received step request: {request}")
        
        return {
            "question": "That's interesting. Can you tell me more about your experience with that?",
            "advisor_tip": "Provide specific examples and quantify your achievements.",
            "phase": "experience", 
            "topic": "general_experience",
            "is_followup": False,
            "is_completed": False
        }
        
    except Exception as e:
        print(f"Error in step: {str(e)}")
        return {
            "question": "What would you like to discuss next?",
            "advisor_tip": "Feel free to share any relevant experience.",
            "phase": "general",
            "topic": None,
            "is_followup": False,
            "is_completed": False
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)