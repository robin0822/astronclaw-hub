import { useMemo, useState } from 'react';
import { useStore, nowStamp } from '../store/store-context';
import Select from '../components/Select';

type ShareStatus = '生效中' | '审批中' | '已回收';

interface ShareRecord {
  id: string;
  agentId: string;
  scope: string;
  target: string;
  permission: string;
  status: ShareStatus;
  applicant: string;
  approver: string;
  createdAt: string;
  expireAt: string;
}

const INITIAL_RECORDS: ShareRecord[] = [
  {
    id: 'SH-20260701-001',
    agentId: 'ag-006',
    scope: '部门级',
    target: '法务与合规中心',
    permission: '可使用对话',
    status: '生效中',
    applicant: '王琳',
    approver: '平台管理员',
    createdAt: '2026-07-01 09:20:00',
    expireAt: '2026-07-31',
  },
  {
    id: 'SH-20260701-002',
    agentId: 'ag-001',
    scope: '项目级',
    target: '客户服务质检项目',
    permission: '可查看配置',
    status: '审批中',
    applicant: '王海燕',
    approver: '部门负责人',
    createdAt: '2026-07-01 10:12:00',
    expireAt: '2026-07-15',
  },
  {
    id: 'SH-20260628-011',
    agentId: 'ag-005',
    scope: '个人级',
    target: '赵建国',
    permission: '只读体验',
    status: '已回收',
    applicant: '李涛',
    approver: '安全管理员',
    createdAt: '2026-06-28 16:45:00',
    expireAt: '2026-07-05',
  },
];

const STATUS_META: Record<ShareStatus, string> = {
  生效中: 'success',
  审批中: 'warning',
  已回收: 'neutral',
};

