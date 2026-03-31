import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
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
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Sonner />
      <BrowserRouter>
        <AppLayout>
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/orchestration" element={<OrchestrationPage />} />
            <Route path="/swarm" element={<SwarmPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/session" element={<SessionPage />} />
            <Route path="/portfolio" element={<PortfolioPage />} />
            <Route path="/reflection" element={<ReflectionPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </AppLayout>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
