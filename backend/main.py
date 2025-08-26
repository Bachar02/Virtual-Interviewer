import os, io, json, asyncio, re
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from PyPDF2 import PdfReader
import google.generativeai as genai

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

app = FastAPI(title="Virtual Interviewer", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor()

# Pydantic models for request validation
class HistoryItem(BaseModel):
    question: str
    answer: str
    topic: Optional[str] = None
    phase: Optional[str] = "general"

class StepRequest(BaseModel):
    job: str
    cv: str
    history: List[HistoryItem] = []

class InterviewResponse(BaseModel):
    question: str
    advisor_tip: str
    phase: str
    topic: Optional[str] = None
    is_followup: bool = False

# Interview phases and their characteristics
INTERVIEW_PHASES = {
    "introduction": {
        "max_questions": 2,
        "focus": "Getting to know the candidate and their background"
    },
    "experience": {
        "max_questions": 4,
        "focus": "Work experience and achievements"
    },
    "technical": {
        "max_questions": 3,
        "focus": "Technical skills and problem-solving"
    },
    "behavioral": {
        "max_questions": 3,
        "focus": "Behavioral and situational questions"
    },
    "closing": {
        "max_questions": 2,
        "focus": "Final questions and wrap-up"
    }
}

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF with better error handling."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + " "
        return text.strip()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading PDF: {str(e)}")

def analyze_interview_state(history: List[HistoryItem]) -> Dict:
    """Analyze current interview state to determine next action."""
    if not history:
        return {
            "current_phase": "introduction",
            "questions_in_phase": 0,
            "current_topic": None,
            "followup_count": 0,
            "should_change_topic": False,
            "should_change_phase": False
        }
    
    # Get current phase from last question or default to introduction
    current_phase = history[-1].phase if history[-1].phase else "introduction"
    
    # Count questions in current phase
    questions_in_phase = len([h for h in history if h.phase == current_phase])
    
    # Get current topic and count followups
    current_topic = history[-1].topic if history[-1].topic else None
    followup_count = 0
    
    # Count consecutive questions on the same topic
    for item in reversed(history):
        if item.topic == current_topic and current_topic:
            followup_count += 1
        else:
            break
    
    # Determine if we should change topic/phase
    max_questions_in_phase = INTERVIEW_PHASES.get(current_phase, {}).get("max_questions", 3)
    should_change_phase = questions_in_phase >= max_questions_in_phase
    should_change_topic = followup_count >= 2  # Max 2 followups per topic
    
    return {
        "current_phase": current_phase,
        "questions_in_phase": questions_in_phase,
        "current_topic": current_topic,
        "followup_count": followup_count,
        "should_change_topic": should_change_topic,
        "should_change_phase": should_change_phase
    }

def get_next_phase(current_phase: str) -> str:
    """Get the next interview phase."""
    phases = list(INTERVIEW_PHASES.keys())
    try:
        current_index = phases.index(current_phase)
        return phases[min(current_index + 1, len(phases) - 1)]
    except ValueError:
        return "introduction"

def clean_json_response(response_text: str) -> Dict:
    """Clean and parse JSON response from AI."""
    try:
        # Try to find JSON in the response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            return json.loads(json_str)
        else:
            # Fallback if no JSON found
            return {
                "question": response_text.strip(),
                "advisor_tip": "Focus on providing specific examples.",
                "topic": None
            }
    except json.JSONDecodeError:
        return {
            "question": "Can you tell me more about your experience?",
            "advisor_tip": "Provide specific examples with measurable results.",
            "topic": "experience"
        }

async def generate_question(job: str, cv: str, history: List[HistoryItem], state: Dict) -> InterviewResponse:
    """Generate the next interview question based on current state."""
    
    # Determine the action based on state
    if state["should_change_phase"]:
        next_phase = get_next_phase(state["current_phase"])
        action = "new_phase"
        target_phase = next_phase
    elif state["should_change_topic"]:
        action = "new_topic"
        target_phase = state["current_phase"]
    else:
        action = "followup"
        target_phase = state["current_phase"]
    
    # Build prompt based on action
    phase_info = INTERVIEW_PHASES.get(target_phase, {})
    
    if action == "new_phase":
        prompt = f"""
Job Description: {job}
CV/Resume: {cv}

INTERVIEW STATE:
- Moving to NEW PHASE: {target_phase}
- Phase Focus: {phase_info.get('focus', '')}
- Questions asked so far: {len(history)}

CONVERSATION HISTORY:
{json.dumps([{"q": h.question, "a": h.answer} for h in history], ensure_ascii=False, indent=2)}

INSTRUCTIONS:
Generate a question appropriate for the {target_phase} phase of the interview.
Focus on: {phase_info.get('focus', '')}

Return ONLY valid JSON:
{{
    "question": "<your question here>",
    "advisor_tip": "<helpful tip for the candidate>",
    "topic": "<main topic/skill being discussed>"
}}
"""
    
    elif action == "new_topic":
        prompt = f"""
Job Description: {job}
CV/Resume: {cv}

INTERVIEW STATE:
- Current Phase: {target_phase}
- Phase Focus: {phase_info.get('focus', '')}
- Current Topic: {state['current_topic']} (changing to new topic)

LAST ANSWER: {history[-1].answer if history else ""}

INSTRUCTIONS:
Generate a NEW question on a DIFFERENT topic within the {target_phase} phase.
Avoid repeating the current topic: {state['current_topic']}

Return ONLY valid JSON:
{{
    "question": "<your question here>",
    "advisor_tip": "<helpful tip for the candidate>",
    "topic": "<new topic/skill being discussed>"
}}
"""
    
    else:  # followup
        prompt = f"""
Job Description: {job}
CV/Resume: {cv}

INTERVIEW STATE:
- Current Phase: {target_phase}
- Current Topic: {state['current_topic']}
- This is a FOLLOWUP question

LAST ANSWER: {history[-1].answer if history else ""}

INSTRUCTIONS:
Generate a deeper FOLLOWUP question about the same topic: {state['current_topic']}
Ask for more details, examples, or clarification.

Return ONLY valid JSON:
{{
    "question": "<your followup question here>",
    "advisor_tip": "<helpful tip for the candidate>",
    "topic": "{state['current_topic']}"
}}
"""

    try:
        # Generate response
        response = await asyncio.get_event_loop().run_in_executor(
            executor, 
            lambda: model.generate_content(prompt).text.strip()
        )
        
        # Parse response
        result = clean_json_response(response)
        
        return InterviewResponse(
            question=result.get("question", "Tell me about yourself."),
            advisor_tip=result.get("advisor_tip", "Be specific and provide examples."),
            phase=target_phase,
            topic=result.get("topic"),
            is_followup=(action == "followup")
        )
        
    except Exception as e:
        # Fallback response
        return InterviewResponse(
            question="Can you elaborate on that?",
            advisor_tip="Provide specific examples with measurable results.",
            phase=target_phase,
            topic=state.get("current_topic"),
            is_followup=True
        )

@app.post("/upload")
async def upload_cv(file: UploadFile = File(...), job: str = Form("")):
    """Upload CV and get initial interview question."""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    if not job.strip():
        raise HTTPException(status_code=400, detail="Job description is required")
    
    try:
        # Extract text from PDF
        pdf_content = await file.read()
        cv_text = extract_text_from_pdf(pdf_content)
        
        if not cv_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from PDF")
        
        # Generate initial question
        prompt = f"""
Job Description: {job}
CV/Resume: {cv_text}

Generate an opening interview question to start the conversation.
This should be a warm, welcoming question that helps the candidate feel comfortable.

Return ONLY valid JSON:
{{
    "question": "<your opening question>",
    "advisor_tip": "<helpful tip for the candidate>",
    "topic": "introduction"
}}
"""
        
        response = await asyncio.get_event_loop().run_in_executor(
            executor, 
            lambda: model.generate_content(prompt).text.strip()
        )
        
        result = clean_json_response(response)
        
        return {
            "question": result.get("question", "Thank you for your interest! Can you start by telling me a bit about yourself?"),
            "advisor_tip": result.get("advisor_tip", "Keep it concise and highlight your key strengths."),
            "cv": cv_text,
            "job": job,
            "phase": "introduction",
            "topic": result.get("topic", "introduction")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing upload: {str(e)}")

@app.post("/step")
async def interview_step(request: StepRequest):
    """Generate next interview question based on conversation history."""
    try:
        # Analyze current interview state
        state = analyze_interview_state(request.history)
        
        # Generate next question
        response = await generate_question(
            request.job, 
            request.cv, 
            request.history, 
            state
        )
        
        return {
            "question": response.question,
            "advisor_tip": response.advisor_tip,
            "phase": response.phase,
            "topic": response.topic,
            "is_followup": response.is_followup,
            "interview_progress": {
                "current_phase": response.phase,
                "questions_asked": len(request.history),
                "phase_progress": f"{state['questions_in_phase']}/{INTERVIEW_PHASES.get(response.phase, {}).get('max_questions', 3)}"
            }
        }
        
    except Exception as e:
        # Fallback response
        return {
            "question": "Is there anything else you'd like to share about your experience?",
            "advisor_tip": "Feel free to elaborate on any relevant experiences.",
            "phase": "general",
            "topic": None,
            "is_followup": False,
            "interview_progress": {
                "current_phase": "general",
                "questions_asked": len(request.history),
                "phase_progress": "unknown"
            }
        }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "Virtual Interviewer API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)