import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import Home from "./pages/Home";
import Project from "./pages/Project";

function App() {
  return (
    <div
      className="App min-h-screen bg-[#0e0b08] text-[#f4ede3]"
      style={{
        fontFamily: "'Fraunces', 'Playfair Display', Georgia, serif",
        backgroundImage:
          "radial-gradient(circle at 20% 10%, #2a1d11 0%, transparent 45%), radial-gradient(circle at 85% 80%, #1a2214 0%, transparent 45%)",
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/project/:id" element={<Project />} />
        </Routes>
      </BrowserRouter>
      <Toaster richColors position="top-right" theme="dark" />
    </div>
  );
}

export default App;
