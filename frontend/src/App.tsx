import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";

import { AuthProvider, useAuth } from "./auth/AuthContext";
import { AppShell } from "./components/AppShell";
import { LoadingState } from "./components/Shared";

const AssistantPage = lazy(() =>
  import("./pages/AssistantPage").then(({ AssistantPage }) => ({
    default: AssistantPage,
  })),
);
const DashboardPage = lazy(() =>
  import("./pages/DashboardPage").then(({ DashboardPage }) => ({
    default: DashboardPage,
  })),
);
const DocumentsPage = lazy(() =>
  import("./pages/DocumentsPage").then(({ DocumentsPage }) => ({
    default: DocumentsPage,
  })),
);
const ExpensesPage = lazy(() =>
  import("./pages/ExpensesPage").then(({ ExpensesPage }) => ({
    default: ExpensesPage,
  })),
);
const LoginPage = lazy(() =>
  import("./pages/LoginPage").then(({ LoginPage }) => ({ default: LoginPage })),
);
const MechanicPage = lazy(() =>
  import("./pages/MechanicPage").then(({ MechanicPage }) => ({
    default: MechanicPage,
  })),
);
const RemindersPage = lazy(() =>
  import("./pages/RemindersPage").then(({ RemindersPage }) => ({
    default: RemindersPage,
  })),
);
const ServiceHistoryPage = lazy(() =>
  import("./pages/ServiceHistoryPage").then(({ ServiceHistoryPage }) => ({
    default: ServiceHistoryPage,
  })),
);
const VehiclesPage = lazy(() =>
  import("./pages/VehiclesPage").then(({ VehiclesPage }) => ({
    default: VehiclesPage,
  })),
);

function ProtectedRoute() {
  const { user, loading } = useAuth();
  if (loading) return <LoadingState label="Preparing your workspace..." />;
  return user ? <Outlet /> : <Navigate to="/login" replace />;
}

function PublicRoute() {
  const { user, loading } = useAuth();
  if (loading) return <LoadingState label="Preparing your workspace..." />;
  return user ? <Navigate to="/" replace /> : <LoginPage />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<LoadingState label="Loading your workspace..." />}>
          <Routes>
            <Route path="/login" element={<PublicRoute />} />
            <Route path="/register" element={<PublicRoute />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<AppShell />}>
                <Route index element={<DashboardPage />} />
                <Route path="/vehicles" element={<VehiclesPage />} />
                <Route path="/service-history" element={<ServiceHistoryPage />} />
                <Route path="/expenses" element={<ExpensesPage />} />
                <Route path="/assistant" element={<AssistantPage />} />
                <Route path="/mechanic" element={<MechanicPage />} />
                <Route path="/reminders" element={<RemindersPage />} />
                <Route path="/documents" element={<DocumentsPage />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  );
}
