import { useEffect, useState, useRef } from "react";
import { useInterview } from "../contexts/InterviewContext";
import { getNextQuestion } from "../services/api";

type RecognitionState = 'idle' | 'listening' | 'processing';

export default function QuestionCard() {
  const { state, dispatch } = useInterview();
  const [recognitionState, setRecognitionState] = useState<RecognitionState>('idle');
  const [currentAnswer, setCurrentAnswer] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const synth = useRef<SpeechSynthesis | null>(null);
  const recognition = useRef<SpeechRecognition | null>(null);
  const isInitialized = useRef(false);

  // Initialize speech synthesis
  useEffect(() => {
    if (typeof window !== 'undefined') {
      synth.current = window.speechSynthesis;
    }
  }, []);

  // Initialize speech recognition
  useEffect(() => {
    if (typeof window !== 'undefined' && 'webkitSpeechRecognition' in window) {
      recognition.current = new (window as any).webkitSpeechRecognition();
      recognition.current.lang = "en-US";
      recognition.current.continuous = false;
      recognition.current.interimResults = false;
      
      recognition.current.onstart = () => {
        setRecognitionState('listening');
        setCurrentAnswer("");
      };
      
      recognition.current.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setCurrentAnswer(transcript);
        setRecognitionState('processing');
        handleAnswerReceived(transcript);
      };
      
      recognition.current.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setRecognitionState('idle');
      };
      
      recognition.current.onend = () => {
        if (recognitionState === 'listening') {
          setRecognitionState('idle');
        }
      };
    }
  }, [recognitionState]);

  // Speak the initial question when component loads
  useEffect(() => {
    if (state.current && !isInitialized.current) {
      speak(state.current);
      isInitialized.current = true;
    }
  }, [state.current]);

  const speak = (text: string, onEnd?: () => void) => {
    if (!synth.current) return;
    
    // Stop any currently speaking utterance
    synth.current.cancel();
    
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    utterance.rate = 0.9; // Slightly slower for better comprehension
    
    if (onEnd) {
      utterance.onend = onEnd;
    }
    
    synth.current.speak(utterance);
  };

  const startListening = () => {
    if (!recognition.current || recognitionState !== 'idle') return;
    
    try {
      recognition.current.start();
    } catch (error) {
      console.error('Error starting speech recognition:', error);
    }
  };

  const stopListening = () => {
    if (recognition.current && recognitionState === 'listening') {
      recognition.current.stop();
      setRecognitionState('idle');
    }
  };

  const handleAnswerReceived = async (answer: string) => {
    if (!answer.trim()) {
      setRecognitionState('idle');
      return;
    }

    setIsLoading(true);
    
    try {
      // Build proper history format matching backend expectations
      const newHistoryItem = {
        question: state.current,
        answer: answer,
        topic: state.currentTopic,
        phase: state.currentPhase
      };

      const requestBody = {
        job: state.job,
        cv: state.cv,
        history: [...state.history, newHistoryItem]
      };

      const response = await getNextQuestion(requestBody);
      
      // Check if interview is completed
      if (response.is_completed) {
        dispatch({
          type: "COMPLETE_INTERVIEW",
          payload: {
            question: state.current,
            answer: answer,
            advisor: state.advisor,
            finalMessage: response.question
          }
        });
        
        // Speak the final message
        speak(response.question);
        return;
      }
      
      // Update state with the new question and answer
      dispatch({
        type: "ADD",
        payload: {
          question: state.current,
          answer: answer,
          advisor: state.advisor,
          nextQuestion: response.question,
          nextAdvisor: response.advisor_tip,
          phase: response.phase,
          topic: response.topic
        }
      });

      // Speak the next question
      speak(response.question);
      
    } catch (error) {
      console.error('Error getting next question:', error);
    } finally {
      setIsLoading(false);
      setRecognitionState('idle');
    }
  };

  const skipQuestion = async () => {
    if (isLoading) return;
    
    setIsLoading(true);
    
    try {
      const requestBody = {
        job: state.job,
        cv: state.cv,
        history: state.history
      };

      const response = await getNextQuestion(requestBody);
      
      // Check if interview is completed
      if (response.is_completed) {
        dispatch({
          type: "COMPLETE_INTERVIEW",
          payload: {
            finalMessage: response.question
          }
        });
        
        speak(response.question);
        return;
      }
      
      dispatch({
        type: "NEXT_QUESTION",
        payload: {
          question: response.question,
          advisor: response.advisor_tip,
          phase: response.phase,
          topic: response.topic
        }
      });

      speak(response.question);
      
    } catch (error) {
      console.error('Error getting next question:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getButtonText = () => {
    switch (recognitionState) {
      case 'listening':
        return 'Listening...';
      case 'processing':
        return 'Processing...';
      default:
        return 'Start Answering';
    }
  };

  const getButtonColor = () => {
    switch (recognitionState) {
      case 'listening':
        return 'bg-red-600 hover:bg-red-700';
      case 'processing':
        return 'bg-yellow-600';
      default:
        return 'bg-sky-600 hover:bg-sky-700';
    }
  };

  return (
    <div className="w-full max-w-2xl p-6 space-y-6 rounded bg-slate-800">
      {/* Interview Progress */}
      {state.currentPhase && (
        <div className="text-sm text-slate-400 mb-4">
          Phase: <span className="capitalize text-sky-400">{state.currentPhase}</span>
          {state.currentTopic && (
            <> | Topic: <span className="text-green-400">{state.currentTopic}</span></>
          )}
        </div>
      )}

      {/* Current Question */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-white leading-relaxed">
          {state.current}
        </h2>
        
        {state.advisor && (
          <div className="p-3 bg-green-900/30 border border-green-700/50 rounded">
            <p className="text-sm text-green-300">
              <strong>💡 Tip:</strong> {state.advisor}
            </p>
          </div>
        )}
      </div>

      {/* Current Answer Display */}
      {currentAnswer && (
        <div className="p-3 bg-blue-900/30 border border-blue-700/50 rounded">
          <p className="text-sm text-blue-300">
            <strong>Your answer:</strong> {currentAnswer}
          </p>
        </div>
      )}

      {/* Action Buttons */}
      {state.isCompleted ? (
        <div className="text-center space-y-4">
          <div className="p-4 bg-green-900/30 border border-green-700/50 rounded-lg">
            <h3 className="text-lg font-semibold text-green-300 mb-2">
              🎉 Interview Completed!
            </h3>
            <p className="text-green-200">
              Thank you for participating in this mock interview. 
              You can review your responses below.
            </p>
          </div>
          
          <button
            onClick={() => window.location.reload()}
            className="px-6 py-3 bg-sky-600 hover:bg-sky-700 text-white rounded-lg font-medium transition-colors"
          >
            Start New Interview
          </button>
        </div>
      ) : (
        <div className="flex gap-3">
          {recognitionState === 'listening' ? (
            <button
              onClick={stopListening}
              className="flex-1 py-3 px-4 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors"
            >
              Stop Recording
            </button>
          ) : (
            <button
              onClick={startListening}
              disabled={recognitionState === 'processing' || isLoading}
              className={`flex-1 py-3 px-4 text-white rounded-lg font-medium transition-colors disabled:opacity-50 ${getButtonColor()}`}
            >
              {isLoading ? 'Processing...' : getButtonText()}
            </button>
          )}
          
          <button
            onClick={skipQuestion}
            disabled={isLoading || recognitionState !== 'idle'}
            className="px-6 py-3 bg-slate-600 hover:bg-slate-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            Skip
          </button>
        </div>
      )}

      {/* Interview History */}
      {state.history.length > 0 && (
        <div className="mt-8">
          <h3 className="text-lg font-medium text-white mb-4">Previous Questions</h3>
          <div className="space-y-3 max-h-64 overflow-y-auto">
            {state.history.map((item, index) => (
              <div key={index} className="p-3 bg-slate-700/50 rounded text-sm">
                <p className="text-slate-300 mb-1">
                  <strong>Q:</strong> {item.question}
                </p>
                <p className="text-slate-400">
                  <strong>A:</strong> {item.answer}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Browser Compatibility Check */}
      {typeof window !== 'undefined' && !('webkitSpeechRecognition' in window) && (
        <div className="p-3 bg-yellow-900/30 border border-yellow-700/50 rounded">
          <p className="text-sm text-yellow-300">
            ⚠️ Voice recognition is not supported in your browser. Please use Chrome for the best experience.
          </p>
        </div>
      )}
    </div>
  );
}