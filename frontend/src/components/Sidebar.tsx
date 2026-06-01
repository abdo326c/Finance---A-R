import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, FileText, LogOut, FileBarChart, Calculator, Settings, GraduationCap, UserPlus, Award, CloudRain, ShieldCheck, RefreshCw, ArrowLeftRight, FileSpreadsheet, Archive, Mail, Search, Key, X, Sun, Moon } from 'lucide-react';
import './Sidebar.css';
import { useTheme } from '../context/ThemeContext';

export default function Sidebar({ isOpen, setIsOpen }: { isOpen?: boolean, setIsOpen?: (val: boolean) => void }) {
  const navigate = useNavigate();
  const username = localStorage.getItem('username');
  const { theme, toggleTheme } = useTheme();
  
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

  const handleLogout = () => {
    localStorage.clear();
    navigate('/login');
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
        
        {role === 'Admin' && (
          <NavLink to="/admin" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <ShieldCheck size={20} />
            <span>System Admin</span>
          </NavLink>
        )}
      </nav>

      <div className="sidebar-footer" style={{ borderTop: '1px solid var(--border-color)', padding: '16px' }}>
        <div className="user-profile" style={{ marginBottom: '16px', padding: '0 8px', borderBottom: 'none' }}>
          <div className="avatar" style={{ width: '32px', height: '32px', fontSize: '1rem', borderRadius: '8px' }}>
            {username?.charAt(0).toUpperCase()}
          </div>
          <div className="user-info">
            <p className="user-name" style={{ fontSize: '0.85rem' }}>{username}</p>
            <p className="user-role" style={{ fontSize: '0.7rem' }}>{role}</p>
          </div>
          <button onClick={toggleTheme} className="btn-icon" style={{ marginLeft: 'auto' }} title="Toggle Theme">
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </div>

        <button onClick={handleLogout} className="btn-logout-sidebar" style={{ padding: '8px 12px', fontSize: '0.85rem' }}>
          <LogOut size={16} />
          <span>Logout</span>
        </button>
      </div>
    </div>
    </>
  );
}
