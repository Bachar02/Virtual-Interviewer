import { BrowserRouter, Routes, Route } from "react-router-dom";
import { InterviewProvider } from "./contexts/InterviewContext";
import UploadPage from "./pages/UploadPage";
import InterviewPage from "./pages/InterviewPage";
import ReportPage from "./pages/ReportPage";

export default function App() {
  return (
    <InterviewProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/interview" element={<InterviewPage />} />
          <Route path="/report" element={<ReportPage />} />
        </Routes>
      </BrowserRouter>
    </InterviewProvider>
  );
}