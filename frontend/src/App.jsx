import { Routes, Route, Navigate } from "react-router-dom";
import { Layout, EmptyState } from "./ui";
import RiskMap from "./pages/RiskMap";
import PlanTomorrow from "./pages/PlanTomorrow";
import Worker from "./pages/Worker";
import ReportsQueue from "./pages/ReportsQueue";
import CheckItem from "./pages/CheckItem";
import MessLog from "./pages/MessLog";
import TwinLab from "./pages/TwinLab";
import Dashboard from "./pages/Dashboard";
import ScaleLab from "./pages/ScaleLab";
import QrSheet from "./pages/QrSheet";
import BinReport from "./pages/BinReport";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/map" replace />} />
      <Route path="/map" element={<Layout><RiskMap /></Layout>} />
      <Route path="/plan" element={<Layout><PlanTomorrow /></Layout>} />
      <Route path="/worker" element={<Layout><Worker /></Layout>} />
      <Route path="/reports" element={<Layout><ReportsQueue /></Layout>} />
      <Route path="/check" element={<Layout><CheckItem /></Layout>} />
      <Route path="/mess" element={<Layout><MessLog /></Layout>} />
      <Route path="/twin" element={<Layout><TwinLab /></Layout>} />
      <Route path="/dashboard" element={<Layout><Dashboard /></Layout>} />
      <Route path="/scale" element={<Layout><ScaleLab /></Layout>} />
      <Route path="/qr" element={<Layout><QrSheet /></Layout>} />
      <Route path="/bin/:binId/report" element={<BinReport />} />
      <Route path="*" element={<Layout><EmptyState title="Page not found" /></Layout>} />
    </Routes>
  );
}
