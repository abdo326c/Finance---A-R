import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Shield, Users, Wrench, Settings, FileText, Upload, UserPlus, Plus, Trash2 } from 'lucide-react';
import DataTable from 'react-data-table-component';
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

  const [scholarshipMappings, setScholarshipMappings] = useState<any[]>([]);

  useEffect(() => {
    fetchUsers();
    fetchLogs();
    fetchSettings();
    fetchMappings();
  }, []);

  const fetchUsers = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/admin/users`, {
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
      const res = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/admin/audit-logs`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setLogs(res.data.items || res.data || []);
    } catch (e) {
      console.error(e);
    }
  };

  const [scholarshipTypes, setScholarshipTypes] = useState<any[]>([]);
  
  // New lookup inputs
  const [newCollege, setNewCollege] = useState('');
  const [newTerm, setNewTerm] = useState('');
  const [newStatus, setNewStatus] = useState('');
  const [newScholarship, setNewScholarship] = useState('');
  const [newMappingCode, setNewMappingCode] = useState('');
  const [newMappingType, setNewMappingType] = useState('');

  const fetchMappings = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/lookups/scholarship_mappings`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setScholarshipMappings(res.data);
    } catch (e) {
      console.error("Failed to fetch mappings", e);
    }
  };

  const fetchSettings = async () => {
    try {
      const token = localStorage.getItem('token');
      const [lookupsRes, schRes] = await Promise.all([
        axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/lookups/manage`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/lookups/scholarship_types`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setSettings(lookupsRes.data);
      setScholarshipTypes(schRes.data);
    } catch (e) {
      console.error(e);
    }
  };

  const saveList = async (key: string, values: string[]) => {
    try {
      const token = localStorage.getItem('token');
      await axios.put(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/lookups/manage/${key}`, { values }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSettings((prev: any) => ({ ...prev, [key]: values }));
    } catch (err) {
      alert(`Failed to save ${key}.`);
    }
  };

  const handleAddLookup = (key: string, newValue: string, setter: React.Dispatch<React.SetStateAction<string>>) => {
    if (!newValue.trim() || !settings) return;
    if (settings[key].includes(newValue.trim())) return alert("Item already exists!");
    const newList = [...settings[key], newValue.trim()];
    saveList(key, newList);
    setter('');
  };

  const handleDeleteLookup = (key: string, itemToRemove: string) => {
    if (!settings) return;
    if (!window.confirm(`Are you sure you want to remove '${itemToRemove}'?`)) return;
    const newList = settings[key].filter((i: string) => i !== itemToRemove);
    saveList(key, newList);
  };

  const handleAddScholarship = async () => {
    if (!newScholarship.trim()) return;
    try {
      const token = localStorage.getItem('token');
      const res = await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/lookups/scholarship_types`, 
        { name: newScholarship.trim() },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setScholarshipTypes(prev => [...prev, { id: res.data.id, name: res.data.name }]);
      setNewScholarship('');
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to add scholarship");
    }
  };

  const handleDeleteScholarship = async (id: number, name: string) => {
    if (!window.confirm(`Are you sure you want to delete '${name}'?`)) return;
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/lookups/scholarship_types/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setScholarshipTypes(prev => prev.filter(s => s.id !== id));
    } catch (err) {
      alert("Failed to delete scholarship type");
    }
  };

  const customStyles = {
    table: { style: { backgroundColor: 'transparent' } },
    header: { style: { backgroundColor: 'transparent', color: 'var(--text-primary)' } },
    headRow: { style: { backgroundColor: 'var(--surface-hover)', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-color)' } },
    headCells: { style: { fontSize: '0.85rem', fontWeight: 600, textTransform: 'uppercase' as any } },
    rows: {
      style: {
        backgroundColor: 'transparent',
        color: 'var(--text-primary)',
        borderBottom: '1px solid var(--border-color)',
        '&:hover': { backgroundColor: 'var(--surface-hover)' },
      },
    },
    pagination: {
      style: { backgroundColor: 'transparent', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-color)' },
      pageButtonsStyle: { color: 'var(--text-primary)', fill: 'var(--text-primary)' }
    }
  };

  const createColumns = (key: string) => [
    { name: 'Value', selector: (row: { value: string }) => row.value, sortable: true, grow: 2 },
    {
      name: 'Actions',
      cell: (row: { value: string }) => (
        <button className="btn-icon text-danger" onClick={() => handleDeleteLookup(key, row.value)} title="Remove">
          <Trash2 size={16} />
        </button>
      ),
      button: true,
      width: '100px',
    }
  ];

  const schColumns = [
    { name: 'ID', selector: (row: any) => row.id, sortable: true, width: '80px' },
    { name: 'Scholarship Name', selector: (row: any) => row.name, sortable: true, grow: 2 },
    {
      name: 'Actions',
      cell: (row: any) => (
        <button className="btn-icon text-danger" onClick={() => handleDeleteScholarship(row.id, row.name)} title="Remove">
          <Trash2 size={16} />
        </button>
      ),
      button: true,
      width: '100px',
    }
  ];

  const handleUpdateUser = async (userId: number, role: string, isActive: boolean, password?: string) => {
    try {
      const token = localStorage.getItem('token');
      await axios.put(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/admin/users/${userId}`, {
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
      await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/admin/users`, {
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
      const res = await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/admin/fixes/${endpoint}`, {}, {
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
      const res = await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/admin/fixes/bulk-dimensions`, formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      alert(res.data.message);
    } catch (e: any) {
      alert(e.response?.data?.detail || "Failed to upload file");
    } finally {
      e.target.value = '';
    }
  };

  const handleUploadMappings = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const token = localStorage.getItem('token');
      const res = await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/lookups/scholarship_mappings/upload`, formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      alert(res.data.message);
      fetchMappings();
    } catch (e: any) {
      alert(e.response?.data?.detail || "Failed to upload file");
    } finally {
      e.target.value = '';
    }
  };

  const handleAddMapping = async () => {
    if (!newMappingCode.trim() || !newMappingType) return;
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/lookups/scholarship_mappings`, 
        { charge_code: newMappingCode.trim(), scholarship_type_id: parseInt(newMappingType) },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNewMappingCode('');
      setNewMappingType('');
      fetchMappings();
    } catch (e: any) {
      alert(e.response?.data?.detail || "Failed to add mapping");
    }
  };

  const handleDeleteMapping = async (id: number) => {
    if (!window.confirm("Are you sure you want to delete this mapping?")) return;
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/lookups/scholarship_mappings/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      fetchMappings();
    } catch (e) {
      alert("Failed to delete mapping");
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/admin/fixes/template`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'D365_Students_Dimensions_Template.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (e) {
      alert("Failed to download template");
    }
  };

  // The rest of the original functions follow here...

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
            <p style={{ color: 'var(--text-secondary)', marginBottom: '15px' }}>Download the verified Excel template, fill your data, and upload it back to sync with Supabase.</p>
            
            <button className="btn-secondary" style={{ marginBottom: '20px' }} onClick={handleDownloadTemplate}>
              📥 Download Verified Excel Template
            </button>

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
        <div className="animate-fade-in lookups-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
          <div style={{ gridColumn: '1 / -1', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))', gap: '24px' }}>
            <section className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', height: '100%' }}>
              <div className="page-header" style={{ marginBottom: '20px' }}>
                <h3 style={{ margin: 0 }}>Scholarship Types</h3>
              </div>
              <div style={{ display: 'flex', gap: '10px', marginBottom: '15px' }}>
                <input 
                  type="text" 
                  placeholder="New Scholarship Type (e.g. SCH: Excellence %)" 
                  value={newScholarship} 
                  onChange={e => setNewScholarship(e.target.value)} 
                  onKeyDown={e => e.key === 'Enter' && handleAddScholarship()}
                  style={{ flex: 1, maxWidth: '400px' }}
                />
                <button className="btn-primary" onClick={handleAddScholarship} style={{ padding: '0 20px' }}>
                  <Plus size={16} /> Add
                </button>
              </div>
              <div style={{ border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}>
                <DataTable
                  columns={schColumns}
                  data={scholarshipTypes}
                  customStyles={customStyles}
                  pagination
                  paginationPerPage={5}
                  paginationRowsPerPageOptions={[5, 10, 20]}
                  noHeader
                />
              </div>
            </section>

            <section className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ margin: 0 }}>Scholarship Mappings</h3>
              <div>
                <label htmlFor="mapping-upload" className="btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', cursor: 'pointer', padding: '8px 16px', borderRadius: '8px' }}>
                  <Upload size={16} />
                  <span>Bulk Upload (.xlsx)</span>
                </label>
                <input 
                  type="file" 
                  id="mapping-upload" 
                  accept=".xlsx, .xls" 
                  style={{ display: 'none' }}
                  onChange={handleUploadMappings}
                />
              </div>
            </div>
            
            <div style={{ display: 'flex', gap: '10px', marginBottom: '15px' }}>
              <input 
                type="text" 
                placeholder="Charge Code (e.g. MeritHiScl)" 
                value={newMappingCode} 
                onChange={e => setNewMappingCode(e.target.value)} 
                onKeyDown={e => e.key === 'Enter' && handleAddMapping()}
                style={{ flex: 1, maxWidth: '300px' }}
              />
              <select 
                value={newMappingType} 
                onChange={e => setNewMappingType(e.target.value)}
                style={{ flex: 1, maxWidth: '400px', padding: '10px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.2)', background: 'var(--bg-color)', color: 'var(--text-color)' }}
              >
                <option value="">-- Select Scholarship Category --</option>
                {scholarshipTypes.map((st: any) => (
                  <option key={st.id} value={st.id}>{st.name}</option>
                ))}
              </select>
              <button className="btn-primary" onClick={handleAddMapping} style={{ padding: '0 20px' }}>
                <Plus size={16} /> Add
              </button>
            </div>
            
            <div style={{ border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}>
              <DataTable
                columns={[
                  { name: 'Charge Code', selector: (row: any) => row.charge_code, sortable: true },
                  { name: 'Scholarship Category', selector: (row: any) => row.scholarship_type_name, sortable: true },
                  { 
                    name: 'Actions', 
                    cell: (row: any) => (
                      <button 
                        onClick={() => handleDeleteMapping(row.id)}
                        style={{ background: 'none', border: 'none', color: '#dc2626', cursor: 'pointer' }}
                        title="Delete Mapping"
                      >
                        <Trash2 size={16} />
                      </button>
                    ),
                    width: '100px',
                    center: true
                  }
                ]}
                data={scholarshipMappings}
                customStyles={customStyles}
                pagination
                paginationPerPage={5}
                paginationRowsPerPageOptions={[5, 10, 20]}
                noHeader
              />
            </div>
          </section>
        </div>

        <section className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', height: '100%' }}>
            <h3 style={{ margin: '0 0 20px 0' }}>Registered Colleges</h3>
            <div style={{ display: 'flex', gap: '10px', marginBottom: '15px' }}>
              <input 
                type="text" 
                placeholder="New College (e.g. ENG)" 
                value={newCollege} 
                onChange={e => setNewCollege(e.target.value)} 
                onKeyDown={e => e.key === 'Enter' && handleAddLookup('VALID_COLLEGES', newCollege, setNewCollege)}
                style={{ flex: 1 }}
              />
              <button className="btn-primary" onClick={() => handleAddLookup('VALID_COLLEGES', newCollege, setNewCollege)}>
                <Plus size={16} /> Add
              </button>
            </div>
            <div style={{ border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', maxHeight: '400px', overflowY: 'auto' }}>
              <DataTable
                columns={createColumns('VALID_COLLEGES')}
                data={(settings.VALID_COLLEGES || []).map((v: string) => ({ value: v }))}
                customStyles={customStyles}
                noHeader
              />
            </div>
          </section>

          <section className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', height: '100%' }}>
            <h3 style={{ margin: '0 0 20px 0' }}>Academic Terms</h3>
            <div style={{ display: 'flex', gap: '10px', marginBottom: '15px' }}>
              <input 
                type="text" 
                placeholder="New Term (e.g. Winter)" 
                value={newTerm} 
                onChange={e => setNewTerm(e.target.value)} 
                onKeyDown={e => e.key === 'Enter' && handleAddLookup('VALID_TERMS', newTerm, setNewTerm)}
                style={{ flex: 1 }}
              />
              <button className="btn-primary" onClick={() => handleAddLookup('VALID_TERMS', newTerm, setNewTerm)}>
                <Plus size={16} /> Add
              </button>
            </div>
            <div style={{ border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', maxHeight: '400px', overflowY: 'auto' }}>
              <DataTable
                columns={createColumns('VALID_TERMS')}
                data={(settings.VALID_TERMS || []).map((v: string) => ({ value: v }))}
                customStyles={customStyles}
                noHeader
              />
            </div>
          </section>

          <section className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', height: '100%' }}>
            <h3 style={{ margin: '0 0 20px 0' }}>Student Statuses</h3>
            <div style={{ display: 'flex', gap: '10px', marginBottom: '15px' }}>
              <input 
                type="text" 
                placeholder="New Status (e.g. Graduated)" 
                value={newStatus} 
                onChange={e => setNewStatus(e.target.value)} 
                onKeyDown={e => e.key === 'Enter' && handleAddLookup('VALID_STATUSES', newStatus, setNewStatus)}
                style={{ flex: 1 }}
              />
              <button className="btn-primary" onClick={() => handleAddLookup('VALID_STATUSES', newStatus, setNewStatus)}>
                <Plus size={16} /> Add
              </button>
            </div>
            <div style={{ border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', maxHeight: '400px', overflowY: 'auto' }}>
              <DataTable
                columns={createColumns('VALID_STATUSES')}
                data={(settings.VALID_STATUSES || []).map((v: string) => ({ value: v }))}
                customStyles={customStyles}
                noHeader
              />
            </div>
          </section>

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
