import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, FileText, LogOut, FileBarChart, Calculator, Settings, GraduationCap, UserPlus, Award, CloudRain, ShieldCheck, RefreshCw, ArrowLeftRight } from 'lucide-react';
import './Sidebar.css';

export default function Sidebar() {
  const navigate = useNavigate();
  const username = localStorage.getItem('username');

  const handleLogout = () => {
    localStorage.clear();
    navigate('/login');
  };

  return (
    <div className="sidebar glass-panel">
      <div className="sidebar-header">
        <div className="logo-icon">🏦</div>
        <h2>Finance A/R</h2>
      </div>
      
      <div className="user-profile">
        <div className="avatar">{username?.charAt(0).toUpperCase()}</div>
        <div className="user-info">
          <p className="user-name">{username}</p>
          <p className="user-role">Administrator</p>
        </div>
      </div>

      <nav className="sidebar-nav">
        <NavLink to="/dashboard" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <LayoutDashboard size={20} />
          <span>Dashboard</span>
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
        <NavLink to="/admin/lookups" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <Settings size={20} />
          <span>Data Lookups</span>
        </NavLink>
        
        {/* Additional links can go here as we build more pages */}
      </nav>

      <div className="sidebar-footer">
        <button onClick={handleLogout} className="btn-logout-sidebar">
          <LogOut size={20} />
          <span>Logout</span>
        </button>
      </div>
    </div>
  );
}
