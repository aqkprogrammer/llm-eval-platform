import { lazy } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import { EmptyState } from "./components/ui/EmptyState";

const OverviewPage = lazy(() => import("./pages/OverviewPage"));
const ExperimentsPage = lazy(() => import("./pages/ExperimentsPage"));
const ExperimentDetailPage = lazy(() => import("./pages/ExperimentDetailPage"));
const ComparePage = lazy(() => import("./pages/ComparePage"));
const LeaderboardPage = lazy(() => import("./pages/LeaderboardPage"));
const DatasetsPage = lazy(() => import("./pages/DatasetsPage"));
const DatasetDetailPage = lazy(() => import("./pages/DatasetDetailPage"));
const PromptsPage = lazy(() => import("./pages/PromptsPage"));
const ModelsPage = lazy(() => import("./pages/ModelsPage"));
const TracesPage = lazy(() => import("./pages/TracesPage"));
const TraceDetailPage = lazy(() => import("./pages/TraceDetailPage"));
const MonitoringPage = lazy(() => import("./pages/MonitoringPage"));

function NotFound() {
  return (
    <EmptyState
      title="Page not found"
      description="The page you are looking for does not exist."
      action={
        <Link to="/" className="text-sm font-medium text-accent-600 hover:underline dark:text-accent-400">
          Back to overview
        </Link>
      }
    />
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="experiments" element={<ExperimentsPage />} />
        <Route path="experiments/:id" element={<ExperimentDetailPage />} />
        <Route path="compare" element={<ComparePage />} />
        <Route path="leaderboard" element={<LeaderboardPage />} />
        <Route path="datasets" element={<DatasetsPage />} />
        <Route path="datasets/:id" element={<DatasetDetailPage />} />
        <Route path="prompts" element={<PromptsPage />} />
        <Route path="models" element={<ModelsPage />} />
        <Route path="traces" element={<TracesPage />} />
        <Route path="traces/:id" element={<TraceDetailPage />} />
        <Route path="monitoring" element={<MonitoringPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
