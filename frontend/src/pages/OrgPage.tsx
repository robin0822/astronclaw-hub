import { useEffect, useMemo, useState } from 'react';
import { useStore } from '../store/store-context';
import { confirmDangerousAction } from '../utils';
import type { Department, Member, Role } from '../store/types';
import Modal from '../components/Modal';
import Select from '../components/Select';
import Checkbox from '../components/Checkbox';

type Tab = 'structure' | 'members' | 'roles' | 'permissions' | 'oplog';

const PERMISSION_GROUPS = [
  {
    group: '智能体管理',
    items: [
      { key: 'agent.view', label: '查看实例' },
      { key: 'agent.create', label: '创建实例' },
      { key: 'agent.edit', label: '编辑配置' },
      { key: 'agent.delete', label: '删除实例' },
      { key: 'agent.lifecycle', label: '生命周期操作（启停/升级/重启）' },
    ],
  },
  {
    group: '组织与权限',
    items: [
      { key: 'org.view', label: '查看组织架构' },
      { key: 'org.edit', label: '编辑组织/人员' },
      { key: 'role.manage', label: '角色管理' },
      { key: 'perm.manage', label: '权限分配' },
    ],
  },
  {
    group: '监控与运维',
    items: [
      { key: 'monitor.view', label: '查看监控' },
      { key: 'monitor.handle', label: '处置告警' },
      { key: 'ops.view', label: '查看巡检' },
      { key: 'ops.run', label: '执行巡检/自动化' },
    ],
  },
  {
    group: '模型与安全',
    items: [
      { key: 'model.view', label: '查看模型' },
      { key: 'model.manage', label: '模型治理' },
      { key: 'security.view', label: '查看安全' },
      { key: 'security.manage', label: '安全策略管理' },
      { key: 'oplog.view', label: '查看操作日志' },
    ],
  },
];
const TABS: { key: Tab; label: string }[] = [
  { key: 'structure', label: '组织架构展示' },
  { key: 'members', label: '人员设置' },
  { key: 'roles', label: '角色设置' },
  { key: 'permissions', label: '权限查看' },
  { key: 'oplog', label: '操作日志' },
];

export default function OrgPage() {
  const [tab, setTab] = useState<Tab>('structure');
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>组织架构管理</h1>
          <p>统一管理企业组织架构、人员、角色与权限，并按 AstronClaw 风格提供操作日志审计追溯。</p>
        </div>
      </div>
      <div className="tab-row">
        <div className="tab-group">
          {TABS.map((t) => (
            <button key={t.key} className={`tab${tab === t.key ? ' active' : ''}`} onClick={() => setTab(t.key)}>
              {t.label}
            </button>
          ))}
        </div>
      </div>
      {tab === 'structure' && <Structure />}
      {tab === 'members' && <Members />}
      {tab === 'roles' && <Roles />}
      {tab === 'permissions' && <Permissions />}
      {tab === 'oplog' && <OpLogView />}
    </div>
  );
}

