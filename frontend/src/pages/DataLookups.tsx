import React, { useState, useEffect } from 'react';
import axios from 'axios';
import DataTable from 'react-data-table-component';
import { Settings, Plus, Trash2, Save, AlertTriangle } from 'lucide-react';
import './DataLookups.css';

interface LookupData {
  VALID_COLLEGES: string[];
  VALID_TERMS: string[];
  VALID_STATUSES: string[];
}

export default function DataLookups() {
  const [data, setData] = useState<LookupData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<{msg: string, type: 'success'|'error'} | null>(null);

  // New item inputs
  const [newCollege, setNewCollege] = useState('');
  const [newTerm, setNewTerm] = useState('');
  const [newStatus, setNewStatus] = useState('');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get('http://127.0.0.1:8000/api/lookups/manage', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setData(res.data);
      setError(null);
    } catch (err: any) {
      if (err.response?.status === 403) {
        setError("You do not have Administrator access to view or edit this page.");
      } else {
        setError("Failed to load lookups data.");
      }
    } finally {
      setLoading(false);
    }
  };

  const saveList = async (key: keyof LookupData, values: string[]) => {
    try {
      const token = localStorage.getItem('token');
      await axios.put(`http://127.0.0.1:8000/api/lookups/manage/${key}`, { values }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setFlash({ msg: `${key.replace('VALID_', '')} updated successfully!`, type: 'success' });
      // Update local state directly to avoid re-fetching overhead
      setData(prev => prev ? { ...prev, [key]: values } : null);
      setTimeout(() => setFlash(null), 3000);
    } catch (err) {
      setFlash({ msg: `Failed to save ${key}.`, type: 'error' });
      setTimeout(() => setFlash(null), 3000);
    }
  };

  const handleAdd = (key: keyof LookupData, newValue: string, setter: React.Dispatch<React.SetStateAction<string>>) => {
    if (!newValue.trim() || !data) return;
    if (data[key].includes(newValue.trim())) {
      setFlash({ msg: "Item already exists!", type: 'error' });
      return;
    }
    const newList = [...data[key], newValue.trim()];
    saveList(key, newList);
    setter('');
  };

  const handleDelete = (key: keyof LookupData, itemToRemove: string) => {
    if (!data) return;
    if (!window.confirm(`Are you sure you want to remove '${itemToRemove}'? This might affect historical data views.`)) return;
    const newList = data[key].filter(i => i !== itemToRemove);
    saveList(key, newList);
  };

  const customStyles = {
    table: { style: { backgroundColor: 'transparent' } },
    header: { style: { backgroundColor: 'transparent', color: 'var(--text-primary)' } },
    headRow: { style: { backgroundColor: 'rgba(15, 23, 42, 0.4)', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-color)' } },
    headCells: { style: { fontSize: '0.85rem', fontWeight: 600, textTransform: 'uppercase' as any } },
    rows: {
      style: {
        backgroundColor: 'transparent',
        color: 'var(--text-primary)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
        '&:hover': { backgroundColor: 'rgba(255, 255, 255, 0.02)' },
      },
    },
    pagination: {
      style: { backgroundColor: 'transparent', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-color)' },
      pageButtonsStyle: { color: 'var(--text-primary)', fill: 'var(--text-primary)' }
    }
  };

  const createColumns = (key: keyof LookupData) => [
    {
      name: 'Value',
      selector: (row: { value: string }) => row.value,
      sortable: true,
      grow: 2,
    },
    {
      name: 'Actions',
      cell: (row: { value: string }) => (
        <button className="btn-icon text-danger" onClick={() => handleDelete(key, row.value)} title="Remove">
          <Trash2 size={16} />
        </button>
      ),
      button: true,
      width: '100px',
    }
  ];

  if (loading) return <div className="lookups-container"><div className="spinner-large"></div></div>;
  if (error) return <div className="lookups-container"><div className="error-state"><AlertTriangle size={48} /><h3>Access Denied</h3><p>{error}</p></div></div>;
  if (!data) return null;

  return (
    <div className="lookups-container">
      <header className="page-header">
        <h1 className="page-title"><Settings size={28} /> Data Lookups & System Configuration</h1>
        <p className="page-subtitle">Manage static lists such as Colleges, Terms, and Statuses directly from the database.</p>
      </header>

      {flash && (
        <div className={`flash-message ${flash.type} animate-fade-in`} style={{ marginBottom: '24px' }}>
          {flash.type === 'error' ? <AlertTriangle size={20} /> : <Save size={20} />}
          <span>{flash.msg}</span>
        </div>
      )}

      <div className="lookups-grid">
        {/* Colleges */}
        <section className="lookup-card glass-panel">
          <div className="lookup-card-header">
            <h3>Registered Colleges</h3>
          </div>
          <div className="lookup-card-body">
            <div className="add-row">
              <input 
                type="text" 
                placeholder="New College (e.g. ENG)" 
                value={newCollege} 
                onChange={e => setNewCollege(e.target.value)} 
                onKeyDown={e => e.key === 'Enter' && handleAdd('VALID_COLLEGES', newCollege, setNewCollege)}
              />
              <button className="btn-primary" onClick={() => handleAdd('VALID_COLLEGES', newCollege, setNewCollege)}>
                <Plus size={16} /> Add
              </button>
            </div>
            <div className="table-wrapper">
              <DataTable
                columns={createColumns('VALID_COLLEGES')}
                data={data.VALID_COLLEGES.map(v => ({ value: v }))}
                customStyles={customStyles}
                pagination
                paginationPerPage={5}
                paginationRowsPerPageOptions={[5, 10, 20]}
                noHeader
              />
            </div>
          </div>
        </section>

        {/* Terms */}
        <section className="lookup-card glass-panel">
          <div className="lookup-card-header">
            <h3>Academic Terms</h3>
          </div>
          <div className="lookup-card-body">
            <div className="add-row">
              <input 
                type="text" 
                placeholder="New Term (e.g. Winter)" 
                value={newTerm} 
                onChange={e => setNewTerm(e.target.value)} 
                onKeyDown={e => e.key === 'Enter' && handleAdd('VALID_TERMS', newTerm, setNewTerm)}
              />
              <button className="btn-primary" onClick={() => handleAdd('VALID_TERMS', newTerm, setNewTerm)}>
                <Plus size={16} /> Add
              </button>
            </div>
            <div className="table-wrapper">
              <DataTable
                columns={createColumns('VALID_TERMS')}
                data={data.VALID_TERMS.map(v => ({ value: v }))}
                customStyles={customStyles}
                pagination
                paginationPerPage={5}
                paginationRowsPerPageOptions={[5, 10]}
                noHeader
              />
            </div>
          </div>
        </section>

        {/* Statuses */}
        <section className="lookup-card glass-panel">
          <div className="lookup-card-header">
            <h3>Student Statuses</h3>
          </div>
          <div className="lookup-card-body">
            <div className="add-row">
              <input 
                type="text" 
                placeholder="New Status (e.g. Graduated)" 
                value={newStatus} 
                onChange={e => setNewStatus(e.target.value)} 
                onKeyDown={e => e.key === 'Enter' && handleAdd('VALID_STATUSES', newStatus, setNewStatus)}
              />
              <button className="btn-primary" onClick={() => handleAdd('VALID_STATUSES', newStatus, setNewStatus)}>
                <Plus size={16} /> Add
              </button>
            </div>
            <div className="table-wrapper">
              <DataTable
                columns={createColumns('VALID_STATUSES')}
                data={data.VALID_STATUSES.map(v => ({ value: v }))}
                customStyles={customStyles}
                pagination
                paginationPerPage={5}
                paginationRowsPerPageOptions={[5, 10]}
                noHeader
              />
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
