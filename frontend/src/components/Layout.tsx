import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { BellOutlined, DownOutlined, LogoutOutlined, MenuOutlined, UserOutlined } from '@ant-design/icons';
import { NavLink, Outlet, useLocation, Link, useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';
import { auditApi } from '../api/audit';
import { notificationsApi } from '../api/notifications';
import { APP_SECTIONS, PAGE_TITLES, type AppRouteIcon } from '../routes/route-config';
import { useStore } from '../store/store-context';
import Modal from './Modal';
import ThemeToggle from './ThemeToggle';

type NavIconMeta = {
  mark: string;
  tint: string;
  ink: string;
};

const NAV_ICONS: Record<AppRouteIcon, NavIconMeta> = {
  agents: { mark: '🦞', tint: '#fff1e8', ink: '#de4b27' },
  org: { mark: '🏢', tint: '#e8f0ff', ink: '#246bff' },
  monitoring: { mark: '🚨', tint: '#ffe7e7', ink: '#f05252' },
  models: { mark: '🧠', tint: '#f0ebff', ink: '#7c5cff' },
  security: { mark: '🛡️', tint: '#e9f9ef', ink: '#22a65b' },
  ops: { mark: '⚙️', tint: '#fff4de', ink: '#d97706' },
  skills: { mark: '✨', tint: '#eef2ff', ink: '#4f46e5' },
  knowledge: { mark: '📚', tint: '#ecfeff', ink: '#0891b2' },
  memory: { mark: '🧩', tint: '#fdf2f8', ink: '#db2777' },
  seats: { mark: '👥', tint: '#f0fdf4', ink: '#16a34a' },
  sharing: { mark: '🔗', tint: '#eff6ff', ink: '#2563eb' },
  channels: { mark: '💬', tint: '#f5f3ff', ink: '#8b5cf6' },
  diagnosis: { mark: '🩺', tint: '#fff7ed', ink: '#ea580c' },
};

const USER_NAME_KEYS = ['name', 'displayName', 'realName', 'nickname', 'username', 'account'] as const;

type RecentOperation = {
  id: string;
  time: string;
  operator: string;
  module: string;
  action: string;
  target: string;
};
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function extractUserName(profile: Record<string, unknown>) {
  const sources = [profile.user, profile].filter(isRecord);
  for (const source of sources) {
    for (const key of USER_NAME_KEYS) {
      const value = source[key];
      if (typeof value === 'string' && value.trim()) return value.trim();
    }
  }
  return '当前用户';
}

function pageItems(value: unknown): Record<string, unknown>[] {
  if (Array.isArray(value)) return value.filter(isRecord);
  if (!isRecord(value)) return [];
  const candidates = [value.list, value.records, value.items, value.data, value.content];
  for (const candidate of candidates) {
    if (Array.isArray(candidate)) return candidate.filter(isRecord);
  }
  return [];
}

function textValue(value: unknown, fallback = '-') {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback;
}

function normalizeAuditLog(log: Record<string, unknown>, index: number): RecentOperation {
  return {
    id: textValue(log.id ?? log.logId, `audit-${index}`),
    time: textValue(log.time ?? log.ts ?? log.createdAt ?? log.operationTime),
    operator: textValue(log.operator ?? log.operatorName ?? log.username ?? log.userName),
    module: textValue(log.module ?? log.bizModule ?? log.resourceType),
    action: textValue(log.action ?? log.operation ?? log.eventType),
    target: textValue(log.target ?? log.resourceName ?? log.resourceId),
  };
}

export default function Layout() {
  const [open, setOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [userName, setUserName] = useState('当前用户');
  const [notifications, setNotifications] = useState<Record<string, unknown>[]>([]);
  const [notificationUnreadCount, setNotificationUnreadCount] = useState(0);
  const [recentAuditLogs, setRecentAuditLogs] = useState<RecentOperation[]>([]);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const { alerts, opLogs, toast } = useStore();
  const navigate = useNavigate();
  const loc = useLocation();
  const title = Object.entries(PAGE_TITLES).find(([path]) => loc.pathname.startsWith(path))?.[1] || 'AstronClaw 平台';

  const pendingAlerts = useMemo(() => alerts.filter((alert) => alert.status !== 'resolved'), [alerts]);
  const unreadNotifications = useMemo(() => notifications.filter((item) => item.status !== 'read'), [notifications]);
  const notificationCount = notificationUnreadCount || unreadNotifications.length || pendingAlerts.length;
  const recentLogs = useMemo<RecentOperation[]>(() => {
    if (recentAuditLogs.length) return recentAuditLogs;
    return opLogs.slice(0, 8).map((log) => ({
      id: log.id,
      time: log.ts,
      operator: log.operator,
      module: log.module,
      action: log.action,
      target: log.target,
    }));
  }, [opLogs, recentAuditLogs]);

  useEffect(() => {
    let active = true;
    void authApi
      .me()
      .then((profile) => {
        if (active) setUserName(extractUserName(profile));
      })
      .catch(() => {
        if (active) setUserName('当前用户');
      });

    void Promise.allSettled([notificationsApi.summary(), notificationsApi.list({ status: 'unread', page: 1, pageSize: 8 }), auditApi.operationLogs({ page: 1, pageSize: 8 })]).then(
      ([summaryResult, notificationsResult, logsResult]) => {
        if (!active) return;

        if (summaryResult.status === 'fulfilled') {
          const summary = summaryResult.value;
          if (isRecord(summary)) {
            const unread = summary.unreadCount ?? summary.unread ?? summary.pendingCount;
            if (typeof unread === 'number') setNotificationUnreadCount(unread);
          }
        }

        if (notificationsResult.status === 'fulfilled') {
          setNotifications(pageItems(notificationsResult.value));
        }

        if (logsResult.status === 'fulfilled') {
          setRecentAuditLogs(pageItems(logsResult.value).slice(0, 8).map(normalizeAuditLog));
        }
      },
    );

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!userMenuOpen) return undefined;

    function handlePointerDown(event: MouseEvent) {
      if (!userMenuRef.current?.contains(event.target as Node)) setUserMenuOpen(false);
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setUserMenuOpen(false);
    }

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [userMenuOpen]);

  async function handleLogout() {
    setUserMenuOpen(false);
    try {
      await authApi.logout();
    } catch (error) {
      toast(error instanceof Error ? error.message : '业务后端调用失败', 'warning');
    } finally {
      navigate('/login', { replace: true });
    }
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar${open ? ' open' : ''}`}>
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            🦞
          </div>
          <div className="brand-copy">
            <strong>讯飞 AstronClaw</strong>
            <span>智能体管理平台</span>
          </div>
        </div>
        {APP_SECTIONS.map((section) => (
          <div className="nav-section" key={section.title}>
            <p className="nav-section-title">{section.title}</p>
            {section.items.map((item) => {
              const icon = NAV_ICONS[item.icon];
              const iconStyle = { '--nav-tint': icon.tint, '--nav-ink': icon.ink } as CSSProperties;
              return (
                <NavLink key={item.to} to={item.to} className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`} onClick={() => setOpen(false)}>
                  <span className="nav-ico" style={iconStyle} aria-hidden="true">
                    <span className="nav-symbol">{icon.mark}</span>
                  </span>
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </div>
        ))}
      </aside>
      <main className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            <button className="mobile-menu" onClick={() => setOpen((value) => !value)} aria-label="展开导航">
              <MenuOutlined aria-hidden="true" />
            </button>
            <div className="breadcrumb">
              <span>AstronClaw</span>
              <span>/</span>
              <strong>{title}</strong>
            </div>
          </div>
          <div className="topbar-right">
            <ThemeToggle />
            <button className="icon-btn notif-btn" onClick={() => setNotifOpen(true)} aria-label="通知中心">
              <BellOutlined aria-hidden="true" />
              {notificationCount > 0 && <span className="badge">{notificationCount}</span>}
            </button>
            <div className={`user-menu${userMenuOpen ? ' open' : ''}`} ref={userMenuRef}>
              <button type="button" className="user-menu-trigger" onClick={() => setUserMenuOpen((value) => !value)} aria-haspopup="menu" aria-expanded={userMenuOpen}>
                <span className="user-menu-avatar" aria-hidden="true">
                  <UserOutlined />
                </span>
                <span className="user-menu-name">{userName}</span>
                <DownOutlined className="user-menu-caret" aria-hidden="true" />
              </button>
              {userMenuOpen && (
                <div className="user-menu-dropdown" role="menu">
                  <div className="user-menu-header">
                    <span>当前账号</span>
                    <strong>{userName}</strong>
                  </div>
                  <button type="button" className="user-menu-item danger" role="menuitem" onClick={() => void handleLogout()}>
                    <LogoutOutlined aria-hidden="true" />
                    <span>退出登录</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>
        <div className="pages">
          <Outlet />
        </div>
      </main>
      <Modal open={notifOpen} title="通知中心" wide onClose={() => setNotifOpen(false)}>
        <div className="section-title" style={{ marginTop: 0 }}>
          待处理告警（{pendingAlerts.length}）
        </div>
        {pendingAlerts.length === 0 ? (
          <p className="subtle">暂无待处理告警</p>
        ) : (
          <div style={{ marginBottom: 24 }}>
            {pendingAlerts.slice(0, 5).map((alert) => (
              <div key={alert.id} className="notif-item">
                <div>
                  <span className={`status-tag ${alert.level === 'critical' ? 'danger' : 'warning'}`}>
                    {alert.level === 'critical' ? '严重' : alert.level === 'warning' ? '告警' : '提示'}
                  </span>
                  <strong>{alert.source}</strong>
                  <span className="subtle"> · {alert.type}</span>
                </div>
                <div className="subtle">{alert.triggeredAt}</div>
                <Link to="/monitoring" onClick={() => setNotifOpen(false)} className="text-btn">
                  前往处理
                </Link>
              </div>
            ))}
          </div>
        )}
        <div className="section-title">最近操作</div>
        <div className="table-scroll" style={{ maxHeight: 280 }}>
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>操作人</th>
                <th>模块</th>
                <th>操作</th>
                <th>对象</th>
              </tr>
            </thead>
            <tbody>
              {recentLogs.map((log) => (
                <tr key={log.id}>
                  <td>{log.time}</td>
                  <td>{log.operator}</td>
                  <td>
                    <span className="tag-pill">{log.module}</span>
                  </td>
                  <td>{log.action}</td>
                  <td>{log.target}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Modal>
    </div>
  );
}
