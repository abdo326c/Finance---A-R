import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, FileText, LogOut, FileBarChart, Calculator, Settings, GraduationCap, UserPlus, Award, CloudRain, ShieldCheck, RefreshCw, ArrowLeftRight, FileSpreadsheet, Archive, Mail, Search, Key, X } from 'lucide-react';
import axios from 'axios';
import './Sidebar.css';

export default function Sidebar({ isOpen, setIsOpen }: { isOpen?: boolean, setIsOpen?: (val: boolean) => void }) {
  const navigate = useNavigate();
  const username = localStorage.getItem('username');
  
  const [role] = useState(() => {
    try {
      const token = localStorage.getItem('token');
      if (!token) return 'Viewer';
      const payload = JSON.parse(atob(token.split('.')[1]));
      return payload.role;
    } catch {
      return 'Viewer';
    }
  });

  const [showChangePw, setShowChangePw] = useState(false);
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [pwError, setPwError] = useState('');

  const handleLogout = () => {
    localStorage.clear();
    navigate('/login');
  };

  const handleChangePassword = async () => {
    try {
      const token = localStorage.getItem('token');
      await axios.post('http://127.0.0.1:8000/api/auth/change-password', {
        current_password: currentPw,
        new_password: newPw
      }, { headers: { Authorization: `Bearer ${token}` } });
      alert('Password changed successfully');
      setShowChangePw(false);
      setCurrentPw('');
      setNewPw('');
      setPwError('');
    } catch (err: any) {
      setPwError(err.response?.data?.detail || 'Failed to change password');
    }
  };

  return (
    <>
      {isOpen && <div className="sidebar-backdrop" onClick={() => setIsOpen && setIsOpen(false)}></div>}
      <div className={`sidebar glass-panel ${!isOpen ? 'desktop-closed' : ''} ${isOpen ? 'mobile-open' : ''}`}>
        <div className="sidebar-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div className="logo-icon">🏦</div>
            <h2>Finance A/R</h2>
          </div>
          {setIsOpen && (
            <button className="close-sidebar-btn btn-icon" onClick={() => setIsOpen(false)}>
              <X size={24} />
            </button>
          )}
        </div>
      
      <div className="user-profile">
        <div className="avatar">{username?.charAt(0).toUpperCase()}</div>
        <div className="user-info">
          <p className="user-name">{username}</p>
          <p className="user-role">{role}</p>
        </div>
      </div>

      <nav className="sidebar-nav">
        <NavLink to="/dashboard" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <LayoutDashboard size={20} />
          <span>Dashboard</span>
        </NavLink>
        
        <NavLink to="/explorer" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <Search size={20} />
          <span>Student Explorer</span>
        </NavLink>
        
        <NavLink to="/statement" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <FileText size={20} />
          <span>Statement</span>
        </NavLink>
        
        <NavLink to="/reports" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <FileBarChart size={20} />
          <span>Reports</span>
        </NavLink>
        
        <NavLink to="/registration" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <UserPlus size={20} />
          <span>Registration</span>
        </NavLink>
        
        <NavLink to="/scholarships" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <Award size={20} />
          <span>Scholarships</span>
        </NavLink>
        
        <NavLink to="/policies" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <FileText size={20} />
          <span>Policies</span>
        </NavLink>
        
        <NavLink to="/operations" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <Calculator size={20} />
          <span>Operations</span>
        </NavLink>

        <div className="sidebar-title" style={{ marginTop: '32px' }}>INTEGRATIONS</div>
        <NavLink to="/fawry" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <CloudRain size={20} />
          <span>Fawry Sync</span>
        </NavLink>
        
        <NavLink to="/d365" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <RefreshCw size={20} />
          <span>D365 Export</span>
        </NavLink>
        
        <NavLink to="/reconciliation" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <ArrowLeftRight size={20} />
          <span>Reconciliation</span>
        </NavLink>
        
        <div className="sidebar-title" style={{ marginTop: '32px' }}>ADMINISTRATION</div>
        <NavLink to="/bulk" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <FileSpreadsheet size={20} />
          <span>Bulk Operations</span>
        </NavLink>
        
        <NavLink to="/batches" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <Archive size={20} />
          <span>Batch Management</span>
        </NavLink>
        
        <NavLink to="/emails" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <Mail size={20} />
          <span>Email Follow-up</span>
        </NavLink>
        
        {role === 'Admin' && (
          <NavLink to="/admin" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <ShieldCheck size={20} />
            <span>System Admin</span>
          </NavLink>
        )}
      </nav>

      <div className="sidebar-footer">
        <button onClick={() => setShowChangePw(true)} className="btn-logout-sidebar" style={{ background: 'transparent', color: 'var(--text-primary)', border: '1px solid rgba(255,255,255,0.1)', marginBottom: '10px' }}>
          <Key size={18} />
          <span>Change Password</span>
        </button>
        <button onClick={handleLogout} className="btn-logout-sidebar">
          <LogOut size={20} />
          <span>Logout</span>
        </button>
      </div>

      {showChangePw && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="glass-panel" style={{ width: '350px', padding: '24px' }}>
            <h3 style={{ margin: '0 0 20px 0', display: 'flex', alignItems: 'center', gap: '8px' }}><Key size={18}/> Change Password</h3>
            {pwError && <div style={{ color: '#ef4444', marginBottom: '15px', fontSize: '13px' }}>{pwError}</div>}
            
            <div className="form-group">
              <label>Current Password</label>
              <input type="password" value={currentPw} onChange={e => setCurrentPw(e.target.value)} />
            </div>
            
            <div className="form-group">
              <label>New Password</label>
              <input type="password" value={newPw} onChange={e => setNewPw(e.target.value)} />
            </div>
            
            <div style={{ display: 'flex', gap: '10px', marginTop: '20px' }}>
              <button className="btn-secondary" style={{ flex: 1 }} onClick={() => setShowChangePw(false)}>Cancel</button>
              <button className="btn-primary" style={{ flex: 1 }} onClick={handleChangePassword}>Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
    </>
  );
}
