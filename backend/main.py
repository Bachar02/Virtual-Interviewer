import os, io, json, asyncio, re
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from PyPDF2 import PdfReader

# Try to import and configure Gemini
try:
    import google.generativeai as genai
    from dotenv import load_dotenv
    
    # Load environment variables from .env file
    load_dotenv()
    
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        GEMINI_AVAILABLE = True
        print("✅ Gemini API configured successfully")
    else:
        GEMINI_AVAILABLE = False
        print("⚠️  GEMINI_API_KEY not found. Running in fallback mode.")
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️  google-generativeai not installed. Running in fallback mode.")

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
            "should_change_phase": False,
            "should_end_interview": False,
            "total_questions": 0,
            "recent_questions": [],
            "last_answer_length": 0
        }
    
    # Get current phase from last question or default to introduction
    current_phase = history[-1].phase if history[-1].phase else "introduction"
    
    # Count questions in current phase
    questions_in_phase = len([h for h in history if h.phase == current_phase])
    
    # Count total questions asked
    total_questions = len(history)
    
    # Get current topic and count followups
    current_topic = history[-1].topic if history[-1].topic else None
    followup_count = 0
    
    # Count consecutive questions on the same topic
    for item in reversed(history):
        if item.topic == current_topic and current_topic:
            followup_count += 1
        else:
            break
    
    # Get recent questions to avoid repetition
    recent_questions = [h.question.lower() for h in history[-3:]]
    
    # Check if we're repeating the same question
    last_question = history[-1].question.lower() if history else ""
    is_repetitive = recent_questions.count(last_question) > 1
    
    # Get last answer length to gauge engagement
    last_answer_length = len(history[-1].answer.split()) if history and history[-1].answer else 0
    
    # Determine if we should end the interview
    should_end_interview = (
        current_phase == "closing" and questions_in_phase >= 2
    ) or total_questions >= 15  # Maximum interview length
    
    # Determine if we should change topic/phase
    max_questions_in_phase = INTERVIEW_PHASES.get(current_phase, {}).get("max_questions", 3)
    should_change_phase = questions_in_phase >= max_questions_in_phase and not should_end_interview
    
    # Enhanced topic change logic
    should_change_topic = (
        followup_count >= 3 or  # Max 3 followups per topic
        is_repetitive or  # Avoid repetitive questions
        (followup_count >= 2 and last_answer_length <= 5)  # Move on if getting very short answers
    )
    
    return {
        "current_phase": current_phase,
        "questions_in_phase": questions_in_phase,
        "current_topic": current_topic,
        "followup_count": followup_count,
        "should_change_topic": should_change_topic,
        "should_change_phase": should_change_phase,
        "should_end_interview": should_end_interview,
        "total_questions": total_questions,
        "recent_questions": recent_questions,
        "last_answer_length": last_answer_length,
        "is_repetitive": is_repetitive
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

def get_fallback_question(phase: str, history: List[HistoryItem], cv_text: str = "") -> Dict:
    """Generate fallback questions when Gemini is not available."""
    
    question_bank = {
        "introduction": [
            "Thank you for your time today! Can you start by telling me about yourself and what interests you about this position?",
            "What initially sparked your interest in this field?",
            "How would you describe your professional journey so far?"
        ],
        "experience": [
            "Can you walk me through one of your most significant projects?",
            "Tell me about a challenging problem you solved recently.",
            "What's an achievement you're particularly proud of?",
            "How do you typically approach learning new technologies?",
            "Can you describe your experience with [relevant technology from CV]?"
        ],
        "technical": [
            "How do you stay updated with the latest developments in your field?",
            "Can you explain a complex technical concept in simple terms?",
            "What's your approach to debugging or troubleshooting?",
            "Tell me about a time when you had to learn something completely new."
        ],
        "behavioral": [
            "Tell me about a time you worked in a team. What was your role?",
            "How do you handle tight deadlines and pressure?",
            "Describe a situation where you had to adapt to change.",
            "What motivates you in your work?"
        ],
        "closing": [
            "What questions do you have for us about the role or company?",
            "Where do you see yourself in the next few years?",
            "Is there anything else you'd like us to know about you?"
        ]
    }
    
    # Get questions for the phase
    questions = question_bank.get(phase, question_bank["experience"])
    
    # Try to pick a question we haven't asked yet
    asked_questions = [h.question.lower() for h in history]
    available_questions = [q for q in questions if q.lower() not in asked_questions]
    
    if available_questions:
        question = available_questions[0]
    else:
        # If all questions used, pick the first one
        question = questions[0]
    
    return {
        "question": question,
        "advisor_tip": "Provide specific examples and quantify your achievements when possible.",
        "topic": f"{phase}_discussion"
    }

async def generate_question(job: str, cv: str, history: List[HistoryItem], state: Dict) -> InterviewResponse:
    """Generate the next interview question based on current state."""
    
    # Check if interview should end
    if state["should_end_interview"]:
        return InterviewResponse(
            question="Thank you for your time today. That concludes our interview. Do you have any final questions for us?",
            advisor_tip="This is your chance to ask thoughtful questions about the role, company culture, or next steps.",
            phase="completed",
            topic="wrap_up",
            is_followup=False
        )
    
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

    # If Gemini is not available, use fallback questions
    if not GEMINI_AVAILABLE:
        print(f"Using fallback questions for {target_phase} phase")
        result = get_fallback_question(target_phase, history, cv)
        return InterviewResponse(
            question=result["question"],
            advisor_tip=result["advisor_tip"],
            phase=target_phase,
            topic=result["topic"],
            is_followup=(action == "followup")
        )
    
    # Build prompt based on action
    phase_info = INTERVIEW_PHASES.get(target_phase, {})
    
    if action == "new_phase":
        # Special handling for closing phase
        if target_phase == "closing":
            prompt = f"""
Job Description: {job}
CV/Resume: {cv}

INTERVIEW STATE:
- Moving to CLOSING PHASE (final questions before ending)
- Total questions asked: {state['total_questions']}
- This phase should have MAX 2 questions before ending

CONVERSATION HISTORY:
{json.dumps([{"q": h.question, "a": h.answer} for h in history], ensure_ascii=False, indent=2)}

INSTRUCTIONS:
Generate a thoughtful closing question for the interview. Focus on:
- Final questions about the candidate's interest in the role
- Questions about their availability or next steps
- Opportunity for the candidate to ask questions
- Keep it concise as the interview is wrapping up

Return ONLY valid JSON:
{{
    "question": "<your closing question here>",
    "advisor_tip": "<helpful tip for the candidate>",
    "topic": "closing_remarks"
}}
"""
        else:
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
The candidate seems to have finished discussing: {state['current_topic']}

Choose a fresh topic that:
1. Fits the {target_phase} phase
2. Is relevant to the job requirements
3. Hasn't been covered extensively yet

CONVERSATION ANALYSIS:
Previous topics covered: {list(set([h.topic for h in history if h.topic]))}

Return ONLY valid JSON:
{{
    "question": "<your question on a NEW topic here>",
    "advisor_tip": "<helpful tip for the candidate>",
    "topic": "<completely new topic/skill being discussed>"
}}
"""
    
    else:  # followup
        # Generate varied followup questions to avoid repetition
        recent_q_text = ", ".join(state['recent_questions'])
        
        prompt = f"""
Job Description: {job}
CV/Resume: {cv}

INTERVIEW STATE:
- Current Phase: {target_phase}
- Current Topic: {state['current_topic']}
- This is FOLLOWUP #{state['followup_count']} on this topic
- Last answer was {state['last_answer_length']} words long
- Recent questions asked: {recent_q_text}

LAST ANSWER: {history[-1].answer if history else ""}

CRITICAL INSTRUCTIONS:
1. DO NOT repeat recent questions or ask "Can you elaborate on that?" again
2. If the last answer was very short (under 5 words), acknowledge it and move to a different angle
3. Ask a SPECIFIC followup that explores a different aspect of {state['current_topic']}
4. Use varied question starters like:
   - "What specific challenges did you face when..."
   - "How did you approach..."
   - "What was the outcome of..."
   - "Can you walk me through..."
   - "What did you learn from..."

AVOID these repetitive phrases:
- "Can you elaborate on that?"
- "Tell me more about that"
- "Could you expand on that?"

Return ONLY valid JSON:
{{
    "question": "<your SPECIFIC and VARIED followup question here>",
    "advisor_tip": "<helpful tip for the candidate>",
    "topic": "{state['current_topic']}"
}}
"""

    try:
        # Generate response
        if GEMINI_AVAILABLE:
            response = await asyncio.get_event_loop().run_in_executor(
                executor, 
                lambda: model.generate_content(prompt).text.strip()
            )
            print(f"Gemini response: {response}")
        else:
            # Use fallback
            print("Gemini not available, using fallback")
            result = get_fallback_question(target_phase, history, cv)
            return InterviewResponse(
                question=result["question"],
                advisor_tip=result["advisor_tip"],
                phase=target_phase,
                topic=result["topic"],
                is_followup=(action == "followup")
            )
        
        # Parse response
        result = clean_json_response(response)
        
        # Check if the generated question is too similar to recent ones
        new_question = result.get("question", "").lower()
        if any(new_question in recent_q or recent_q in new_question for recent_q in state.get('recent_questions', [])):
            # Force a topic change if we're generating repetitive questions
            result = {
                "question": "Let's shift focus. Can you tell me about a specific project or achievement you're particularly proud of?",
                "advisor_tip": "Choose something that showcases your skills and impact.",
                "topic": "achievements"
            }
        
        return InterviewResponse(
            question=result.get("question", "Tell me about yourself."),
            advisor_tip=result.get("advisor_tip", "Be specific and provide examples."),
            phase=target_phase,
            topic=result.get("topic"),
            is_followup=(action == "followup")
        )
        
    except Exception as e:
        print(f"Error generating question: {e}")
        # Fallback response
        result = get_fallback_question(target_phase, history, cv)
        return InterviewResponse(
            question=result["question"],
            advisor_tip=result["advisor_tip"],
            phase=target_phase,
            topic=result.get("topic", "general"),
            is_followup=(action == "followup")
        )

@app.post("/upload")
async def upload_cv(file: UploadFile = File(...), job: str = Form("")):
    """Upload CV and get initial interview question."""
    import traceback
    
    try:
        print(f"Received file: {file.filename}")
        print(f"Job description length: {len(job)}")
        
        if not file.filename or not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        if not job.strip():
            raise HTTPException(status_code=400, detail="Job description is required")
        
        # Extract text from PDF
        print("Reading PDF file...")
        pdf_content = await file.read()
        print(f"PDF content length: {len(pdf_content)} bytes")
        
        print("Extracting text from PDF...")
        cv_text = extract_text_from_pdf(pdf_content)
        print(f"Extracted text length: {len(cv_text)} characters")
        
        if not cv_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from PDF")
        
        # Generate initial question
        print("Generating initial question...")
        
        if GEMINI_AVAILABLE:
            print("Using Gemini AI for question generation")
            prompt = f"""
Job Description: {job}
CV/Resume: {cv_text[:2000]}...

Generate an opening interview question to start the conversation.
This should be a warm, welcoming question that helps the candidate feel comfortable.

Return ONLY valid JSON:
{{
    "question": "<your opening question>",
    "advisor_tip": "<helpful tip for the candidate>",
    "topic": "introduction"
}}
"""
            
            try:
                response = await asyncio.get_event_loop().run_in_executor(
                    executor, 
                    lambda: model.generate_content(prompt).text.strip()
                )
                print(f"Gemini response: {response}")
                result = clean_json_response(response)
            except Exception as gemini_error:
                print(f"Gemini API error: {str(gemini_error)}")
                # Use fallback
                result = get_fallback_question("introduction", [], cv_text)
        else:
            print("Using fallback questions (Gemini not available)")
            result = get_fallback_question("introduction", [], cv_text)
        
        final_response = {
            "question": result.get("question", "Thank you for your interest! Can you start by telling me a bit about yourself?"),
            "advisor_tip": result.get("advisor_tip", "Keep it concise and highlight your key strengths."),
            "cv": cv_text,
            "job": job,
            "phase": "introduction",
            "topic": result.get("topic", "introduction")
        }
        
        print("Upload successful, returning response")
        return final_response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in upload: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error processing upload: {str(e)}")

@app.post("/step")
async def interview_step(request: StepRequest):
    """Generate next interview question based on conversation history."""
    import traceback
    
    try:
        print(f"Received step request with {len(request.history)} history items")
        print(f"Job: {request.job[:100]}...")
        print(f"CV: {request.cv[:100]}...")
        
        # Analyze current interview state
        print("Analyzing interview state...")
        state = analyze_interview_state(request.history)
        print(f"State analysis: {state}")
        
        # Generate next question
        print("Generating next question...")
        response = await generate_question(
            request.job, 
            request.cv, 
            request.history, 
            state
        )
        print(f"Generated response: {response}")
        
        final_response = {
            "question": response.question,
            "advisor_tip": response.advisor_tip,
            "phase": response.phase,
            "topic": response.topic,
            "is_followup": response.is_followup,
            "is_completed": response.phase == "completed",
            "interview_progress": {
                "current_phase": response.phase,
                "questions_asked": len(request.history),
                "phase_progress": f"{state['questions_in_phase']}/{INTERVIEW_PHASES.get(response.phase, {}).get('max_questions', 3)}",
                "total_questions": state.get('total_questions', len(request.history))
            }
        }
        
        print("Step successful, returning response")
        return final_response
        
    except Exception as e:
        print(f"Unexpected error in step: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        
        # Fallback response
        return {
            "question": "Is there anything else you'd like to share about your experience?",
            "advisor_tip": "Feel free to elaborate on any relevant experiences.",
            "phase": "general",
            "topic": None,
            "is_followup": False,
            "is_completed": False,
            "interview_progress": {
                "current_phase": "general",
                "questions_asked": len(request.history) if hasattr(request, 'history') else 0,
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