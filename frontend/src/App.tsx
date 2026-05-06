import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { fetchSetupStatus } from "./api/setup";
import Dashboard from "./routes/Dashboard";
import EffortAndCost from "./routes/EffortAndCost";
import JobInProgress from "./routes/JobInProgress";
import JobPreview from "./routes/JobPreview";
import NewProject from "./routes/NewProject";
import Setup from "./routes/Setup";
import { useSetupStore } from "./stores/setupStore";

export default function App() {
  const status = useSetupStore((s) => s.status);
  const setStatus = useSetupStore((s) => s.setStatus);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    let cancelled = false;
    fetchSetupStatus()
      .then((res) => {
        if (cancelled) return;
        setStatus(res.setup_complete ? "complete" : "incomplete");
      })
      .catch(() => {
        if (cancelled) return;
        // If the API is unreachable, leave status "unknown" so the UI
        // surfaces an error rather than silently navigating.
      });
    return () => {
      cancelled = true;
    };
  }, [setStatus]);

  // First-paint redirect once we know the status.
  useEffect(() => {
    if (status === "unknown") return;
    if (status === "incomplete" && location.pathname !== "/setup") {
      navigate("/setup", { replace: true });
    } else if (status === "complete" && location.pathname === "/setup") {
      navigate("/dashboard", { replace: true });
    }
  }, [status, location.pathname, navigate]);

  if (status === "unknown") {
    return (
      <div className="flex h-full items-center justify-center text-slate-500">
        Loading…
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/setup" element={<Setup />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/projects/new" element={<NewProject />} />
      <Route path="/projects/new/effort" element={<EffortAndCost />} />
      <Route path="/jobs/:job_id" element={<JobInProgress />} />
      <Route path="/jobs/:job_id/preview" element={<JobPreview />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
