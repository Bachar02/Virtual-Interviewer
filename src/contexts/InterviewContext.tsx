import { createContext, useContext, useReducer, ReactNode } from "react";

export type HistoryItem = {
  question: string;
  answer: string;
  advisor: string;
  topic?: string;
  phase?: string;
};

export type State = {
  step: 0 | 1 | 2;               // 0 = upload, 1 = interview, 2 = report
  job: string;                   // job description
  cv: string;                    // résumé text
  history: HistoryItem[];        // all Q-A pairs with metadata
  current: string;               // current question
  advisor: string;               // latest advisor tip
  currentPhase?: string;         // current interview phase
  currentTopic?: string;         // current topic being discussed
  isCompleted: boolean;          // whether interview is finished
  finalMessage?: string;         // final closing message
};

type Action =
  | { 
      type: "START"; 
      payload: { 
        question: string; 
        job: string; 
        cv: string; 
        advisor: string;
        phase?: string;
        topic?: string;
      } 
    }
  | { 
      type: "ADD"; 
      payload: { 
        question: string;
        answer: string; 
        advisor: string;
        nextQuestion: string;
        nextAdvisor: string;
        phase?: string;
        topic?: string;
      } 
    }
  | {
      type: "NEXT_QUESTION";
      payload: {
        question: string;
        advisor: string;
        phase?: string;
        topic?: string;
      }
    }
  | {
      type: "COMPLETE_INTERVIEW";
      payload: {
        question?: string;
        answer?: string;
        advisor?: string;
        finalMessage: string;
      }
    }
  | { type: "RESET" };

const initial: State = {
  step: 0,
  job: "",
  cv: "",
  history: [],
  current: "",
  advisor: "",
  currentPhase: undefined,
  currentTopic: undefined,
  isCompleted: false,
  finalMessage: undefined,
};

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "START":
      return {
        ...initial,
        step: 1,
        job: action.payload.job,
        cv: action.payload.cv,
        current: action.payload.question,
        advisor: action.payload.advisor,
        currentPhase: action.payload.phase,
        currentTopic: action.payload.topic,
      };
    
    case "ADD":
      return {
        ...state,
        history: [...state.history, { 
          question: action.payload.question, 
          answer: action.payload.answer, 
          advisor: action.payload.advisor,
          topic: state.currentTopic,
          phase: state.currentPhase
        }],
        current: action.payload.nextQuestion,
        advisor: action.payload.nextAdvisor,
        currentPhase: action.payload.phase,
        currentTopic: action.payload.topic,
        step: 1,
      };
    
    case "NEXT_QUESTION":
      return {
        ...state,
        current: action.payload.question,
        advisor: action.payload.advisor,
        currentPhase: action.payload.phase,
        currentTopic: action.payload.topic,
      };
    
    case "COMPLETE_INTERVIEW":
      const finalHistory = [...state.history];
      if (action.payload.question && action.payload.answer) {
        finalHistory.push({
          question: action.payload.question,
          answer: action.payload.answer,
          advisor: action.payload.advisor || "",
          topic: state.currentTopic,
          phase: state.currentPhase
        });
      }
      
      return {
        ...state,
        history: finalHistory,
        current: action.payload.finalMessage,
        isCompleted: true,
        finalMessage: action.payload.finalMessage,
        step: 2, // Move to report/completion step
      };
    
    case "RESET":
      return initial;
    
    default:
      return state;
  }
}

const InterviewContext = createContext<{
  state: State;
  dispatch: React.Dispatch<Action>;
}>({ state: initial, dispatch: () => null });

export const InterviewProvider = ({ children }: { children: ReactNode }) => {
  const [state, dispatch] = useReducer(reducer, initial);
  return <InterviewContext.Provider value={{ state, dispatch }}>{children}</InterviewContext.Provider>;
};

export const useInterview = () => useContext(InterviewContext);