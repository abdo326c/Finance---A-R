import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Shield, Users, Wrench, Settings, FileText, Upload, UserPlus } from 'lucide-react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import './Admin.css';

const COLORS = ['#0d47a1', '#00897b', '#fb8c00', '#5e35b1', '#e53935'];

export default function Admin() {
  const [activeTab, setActiveTab] = useState('users');
  const [users, setUsers] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [settings, setSettings] = useState<any>(null);
  
  // New user state
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState('User');

  useEffect(() => {
    fetchUsers();
    fetchLogs();
    fetchSettings();
  }, []);

  const fetchUsers = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get('http://127.0.0.1:8000/api/admin/users', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUsers(res.data);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchLogs = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get('http://127.0.0.1:8000/api/admin/audit-logs', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setLogs(res.data);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchSettings = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get('http://127.0.0.1:8000/api/lookups/manage', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSettings(res.data);
    } catch (e) {
      console.error(e);
    }
  };

  const handleUpdateUser = async (userId: number, role: string, isActive: boolean, password?: string) => {
    try {
      const token = localStorage.getItem('token');
      await axios.put(`http://127.0.0.1:8000/api/admin/users/${userId}`, {
        role,
        is_active: isActive,
        password: password || undefined
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      alert('User updated successfully');
      fetchUsers();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to update user');
    }
  };

  const handleCreateUser = async () => {
    if (!newUsername || !newPassword) return alert("Username and Password required");
    try {
      const token = localStorage.getItem('token');
      await axios.post('http://127.0.0.1:8000/api/admin/users', {
        username: newUsername,
        password: newPassword,
        role: newRole
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setNewUsername('');
      setNewPassword('');
      alert('User created successfully');
      fetchUsers();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to create user');
    }
  };

  const runFix = async (endpoint: string) => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.post(`http://127.0.0.1:8000/api/admin/fixes/${endpoint}`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      alert(res.data.message);
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Fix failed');
    }
  };

  const handleBulkDimensions = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const token = localStorage.getItem('token');
      const res = await axios.post('http://127.0.0.1:8000/api/admin/fixes/bulk-dimensions', formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      alert(res.data.message);
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Upload failed');
    }
    // reset file input
    e.target.value = '';
  };

  const saveSetting = async (key: string, valuesStr: string) => {
    try {
      const values = valuesStr.split(',').map(s => s.trim()).filter(s => s);
      const token = localStorage.getItem('token');
      await axios.put(`http://127.0.0.1:8000/api/lookups/manage/${key}`, { values }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      alert('Settings saved successfully');
      fetchSettings();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to save settings');
    }
  };

  // Prepare chart data
  const actionCounts = logs.reduce((acc: any, log: any) => {
    acc[log.action] = (acc[log.action] || 0) + 1;
    return acc;
  }, {});
  const actionChartData = Object.keys(actionCounts).map(k => ({ name: k, value: actionCounts[k] }));

  const userCounts = logs.reduce((acc: any, log: any) => {
    acc[log.user] = (acc[log.user] || 0) + 1;
    return acc;
  }, {});
  const userChartData = Object.keys(userCounts).map(k => ({ name: k, count: userCounts[k] })).sort((a,b) => b.count - a.count).slice(0,10);

  return (
    <div className="admin-page" style={{ padding: '24px' }}>
      <div className="page-header">
        <h1><Shield size={28} style={{ marginRight: '10px' }} /> System Administration</h1>
        <p>Manage users, database health, system configs, and view audit logs.</p>
      </div>

      <div className="admin-tabs">
        <button className={`admin-tab ${activeTab === 'users' ? 'active' : ''}`} onClick={() => setActiveTab('users')}><Users size={18} /> Manage Users</button>
        <button className={`admin-tab ${activeTab === 'fixes' ? 'active' : ''}`} onClick={() => setActiveTab('fixes')}><Wrench size={18} /> Database Fixes</button>
        <button className={`admin-tab ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => setActiveTab('settings')}><Settings size={18} /> System Settings</button>
        <button className={`admin-tab ${activeTab === 'audit' ? 'active' : ''}`} onClick={() => setActiveTab('audit')}><FileText size={18} /> Audit Logs</button>
      </div>

      {activeTab === 'users' && (
        <div className="animate-fade-in">
          <div className="glass-panel" style={{ padding: '24px', marginBottom: '24px' }}>
            <h3 style={{ marginTop: 0, display: 'flex', alignItems: 'center', gap: '8px' }}><UserPlus size={20}/> Add New User</h3>
            <div style={{ display: 'flex', gap: '15px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <div className="form-group" style={{ flex: 1, minWidth: '200px' }}>
                <label>Username</label>
                <input type="text" value={newUsername} onChange={e => setNewUsername(e.target.value)} />
              </div>
              <div className="form-group" style={{ flex: 1, minWidth: '200px' }}>
                <label>Password</label>
                <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} />
              </div>
              <div className="form-group" style={{ flex: 1, minWidth: '150px' }}>
                <label>Role</label>
                <select value={newRole} onChange={e => setNewRole(e.target.value)}>
                  <option value="Admin">Admin</option>
                  <option value="Editor">Editor</option>
                  <option value="Viewer">Viewer</option>
                </select>
              </div>
              <button className="btn-primary" onClick={handleCreateUser} style={{ height: '42px', marginBottom: '4px' }}>Create User</button>
            </div>
          </div>

          <h3 style={{ marginTop: '30px' }}>Existing Users</h3>
          <div className="users-grid">
            {users.map(u => (
              <div key={u.id} className="user-card">
                <div className="user-header">
                  <div className="user-title">
                    <span style={{ fontSize: '20px' }}>👤</span> {u.username}
                  </div>
                  <span className={`badge ${u.is_active ? 'badge-active' : 'badge-inactive'}`}>
                    {u.is_active ? 'Active' : 'Disabled'}
                  </span>
                </div>
                
                <div className="user-form-grid">
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label>Role</label>
                    <select 
                      defaultValue={u.role} 
                      onChange={(e) => handleUpdateUser(u.id, e.target.value, u.is_active)}
                    >
                      <option value="Admin">Admin</option>
                      <option value="Editor">Editor</option>
                      <option value="Viewer">Viewer</option>
                    </select>
                  </div>
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '5px' }}>
                    <input 
                      type="checkbox" 
                      id={`active-${u.id}`} 
                      defaultChecked={u.is_active}
                      onChange={(e) => handleUpdateUser(u.id, u.role, e.target.checked)}
                    />
                    <label htmlFor={`active-${u.id}`} style={{ margin: 0, cursor: 'pointer' }}>Account Active</label>
                  </div>
                  
                  <div className="form-group" style={{ marginTop: '10px', marginBottom: 0 }}>
                    <label>Reset Password (leave blank to keep current)</label>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <input 
                        type="password" 
                        placeholder="New Password" 
                        id={`pwd-${u.id}`}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            const val = (e.target as HTMLInputElement).value;
                            if (val) handleUpdateUser(u.id, u.role, u.is_active, val);
                          }
                        }}
                      />
                      <button 
                        className="btn-secondary" 
                        onClick={() => {
                          const val = (document.getElementById(`pwd-${u.id}`) as HTMLInputElement).value;
                          if (val) handleUpdateUser(u.id, u.role, u.is_active, val);
                        }}
                      >Save</button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'fixes' && (
        <div className="animate-fade-in">
          <div className="fix-card">
            <div className="fix-header">
              <span style={{ fontSize: '24px' }}>🧹</span>
              <h3>College Name Normalisation</h3>
            </div>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '15px' }}>Strips whitespace and uppercases all college codes in the students table.</p>
            <button className="btn-primary" onClick={() => runFix('college-names')}>Run Fix</button>
          </div>

          <div className="fix-card">
            <div className="fix-header">
              <span style={{ fontSize: '24px' }}>🔢</span>
              <h3>Scholarship Percentage Normalisation</h3>
            </div>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '15px' }}>Converts any percentage stored as a decimal (0.60 → 60.0) to 0–100 format.</p>
            <button className="btn-primary" onClick={() => runFix('scholarships')}>Normalise Percentages</button>
          </div>

          <div className="fix-card">
            <div className="fix-header">
              <span style={{ fontSize: '24px' }}>🛠️</span>
              <h3>Bulk Update: Financial Dimensions (D365)</h3>
            </div>
            <p style={{ color: 'var(--text-secondary)' }}>Upload an Excel file with exactly two columns: 'ID' and 'Dimension' to sync with the database in batches of 2000.</p>
            
            <label htmlFor="dim-upload" className="upload-zone" style={{ display: 'block' }}>
              <Upload size={32} style={{ color: '#3b82f6', marginBottom: '10px' }} />
              <div style={{ fontWeight: 'bold' }}>Click to Browse Excel File (.xlsx)</div>
              <div style={{ fontSize: '12px', color: 'gray', marginTop: '5px' }}>Data will be processed and saved automatically</div>
            </label>
            <input 
              type="file" 
              id="dim-upload" 
              accept=".xlsx" 
              style={{ display: 'none' }}
              onChange={handleBulkDimensions}
            />
          </div>
        </div>
      )}

      {activeTab === 'settings' && settings && (
        <div className="animate-fade-in glass-panel" style={{ padding: '24px' }}>
          <h3>System Settings & Configurations</h3>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '24px' }}>Dynamic system parameters (changes reflect instantly throughout the system).</p>
          
          <div className="form-group">
            <label>Valid Colleges (comma-separated)</label>
            <div style={{ display: 'flex', gap: '10px' }}>
              <input 
                type="text" 
                defaultValue={(settings.VALID_COLLEGES || []).join(', ')} 
                id="cfg-colleges"
              />
              <button className="btn-secondary" onClick={() => saveSetting('VALID_COLLEGES', (document.getElementById('cfg-colleges') as HTMLInputElement).value)}>Save</button>
            </div>
          </div>

          <div className="form-group">
            <label>Valid Terms (comma-separated)</label>
            <div style={{ display: 'flex', gap: '10px' }}>
              <input 
                type="text" 
                defaultValue={(settings.VALID_TERMS || []).join(', ')} 
                id="cfg-terms"
              />
              <button className="btn-secondary" onClick={() => saveSetting('VALID_TERMS', (document.getElementById('cfg-terms') as HTMLInputElement).value)}>Save</button>
            </div>
          </div>

          <div className="form-group">
            <label>Valid Student Statuses (comma-separated)</label>
            <div style={{ display: 'flex', gap: '10px' }}>
              <textarea 
                defaultValue={(settings.VALID_STATUSES || []).join(', ')} 
                id="cfg-statuses"
                rows={3}
                style={{ width: '100%', background: 'var(--bg-color)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '10px', fontFamily: 'inherit' }}
              />
              <button className="btn-secondary" onClick={() => saveSetting('VALID_STATUSES', (document.getElementById('cfg-statuses') as HTMLTextAreaElement).value)}>Save</button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'audit' && (
        <div className="animate-fade-in">
          <div className="audit-stats">
            <div className="audit-chart-container">
              <h4 style={{ textAlign: 'center', margin: '0 0 15px 0' }}>🎛️ Logs Count by Action Type</h4>
              <ResponsiveContainer width="100%" height="90%">
                <PieChart>
                  <Pie
                    data={actionChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {actionChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#1a1f2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }} />
                  <Legend verticalAlign="bottom" height={36}/>
                </PieChart>
              </ResponsiveContainer>
            </div>
            
            <div className="audit-chart-container">
              <h4 style={{ textAlign: 'center', margin: '0 0 15px 0' }}>👥 User Activity Volume</h4>
              <ResponsiveContainer width="100%" height="90%">
                <BarChart data={userChartData} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis type="number" stroke="rgba(255,255,255,0.5)" />
                  <YAxis dataKey="name" type="category" stroke="rgba(255,255,255,0.5)" width={80} />
                  <Tooltip contentStyle={{ background: '#1a1f2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }} cursor={{fill: 'rgba(255,255,255,0.05)'}}/>
                  <Bar dataKey="count" fill="#00897b" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="audit-table-wrapper">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>Target</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l: any) => (
                  <tr key={l.id}>
                    <td style={{ whiteSpace: 'nowrap' }}>{new Date(l.time).toLocaleString()}</td>
                    <td>{l.user}</td>
                    <td><span style={{ background: 'rgba(255,255,255,0.1)', padding: '3px 8px', borderRadius: '4px', fontSize: '12px' }}>{l.action}</span></td>
                    <td>{l.target}</td>
                    <td>{l.detail}</td>
                  </tr>
                ))}
                {logs.length === 0 && <tr><td colSpan={5} style={{ textAlign: 'center', color: 'gray' }}>No audit logs found.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
