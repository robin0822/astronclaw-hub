import { useMemo, useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '../api/auth';
import ThemeToggle from '../components/ThemeToggle';

function safeRedirect(value: string | null) {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.startsWith('/login')) return '/agents';
  return value;
}

function EyeIcon({ open }: { open: boolean }) {
  return open ? (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2.25 12s3.5-6 9.75-6 9.75 6 9.75 6-3.5 6-9.75 6-9.75-6-9.75-6Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 3l18 18" />
      <path d="M9.9 5.25A10.7 10.7 0 0 1 12 5c6.25 0 9.75 7 9.75 7a17.6 17.6 0 0 1-3.02 3.68" />
      <path d="M14.12 14.12A3 3 0 0 1 9.88 9.88" />
      <path d="M6.7 6.7C3.86 8.6 2.25 12 2.25 12s3.5 7 9.75 7a10.2 10.2 0 0 0 4.6-1.08" />
    </svg>
  );
}

export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const redirectTo = useMemo(() => safeRedirect(searchParams.get('redirect')), [searchParams]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    if (!username.trim() || !password) {
      setError('请输入账号和密码');
      return;
    }
    setSubmitting(true);
    try {
      await authApi.login({ username: username.trim(), password });
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : '业务后端调用失败');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <ThemeToggle className="login-theme-toggle" />
      <section className="login-shell" aria-label="AstronClaw 登录">
        <div className="login-copy">
          <div className="login-copy-main">
            <div className="login-brandline">
              <span className="login-mark">🦞</span>
              <span>讯飞 AstronClaw</span>
            </div>
            <div className="login-hero-text">
              <h1>企业智能体管理平台</h1>
              <p>面向企业智能体全生命周期，统一管理实例部署、模型接入、知识技能、权限席位与运行审计。</p>
            </div>
          </div>
          <div className="login-signal-grid">
            <div>
              <strong>统一身份</strong>
              <span>企业账号登录</span>
            </div>
            <div>
              <strong>权限隔离</strong>
              <span>按角色访问</span>
            </div>
            <div>
              <strong>操作留痕</strong>
              <span>安全审计闭环</span>
            </div>
          </div>
        </div>
        <form className="login-panel" onSubmit={handleSubmit}>
          <span className="login-kicker">Secure Sign In</span>
          <h2>登录工作台</h2>
          <p className="login-muted">使用企业账号进入管理后台。</p>
          {error && <div className="login-alert">{error}</div>}
          <label>
            账号
            <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" placeholder="请输入账号" />
          </label>
          <label htmlFor="login-password">密码</label>
          <div className="password-field">
            <input
              id="login-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type={passwordVisible ? 'text' : 'password'}
              autoComplete="current-password"
              placeholder="请输入密码"
            />
            <button className="password-toggle" type="button" onClick={() => setPasswordVisible((value) => !value)} aria-label={passwordVisible ? '隐藏密码' : '显示密码'}>
              <EyeIcon open={passwordVisible} />
            </button>
          </div>
          <button className="primary-btn login-submit" type="submit" disabled={submitting}>
            {submitting ? '登录中...' : '登录'}
          </button>
        </form>
      </section>
    </main>
  );
}
