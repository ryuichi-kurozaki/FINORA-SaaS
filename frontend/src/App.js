import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AppProvider, useApp } from "@/context/AppContext";
import Layout from "@/components/Layout";
import { Spinner } from "@/components/common";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Clients from "@/pages/Clients";
import ClientDetail from "@/pages/ClientDetail";
import EntityPage from "@/pages/EntityPage";
import Portfolio from "@/pages/Portfolio";
import Analytics from "@/pages/Analytics";
import Simulation from "@/pages/Simulation";
import Risk from "@/pages/Risk";
import AIInsight from "@/pages/AIInsight";
import Reports from "@/pages/Reports";
import Documents from "@/pages/Documents";
import SettingsPage from "@/pages/Settings";
import Landing from "@/pages/Landing";
import ConsultingHub from "@/pages/ConsultingHub";
import Transactions from "@/pages/Transactions";
import { GoalsPage, DataHealthPage } from "@/pages/GoalsHealth";
import Timeline from "@/pages/Timeline";
import Notifications from "@/pages/Notifications";
import Billing from "@/pages/Billing";
import Platform from "@/pages/Platform";
import { Signup, InviteAccept } from "@/pages/Signup";
import { PaymentSuccess, PaymentCancel } from "@/pages/PaymentResult";
import Legal from "@/pages/Legal";

function Protected() {
  const { user } = useApp();
  const { pathname } = useLocation();
  if (user === null) return <div className="min-h-screen bg-[#F7F9FC]"><Spinner /></div>;
  if (!user) return pathname === "/" ? <Landing /> : <Navigate to="/login" replace />;
  return <Layout />;
}

function App() {
  return (
    <div className="App">
      <AppProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/legal" element={<Legal />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/invite/:token" element={<InviteAccept />} />
            <Route path="/payment/success" element={<PaymentSuccess />} />
            <Route path="/payment/cancel" element={<PaymentCancel />} />
            <Route element={<Protected />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/clients" element={<Clients />} />
              <Route path="/clients/:id" element={<ClientDetail />} />
              <Route path="/assets" element={<EntityPage entity="assets" />} />
              <Route path="/portfolio" element={<Portfolio />} />
              <Route path="/accounts" element={<EntityPage entity="accounts" />} />
              <Route path="/liabilities" element={<EntityPage entity="liabilities" />} />
              <Route path="/cashflow" element={<EntityPage entity="cashflows" />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/simulation" element={<Simulation />} />
              <Route path="/risk" element={<Risk />} />
              <Route path="/ai" element={<AIInsight />} />
              <Route path="/consulting" element={<ConsultingHub />} />
              <Route path="/transactions" element={<Transactions />} />
              <Route path="/goals" element={<GoalsPage />} />
              <Route path="/data-health" element={<DataHealthPage />} />
              <Route path="/timeline" element={<Timeline />} />
              <Route path="/notifications" element={<Notifications />} />
              <Route path="/billing" element={<Billing />} />
              <Route path="/platform" element={<Platform />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/documents" element={<Documents />} />
              <Route path="/tasks" element={<EntityPage entity="tasks" />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" richColors />
      </AppProvider>
    </div>
  );
}

export default App;
