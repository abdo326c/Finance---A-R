import React, { useEffect, useState, useMemo } from 'react';
import axios from 'axios';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell
} from 'recharts';
import { TrendingUp, Users, DollarSign, Activity, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import './Dashboard.css';

interface DashboardData {
  metrics: {
    gross_billed: number;
    total_discounts: number;
    total_payments: number;
    net_balance: number;
    net_adjustments: number;
    total_students: number;
    active_count: number;
  };
  breakdown: Array<{
    College: string;
    Students: number;
    Tuition_Billed: number;
    Discounts: number;
    Payments: number;
    Net_Balance: number;
  }>;
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  // Filters state
  const [term, setTerm] = useState('All Terms');
  const [year, setYear] = useState('All Years');
  const [college, setCollege] = useState('All Colleges');
  
  // Dynamic lookups
  const [lookups, setLookups] = useState({ terms: [], years: [], colleges: [] });

  const fetchLookups = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/lookups`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setLookups({
        terms: response.data.terms || [],
        years: response.data.years || [],
        colleges: response.data.colleges || []
      });
    } catch (error) {
      console.error("Error fetching lookups", error);
    }
  };

  useEffect(() => {
    fetchLookups();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/dashboard/metrics`, {
        params: { term, year, college },
        headers: { Authorization: `Bearer ${token}` }
      });
      setData(response.data);
    } catch (error) {
      console.error("Error fetching dashboard data", error);
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        handleLogout();
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [term, year, college]);

  const handleLogout = () => {
    localStorage.clear();
    navigate('/login');
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-EG', { style: 'currency', currency: 'EGP', maximumFractionDigits: 0 }).format(value);
  };

  const COLORS = ['#0d47a1', '#e53935', '#00897b', '#fb8c00', '#5e35b1'];

  return (
    <div className="dashboard-layout">
      <main className="dashboard-content">
        <div className="filters-bar glass-panel animate-fade-in">
          <div className="filter-group">
            <label>Term</label>
            <select value={term} onChange={e => setTerm(e.target.value)} className="input-field">
              <option value="All Terms">All Terms</option>
              {lookups.terms.map((t: string) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="filter-group">
            <label>Year</label>
            <select value={year} onChange={e => setYear(e.target.value)} className="input-field">
              <option value="All Years">All Years</option>
              {lookups.years.map((y: number) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <div className="filter-group">
            <label>College</label>
            <select value={college} onChange={e => setCollege(e.target.value)} className="input-field">
              <option value="All Colleges">All Colleges</option>
              {lookups.colleges.map((c: string) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>

        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Loading financial data...</p>
          </div>
        ) : data ? (
          <>
            <div className="kpi-grid animate-fade-in">
              <div className="kpi-card kpi-blue glass-panel">
                <div className="kpi-icon"><TrendingUp /></div>
                <div>
                  <p className="kpi-label">Gross Billed</p>
                  <h3 className="kpi-value">{formatCurrency(data.metrics.gross_billed)}</h3>
                </div>
              </div>
              <div className="kpi-card kpi-red glass-panel">
                <div className="kpi-icon"><DollarSign /></div>
                <div>
                  <p className="kpi-label">Total Scholarships</p>
                  <h3 className="kpi-value">{formatCurrency(data.metrics.total_discounts)}</h3>
                </div>
              </div>
              <div className="kpi-card kpi-teal glass-panel">
                <div className="kpi-icon"><Activity /></div>
                <div>
                  <p className="kpi-label">Total Payments</p>
                  <h3 className="kpi-value">{formatCurrency(data.metrics.total_payments)}</h3>
                </div>
              </div>
              <div className="kpi-card kpi-purple glass-panel">
                <div className="kpi-icon"><Users /></div>
                <div>
                  <p className="kpi-label">Net Balance Due</p>
                  <h3 className="kpi-value">{formatCurrency(data.metrics.net_balance)}</h3>
                </div>
              </div>
            </div>

            <div className="charts-grid">
                {useMemo(() => (
                  <div className="chart-card glass-panel">
                    <h3 className="chart-title">Revenue Breakdown by College</h3>
                    <div style={{ width: '100%', height: 350 }}>
                      <ResponsiveContainer>
                        <BarChart data={data.breakdown} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                          <XAxis dataKey="College" stroke="var(--text-secondary)" tick={{fontSize: 12}} />
                          <YAxis stroke="var(--text-secondary)" tickFormatter={(v) => `${(v/1000000).toFixed(1)}M`} />
                          <RechartsTooltip 
                            formatter={(value: number) => formatCurrency(value)}
                            contentStyle={{ backgroundColor: 'var(--surface-color)', borderColor: 'var(--border-color)', borderRadius: '8px' }}
                          />
                          <Legend wrapperStyle={{ paddingTop: '20px' }}/>
                          <Bar dataKey="Tuition_Billed" name="Gross Tuition" fill="var(--primary-color)" radius={[4, 4, 0, 0]} />
                          <Bar dataKey="Discounts" name="Scholarships" fill="var(--danger)" radius={[4, 4, 0, 0]} />
                          <Bar dataKey="Payments" name="Collected" fill="var(--success)" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                ), [data.breakdown])}

              <div className="chart-container glass-panel">
                <h3 className="chart-title">👥 Students by College</h3>
                <div style={{ height: 350 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={data.breakdown}
                        cx="50%"
                        cy="50%"
                        innerRadius={80}
                        outerRadius={120}
                        paddingAngle={5}
                        dataKey="Students"
                        nameKey="College"
                        label
                      >
                        {data.breakdown.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <RechartsTooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            <div className="table-container glass-panel animate-fade-in" style={{ animationDelay: '0.2s' }}>
              <h3 className="chart-title">📋 Detailed Revenue Breakdown</h3>
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>College</th>
                      <th>Students</th>
                      <th>Tuition Billed</th>
                      <th>Discounts</th>
                      <th>Payments</th>
                      <th>Net Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.breakdown.map((row, idx) => (
                      <tr key={idx}>
                        <td style={{fontWeight: 600}}>{row.College}</td>
                        <td>{row.Students}</td>
                        <td>{formatCurrency(row.Tuition_Billed)}</td>
                        <td>{formatCurrency(row.Discounts)}</td>
                        <td>{formatCurrency(row.Payments)}</td>
                        <td className={row.Net_Balance > 0 ? 'text-positive' : 'text-neutral'}>
                          {formatCurrency(row.Net_Balance)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        ) : (
          <div className="error-state">Failed to load data</div>
        )}
      </main>
    </div>
  );
}
