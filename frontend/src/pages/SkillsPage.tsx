import { useMemo, useState, useCallback } from 'react';
import { useStore } from '../store/store-context';
import { confirmDangerousAction } from '../utils';
import type { Skill } from '../store/types';
import Modal from '../components/Modal';
import Select from '../components/Select';
import Checkbox from '../components/Checkbox';

const STATUS_META: Record<Skill['status'], { label: string; tag: string }> = {
  enabled: { label: '已启用', tag: 'success' },
  disabled: { label: '已禁用', tag: 'neutral' },
  reviewing: { label: '待审核', tag: 'warning' },
};

const CATEGORIES = ['全部', '法务', '财务', '办公', '知识', '自动化'];
const FORM_CATEGORIES = ['法务', '财务', '办公', '知识', '自动化'];

const today = () => new Date().toISOString().slice(0, 10);

interface DraftSkill {
  name: string;
  category: string;
  source: string;
  description: string;
  mode: 'prompt' | 'file' | 'url';
  file: File | null;
  url: string;
}

const emptyDraft = (): DraftSkill => ({ name: '', category: '办公', source: '自定义', description: '', mode: 'prompt', file: null, url: '' });

function bumpVersion(v: string): string {
  const m = v.match(/^(v?)(\d+)\.(\d+)\.(\d+)$/);
  if (!m) return v;
  const [, prefix, major, minor, patch] = m;
  return `${prefix}${major}.${minor}.${Number(patch) + 1}`;
}

function packageNameFromName(name: string) {
  return (
    name
      .trim()
      .toLowerCase()
      .replace(/[^\da-z]+/g, '_')
      .replace(/^_+|_+$/g, '') || name.trim()
  );
}

