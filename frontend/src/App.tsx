import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';

import Dashboard from './pages/Dashboard';
import StudentStatement from './pages/StudentStatement';
import Reports from './pages/Reports';
import Operations from './pages/Operations';
import DataLookups from './pages/DataLookups';
import Policies from './pages/Policies';
import Scholarships from './pages/Scholarships';
import Registration from './pages/Registration';
import FawrySync from './pages/FawrySync';
import D365Export from './pages/D365Export';
import Reconciliation from './pages/Reconciliation';
import Sidebar from './components/Sidebar';

// Layout wrapper for authenticated pages
const AppLayout = ({ children }: { children: React.ReactNode }) => {
  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', background: 'var(--bg-color)', overflow: 'hidden' }}>
      <Sidebar />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, minWidth: 0, overflowY: 'auto', overflowX: 'hidden' }}>
        {children}
      </div>
    </div>
  );
};

// Protected route logic
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('token');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <AppLayout>{children}</AppLayout>;
};

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route 
          path="/dashboard" 
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/statement" 
          element={
            <ProtectedRoute>
              <StudentStatement />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/reports" 
          element={
            <ProtectedRoute>
              <Reports />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/scholarships" 
          element={
            <ProtectedRoute>
              <Scholarships />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/registration" 
          element={
            <ProtectedRoute>
              <Registration />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/operations" 
          element={
            <ProtectedRoute>
              <Operations />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/policies" 
          element={
            <ProtectedRoute>
              <Policies />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/admin/lookups" 
          element={
            <ProtectedRoute>
              <DataLookups />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/fawry" 
          element={
            <ProtectedRoute>
              <FawrySync />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/d365" 
          element={
            <ProtectedRoute>
              <D365Export />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/reconciliation" 
          element={
            <ProtectedRoute>
              <Reconciliation />
            </ProtectedRoute>
          } 
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
