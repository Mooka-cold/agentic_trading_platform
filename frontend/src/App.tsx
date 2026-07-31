import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppLayout } from "@/components/layout/AppLayout";
import OverviewPage from "./pages/OverviewPage";
import OrchestrationPage from "./pages/OrchestrationPage";
import SwarmPage from "./pages/SwarmPage";
import SessionPage from "./pages/SessionPage";
import PortfolioPage from "./pages/PortfolioPage";
import ReflectionPage from "./pages/ReflectionPage";
import SettingsPage from "./pages/SettingsPage";
import DashboardPage from "./pages/DashboardPage";
import AgentStudioPage from "./pages/AgentStudioPage";
import AutomationBuilderPage from "./pages/AutomationBuilderPage";
import DataSourcePage from "./pages/DataSourcePage";
import LoginPage from "./pages/LoginPage";
import NotFound from "./pages/NotFound";
import { getToken } from "./data/api";

const queryClient = new QueryClient();

// Protected Route Wrapper
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const isAuthenticated = !!getToken();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <AppLayout>{children}</AppLayout>;
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          
          <Route path="/" element={<ProtectedRoute><OverviewPage /></ProtectedRoute>} />
          <Route path="/swarm" element={<ProtectedRoute><SwarmPage /></ProtectedRoute>} />
          <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/studio" element={<ProtectedRoute><AgentStudioPage /></ProtectedRoute>} />
          <Route path="/automation" element={<ProtectedRoute><AutomationBuilderPage /></ProtectedRoute>} />
          <Route path="/data-sources" element={<ProtectedRoute><DataSourcePage /></ProtectedRoute>} />
          <Route path="/session" element={<ProtectedRoute><SessionPage /></ProtectedRoute>} />
          <Route path="/portfolio" element={<ProtectedRoute><PortfolioPage /></ProtectedRoute>} />
          <Route path="/reflection" element={<ProtectedRoute><ReflectionPage /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
          
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
