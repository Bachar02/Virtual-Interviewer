// src/contexts/InterviewContext.tsx
import { createContext, useContext, useReducer, ReactNode } from "react";

export type State = {
  step: 0 | 1 | 2;               // 0 = upload, 1 = interview, 2 = report
  job: string;                   // job description
  cv: string;                    // résumé text
  history: { q: string; a: string; advisor: string }[]; // all Q-A pairs
  current: string;               // current question
  advisor: string;               // latest advisor tip
};

type Action =
  | { type: "START"; payload: { question: string; job: string; cv: string } }
  | { type: "ADD"; payload: { answer: string; question: string; advisor: string } }
  | { type: "RESET" };

const initial: State = {
  step: 0,
  job: "",
  cv: "",
  history: [],
  current: "",
  advisor: "",
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
      };
    case "ADD":
      return {
        ...state,
        history: [...state.history, { q: action.payload.question, a: action.payload.answer, advisor: action.payload.advisor }],
        current: action.payload.question,
        advisor: action.payload.advisor,
        step: 1,
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