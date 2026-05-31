import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock } from 'lucide-react';
import './Login.css'; // We'll create this specific file for any extra component styles

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [isChangingPw, setIsChangingPw] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');
    setLoading(true);

    if (isChangingPw) {
      try {
        const response = await fetch('http://127.0.0.1:8000/api/auth/change-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username,
            current_password: password,
            new_password: newPassword
          }),
        });

        if (!response.ok) {
          const errData = await response.json();
          throw new Error(errData.detail || 'Failed to change password');
        }

        setSuccessMsg('Password changed successfully. You can now login.');
        setIsChangingPw(false);
        setPassword('');
        setNewPassword('');
      } catch (err: any) {
        setError(err.message || 'Something went wrong');
      } finally {
        setLoading(false);
      }
      return;
    }

    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const response = await fetch('http://127.0.0.1:8000/api/auth/token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString(),
      });

      if (!response.ok) {
        throw new Error('Invalid username or password');
      }

      const data = await response.json();
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('user_role', data.user_role);
      localStorage.setItem('username', data.username);
      
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="glass-panel login-card animate-fade-in">
        <div className="login-header">
          <div className="icon-circle">
            <Lock size={32} color="var(--primary-color)" />
          </div>
          <h2>{isChangingPw ? 'Change Password' : 'Finance Login'}</h2>
          <p>Nile University A/R System</p>
        </div>

        {error && (
          <div className="error-alert animate-fade-in">
            {error}
          </div>
        )}
        
        {successMsg && (
          <div className="success-alert animate-fade-in" style={{ background: 'rgba(22, 163, 74, 0.1)', color: '#16a34a', padding: '12px', borderRadius: '8px', marginBottom: '20px', border: '1px solid rgba(22, 163, 74, 0.2)' }}>
            {successMsg}
          </div>
        )}

        <form onSubmit={handleLogin} className="login-form">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              className="input-field"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">{isChangingPw ? 'Current Password' : 'Password'}</label>
            <input
              id="password"
              type="password"
              className="input-field"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>

          {isChangingPw && (
            <div className="form-group animate-fade-in">
              <label htmlFor="new-password">New Password</label>
              <input
                id="new-password"
                type="password"
                className="input-field"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                autoComplete="new-password"
              />
            </div>
          )}

          <button 
            type="submit" 
            className="btn-primary login-btn" 
            disabled={loading}
          >
            {loading ? 'Processing...' : (isChangingPw ? 'Update Password' : 'Secure Login')}
          </button>
          
          <div style={{ textAlign: 'center', marginTop: '16px' }}>
            <button 
              type="button" 
              onClick={() => {
                setIsChangingPw(!isChangingPw);
                setError('');
                setSuccessMsg('');
                setPassword('');
                setNewPassword('');
              }}
              style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.85rem', textDecoration: 'underline' }}
            >
              {isChangingPw ? 'Back to Login' : 'Change Password'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