export default function SharingPage() {
  const { agents, departments, members, addOpLog, toast } = useStore();
  const [records, setRecords] = useState(INITIAL_RECORDS);
  const [form, setForm] = useState({
    agentId: agents[0]?.id ?? '',
    scope: '部门级',
    target: departments.find((item) => item.parentId)?.name ?? '客户服务中心',
    permission: '可使用对话',
    approver: '平台管理员',
    expireAt: '2026-07-31',
  });
  const [filter, setFilter] = useState<'全部' | ShareStatus>('全部');

  const agentName = (id: string) => agents.find((agent) => agent.id === id)?.name ?? id;
  const activeRecords = records.filter((record) => record.status === '生效中');
  const pendingRecords = records.filter((record) => record.status === '审批中');
  const filtered = records.filter((record) => filter === '全部' || record.status === filter);

  const targets = useMemo(() => {
    const deptTargets = departments.filter((dept) => dept.parentId).map((dept) => dept.name);
    const memberTargets = members.map((member) => member.name);
    return Array.from(new Set([...deptTargets, '客户服务质检项目', '养老金融试点项目', ...memberTargets]));
  }, [departments, members]);

  function submitShare() {
    if (!form.agentId) {
      toast('请选择要共享的智能体实例', 'danger');
      return;
    }
    const id = `SH-${Date.now().toString().slice(-10)}`;
    const next: ShareRecord = {
      id,
      agentId: form.agentId,
      scope: form.scope,
      target: form.target,
      permission: form.permission,
      status: form.scope === '个人级' ? '生效中' : '审批中',
      applicant: 'admin',
      approver: form.approver,
      createdAt: nowStamp(),
      expireAt: form.expireAt,
    };
    setRecords((items) => [next, ...items]);
    addOpLog({
      operator: 'admin',
      module: '实例共享',
      action: '发起共享',
      target: `${agentName(next.agentId)} -> ${next.target}`,
      result: 'success',
      ip: '10.1.28.16',
      detail: `${next.scope} · ${next.permission} · ${next.status}`,
    });
    toast(next.status === '审批中' ? '共享申请已提交审批' : '共享已生效', next.status === '审批中' ? 'info' : 'success');
  }

  function approve(record: ShareRecord) {
    setRecords((items) => items.map((item) => (item.id === record.id ? { ...item, status: '生效中' } : item)));
    addOpLog({
      operator: 'admin',
      module: '实例共享',
      action: '审批通过',
      target: record.id,
      result: 'success',
      ip: '10.1.28.16',
      detail: `${agentName(record.agentId)} 共享给 ${record.target}`,
    });
    toast('共享审批已通过', 'success');
  }

  function revoke(record: ShareRecord) {
    setRecords((items) => items.map((item) => (item.id === record.id ? { ...item, status: '已回收' } : item)));
    addOpLog({
      operator: 'admin',
      module: '实例共享',
      action: '回收共享',
      target: record.id,
      result: 'success',
      ip: '10.1.28.16',
      detail: `${agentName(record.agentId)} / ${record.target}`,
    });
    toast('共享授权已回收', 'warning');
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>实例共享</h1>
          <p>支持个人级、部门级、项目级智能体共享，按权限、审批、到期回收和审计留痕闭环管理。</p>
        </div>
      </div>

      <div className="four-cols stats-grid">
        <div className="stat-card accent">
          <span>共享总数</span>
          <strong>{records.length}</strong>
          <em>含历史回收记录</em>
        </div>
        <div className="stat-card">
          <span>生效中</span>
          <strong>{activeRecords.length}</strong>
          <em>可被授权对象使用</em>
        </div>
        <div className="stat-card">
          <span>审批中</span>
          <strong>{pendingRecords.length}</strong>
          <em>部门/项目共享需审批</em>
        </div>
        <div className="stat-card">
          <span>已回收</span>
          <strong>{records.filter((record) => record.status === '已回收').length}</strong>
          <em>权限已失效</em>
        </div>
      </div>

      <div className="split-layout">
        <div className="form-card" style={{ flex: 0.9 }}>
          <div className="card-topline">
            <h3>发起共享</h3>
            <span className="status-tag info">需审计</span>
          </div>
          <div className="form-grid two-cols">
            <label className="full">
              智能体实例
              <Select
                value={form.agentId}
                options={agents.map((agent) => ({ value: agent.id, label: `${agent.name} · ${agent.department}` }))}
                onChange={(value) => setForm({ ...form, agentId: value })}
              />
            </label>
            <label>
              共享级别
              <Select
                value={form.scope}
                options={['个人级', '部门级', '项目级'].map((item) => ({ value: item, label: item }))}
                onChange={(value) => setForm({ ...form, scope: value })}
              />
            </label>
            <label>
              权限
              <Select
                value={form.permission}
                options={['只读体验', '可使用对话', '可查看配置', '协作管理'].map((item) => ({ value: item, label: item }))}
                onChange={(value) => setForm({ ...form, permission: value })}
              />
            </label>
            <label>
              授权对象
              <Select value={form.target} options={targets.map((target) => ({ value: target, label: target }))} onChange={(value) => setForm({ ...form, target: value })} />
            </label>
            <label>
              审批人
              <Select
                value={form.approver}
                options={['平台管理员', '部门负责人', '安全管理员'].map((item) => ({ value: item, label: item }))}
                onChange={(value) => setForm({ ...form, approver: value })}
              />
            </label>
            <label className="full">
              到期日期
              <input value={form.expireAt} onChange={(event) => setForm({ ...form, expireAt: event.target.value })} placeholder="YYYY-MM-DD" />
            </label>
          </div>
          <button className="primary-btn" style={{ marginTop: 16 }} onClick={submitShare}>
            提交共享
          </button>
          <div className="info-banner" style={{ marginTop: 16 }}>
            部门级和项目级共享默认进入审批流；审批通过后写入授权台账，到期自动提示回收。
          </div>
        </div>

        <div className="summary-card">
          <h3>共享控制点</h3>
          <div className="summary-metrics">
            <div>
              <span>权限范围</span>
              <strong>个人 / 部门 / 项目</strong>
            </div>
            <div>
              <span>审批策略</span>
              <strong>部门级和项目级需审批</strong>
            </div>
            <div>
              <span>高危权限</span>
              <strong>协作管理需二次确认</strong>
            </div>
            <div>
              <span>回收机制</span>
              <strong>到期回收 / 手动回收</strong>
            </div>
            <div>
              <span>审计字段</span>
              <strong>申请人、审批人、对象、权限、时间</strong>
            </div>
          </div>
          <div className="success-box">共享授权只影响已授权范围，不改变智能体所属部门、模型额度或知识库原始权限。</div>
        </div>
      </div>

      <div className="toolbar-card">
        <div className="chip-group">
          {(['全部', '生效中', '审批中', '已回收'] as const).map((item) => (
            <button key={item} className={`chip${filter === item ? ' active' : ''}`} onClick={() => setFilter(item)}>
              {item}
            </button>
          ))}
        </div>
        <div className="subtle">共 {filtered.length} 条授权记录</div>
      </div>

      <div className="table-card">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>共享单号</th>
                <th>智能体</th>
                <th>级别</th>
                <th>授权对象</th>
                <th>权限</th>
                <th>申请人</th>
                <th>审批人</th>
                <th>创建时间</th>
                <th>到期</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((record) => (
                <tr key={record.id}>
                  <td>{record.id}</td>
                  <td>{agentName(record.agentId)}</td>
                  <td>
                    <span className="tag-pill">{record.scope}</span>
                  </td>
                  <td>{record.target}</td>
                  <td>{record.permission}</td>
                  <td>{record.applicant}</td>
                  <td>{record.approver}</td>
                  <td>{record.createdAt}</td>
                  <td>{record.expireAt}</td>
                  <td>
                    <span className={`status-tag ${STATUS_META[record.status]}`}>{record.status}</span>
                  </td>
                  <td>
                    {record.status === '审批中' && (
                      <button className="text-btn" onClick={() => approve(record)}>
                        通过
                      </button>
                    )}
                    {record.status === '生效中' && (
                      <button className="text-btn danger-text" onClick={() => revoke(record)}>
                        回收
                      </button>
                    )}
                    {record.status === '已回收' && <span className="subtle">已结束</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