/* ---------------- 组织架构展示 ---------------- */
function OrgNode({
  dept,
  all,
  members,
  activeId,
  onPick,
  depth,
}: {
  dept: Department;
  all: Department[];
  members: Member[];
  activeId: string;
  onPick: (id: string) => void;
  depth: number;
}) {
  const children = all.filter((d) => d.parentId === dept.id);

  // 计算部门总人数（包含所有下级部门）
  function getTotalMembers(deptId: string): number {
    const childDepts = all.filter((d) => d.parentId === deptId);
    const directMembers = members.filter((m) => m.deptId === deptId).length;
    const childMembers = childDepts.reduce((sum, child) => sum + getTotalMembers(child.id), 0);
    return directMembers + childMembers;
  }

  return (
    <div>
      <div className={`org-node${activeId === dept.id ? ' active' : ''}`} onClick={() => onPick(dept.id)}>
        <span>{depth === 0 ? '🏛️' : '🏢'}</span>
        <span>{dept.name}</span>
        <span className="count">
          {dept.manager} · {getTotalMembers(dept.id)} 人
        </span>
      </div>
      {children.length > 0 && (
        <div className="org-children">
          {children.map((c) => (
            <OrgNode key={c.id} dept={c} all={all} members={members} activeId={activeId} onPick={onPick} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

function Structure() {
  const { departments, members, update, addOpLog, toast } = useStore();
  const root = departments.find((d) => d.parentId === null);
  const [active, setActive] = useState(root?.id ?? '');
  const [creating, setCreating] = useState<Omit<Department, 'id'> | null>(null);

  useEffect(() => {
    if (!root) {
      if (active) setActive('');
      return;
    }
    if (!departments.some((d) => d.id === active)) setActive(root.id);
  }, [active, departments, root]);

  if (!root) return <div className="empty-state">未加载组织架构数据，请连接业务后端。</div>;

  const rootDept = root;
  const dept = departments.find((d) => d.id === active) ?? rootDept;
  const deptMembers = members.filter((m) => m.deptId === dept.id);

  // 计算部门总人数（包含所有下级部门）
  function getTotalMembers(deptId: string): number {
    const childDepts = departments.filter((d) => d.parentId === deptId);
    const directMembers = members.filter((m) => m.deptId === deptId).length;
    const childMembers = childDepts.reduce((sum, child) => sum + getTotalMembers(child.id), 0);
    return directMembers + childMembers;
  }

  function saveDept() {
    if (!creating) return;
    if (!creating.name) {
      toast('请填写部门名称', 'danger');
      return;
    }
    const id = `d-${Date.now().toString().slice(-6)}`;
    const newDept: Department = { ...creating, id };
    update((d) => ({ departments: [...d.departments, newDept] }));
    addOpLog({
      operator: 'admin',
      module: '组织架构',
      action: '新增部门',
      target: creating.name,
      result: 'success',
      ip: '10.1.28.16',
      detail: `上级部门 ${departments.find((d) => d.id === creating.parentId)?.name || '根部门'}`,
    });
    toast('部门已新增', 'success');
    setCreating(null);
  }

  function deleteDept() {
    if (active === rootDept.id) {
      toast('根部门不可删除', 'danger');
      return;
    }
    const hasChildren = departments.some((d) => d.parentId === active);
    const directMembers = members.filter((m) => m.deptId === active).length;
    if (hasChildren) {
      toast('该部门下存在子部门，请先删除子部门', 'danger');
      return;
    }
    if (directMembers > 0) {
      toast(`该部门下有 ${directMembers} 名直属成员，请先移出后再删除`, 'danger');
      return;
    }
    if (!confirmDangerousAction(`确认删除部门「${dept.name}」？删除操作会写入组织审计。`)) return;
    const name = dept.name;
    update((d) => ({ departments: d.departments.filter((x) => x.id !== active) }));
    addOpLog({ operator: 'admin', module: '组织架构', action: '删除部门', target: name, result: 'success', ip: '10.1.28.16', detail: '空部门删除' });
    toast(`部门「${name}」已删除`, 'danger');
    setActive(rootDept.id);
  }

  return (
    <>
      <div className="toolbar-card">
        <div>
          <strong>{departments.length - 1}</strong> 个部门 · <strong>{members.length}</strong> 名成员
        </div>
        <button className="primary-btn" onClick={() => setCreating({ name: '', parentId: active, manager: '待指定' })}>
          + 新增部门
        </button>
      </div>
      <div className="split-layout">
        <div className="table-card" style={{ padding: 18, flex: '1.2' }}>
          <h3 style={{ marginTop: 0 }}>组织树</h3>
          <div className="org-tree">
            <OrgNode dept={rootDept} all={departments} members={members} activeId={active} onPick={setActive} depth={0} />
          </div>
        </div>
        <div className="summary-card">
          <div className="card-topline">
            <h3 style={{ margin: 0 }}>{dept.name}</h3>
            {active !== rootDept.id && (
              <button className="text-btn danger-text" onClick={deleteDept}>
                删除部门
              </button>
            )}
          </div>
          <div className="summary-metrics">
            <div>
              <span>负责人</span>
              <strong>{dept.manager}</strong>
            </div>
            <div>
              <span>总人数</span>
              <strong>{getTotalMembers(dept.id)}</strong>
            </div>
            <div>
              <span>直属成员</span>
              <strong>{deptMembers.length}</strong>
            </div>
            <div>
              <span>下级部门</span>
              <strong>{departments.filter((d) => d.parentId === dept.id).length}</strong>
            </div>
          </div>
          <hr />
          <h4 style={{ margin: '0 0 10px' }}>直属成员</h4>
          {deptMembers.length === 0 ? (
            <p className="subtle">该部门下无直属成员（成员分布在下级部门）</p>
          ) : (
            deptMembers.map((m) => (
              <div className="metric-pair" key={m.id}>
                <span>
                  {m.name} · {m.empNo}
                </span>
                <span>{m.email}</span>
              </div>
            ))
          )}
        </div>
      </div>

      <Modal
        open={!!creating}
        title="新增部门"
        onClose={() => setCreating(null)}
        footer={
          <>
            <button className="ghost-btn" onClick={() => setCreating(null)}>
              取消
            </button>
            <button className="primary-btn" onClick={saveDept}>
              保存
            </button>
          </>
        }
      >
        {creating && (
          <div className="form-grid two-cols">
            <label className="full">
              部门名称
              <input value={creating.name} onChange={(e) => setCreating({ ...creating, name: e.target.value })} placeholder="如：产品部" />
            </label>
            <label>
              上级部门
              <Select
                value={creating.parentId || ''}
                options={departments.map((d) => ({ value: d.id, label: d.name }))}
                onChange={(val) => setCreating({ ...creating, parentId: val })}
              />
            </label>
            <label>
              负责人
              <input value={creating.manager} onChange={(e) => setCreating({ ...creating, manager: e.target.value })} placeholder="负责人姓名" />
            </label>
          </div>
        )}
      </Modal>
    </>
  );
}

/* ---------------- 人员设置 ---------------- */
const emptyMember = (deptId: string): Omit<Member, 'id'> => ({
  name: '',
  empNo: '',
  deptId,
  roleId: 'r4',
  email: '',
  status: 'active',
  seat: 'assigned',
  lastLogin: '—',
  sso: true,
});

function Members() {
  const { members, departments, roles, update, addOpLog, toast } = useStore();
  const [editing, setEditing] = useState<Member | null>(null);
  const [creating, setCreating] = useState<Omit<Member, 'id'> | null>(null);
  const deptName = (id: string) => departments.find((d) => d.id === id)?.name || '—';
  const roleName = (id: string) => roles.find((r) => r.id === id)?.name || '—';
  const isEmail = (email: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  function validateMember(member: Omit<Member, 'id'> | Member, currentId?: string) {
    if (!member.name.trim() || !member.empNo.trim()) {
      toast('请填写姓名和工号', 'danger');
      return false;
    }
    if (member.email && !isEmail(member.email)) {
      toast('邮箱格式不正确', 'danger');
      return false;
    }
    if (!departments.some((d) => d.id === member.deptId)) {
      toast('请选择有效部门', 'danger');
      return false;
    }
    if (!roles.some((r) => r.id === member.roleId)) {
      toast('请选择有效角色', 'danger');
      return false;
    }
    if (members.some((m) => m.empNo === member.empNo && m.id !== currentId)) {
      toast('工号已存在，不能重复添加', 'danger');
      return false;
    }
    return true;
  }

  function save() {
    if (editing) {
      if (!validateMember(editing, editing.id)) return;
      const next = { ...editing, name: editing.name.trim(), empNo: editing.empNo.trim(), email: editing.email.trim() };
      update((d) => ({ members: d.members.map((m) => (m.id === next.id ? next : m)) }));
      addOpLog({
        operator: 'admin',
        module: '组织架构',
        action: '编辑人员',
        target: next.name,
        result: 'success',
        ip: '10.1.28.16',
        detail: `更新角色为 ${roleName(next.roleId)}`,
      });
      toast('人员信息已更新', 'success');
      setEditing(null);
    } else if (creating) {
      if (!validateMember(creating)) return;
      const id = `m-${Date.now().toString().slice(-6)}`;
      const next = { ...creating, id, name: creating.name.trim(), empNo: creating.empNo.trim(), email: creating.email.trim() };
      update((d) => ({ members: [next, ...d.members] }));
      addOpLog({
        operator: 'admin',
        module: '组织架构',
        action: '新增人员',
        target: `${deptName(next.deptId)} / ${next.name}`,
        result: 'success',
        ip: '10.1.28.16',
        detail: `分配角色 ${roleName(next.roleId)}`,
      });
      toast('人员已新增', 'success');
      setCreating(null);
    }
  }

  function toggleFreeze(m: Member) {
    const next = m.status === 'frozen' ? 'active' : 'frozen';
    update((d) => ({ members: d.members.map((x) => (x.id === m.id ? { ...x, status: next } : x)) }));
    addOpLog({ operator: 'admin', module: '组织架构', action: next === 'frozen' ? '冻结账号' : '解冻账号', target: m.name, result: 'success', ip: '10.1.28.16', detail: '' });
    toast(`${m.name} 已${next === 'frozen' ? '冻结' : '解冻'}`, next === 'frozen' ? 'warning' : 'success');
  }

  const editForm = editing || creating;
  const setEF = (p: Partial<Member>) => {
    if (editing) setEditing({ ...editing, ...p });
    else if (creating) setCreating({ ...creating, ...p });
  };

  return (
    <>
      <div className="toolbar-card">
        <div>
          <strong>{members.length}</strong> 名平台用户 · {members.filter((m) => m.status === 'active').length} 个激活账号
        </div>
        <button
          className="primary-btn"
          disabled={departments.length === 0 || roles.length === 0}
          onClick={() => setCreating(emptyMember(departments.find((d) => d.parentId)?.id ?? departments[0]?.id ?? ''))}
        >
          + 新增人员
        </button>
      </div>
      <div className="table-card">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>姓名</th>
                <th>工号</th>
                <th>部门</th>
                <th>角色</th>
                <th>账号状态</th>
                <th>席位</th>
                <th>最近登录</th>
                <th>SSO</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.id}>
                  <td>{m.name}</td>
                  <td>{m.empNo}</td>
                  <td>{deptName(m.deptId)}</td>
                  <td>{roleName(m.roleId)}</td>
                  <td>
                    <span className={`status-tag ${m.status === 'active' ? 'success' : m.status === 'frozen' ? 'warning' : 'neutral'}`}>
                      {m.status === 'active' ? '正常' : m.status === 'frozen' ? '冻结中' : '待激活'}
                    </span>
                  </td>
                  <td>
                    <span className={`status-tag ${m.seat === 'assigned' ? 'success' : 'neutral'}`}>{m.seat === 'assigned' ? '已分配' : '未分配'}</span>
                  </td>
                  <td>{m.lastLogin}</td>
                  <td>
                    <span className={`status-tag ${m.sso ? 'success' : 'neutral'}`}>{m.sso ? '已接入' : '未接入'}</span>
                  </td>
                  <td>
                    <button className="text-btn" onClick={() => setEditing({ ...m })}>
                      编辑
                    </button>
                    {'　'}
                    <button className="text-btn danger-text" onClick={() => toggleFreeze(m)}>
                      {m.status === 'frozen' ? '解冻' : '冻结'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Modal
        open={!!editForm}
        title={editing ? `编辑人员 · ${editing.name}` : '新增人员'}
        onClose={() => {
          setEditing(null);
          setCreating(null);
        }}
        footer={
          <>
            <button
              className="ghost-btn"
              onClick={() => {
                setEditing(null);
                setCreating(null);
              }}
            >
              取消
            </button>
            <button className="primary-btn" onClick={save}>
              保存
            </button>
          </>
        }
      >
        {editForm && (
          <div className="form-grid two-cols">
            <label>
              姓名
              <input value={editForm.name} onChange={(e) => setEF({ name: e.target.value })} />
            </label>
            <label>
              工号
              <input value={editForm.empNo} onChange={(e) => setEF({ empNo: e.target.value })} />
            </label>
            <label>
              部门
              <Select
                value={editForm.deptId}
                options={departments.filter((d) => d.parentId).map((d) => ({ value: d.id, label: d.name }))}
                onChange={(val) => setEF({ deptId: val })}
              />
            </label>
            <label>
              角色
              <Select value={editForm.roleId} options={roles.map((r) => ({ value: r.id, label: r.name }))} onChange={(val) => setEF({ roleId: val })} />
            </label>
            <label>
              邮箱
              <input value={editForm.email} onChange={(e) => setEF({ email: e.target.value })} />
            </label>
            <label>
              席位
              <Select
                value={editForm.seat}
                options={[
                  { value: 'assigned', label: '已分配' },
                  { value: 'unassigned', label: '未分配' },
                ]}
                onChange={(val) => setEF({ seat: val as Member['seat'] })}
              />
            </label>
          </div>
        )}
      </Modal>
    </>
  );
}

/* ---------------- 角色设置 ---------------- */
function Roles() {
  const { roles, update, addOpLog, toast } = useStore();
  const [editing, setEditing] = useState<Role | null>(null);

  function save() {
    if (!editing) return;
    update((d) => ({ roles: d.roles.map((r) => (r.id === editing.id ? editing : r)) }));
    addOpLog({
      operator: 'admin',
      module: '角色设置',
      action: '修改角色',
      target: editing.name,
      result: 'success',
      ip: '10.1.28.16',
      detail: `权限项 ${editing.permissions.length} 个`,
    });
    toast('角色已保存', 'success');
    setEditing(null);
  }

  function addRole() {
    const id = `r-${Date.now().toString().slice(-5)}`;
    const role: Role = { id, name: '新建角色', desc: '自定义角色', dataScope: '所属部门', instanceScope: '授权实例', permissions: ['agent.view'], memberCount: 0, builtIn: false };
    update((d) => ({ roles: [...d.roles, role] }));
    addOpLog({ operator: 'admin', module: '角色设置', action: '新增角色', target: role.name, result: 'success', ip: '10.1.28.16', detail: '' });
    setEditing(role);
  }

  return (
    <>
      <div className="toolbar-card">
        <div>
          <strong>{roles.length}</strong> 个角色 · 支持功能 / 数据 / 实例三维授权
        </div>
        <button className="primary-btn" onClick={addRole}>
          + 新增角色
        </button>
      </div>
      <div className="card-grid two-cols">
        {roles.map((r) => (
          <div className="form-card" key={r.id}>
            <div className="card-topline">
              <h3>
                {r.name}{' '}
                {r.builtIn && (
                  <span className="status-tag info" style={{ marginLeft: 8 }}>
                    内置
                  </span>
                )}
              </h3>
              <button className="text-btn" onClick={() => setEditing({ ...r })}>
                配置权限
              </button>
            </div>
            <p className="subtle" style={{ marginTop: 0 }}>
              {r.desc}
            </p>
            <div className="summary-metrics">
              <div>
                <span>数据范围</span>
                <strong>{r.dataScope}</strong>
              </div>
              <div>
                <span>实例范围</span>
                <strong>{r.instanceScope}</strong>
              </div>
              <div>
                <span>成员数</span>
                <strong>{r.memberCount}</strong>
              </div>
              <div>
                <span>权限项</span>
                <strong>{r.permissions.length}</strong>
              </div>
            </div>
          </div>
        ))}
      </div>

      <Modal
        open={!!editing}
        title={editing ? `角色权限 · ${editing.name}` : ''}
        wide
        onClose={() => setEditing(null)}
        footer={
          <>
            <button className="ghost-btn" onClick={() => setEditing(null)}>
              取消
            </button>
            <button className="primary-btn" onClick={save}>
              保存
            </button>
          </>
        }
      >
        {editing && (
          <>
            <div className="form-grid two-cols" style={{ marginBottom: 16 }}>
              <label>
                角色名称
                <input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
              </label>
              <label>
                数据范围
                <Select
                  value={editing.dataScope}
                  options={['全平台', '运行数据', '所属部门', '个人数据'].map((s) => ({ value: s, label: s }))}
                  onChange={(val) => setEditing({ ...editing, dataScope: val })}
                />
              </label>
            </div>
            <div className="perm-tree">
              {PERMISSION_GROUPS.map((g) => (
                <div className="perm-group" key={g.group}>
                  <label>{g.group}</label>
                  <div className="perm-items">
                    {g.items.map((it) => (
                      <Checkbox
                        key={it.key}
                        checked={editing.permissions.includes(it.key)}
                        onChange={(e) => {
                          setEditing({
                            ...editing,
                            permissions: e.target.checked ? [...editing.permissions, it.key] : editing.permissions.filter((p) => p !== it.key),
                          });
                        }}
                      >
                        {it.label}
                      </Checkbox>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </Modal>
    </>
  );
}

/* ---------------- 权限查看（权限矩阵） ---------------- */
function Permissions() {
  const { roles } = useStore();
  const allPerms = PERMISSION_GROUPS.flatMap((g) => g.items.map((i) => ({ ...i, group: g.group })));
  return (
    <>
      <div className="info-banner">权限矩阵：展示各角色对功能权限项的授权情况。✓ 表示已授权，可在「角色设置」中调整。</div>
      <div className="table-card">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>权限项</th>
                <th>分组</th>
                {roles.map((r) => (
                  <th key={r.id} style={{ textAlign: 'center' }}>
                    {r.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {allPerms.map((p) => (
                <tr key={p.key}>
                  <td>{p.label}</td>
                  <td>
                    <span className="tag-pill">{p.group}</span>
                  </td>
                  {roles.map((r) => (
                    <td key={r.id} style={{ textAlign: 'center' }}>
                      {r.permissions.includes(p.key) ? <span style={{ color: 'var(--success)', fontWeight: 700 }}>✓</span> : <span style={{ color: '#cbd5e1' }}>—</span>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="four-cols" style={{ marginTop: 18 }}>
        <div className="stat-card">
          <span>高危操作项</span>
          <strong>5</strong>
          <em>删除/下线/权限变更等</em>
        </div>
        <div className="stat-card">
          <span>审批型权限项</span>
          <strong>3</strong>
          <em>共享/发布需审批</em>
        </div>
        <div className="stat-card">
          <span>按钮级权限</span>
          <strong>{allPerms.length}</strong>
          <em>细粒度控制</em>
        </div>
        <div className="stat-card">
          <span>数据范围规则</span>
          <strong>4</strong>
          <em>全平台→个人</em>
        </div>
      </div>
    </>
  );
}

/* ---------------- 操作日志 ---------------- */
function OpLogView() {
  const { opLogs } = useStore();
  const [q, setQ] = useState('');
  const [mod, setMod] = useState('全部');
  const modules = useMemo(() => ['全部', ...Array.from(new Set(opLogs.map((o) => o.module)))], [opLogs]);
  const filtered = opLogs.filter((o) => (mod === '全部' || o.module === mod) && (q === '' || o.operator.includes(q) || o.target.includes(q) || o.action.includes(q)));
  return (
    <>
      <div className="toolbar-card">
        <div className="search-row">
          <input placeholder="搜索操作人 / 操作 / 对象" value={q} onChange={(e) => setQ(e.target.value)} />
          <Select value={mod} options={modules.map((m) => ({ value: m, label: m }))} onChange={(val) => setMod(val)} />
        </div>
        <div className="subtle">共 {filtered.length} 条，实时记录到本地</div>
      </div>
      <div className="table-card">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>操作人</th>
                <th>模块</th>
                <th>操作</th>
                <th>对象</th>
                <th>结果</th>
                <th>IP</th>
                <th>详情</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((o) => (
                <tr key={o.id}>
                  <td>{o.ts}</td>
                  <td>{o.operator}</td>
                  <td>
                    <span className="tag-pill">{o.module}</span>
                  </td>
                  <td>{o.action}</td>
                  <td>{o.target}</td>
                  <td>
                    <span className={`status-tag ${o.result === 'success' ? 'success' : 'danger'}`}>{o.result === 'success' ? '成功' : '失败'}</span>
                  </td>
                  <td>{o.ip}</td>
                  <td className="subtle" style={{ maxWidth: 240 }}>
                    {o.detail || '—'}
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
