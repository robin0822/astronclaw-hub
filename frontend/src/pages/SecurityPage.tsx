import { useMemo, useState } from 'react';
import { useStore } from '../store/store-context';
import type { SecurityPolicy } from '../store/types';

type Tab = 'posture' | 'login' | 'access' | 'sensitive';

interface LoginAudit {
  id: string;
  time: string;
  user: string;
  ip: string;
  method: 'SSO' | '密码登录';
  result: 'success' | 'danger';
  reason: string;
}

const LOGIN_SEED: LoginAudit[] = [
  { id: 'L-2026', time: '2026-06-25 09:12:34', user: '张伟 (admin)', ip: '10.1.28.16', method: 'SSO', result: 'success', reason: '—' },
  { id: 'L-2027', time: '2026-06-25 08:51:07', user: '李娜', ip: '10.1.30.42', method: 'SSO', result: 'success', reason: '—' },
  { id: 'L-2028', time: '2026-06-25 08:33:55', user: '王强', ip: '10.1.31.88', method: '密码登录', result: 'success', reason: '—' },
  { id: 'L-2029', time: '2026-06-25 02:14:19', user: '未知账号 (admin@test)', ip: '203.0.113.77', method: '密码登录', result: 'danger', reason: '密码错误超过阈值，已锁定' },
  { id: 'L-2030', time: '2026-06-24 23:47:02', user: '赵敏', ip: '10.1.29.21', method: 'SSO', result: 'success', reason: '—' },
];

const SENSITIVE_KEYWORDS = ['删除', '下线', '权限', '导出', '冻结'];

export default function SecurityPage() {
  const [tab, setTab] = useState<Tab>('posture');
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>安全管理</h1>
          <p>面向私有化部署的纵深防护体系：数据加密、访问控制、审计追溯与隐私合规，保障智能体平台安全可信运行。</p>
        </div>
      </div>
      <div className="tab-row">
        <div className="tab-group">
          <button className={`tab${tab === 'posture' ? ' active' : ''}`} onClick={() => setTab('posture')}>
            安全态势
          </button>
          <button className={`tab${tab === 'login' ? ' active' : ''}`} onClick={() => setTab('login')}>
            登录审计
          </button>
          <button className={`tab${tab === 'access' ? ' active' : ''}`} onClick={() => setTab('access')}>
            访问控制策略
          </button>
          <button className={`tab${tab === 'sensitive' ? ' active' : ''}`} onClick={() => setTab('sensitive')}>
            敏感操作监控
          </button>
        </div>
      </div>
      {tab === 'posture' && <Posture />}
      {tab === 'login' && <LoginAuditView />}
      {tab === 'access' && <AccessControl />}
      {tab === 'sensitive' && <SensitiveOps />}
    </div>
  );
}

/* ---------- 安全态势 ---------- */
function Posture() {
  return (
    <>
      <div className="four-cols stats-grid">
        <div className="stat-card accent">
          <span>安全评分</span>
          <strong>92 分</strong>
          <em>等保三级达标</em>
        </div>
        <div className="stat-card">
          <span>高危权限账号</span>
          <strong>16</strong>
          <em>建议定期复核</em>
        </div>
        <div className="stat-card">
          <span>今日拦截攻击</span>
          <strong>38</strong>
          <em>WAF + 流量清洗</em>
        </div>
        <div className="stat-card">
          <span>待处理安全事件</span>
          <strong style={{ color: 'var(--danger)' }}>3</strong>
          <em>需 24h 内闭环</em>
        </div>
      </div>

      <div className="section-title">安全能力</div>
      <div className="feature-grid">
        <div className="feature-card">
          <h4>数据加密</h4>
          <p>传输全链路 TLS 1.3，存储采用 AES-256，密钥由 KMS 统一托管轮换。</p>
        </div>
        <div className="feature-card">
          <h4>访问控制</h4>
          <p>基于 RBAC 的最小权限模型，按角色/部门/实例三维授权，杜绝越权访问。</p>
        </div>
        <div className="feature-card">
          <h4>审计追溯</h4>
          <p>全操作留痕，登录、配置、数据访问全程记录，支持按对象回溯。</p>
        </div>
        <div className="feature-card">
          <h4>隐私合规</h4>
          <p>敏感字段自动脱敏，数据分级分类管理，满足个保法与等保合规要求。</p>
        </div>
      </div>

      <div className="summary-card">
        <h3>安全基线检查</h3>
        <div className="summary-metrics">
          <div>
            <span>等保合规</span>
            <strong className="status-tag success">已通过 三级</strong>
          </div>
          <div>
            <span>数据加密</span>
            <strong className="status-tag success">已启用</strong>
          </div>
          <div>
            <span>漏洞扫描</span>
            <strong>昨日完成 · 0 高危</strong>
          </div>
          <div>
            <span>渗透测试</span>
            <strong>季度执行 · 上次 2026-04</strong>
          </div>
          <div>
            <span>备份恢复</span>
            <strong>每日全量 · 演练通过</strong>
          </div>
        </div>
      </div>
    </>
  );
}

