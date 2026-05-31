import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';

// Placeholder for protected route logic and layout wrapper
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('token');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  // In a real app, we'd also wrap children in the Sidebar Layout here
  return <>{children}</>;
};

// Placeholder Dashboard for now
const Dashboard = () => {
  const username = localStorage.getItem('username');
  return (
    <div style={{ padding: '40px' }}>
      <h1>Dashboard</h1>
      <p>Welcome back, {username}!</p>
      <button 
        className="btn-primary" 
        onClick={() => { localStorage.clear(); window.location.href='/login'; }}
      >
        Logout
      </button>
    </div>
  );
};

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        
        <Route 
          path="/dashboard" 
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          } 
        />
        
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
