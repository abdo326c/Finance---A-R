import React, { useState, useEffect } from 'react';
import axios from 'axios';
import DataTable from 'react-data-table-component';
import { GraduationCap, Search, Plus, RefreshCw, Download, AlertTriangle, CheckCircle2, Info, Settings, Save, XCircle } from 'lucide-react';
import './Scholarships.css';

interface Scholarship {
  id: number;
  student_id: number;
  scholarship_type_id: number;
  scholarship_name: string;
  percentage: number;
  term: string;
  academic_year: number;
  is_active: boolean;
  internal_note: string | null;
}

interface LookupData {
  years: number[];
  terms: string[];
  scholarships: Record<string, number>;
}

export default function Scholarships() {
  const [activeTab, setActiveTab] = useState<'manage'|'assign'|'tools'>('manage');
  const [flash, setFlash] = useState<{msg: string, type: 'success'|'error'} | null>(null);
  const [lookups, setLookups] = useState<LookupData | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    try {
      const token = localStorage.getItem('token');
      if (token) {
        const payload = JSON.parse(atob(token.split('.')[1]));
        if (payload.role === 'Admin') setIsAdmin(true);
      }
    } catch (e) {}
    
    // Fetch lookups (terms, years, scholarship types)
    const fetchLookups = async () => {
      try {
        const token = localStorage.getItem('token');
        const res = await axios.get('http://127.0.0.1:8000/api/lookups', {
          headers: { Authorization: `Bearer ${token}` }
        });
        setLookups(res.data);
      } catch (e) {
        console.error(e);
      }
    };
    fetchLookups();
  }, []);

  const showFlash = (msg: string, type: 'success'|'error') => {
    setFlash({ msg, type });
    setTimeout(() => setFlash(null), 4000);
  };

  return (
    <div className="scholarships-container">
      <header className="page-header">
        <h1 className="page-title"><GraduationCap size={28} /> Student Scholarships Management</h1>
        <p className="page-subtitle">Assign scholarships, manage student coverage limits, and synchronize past discounts.</p>
      </header>

      {flash && (
        <div className={`flash-message ${flash.type} animate-fade-in`}>
          {flash.type === 'error' ? <AlertTriangle size={20} /> : <CheckCircle2 size={20} />}
          <span>{flash.msg}</span>
        </div>
      )}

      <div className="tabs-container">
        <button className={`tab-btn ${activeTab === 'manage' ? 'active' : ''}`} onClick={() => setActiveTab('manage')}>Search & Manage</button>
        <button className={`tab-btn ${activeTab === 'assign' ? 'active' : ''}`} onClick={() => setActiveTab('assign')}>Assign Scholarship</button>
        <button className={`tab-btn ${activeTab === 'tools' ? 'active' : ''}`} onClick={() => setActiveTab('tools')}>Tools & Reports</button>
      </div>

      <div className="tab-content glass-panel">
        {activeTab === 'manage' && <ManageTab lookups={lookups} isAdmin={isAdmin} showFlash={showFlash} />}
        {activeTab === 'assign' && <AssignTab lookups={lookups} showFlash={showFlash} />}
        {activeTab === 'tools' && <ToolsTab lookups={lookups} showFlash={showFlash} />}
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// MANAGE TAB
// -----------------------------------------------------------------------------
function ManageTab({ lookups, isAdmin, showFlash }: any) {
  const [studentId, setStudentId] = useState('');
  const [term, setTerm] = useState(lookups?.terms[0] || 'Spring');
  const [year, setYear] = useState<number>(lookups?.years[0] || new Date().getFullYear());
  const [scholarships, setScholarships] = useState<Scholarship[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  // Edit Note State
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editNote, setEditNote] = useState('');

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!studentId || !term || !year) return;
    
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get(`http://127.0.0.1:8000/api/scholarships/student/${studentId}`, {
        params: { term, year },
        headers: { Authorization: `Bearer ${token}` }
      });
      setScholarships(res.data);
      setSearched(true);
    } catch (err) {
      showFlash('Failed to fetch scholarships', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleActive = async (sch: Scholarship, newStatus: boolean, reversePast: boolean = false) => {
    if (reversePast && !window.confirm(`Are you sure you want to stop and REVERSE past discounts for ${sch.scholarship_name}?`)) return;
    try {
      const token = localStorage.getItem('token');
      await axios.put(`http://127.0.0.1:8000/api/scholarships/${sch.id}`, {
        is_active: newStatus,
        reverse_past: reversePast
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      showFlash(`Scholarship ${newStatus ? 'activated' : 'stopped'} successfully`, 'success');
      // Refresh
      document.getElementById('search-btn')?.click();
    } catch (err: any) {
      showFlash(err.response?.data?.detail || 'Failed to update scholarship', 'error');
    }
  };

  const handleSaveNote = async (sch: Scholarship) => {
    try {
      const token = localStorage.getItem('token');
      await axios.put(`http://127.0.0.1:8000/api/scholarships/${sch.id}`, {
        internal_note: editNote
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      showFlash('Internal note updated', 'success');
      setEditingId(null);
      document.getElementById('search-btn')?.click();
    } catch (err) {
      showFlash('Failed to save note', 'error');
    }
  };

  const totalActivePct = scholarships.filter(s => s.is_active).reduce((sum, s) => sum + s.percentage, 0);

  return (
    <div className="manage-tab">
      <form className="search-bar" onSubmit={handleSearch}>
        <div className="form-group flex-1">
          <input type="text" placeholder="Student ID (e.g. 26100123)" value={studentId} onChange={e => setStudentId(e.target.value)} required />
        </div>
        <div className="form-group flex-1">
          <select value={term} onChange={e => setTerm(e.target.value)} required>
            {lookups?.terms?.map((t: string) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div className="form-group flex-1">
          <input type="number" placeholder="Year" value={year} onChange={e => setYear(Number(e.target.value))} required />
        </div>
        <button id="search-btn" type="submit" className="btn-primary"><Search size={18} /> Load</button>
      </form>

      {loading && <div className="spinner-large mt-4"></div>}

      {!loading && searched && (
        <div className="sch-results animate-fade-in mt-4">
          {scholarships.length === 0 ? (
            <div className="empty-state-small">No scholarships found for this term.</div>
          ) : (
            <>
              {/* Gauge */}
              <div className="gauge-container mb-4">
                <h4>🎓 Scholarship Stacking Gauge</h4>
                <div className="progress-bg">
                  <div 
                    className={`progress-fill ${totalActivePct > 100 ? 'bg-danger' : 'bg-success'}`} 
                    style={{ width: `${Math.min(totalActivePct, 100)}%` }}
                  ></div>
                </div>
                {totalActivePct <= 100 ? (
                  <p className="gauge-text">Combined active scholarships cover <strong>{totalActivePct}%</strong> of tuition. Student pays {100 - totalActivePct}%.</p>
                ) : (
                  <p className="gauge-text text-danger"><strong>⚠️ Capping Alert:</strong> Combined active scholarships ({totalActivePct}%) exceed the 100% cap. Excess will be capped at 100% during invoice runs.</p>
                )}
              </div>

              {/* List */}
              <div className="sch-list">
                {scholarships.map(sch => (
                  <div key={sch.id} className="sch-item">
                    <div className="sch-item-header">
                      <div>
                        <span className="sch-name">{sch.scholarship_name}</span>
                        <span className="sch-pct">{sch.percentage}%</span>
                      </div>
                      <span className={`status-badge ${sch.is_active ? 'active' : 'inactive'}`}>
                        {sch.is_active ? '✅ Active' : '🔴 Inactive'}
                      </span>
                    </div>
                    <div className="sch-item-body">
                      {editingId === sch.id ? (
                        <div className="edit-note-form">
                          <input type="text" value={editNote} onChange={e => setEditNote(e.target.value)} placeholder="Internal Note (Hidden from PDF)" />
                          <button className="btn-icon text-success" onClick={() => handleSaveNote(sch)}><Save size={18} /></button>
                          <button className="btn-icon" onClick={() => setEditingId(null)}><XCircle size={18} /></button>
                        </div>
                      ) : (
                        <div className="note-display">
                          {sch.internal_note ? (
                            <span className="note-text"><Info size={14} /> Note: {sch.internal_note}</span>
                          ) : (
                            <span className="note-empty">No internal note</span>
                          )}
                          <button className="btn-link" onClick={() => { setEditingId(sch.id); setEditNote(sch.internal_note || ''); }}>Edit Note</button>
                        </div>
                      )}
                      
                      <div className="sch-item-actions">
                        {sch.is_active ? (
                          <>
                            <button className="btn-secondary" onClick={() => handleToggleActive(sch, false)}>Stop (future only)</button>
                            {isAdmin && (
                              <button className="btn-secondary text-danger" onClick={() => handleToggleActive(sch, false, true)}>Stop & Reverse Past</button>
                            )}
                          </>
                        ) : (
                          <button className="btn-primary" onClick={() => handleToggleActive(sch, true)}>Activate</button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// ASSIGN TAB
// -----------------------------------------------------------------------------
function AssignTab({ lookups, showFlash }: any) {
  const [studentId, setStudentId] = useState('');
  const [term, setTerm] = useState(lookups?.terms[0] || 'Spring');
  const [year, setYear] = useState<number>(lookups?.years[0] || new Date().getFullYear());
  const [schType, setSchType] = useState('');
  const [percentage, setPercentage] = useState<number>(0);
  const [note, setNote] = useState('');
  const [siblingId, setSiblingId] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const schTypes = lookups?.scholarships ? Object.keys(lookups.scholarships) : [];

  const handleAssign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!studentId || !schType || !percentage) return;

    setSubmitting(true);
    try {
      const token = localStorage.getItem('token');
      await axios.post('http://127.0.0.1:8000/api/scholarships', {
        student_id: Number(studentId),
        scholarship_type_id: lookups.scholarships[schType],
        percentage: Number(percentage),
        term,
        academic_year: year,
        internal_note: note,
        sibling_id: siblingId ? Number(siblingId) : null
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      showFlash('Scholarship assigned successfully!', 'success');
      setStudentId('');
      setPercentage(0);
      setNote('');
      setSiblingId('');
    } catch (err: any) {
      showFlash(err.response?.data?.detail || 'Failed to assign scholarship', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="assign-tab">
      <form className="assign-form" onSubmit={handleAssign}>
        <div className="form-row">
          <div className="form-group">
            <label>Student ID</label>
            <input type="number" required placeholder="e.g. 251000120" value={studentId} onChange={e => setStudentId(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Term</label>
            <select value={term} onChange={e => setTerm(e.target.value)}>
              {lookups?.terms?.map((t: string) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Year</label>
            <input type="number" required value={year} onChange={e => setYear(Number(e.target.value))} />
          </div>
        </div>
        
        <div className="form-row">
          <div className="form-group">
            <label>Scholarship Type</label>
            <select required value={schType} onChange={e => setSchType(e.target.value)}>
              <option value="">-- Select Type --</option>
              {schTypes.map((t: string) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Percentage (0-100)</label>
            <input type="number" required min="0" max="100" step="5" value={percentage} onChange={e => setPercentage(Number(e.target.value))} />
          </div>
        </div>

        {schType === 'SCH: Sibiling %' && (
          <div className="form-group mb-4">
            <label className="text-warning">⚠️ Sibling ID (Required)</label>
            <input type="number" required placeholder="e.g. 25100999" value={siblingId} onChange={e => setSiblingId(e.target.value)} />
          </div>
        )}

        <div className="form-group mb-4">
          <label>Internal Note (Hidden from PDF)</label>
          <input type="text" placeholder="e.g. Approved by Dean on May 2026" value={note} onChange={e => setNote(e.target.value)} />
        </div>

        <button type="submit" className="btn-primary w-100" disabled={submitting}>
          {submitting ? <div className="spinner-small"></div> : <Plus size={18} />} Assign Scholarship
        </button>
      </form>
    </div>
  );
}

// -----------------------------------------------------------------------------
// TOOLS TAB
// -----------------------------------------------------------------------------
function ToolsTab({ lookups, showFlash }: any) {
  const [term, setTerm] = useState(lookups?.terms[0] || 'Spring');
  const [year, setYear] = useState<number>(lookups?.years[0] || new Date().getFullYear());
  const [syncing, setSyncing] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const token = localStorage.getItem('token');
      const res = await axios.post('http://127.0.0.1:8000/api/scholarships/sync', {
        term, year
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      showFlash(res.data.message, 'success');
    } catch (err) {
      showFlash('Sync failed', 'error');
    } finally {
      setSyncing(false);
    }
  };

  const handleReport = async () => {
    setDownloading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get('http://127.0.0.1:8000/api/scholarships/report/data', {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      // Simple CSV export
      const data = res.data;
      if (!data || !data.length) {
        showFlash("No data found for report", "error");
        return;
      }
      
      const keys = Object.keys(data[0]);
      const csv = [
        keys.join(','),
        ...data.map((row: any) => keys.map(k => `"${String(row[k]).replace(/"/g, '""')}"`).join(','))
      ].join('\n');
      
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.setAttribute("href", url);
      link.setAttribute("download", `Scholarships_Report_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      showFlash('Failed to generate report', 'error');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="tools-tab">
      <div className="tools-grid">
        <div className="tool-card">
          <div className="tool-header">
            <h3><RefreshCw size={20} /> Sync & Recalculate</h3>
          </div>
          <div className="tool-body">
            <p>Scan a specific term and apply any missing retroactive discounts for currently active scholarships.</p>
            <div className="form-row mt-3">
              <div className="form-group flex-1">
                <select value={term} onChange={e => setTerm(e.target.value)}>
                  {lookups?.terms?.map((t: string) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="form-group flex-1">
                <input type="number" value={year} onChange={e => setYear(Number(e.target.value))} />
              </div>
            </div>
            <button className="btn-primary w-100 mt-3" onClick={handleSync} disabled={syncing}>
              {syncing ? <div className="spinner-small"></div> : 'Run Sync'}
            </button>
          </div>
        </div>

        <div className="tool-card">
          <div className="tool-header">
            <h3><Download size={20} /> Scholarships Report</h3>
          </div>
          <div className="tool-body">
            <p>Generate a comprehensive CSV report comparing configured scholarship percentages against actual billed tuition and discounts.</p>
            <button className="btn-secondary w-100 mt-4" onClick={handleReport} disabled={downloading}>
              {downloading ? <div className="spinner-small"></div> : 'Generate Report'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