export default function SkillsPage() {
  const { skills, roles, update, addOpLog, toast } = useStore();
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('全部');
  const [draft, setDraft] = useState<DraftSkill | null>(null);
  const [editingPermission, setEditingPermission] = useState<Skill | null>(null);
  const [importing, setImporting] = useState(false);
  const [selectedImports, setSelectedImports] = useState<string[]>([]);

  // Skill 广场预置（10 个可导入）
  const SKILL_PLAZA = [
    { name: '智能翻译', category: '语言', description: '支持 100+ 语言互译，自动识别源语言' },
    { name: '情感分析', category: 'NLP', description: '文本情感倾向分析（正面/负面/中性）' },
    { name: '实体识别', category: 'NLP', description: '提取文本中的人名、地名、机构名等实体' },
    { name: '文本摘要', category: 'NLP', description: '长文本自动提取关键摘要' },
    { name: '问答生成', category: '对话', description: '根据知识库自动生成问答对' },
    { name: '意图识别', category: '对话', description: '识别用户意图并分类路由' },
    { name: '关键词提取', category: 'NLP', description: '提取文本核心关键词与主题' },
    { name: '文本分类', category: 'NLP', description: '多标签文本自动分类' },
    { name: '相似度计算', category: 'NLP', description: '计算两段文本的语义相似度' },
    { name: '文本纠错', category: '语言', description: '自动检测并纠正拼写与语法错误' },
  ];

  const filtered = useMemo(() => {
    const kw = search.trim().toLowerCase();
    return skills.filter((s) => {
      if (category !== '全部' && s.category !== category) return false;
      if (kw && !`${s.name} ${s.source} ${s.creator}`.toLowerCase().includes(kw)) return false;
      return true;
    });
  }, [skills, search, category]);

  const stats = useMemo(
    () => ({
      total: skills.length,
      enabled: skills.filter((s) => s.status === 'enabled').length,
      reviewing: skills.filter((s) => s.status === 'reviewing').length,
      bound: skills.reduce((sum, s) => sum + s.boundAgents, 0),
    }),
    [skills],
  );

  function toggleStatus(s: Skill) {
    const next: Skill['status'] = s.status === 'enabled' ? 'disabled' : 'enabled';
    update((d) => ({ skills: d.skills.map((x) => (x.id === s.id ? { ...x, status: next, updatedAt: today() } : x)) }));
    addOpLog({
      operator: '平台管理员',
      module: 'Skill 管理',
      action: next === 'enabled' ? '启用 Skill' : '禁用 Skill',
      target: s.name,
      result: 'success',
      ip: '10.1.28.16',
      detail: STATUS_META[next].label,
    });
    toast(`${s.name} 已${STATUS_META[next].label}`, next === 'enabled' ? 'success' : 'warning');
  }

  function approve(s: Skill) {
    update((d) => ({ skills: d.skills.map((x) => (x.id === s.id ? { ...x, status: 'enabled', updatedAt: today() } : x)) }));
    addOpLog({ operator: '平台管理员', module: 'Skill 管理', action: '审核通过', target: s.name, result: 'success', ip: '10.1.28.16', detail: '审核通过并启用' });
    toast(`${s.name} 审核通过`, 'success');
  }

  function bumpSkill(s: Skill) {
    const next = bumpVersion(s.version);
    update((d) => ({ skills: d.skills.map((x) => (x.id === s.id ? { ...x, version: next, updatedAt: today() } : x)) }));
    addOpLog({ operator: '平台管理员', module: 'Skill 管理', action: '更新版本', target: s.name, result: 'success', ip: '10.1.28.16', detail: `${s.version} → ${next}` });
    toast(`${s.name} 已更新至 ${next}`, 'success');
  }

  function deleteSkill(s: Skill) {
    if (!confirmDangerousAction(`确认删除 Skill「${s.name}」？删除前请确认没有生产实例依赖该能力。`)) return;
    if (s.boundAgents > 0) {
      toast(`「${s.name}」已绑定 ${s.boundAgents} 个实例，请先在智能体配置中解绑`, 'danger');
      return;
    }
    update((d) => ({ skills: d.skills.filter((x) => x.id !== s.id) }));
    addOpLog({ operator: '平台管理员', module: 'Skill 管理', action: '删除 Skill', target: s.name, result: 'success', ip: '10.1.28.16', detail: `${s.category} · ${s.version}` });
    toast(`Skill「${s.name}」已删除`, 'warning');
  }

  function createSkill() {
    if (!draft) return;
    if (!draft.name.trim()) {
      toast('请填写 Skill 名称', 'danger');
      return;
    }
    if (draft.mode === 'file' && !draft.file) {
      toast('请选择要上传的文件', 'danger');
      return;
    }
    if (draft.mode === 'url' && !draft.url.trim()) {
      toast('请填写导入 URL', 'danger');
      return;
    }
    const id = `sk-${Date.now().toString().slice(-6)}`;
    const sourceLabel = draft.mode === 'file' ? '文件上传' : draft.mode === 'url' ? 'URL 导入' : draft.source;
    const skill: Skill = {
      id,
      name: draft.name.trim(),
      packageName: draft.mode === 'url' ? packageNameFromName(draft.name) : undefined,
      packageUrl: draft.mode === 'url' ? draft.url.trim() : undefined,
      source: sourceLabel,
      version: 'v0.1.0',
      status: 'reviewing',
      boundAgents: 0,
      creator: '平台管理员',
      updatedAt: today(),
      category: draft.category,
      allowedRoles: [], // 新建时默认无权限，需要后续配置
    };
    update((d) => ({ skills: [skill, ...d.skills] }));
    const detail =
      draft.mode === 'file'
        ? `${skill.category} · 文件 ${draft.file?.name} · 提交审核`
        : draft.mode === 'url'
          ? `${skill.category} · 来源 ${draft.url.trim()} · 提交审核`
          : `${skill.category} · 提交审核`;
    addOpLog({ operator: '平台管理员', module: 'Skill 管理', action: '新建 Skill', target: skill.name, result: 'success', ip: '10.1.28.16', detail });
    toast('Skill 已创建，进入审核流程', 'success');
    setDraft(null);
  }

  function savePermission() {
    if (!editingPermission) return;
    update((d) => ({ skills: d.skills.map((s) => (s.id === editingPermission.id ? editingPermission : s)) }));
    const roleNames = editingPermission.allowedRoles.map((rid) => roles.find((r) => r.id === rid)?.name || rid).join(', ');
    addOpLog({
      operator: '平台管理员',
      module: 'Skill 管理',
      action: '配置权限',
      target: editingPermission.name,
      result: 'success',
      ip: '10.1.28.16',
      detail: `允许角色：${roleNames || '无'}`,
    });
    toast('权限配置已保存', 'success');
    setEditingPermission(null);
  }

  function importSkills() {
    if (selectedImports.length === 0) {
      toast('请至少选择一个 Skill', 'danger');
      return;
    }
    const newSkills = selectedImports.map((name) => {
      const plaza = SKILL_PLAZA.find((p) => p.name === name)!;
      return {
        id: `sk-${Date.now().toString().slice(-6)}-${Math.random().toString(36).slice(2, 5)}`,
        name: plaza.name,
        source: 'Skill 广场',
        version: 'v1.0.0',
        status: 'reviewing' as const,
        boundAgents: 0,
        creator: '平台管理员',
        updatedAt: today(),
        category: plaza.category,
        allowedRoles: [],
      };
    });
    update((d) => ({ skills: [...newSkills, ...d.skills] }));
    addOpLog({
      operator: '平台管理员',
      module: 'Skill 管理',
      action: '从广场导入 Skill',
      target: `${selectedImports.length} 个`,
      result: 'success',
      ip: '10.1.28.16',
      detail: selectedImports.join(', '),
    });
    toast(`已导入 ${selectedImports.length} 个 Skill，进入审核流程`, 'success');
    setImporting(false);
    setSelectedImports([]);
  }

  const toggleRole = useCallback((roleId: string) => {
    setEditingPermission((prev) => {
      if (!prev) return prev;
      const isSelected = prev.allowedRoles.includes(roleId);
      return {
        ...prev,
        allowedRoles: isSelected ? prev.allowedRoles.filter((id) => id !== roleId) : [...prev.allowedRoles, roleId],
      };
    });
  }, []);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Skill 管理</h1>
          <p>官方预置开箱即用、自定义一句话创建、广场一键导入，为智能体灵活装配各类 Skill 能力。</p>
        </div>
        <div className="head-actions">
          <button className="ghost-btn" onClick={() => setImporting(true)}>
            导入 Skill
          </button>
          <button className="primary-btn" onClick={() => setDraft(emptyDraft())}>
            + 新建 Skill
          </button>
        </div>
      </div>

      <div className="triple-hero">
        <div className="hero-card gradient-a">
          <h3>官方预置 Skills</h3>
          <ul>
            <li>Office 三件套自动化</li>
            <li>浏览器自动化操作</li>
            <li>网页抓取与解析</li>
          </ul>
        </div>
        <div className="hero-card gradient-b">
          <h3>自定义 Skills 创建</h3>
          <ul>
            <li>对话式一句话生成</li>
            <li>上传文件导入</li>
            <li>URL 导入封装</li>
          </ul>
        </div>
        <div className="hero-card gradient-c">
          <h3>Skills 广场</h3>
          <ul>
            <li>精选 Skill 一键安装</li>
            <li>发布自有 Skill 到广场</li>
            <li>社区评分与版本订阅</li>
          </ul>
        </div>
      </div>

      <div className="feature-grid">
        <div className="feature-card">
          <h4>启用 / 禁用控制</h4>
          <p>按实例与部门精细化开关 Skill，变更即时生效并写入操作审计。</p>
        </div>
        <div className="feature-card">
          <h4>版本与更新</h4>
          <p>支持灰度发布与一键升级，保留版本记录与回滚能力。</p>
        </div>
        <div className="feature-card">
          <h4>企业预置</h4>
          <p>管理员可将 Skill 预置到企业模板，统一下发到旗下智能体。</p>
        </div>
        <div className="feature-card">
          <h4>安全审核机制</h4>
          <p>自定义与导入 Skill 需经安全审核后方可启用，防止越权调用。</p>
        </div>
      </div>

      <div className="four-cols stats-grid">
        <div className="stat-card accent">
          <span>技能总数</span>
          <strong>{stats.total}</strong>
          <em>官方+自定义+导入</em>
        </div>
        <div className="stat-card">
          <span>已启用</span>
          <strong>{stats.enabled}</strong>
          <em>正在被智能体调用</em>
        </div>
        <div className="stat-card">
          <span>待审核</span>
          <strong>{stats.reviewing}</strong>
          <em>等待安全审核</em>
        </div>
        <div className="stat-card">
          <span>绑定实例总数</span>
          <strong>{stats.bound}</strong>
          <em>累计装配次数</em>
        </div>
      </div>

      <div className="toolbar-card">
        <div className="search-row">
          <input placeholder="搜索 Skill 名称 / 来源 / 创建人…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className="chip-group">
          {CATEGORIES.map((c) => (
            <button key={c} className={`chip${category === c ? ' active' : ''}`} onClick={() => setCategory(c)}>
              {c}
            </button>
          ))}
        </div>
      </div>

      <div className="table-card">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Skill 名称</th>
                <th>来源</th>
                <th>分类</th>
                <th>版本</th>
                <th>状态</th>
                <th>可用角色</th>
                <th>绑定实例数</th>
                <th>创建人</th>
                <th>更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td>{s.source}</td>
                  <td>
                    <span className="tag-pill">{s.category}</span>
                  </td>
                  <td>{s.version}</td>
                  <td>
                    <span className={`status-tag ${STATUS_META[s.status].tag}`}>{STATUS_META[s.status].label}</span>
                  </td>
                  <td>
                    {s.allowedRoles.length === 0 ? (
                      <span style={{ color: 'var(--muted)', fontSize: '12px' }}>未配置</span>
                    ) : (
                      s.allowedRoles.map((rid) => roles.find((r) => r.id === rid)?.name || rid).join(', ')
                    )}
                  </td>
                  <td>{s.boundAgents}</td>
                  <td>{s.creator}</td>
                  <td className="subtle">{s.updatedAt}</td>
                  <td>
                    {s.status === 'reviewing' ? (
                      <button className="text-btn" onClick={() => approve(s)}>
                        通过审核
                      </button>
                    ) : (
                      <button className="text-btn" onClick={() => toggleStatus(s)}>
                        {s.status === 'enabled' ? '禁用' : '启用'}
                      </button>
                    )}
                    {'　'}
                    <button className="text-btn" onClick={() => setEditingPermission({ ...s })}>
                      权限
                    </button>
                    {'　'}
                    <button className="text-btn" onClick={() => bumpSkill(s)}>
                      升级
                    </button>
                    {'　'}
                    <button className="text-btn danger-text" onClick={() => deleteSkill(s)}>
                      删除
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={10} className="subtle" style={{ textAlign: 'center', padding: '28px 0' }}>
                    没有匹配的 Skill
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Modal
        open={!!draft}
        title="新建 Skill"
        wide
        onClose={() => setDraft(null)}
        footer={
          <>
            <button className="ghost-btn" onClick={() => setDraft(null)}>
              取消
            </button>
            <button className="primary-btn" onClick={createSkill}>
              提交审核
            </button>
          </>
        }
      >
        {draft && (
          <>
            <div className="info-banner">新建 Skill 默认进入待审核状态，安全审核通过后方可启用并装配到智能体实例。</div>
            <div className="chip-group" style={{ margin: '14px 0' }}>
              {(
                [
                  { key: 'prompt', label: '一句话生成' },
                  { key: 'file', label: '文件上传' },
                  { key: 'url', label: 'URL 导入' },
                ] as const
              ).map((m) => (
                <button key={m.key} className={`chip${draft.mode === m.key ? ' active' : ''}`} onClick={() => setDraft({ ...draft, mode: m.key })}>
                  {m.label}
                </button>
              ))}
            </div>
            <div className="form-grid two-cols">
              <label>
                名称
                <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="如：合同条款抽取" />
              </label>
              <label>
                分类
                <Select value={draft.category} options={FORM_CATEGORIES.map((c) => ({ value: c, label: c }))} onChange={(val) => setDraft({ ...draft, category: val })} />
              </label>

              {draft.mode === 'prompt' && (
                <label className="full">
                  描述
                  <textarea
                    rows={3}
                    value={draft.description}
                    onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                    placeholder="用一句话描述该 Skill 的能力与适用场景，系统将自动生成"
                  />
                </label>
              )}

              {draft.mode === 'file' && (
                <>
                  <label className="full">
                    选择文件
                    <input
                      type="file"
                      accept=".json,.yaml,.yml,.zip,.py,.js,.ts,.md,.txt"
                      onChange={(e) => {
                        const file = e.target.files?.[0] || null;
                        if (file && !draft.name.trim()) {
                          setDraft({ ...draft, file, name: file.name.replace(/\.[^.]+$/, '') });
                        } else {
                          setDraft({ ...draft, file });
                        }
                      }}
                    />
                  </label>
                  {draft.file && (
                    <p className="subtle full" style={{ margin: 0 }}>
                      已选择：{draft.file.name} ({Math.round(draft.file.size / 1024)} KB)
                    </p>
                  )}
                  <label className="full">
                    描述
                    <textarea
                      rows={2}
                      value={draft.description}
                      onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                      placeholder="补充该 Skill 的能力与适用场景（选填）"
                    />
                  </label>
                </>
              )}

              {draft.mode === 'url' && (
                <>
                  <label className="full">
                    导入 URL
                    <input value={draft.url} onChange={(e) => setDraft({ ...draft, url: e.target.value })} placeholder="如：https://github.com/org/skill-repo 或 OpenAPI 地址" />
                  </label>
                  <label className="full">
                    描述
                    <textarea
                      rows={2}
                      value={draft.description}
                      onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                      placeholder="补充该 Skill 的能力与适用场景（选填）"
                    />
                  </label>
                </>
              )}
            </div>
          </>
        )}
      </Modal>

      {/* 权限配置 Modal */}
      <Modal
        open={!!editingPermission}
        title={editingPermission ? `配置权限 · ${editingPermission.name}` : ''}
        onClose={() => setEditingPermission(null)}
        footer={
          <>
            <button className="ghost-btn" onClick={() => setEditingPermission(null)}>
              取消
            </button>
            <button className="primary-btn" onClick={savePermission}>
              保存
            </button>
          </>
        }
      >
        {editingPermission && (
          <>
            <div className="info-banner">选择允许使用此 Skill 的角色。未勾选的角色将无法在智能体实例中调用该 Skill。</div>
            <div style={{ marginTop: 16 }}>
              <strong style={{ display: 'block', marginBottom: 12 }}>允许使用的角色</strong>
              <div className="perm-items">
                {roles.map((role) => (
                  <div key={role.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Checkbox checked={editingPermission.allowedRoles.includes(role.id)} onChange={() => toggleRole(role.id)}>
                      {role.name}
                    </Checkbox>
                    <span style={{ color: 'var(--muted)', fontSize: '12px' }}>({role.memberCount} 人)</span>
                  </div>
                ))}
                {roles.length === 0 && <p style={{ color: 'var(--muted)', margin: 0 }}>暂无可用角色</p>}
              </div>
            </div>
          </>
        )}
      </Modal>

      {/* 导入 Skill Modal */}
      <Modal
        open={importing}
        title="从 Skill 广场导入"
        wide
        onClose={() => {
          setImporting(false);
          setSelectedImports([]);
        }}
        footer={
          <>
            <button
              className="ghost-btn"
              onClick={() => {
                setImporting(false);
                setSelectedImports([]);
              }}
            >
              取消
            </button>
            <button className="primary-btn" onClick={importSkills}>
              导入 ({selectedImports.length})
            </button>
          </>
        }
      >
        <div className="info-banner">从 Skill 广场选择并导入预置 Skill，导入后状态为「审核中」，需审核通过后才能在智能体创建时使用。</div>
        <div className="card-grid two-cols" style={{ marginTop: 16 }}>
          {SKILL_PLAZA.map((s) => {
            const selected = selectedImports.includes(s.name);
            return (
              <div
                key={s.name}
                className={`form-card${selected ? ' selected' : ''}`}
                style={{ cursor: 'pointer', border: selected ? '2px solid var(--primary)' : undefined }}
                onClick={() => setSelectedImports((prev) => (prev.includes(s.name) ? prev.filter((n) => n !== s.name) : [...prev, s.name]))}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <Checkbox checked={selected} style={{ pointerEvents: 'none' }} />
                  <h4 style={{ margin: 0 }}>{s.name}</h4>
                </div>
                <p className="subtle" style={{ margin: 0, fontSize: 13 }}>
                  {s.description}
                </p>
                <span className="tag-pill" style={{ marginTop: 8 }}>
                  {s.category}
                </span>
              </div>
            );
          })}
        </div>
      </Modal>
    </div>
  );
}
