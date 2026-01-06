import { BrowserRouter, Routes, Route } from "react-router-dom";
import DashboardPage from "./pages/FullPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardPage/>} />
        <Route path="*" element={<div>Route not found</div>} />
        
      </Routes>
    </BrowserRouter>
  );
}