/* ---------- 登录审计 ---------- */
function LoginAuditView() {
  return (
    <>
      <div className="info-banner">登录行为全量审计，异常登录（异地、暴力破解、非常用设备）实时识别并自动锁定账号。</div>
      <div className="table-card">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>登录时间</th>
                <th>用户名</th>
                <th>登录 IP</th>
                <th>登录方式</th>
                <th>结果</th>
                <th>异常原因</th>
              </tr>
            </thead>
            <tbody>
              {LOGIN_SEED.map((r) => (
                <tr key={r.id}>
                  <td>{r.time}</td>
                  <td>{r.user}</td>
                  <td>
                    <span className="kbd">{r.ip}</span>
                  </td>
                  <td>
                    <span className="tag-pill">{r.method}</span>
                  </td>
                  <td>
                    <span className={`status-tag ${r.result}`}>{r.result === 'success' ? '成功' : '失败'}</span>
                  </td>
                  <td className="subtle">{r.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

/* ---------- 访问控制策略 ---------- */
function AccessControl() {
  const { securityPolicies: policies, update, addOpLog, toast } = useStore();

  function toggle(p: SecurityPolicy) {
    const next = !p.enabled;
    update((d) => ({ securityPolicies: d.securityPolicies.map((x) => (x.id === p.id ? { ...x, enabled: next } : x)) }));
    addOpLog({
      operator: 'admin',
      module: '安全管理',
      action: `${next ? '启用' : '停用'}访问控制策略`,
      target: p.name,
      result: 'success',
      ip: '10.1.28.16',
      detail: p.desc,
    });
    toast(`策略「${p.name}」已${next ? '启用' : '停用'}`, next ? 'success' : 'warning');
  }

  return (
    <>
      <div className="info-banner">访问控制策略统一管控登录与操作边界，策略变更即时生效并写入操作日志。</div>
      <div className="table-card">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>策略名称</th>
                <th>说明</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {policies.map((p) => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td className="subtle">{p.desc}</td>
                  <td>
                    <span className={`status-tag ${p.enabled ? 'success' : 'neutral'}`}>{p.enabled ? '已启用' : '已禁用'}</span>
                  </td>
                  <td>
                    <button className={`text-btn${p.enabled ? ' danger-text' : ''}`} onClick={() => toggle(p)}>
                      {p.enabled ? '停用' : '启用'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

/* ---------- 敏感操作监控 ---------- */
function SensitiveOps() {
  const { opLogs } = useStore();

  const rows = useMemo(() => {
    const matched = opLogs.filter((l) => SENSITIVE_KEYWORDS.some((k) => l.action.includes(k)));
    return matched.length > 0 ? matched : opLogs.slice(0, 6);
  }, [opLogs]);

  return (
    <>
      <div className="info-banner">敏感操作（删除 / 下线 / 权限变更 / 数据导出 / 冻结）实时监控并告警，触发后自动通知安全负责人。</div>
      <div className="table-card">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>操作人</th>
                <th>操作</th>
                <th>对象</th>
                <th>结果</th>
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((l) => (
                <tr key={l.id}>
                  <td>{l.ts}</td>
                  <td>{l.operator}</td>
                  <td>{l.action}</td>
                  <td>{l.target}</td>
                  <td>
                    <span className={`status-tag ${l.result === 'success' ? 'success' : 'danger'}`}>{l.result === 'success' ? '成功' : '失败'}</span>
                  </td>
                  <td>
                    <span className="kbd">{l.ip}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
