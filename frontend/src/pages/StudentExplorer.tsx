import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Search, Download, FileText, Medal, Edit3, Save, User, Users, GraduationCap, MapPin, Mail, Phone, Calendar, HeartHandshake, CheckCircle } from 'lucide-react';
import './StudentExplorer.css';

const STATUS_COLORS: Record<string, string> = {
  "Active": "background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb;",
  "Semester Withdraw": "background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba;",
  "Inactive": "background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb;",
  "Graduated": "background-color: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb;",
  "Program Withdraw": "background-color: #e2e3e5; color: #383d41; border: 1px solid #d6d8db;",
  "Test": "background-color: #f8f9fa; color: #6c757d; border: 1px dashed #6c757d;"
};

export default function StudentExplorer() {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [profile, setProfile] = useState<any>(null);
  
  const [activeTab, setActiveTab] = useState('profile');
  const [editMode, setEditMode] = useState(false);
  
  const [editData, setEditData] = useState<any>({});
  const [newStatus, setNewStatus] = useState({ term: 'Spring', year: 2026, status: 'Active' });

  // For data lookups
  const [validColleges, setValidColleges] = useState<string[]>([]);
  const [validTerms, setValidTerms] = useState<string[]>([]);
  const [validStatuses, setValidStatuses] = useState<string[]>([]);

  useEffect(() => {
    fetchLookups();
  }, []);

  const fetchLookups = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/lookups`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setValidColleges(res.data.colleges || []);
      setValidTerms(res.data.terms || []);
      setValidStatuses(res.data.statuses || []);
    } catch (e) {
      console.error("Failed to load lookups", e);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery) return;
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/lookups/students/search?q=${searchQuery}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSearchResults(res.data);
    } catch (e: any) {
      console.error(e);
      alert(e.response?.data?.detail || e.message || "Failed to search. Check if backend is running.");
    }
  };

  const loadProfile = async (id: number) => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/explorer/profile/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setProfile(res.data);
      setEditData(res.data.student);
      setSearchResults([]);
      setSearchQuery('');
    } catch (e: any) {
      alert(e.response?.data?.detail || "Failed to load profile");
    }
  };



  const handleSaveMasterData = async () => {
    try {
      const token = localStorage.getItem('token');
      await axios.put(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/explorer/profile/${profile.student.id}`, editData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      alert("Master data updated successfully");
      setEditMode(false);
      loadProfile(profile.student.id);
    } catch (e: any) {
      alert(e.response?.data?.detail || "Failed to save data");
    }
  };

  const handleUpdateStatus = async () => {
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/explorer/status/${profile.student.id}`, newStatus, {
        headers: { Authorization: `Bearer ${token}` }
      });
      alert("Status updated");
      loadProfile(profile.student.id);
    } catch (e) {
      alert("Failed to update status");
    }
  };

  const getInitials = (name: string) => {
    return name ? name.split(' ').slice(0,2).map(n => n[0]).join('').toUpperCase() : 'NU';
  };

  return (
    <div className="page-container explorer-page animate-fade-in">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1><Search size={28} style={{ marginRight: '10px' }} /> Student Data Explorer</h1>
          <p>Comprehensive CRM view for individual student profiles, financials, and master data.</p>
        </div>
        <button className="btn-secondary" onClick={async () => {
          const token = localStorage.getItem('token');
          const res = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/explorer/export`, { headers: { Authorization: `Bearer ${token}` }, responseType: 'blob' });
          const url = window.URL.createObjectURL(new Blob([res.data]));
          const a = document.createElement('a');
          a.href = url;
          a.download = 'All_Students_Master_Data.xlsx';
          a.click();
        }}><Download size={18}/> Export All Students</button>
      </div>

      <div className="glass-panel" style={{ padding: '24px', marginBottom: '24px', position: 'relative', zIndex: 50 }}>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label>Search Student ID, Name, or Email</label>
          <form onSubmit={e => { e.preventDefault(); handleSearch(); }} style={{ display: 'flex', gap: '10px' }}>
            <input 
              type="text" 
              value={searchQuery} 
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="e.g. 211001234, 'Ahmed', or email@nu.edu.eg"
            />
            <button type="submit" className="btn-primary">Search</button>
          </form>
        </div>
        
        {searchResults.length > 0 && (
          <div style={{ position: 'absolute', top: '100%', left: '24px', right: '24px', background: 'var(--surface-color)', border: '1px solid var(--border-color)', borderRadius: '8px', zIndex: 10, maxHeight: '300px', overflowY: 'auto', boxShadow: '0 10px 25px rgba(0,0,0,0.1)' }}>
            {searchResults.map(s => (
              <div 
                key={s.id} 
                onClick={() => loadProfile(s.id)}
                style={{ padding: '12px 20px', borderBottom: '1px solid var(--border-color)', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', transition: 'var(--transition)' }}
                onMouseOver={e => (e.currentTarget.style.background = 'var(--surface-hover)')}
                onMouseOut={e => (e.currentTarget.style.background = 'transparent')}
              >
                <div style={{ fontWeight: 'bold', color: 'var(--text-primary)' }}>{s.id} - {s.name}</div>
                <div style={{ color: 'var(--text-secondary)' }}>{s.email}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {profile && (
        <div className="animate-fade-in">
          {/* Premium Header */}
          <div className="premium-header">
            <div className="avatar-wrapper">
              <div className="premium-avatar">{getInitials(profile.student.name)}</div>
              <div className="student-identity">
                <h2>{profile.student.name}</h2>
                <p>🆔 Student ID: <b>{profile.student.id}</b> &nbsp;|&nbsp; admit: {profile.student.admit_year}</p>
              </div>
            </div>
            
            <div className="balance-wrapper">
              <div className="status-pill" style={{ ...(STATUS_COLORS[profile.status] ? Object.fromEntries(STATUS_COLORS[profile.status].split(';').filter(Boolean).map(s => s.split(':').map(v => v.trim()))) : { backgroundColor: '#e2e3e5', color: '#383d41' }) }}>
                ● {profile.status}
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div style={{ display: 'flex', gap: '15px', marginBottom: '24px' }}>
            <button className="btn-secondary" style={{ flex: 1, justifyContent: 'center' }} onClick={() => {
              const csv = `Student ID,Name,College,Program,Email,Mobile\n${profile.student.id},"${profile.student.name}","${profile.student.college}","${profile.student.program}","${profile.student.email}","${profile.student.mobile}"`;
              const url = window.URL.createObjectURL(new Blob([csv]));
              const a = document.createElement('a'); a.href = url; a.download = `Student_${profile.student.id}_Profile.csv`; a.click();
            }}>
              <Download size={18}/> Export Profile Data
            </button>
          </div>

          {/* Tabs */}
          <div className="admin-tabs">
            <button className={`admin-tab ${activeTab === 'profile' ? 'active' : ''}`} onClick={() => setActiveTab('profile')}><User size={18} /> Profile Details</button>
            <button className={`admin-tab ${activeTab === 'history' ? 'active' : ''}`} onClick={() => setActiveTab('history')}><FileText size={18} /> Academic History</button>
            <button className={`admin-tab ${activeTab === 'scholarships' ? 'active' : ''}`} onClick={() => setActiveTab('scholarships')}><Medal size={18} /> Scholarships</button>
          </div>

          {activeTab === 'profile' && (
            <div className="animate-fade-in">
              <div className="info-card-grid">
                <div className="info-card">
                  <span className="info-card-label"><GraduationCap size={14}/> College</span>
                  <span className="info-card-value">{profile.student.college || '—'}</span>
                </div>
                <div className="info-card">
                  <span className="info-card-label"><FileText size={14}/> Program</span>
                  <span className="info-card-value">{profile.student.program || '—'}</span>
                </div>
                <div className="info-card">
                  <span className="info-card-label">💰 Price / Credit Hour</span>
                  <span className="info-card-value">{profile.student.price_per_hr ? `${profile.student.price_per_hr.toLocaleString()} EGP` : '—'}</span>
                </div>
              </div>

              <div className="details-grid">
                <div className="detail-box">
                  <h4><Mail size={18}/> Contact Details</h4>
                  <div className="detail-row"><b>Email</b> <span>{profile.student.email || '—'}</span></div>
                  <div className="detail-row"><b>Mobile</b> <span>{profile.student.mobile || '—'}</span></div>
                  <div className="detail-row"><b>Admit Year</b> <span>{profile.student.admit_year || '—'}</span></div>
                </div>
                
                <div className="detail-box">
                  <h4><User size={18}/> Identification</h4>
                  <div className="detail-row"><b>National ID</b> <span>{profile.student.national_id || '—'}</span></div>
                  <div className="detail-row"><b>Nationality</b> <span>{profile.student.nationality || '—'}</span></div>
                  <div className="detail-row"><b>Birth Date</b> <span>{profile.student.birth_date || '—'}</span></div>
                </div>
              </div>
              
              <div style={{ display: 'flex', gap: '20px', marginBottom: '20px' }}>
                <div className="glass-panel" style={{ flex: 1, padding: '20px', background: profile.student.is_sponsored ? 'rgba(59, 130, 246, 0.1)' : 'rgba(255,255,255,0.02)' }}>
                  <h4 style={{ margin: '0 0 10px 0', display: 'flex', alignItems: 'center', gap: '8px' }}><HeartHandshake size={18}/> Sponsorship</h4>
                  {profile.student.is_sponsored ? (
                    <div><b>Sponsored Student</b> (By: {profile.student.sponsor_name})</div>
                  ) : (
                    <div>None</div>
                  )}
                </div>
                <div className="glass-panel" style={{ flex: 1, padding: '20px', background: profile.student.sibling_id ? 'rgba(168, 85, 247, 0.1)' : 'rgba(255,255,255,0.02)' }}>
                  <h4 style={{ margin: '0 0 10px 0', display: 'flex', alignItems: 'center', gap: '8px' }}><Users size={18}/> Sibling</h4>
                  {profile.student.sibling_id ? (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <b>Sibling ID: {profile.student.sibling_id}</b>
                      <button className="btn-secondary" style={{ padding: '4px 10px', fontSize: '12px' }} onClick={() => loadProfile(profile.student.sibling_id)}>Jump to Sibling</button>
                    </div>
                  ) : (
                    <div>None</div>
                  )}
                </div>
              </div>
              
              {profile.student.general_notes && (
                <div style={{ padding: '15px', background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.3)', borderRadius: '8px', marginBottom: '24px' }}>
                  <b style={{ color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '5px' }}><FileText size={16}/> General Notes:</b>
                  <p style={{ margin: '5px 0 0 0' }}>{profile.student.general_notes}</p>
                </div>
              )}


              {/* Edit Master Data */}
              {localStorage.getItem('role') !== 'Viewer' && (
                <div style={{ marginBottom: '40px' }}>
                  <button className={`btn-${editMode ? 'primary' : 'secondary'}`} onClick={() => setEditMode(!editMode)}>
                    {editMode ? 'Cancel Editing' : '🔓 Unlock Edit Mode'}
                  </button>
                  
                  {editMode && (
                    <div className="master-data-form animate-fade-in">
                      <h3 style={{ marginTop: 0, display: 'flex', alignItems: 'center', gap: '8px', color: '#ffb300' }}><Edit3 size={20}/> Edit Master Data</h3>
                      
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '15px', marginBottom: '15px' }}>
                        <div className="form-group">
                          <label>Full Name</label>
                          <input type="text" value={editData.name || ''} onChange={e => setEditData({...editData, name: e.target.value})} />
                        </div>
                        <div className="form-group">
                          <label>College</label>
                          <select value={editData.college || ''} onChange={e => setEditData({...editData, college: e.target.value})}>
                            <option value="">-- Select --</option>
                            {validColleges.map(c => <option key={c} value={c}>{c}</option>)}
                          </select>
                        </div>
                        <div className="form-group">
                          <label>Price/Hr (EGP)</label>
                          <input type="number" value={editData.price_per_hr || ''} onChange={e => setEditData({...editData, price_per_hr: parseFloat(e.target.value)})} />
                        </div>
                      </div>
                      
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '15px', marginBottom: '15px' }}>
                        <div className="form-group">
                          <label>Email</label>
                          <input type="email" value={editData.email || ''} onChange={e => setEditData({...editData, email: e.target.value})} />
                        </div>
                        <div className="form-group">
                          <label>Mobile</label>
                          <input type="text" value={editData.mobile || ''} onChange={e => setEditData({...editData, mobile: e.target.value})} />
                        </div>
                        <div className="form-group">
                          <label>Program</label>
                          <input type="text" value={editData.program || ''} onChange={e => setEditData({...editData, program: e.target.value})} />
                        </div>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr 1fr', gap: '15px', marginBottom: '15px', alignItems: 'center' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <input type="checkbox" id="is_sponsored" checked={editData.is_sponsored || false} onChange={e => setEditData({...editData, is_sponsored: e.target.checked})} />
                          <label htmlFor="is_sponsored" style={{ margin: 0, cursor: 'pointer' }}>Is Sponsored?</label>
                        </div>
                        <div className="form-group" style={{ marginBottom: 0 }}>
                          <label>Sponsor Name</label>
                          <input type="text" disabled={!editData.is_sponsored} value={editData.sponsor_name || ''} onChange={e => setEditData({...editData, sponsor_name: e.target.value})} />
                        </div>
                        <div className="form-group" style={{ marginBottom: 0 }}>
                          <label>Sibling ID</label>
                          <input type="text" value={editData.sibling_id || ''} onChange={e => setEditData({...editData, sibling_id: e.target.value})} />
                        </div>
                      </div>
                      
                      <div className="form-group">
                        <label>General Notes (Internal use)</label>
                        <textarea value={editData.general_notes || ''} onChange={e => setEditData({...editData, general_notes: e.target.value})} rows={3} style={{ width: '100%', background: 'var(--bg-color)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '10px', fontFamily: 'inherit' }} />
                      </div>
                      
                      <button className="btn-primary" onClick={handleSaveMasterData} style={{ width: '100%', justifyContent: 'center' }}>
                        <Save size={18}/> Save Master Data Changes
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === 'history' && (
            <div className="glass-panel animate-fade-in" style={{ padding: '24px', marginBottom: '24px' }}>
              <h3 style={{ marginTop: 0 }}>Academic Status History</h3>
              {profile.status_history.length > 0 ? (
                <table className="data-table">
                  <thead><tr><th>Term</th><th>Year</th><th>Status</th></tr></thead>
                  <tbody>
                    {profile.status_history.map((s: any, idx: number) => (
                      <tr key={idx}>
                        <td>{s.term}</td>
                        <td>{s.year}</td>
                        <td><span className="status-pill" style={{ padding: '4px 10px', fontSize: '11px', ...(STATUS_COLORS[s.status] ? Object.fromEntries(STATUS_COLORS[s.status].split(';').filter(Boolean).map(st => st.split(':').map(v => v.trim()))) : {}) }}>{s.status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p style={{ color: 'gray' }}>No status history yet.</p>
              )}
              
              <div style={{ marginTop: '20px', padding: '15px', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}>
                <h4 style={{ margin: '0 0 15px 0' }}>Update / Add Status</h4>
                <div style={{ display: 'flex', gap: '15px', alignItems: 'flex-end' }}>
                  <div className="form-group" style={{ marginBottom: 0, flex: 1 }}>
                    <label>Term</label>
                    <select value={newStatus.term} onChange={e => setNewStatus({...newStatus, term: e.target.value})}>
                      {validTerms.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                  <div className="form-group" style={{ marginBottom: 0, flex: 1 }}>
                    <label>Year</label>
                    <input type="number" value={newStatus.year} onChange={e => setNewStatus({...newStatus, year: parseInt(e.target.value)})} />
                  </div>
                  <div className="form-group" style={{ marginBottom: 0, flex: 1 }}>
                    <label>Status</label>
                    <select value={newStatus.status} onChange={e => setNewStatus({...newStatus, status: e.target.value})}>
                      {validStatuses.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                  <button className="btn-primary" onClick={handleUpdateStatus}>Update</button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'scholarships' && (
            <div className="animate-fade-in glass-panel" style={{ padding: '24px' }}>
              <h3 style={{ marginTop: 0 }}>Scholarships (All Terms)</h3>
              {profile.scholarships.length > 0 ? (
                <table className="data-table">
                  <thead><tr><th>Term</th><th>Year</th><th>Scholarship</th><th>Percentage</th><th>Status</th></tr></thead>
                  <tbody>
                    {profile.scholarships.map((s: any, idx: number) => (
                      <tr key={idx}>
                        <td>{s.term}</td>
                        <td>{s.year}</td>
                        <td>{s.name}</td>
                        <td>{s.percentage.toFixed(1)}%</td>
                        <td><span className={`badge ${s.is_active ? 'badge-active' : 'badge-inactive'}`}>{s.is_active ? '✅ Active' : '❌ Inactive'}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p style={{ color: 'gray' }}>No scholarships found for this student.</p>
              )}
            </div>
          )}

        </div>
      )}
    </div>
  );
}
