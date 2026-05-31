import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';

import Dashboard from './pages/Dashboard';
import StudentStatement from './pages/StudentStatement';
import Reports from './pages/Reports';
import Operations from './pages/Operations';
import Policies from './pages/Policies';
import Scholarships from './pages/Scholarships';
import Registration from './pages/Registration';
import FawrySync from './pages/FawrySync';
import D365Export from './pages/D365Export';
import Reconciliation from './pages/Reconciliation';
import BulkOperations from './pages/BulkOperations';
import BatchManagement from './pages/BatchManagement';
import EmailFollowup from './pages/EmailFollowup';
import Admin from './pages/Admin';
import StudentExplorer from './pages/StudentExplorer';
import Sidebar from './components/Sidebar';

const AppLayout = ({ children }: { children: React.ReactNode }) => {
  const [sidebarOpen, setSidebarOpen] = useState(window.innerWidth > 768);

  // Optional: Listen to window resize to auto-collapse/open
  React.useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth <= 768) setSidebarOpen(false);
      else setSidebarOpen(true);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div className="app-container" style={{ display: 'flex', height: '100vh', width: '100vw', background: 'var(--bg-color)', overflow: 'hidden' }}>
      <Sidebar isOpen={sidebarOpen} setIsOpen={setSidebarOpen} />
      
      <div className="main-content-area" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, minWidth: 0, overflowY: 'auto', overflowX: 'hidden', position: 'relative' }}>
        
        {/* Universal Header (shows hamburger when sidebar is closed) */}
        {!sidebarOpen && (
          <div className="top-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', background: 'var(--glass-bg)', backdropFilter: 'blur(12px)', borderBottom: 'var(--glass-border)', position: 'sticky', top: 0, zIndex: 50 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <button className="btn-icon" onClick={() => setSidebarOpen(true)}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--text-primary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
              </button>
              <h2 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--primary-color)' }}>Finance A/R</h2>
            </div>
          </div>
        )}

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
        <Route 
          path="/bulk" 
          element={
            <ProtectedRoute>
              <BulkOperations />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/batches" 
          element={
            <ProtectedRoute>
              <BatchManagement />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/emails" 
          element={
            <ProtectedRoute>
              <EmailFollowup />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/admin" 
          element={
            <ProtectedRoute>
              <Admin />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/explorer" 
          element={
            <ProtectedRoute>
              <StudentExplorer />
            </ProtectedRoute>
          } 
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
