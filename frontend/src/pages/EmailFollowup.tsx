import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Mail, Settings, Users, Send, FileText } from 'lucide-react';

export default function EmailFollowup() {
  const [smtpServer, setSmtpServer] = useState('smtp.gmail.com');
  const [smtpPort, setSmtpPort] = useState(587);
  const [senderEmail, setSenderEmail] = useState('');
  const [senderPassword, setSenderPassword] = useState('');
  
  const [balanceScope, setBalanceScope] = useState('Total Historical Balance (All Terms)');
  const [term, setTerm] = useState('Spring');
  const [year, setYear] = useState(2026);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [selectedStudents, setSelectedStudents] = useState<any[]>([]);
  
  const [subject, setSubject] = useState('Nile University - Statement of Account Update');
  const [body, setBody] = useState(`Dear {name},

Please find attached your detailed Statement of Account for {scope} as of {date}.

Your outstanding balance for this period is {balance} EGP. Kindly review the attached PDF for full transaction details.

Best Regards,
Finance Department
Nile University`);

  const [previewData, setPreviewData] = useState<any>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState<any>(null);

  const searchStudents = async () => {
    if (!searchQuery) return;
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/lookups/students/search?q=${searchQuery}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSearchResults(res.data);
    } catch (e) {
      console.error(e);
    }
  };

  const addStudent = (student: any) => {
    if (!selectedStudents.find(s => s.id === student.id)) {
      setSelectedStudents([...selectedStudents, student]);
    }
  };
  
  const removeStudent = (id: number) => {
    setSelectedStudents(selectedStudents.filter(s => s.id !== id));
  };

  useEffect(() => {
    if (selectedStudents.length > 0) {
      updatePreview(selectedStudents[0].id);
    } else {
      setPreviewData(null);
    }
  }, [selectedStudents, subject, body, balanceScope, term, year]);

  const updatePreview = async (studentId: number) => {
    setLoadingPreview(true);
    try {
      const token = localStorage.getItem('token');
      const res = await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/email/preview`, {
        student_id: studentId,
        balance_scope: balanceScope,
        term: term,
        year: year,
        subject: subject,
        body: body
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPreviewData(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleSend = async () => {
    if (!senderEmail || !senderPassword) {
      alert("Please configure SMTP settings.");
      return;
    }
    if (selectedStudents.length === 0) {
      alert("Please select at least one student.");
      return;
    }
    
    setSending(true);
    setSendResult(null);
    
    try {
      const token = localStorage.getItem('token');
      const res = await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/email/send`, {
        student_ids: selectedStudents.map(s => s.id),
        balance_scope: balanceScope,
        term: term,
        year: year,
        subject: subject,
        body: body,
        smtp_server: smtpServer,
        smtp_port: smtpPort,
        sender_email: senderEmail,
        sender_password: senderPassword
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSendResult(res.data);
    } catch (e: any) {
      alert(e.response?.data?.detail || "Failed to send emails.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="operations-page animate-fade-in" style={{ padding: '24px' }}>
      <div className="page-header">
        <h1><Mail size={28} style={{ marginRight: '10px' }} /> Automated Email Follow-up</h1>
        <p>Send real-time statement of accounts with detailed PDF attachments to students.</p>
      </div>

      <div className="glass-panel" style={{ padding: '24px', marginBottom: '24px' }}>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: 0 }}><Settings size={18} /> SMTP Settings</h3>
        <div style={{ display: 'flex', gap: '15px', flexWrap: 'wrap' }}>
          <div className="form-group" style={{ flex: 1, minWidth: '200px' }}>
            <label>Sender Email</label>
            <input type="email" value={senderEmail} onChange={e => setSenderEmail(e.target.value)} placeholder="abdo.325c@gmail.com" />
          </div>
          <div className="form-group" style={{ flex: 1, minWidth: '200px' }}>
            <label>App Password</label>
            <input type="password" value={senderPassword} onChange={e => setSenderPassword(e.target.value)} placeholder="••••••••••••••••" />
          </div>
          <div className="form-group" style={{ flex: 1, minWidth: '200px' }}>
            <label>SMTP Server</label>
            <input type="text" value={smtpServer} onChange={e => setSmtpServer(e.target.value)} />
          </div>
          <div className="form-group" style={{ width: '100px' }}>
            <label>Port</label>
            <input type="number" value={smtpPort} onChange={e => setSmtpPort(Number(e.target.value))} />
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 400px' }}>
          <div className="glass-panel" style={{ padding: '24px', marginBottom: '24px' }}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: 0 }}><Users size={18} /> Select Students</h3>
            
            <div className="form-group">
              <label>Search Student (ID or Name)</label>
              <div style={{ display: 'flex', gap: '10px' }}>
                <input 
                  type="text" 
                  value={searchQuery} 
                  onChange={e => setSearchQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && searchStudents()}
                />
                <button onClick={searchStudents} className="btn-secondary">Search</button>
              </div>
            </div>
            
            {searchResults.length > 0 && (
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px', borderRadius: '8px', maxHeight: '150px', overflowY: 'auto', marginBottom: '15px' }}>
                {searchResults.map(s => (
                  <div key={s.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                    <span>{s.id} - {s.name}</span>
                    <button onClick={() => addStudent(s)} style={{ background: '#3b82f6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', padding: '2px 8px' }}>Add</button>
                  </div>
                ))}
              </div>
            )}
            
            <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Selected ({selectedStudents.length})</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '10px' }}>
              {selectedStudents.map(s => (
                <div key={s.id} style={{ background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)', padding: '4px 10px', borderRadius: '15px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '5px' }}>
                  {s.id} - {s.name.split(' ')[0]}
                  <span onClick={() => removeStudent(s.id)} style={{ cursor: 'pointer', color: '#ff5f56', fontWeight: 'bold' }}>×</span>
                </div>
              ))}
              {selectedStudents.length === 0 && <span style={{ color: 'gray', fontSize: '12px' }}>No students selected</span>}
            </div>
          </div>
          
          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 style={{ marginTop: 0 }}>Template Editor</h3>
            <p style={{ fontSize: '12px', color: 'gray' }}>Placeholders: {'{name}, {id}, {balance}, {date}, {scope}'}</p>
            
            <div className="form-group">
              <label>Subject</label>
              <input type="text" value={subject} onChange={e => setSubject(e.target.value)} />
            </div>
            
            <div className="form-group">
              <label>Message Body</label>
              <textarea value={body} onChange={e => setBody(e.target.value)} rows={10} style={{ width: '100%', background: 'var(--bg-color)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '10px', fontFamily: 'inherit' }} />
            </div>
          </div>
        </div>

        <div style={{ flex: '1 1 400px' }}>
          <div className="glass-panel" style={{ padding: '24px', height: '100%', display: 'flex', flexDirection: 'column' }}>
            <h3 style={{ marginTop: 0 }}>Live Preview</h3>
            
            {loadingPreview ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}><div className="spinner"></div></div>
            ) : previewData ? (
              <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-color)', borderRadius: '12px', overflow: 'hidden' }}>
                <div style={{ padding: '15px', borderBottom: '1px solid var(--border-color)' }}>
                  <div style={{ marginBottom: '8px', fontSize: '13px' }}><strong style={{ color: 'gray', width: '60px', display: 'inline-block' }}>To:</strong> {previewData.student_name} &lt;{previewData.student_email}&gt;</div>
                  <div style={{ fontSize: '13px' }}><strong style={{ color: 'gray', width: '60px', display: 'inline-block' }}>Subject:</strong> {previewData.formatted_subject}</div>
                </div>
                <div style={{ padding: '20px', fontSize: '14px', whiteSpace: 'pre-line' }}>
                  {previewData.formatted_body}
                  <div style={{ marginTop: '20px', padding: '10px', background: 'rgba(59, 130, 246, 0.05)', border: '1px solid rgba(59, 130, 246, 0.2)', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ background: '#3b82f6', color: 'white', padding: '5px', borderRadius: '4px' }}><FileText size={16} /></div>
                    <span style={{ fontSize: '12px' }}>Statement_{selectedStudents[0].id}.pdf</span>
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ padding: '40px', textAlign: 'center', color: 'gray' }}>Select a student to see the live preview.</div>
            )}
            
            <div style={{ marginTop: 'auto', paddingTop: '20px' }}>
              <button 
                onClick={handleSend} 
                className="btn-primary" 
                style={{ width: '100%', justifyContent: 'center', height: '45px' }}
                disabled={sending || selectedStudents.length === 0}
              >
                {sending ? <div className="spinner-small"></div> : <><Send size={18} /> Send {selectedStudents.length} Follow-up Emails</>}
              </button>
              
              {sendResult && (
                <div style={{ marginTop: '15px', padding: '15px', borderRadius: '8px', background: sendResult.success_count > 0 ? 'rgba(39, 201, 63, 0.1)' : 'rgba(255, 95, 86, 0.1)', border: `1px solid ${sendResult.success_count > 0 ? 'rgba(39, 201, 63, 0.3)' : 'rgba(255, 95, 86, 0.3)'}` }}>
                  <div style={{ color: sendResult.success_count > 0 ? '#27c93f' : '#ff5f56', fontWeight: 'bold' }}>
                    ✅ Sent: {sendResult.success_count} emails
                  </div>
                  <div style={{ color: 'gray', fontSize: '13px', marginTop: '5px' }}>
                    ⏭️ Skipped: {sendResult.skipped_count} (zero balance or no email)
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
