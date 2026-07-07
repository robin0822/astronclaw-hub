import { useMemo, useState } from 'react';
import { useStore } from '../store/store-context';
import { confirmDangerousAction } from '../utils';
import type { KnowledgeBaseFile } from '../store/types';
import Modal from '../components/Modal';
import Select from '../components/Select';

const CATEGORIES = ['全部', '合同文档', '制度规范', '技术文档', '产品资料', '财务报表', '培训资料', '其他'];
const FORM_CATEGORIES = CATEGORIES.filter((c) => c !== '全部');
const FILE_EXTS: Record<KnowledgeBaseFile['type'], string> = {
  pdf: 'PDF',
  docx: 'Word',
  txt: 'TXT',
  xlsx: 'Excel',
  pptx: 'PPT',
  md: 'Markdown',
};
const STATUS_LABEL: Record<KnowledgeBaseFile['status'], { label: string; tag: string }> = {
  processing: { label: '解析中', tag: 'warning' },
  indexed: { label: '已入库', tag: 'success' },
  failed: { label: '失败', tag: 'danger' },
};

const today = () => new Date().toISOString().slice(0, 10);

interface DraftFile {
  name: string;
  category: string;
  file: File | null;
}

const emptyDraft = (): DraftFile => ({ name: '', category: FORM_CATEGORIES[0], file: null });

export default function KnowledgePage() {
  const { knowledgeFiles: files, update, addOpLog, toast } = useStore();
  const [search, setSearch] = useState('');
  const [cat, setCat] = useState('全部');
  const [draft, setDraft] = useState<DraftFile | null>(null);
  const [viewing, setViewing] = useState<KnowledgeBaseFile | null>(null);

  const filtered = useMemo(() => {
    const kw = search.trim().toLowerCase();
    return files.filter((f) => {
      if (cat !== '全部' && f.category !== cat) return false;
      if (kw && !`${f.name} ${f.category} ${f.uploadedBy}`.toLowerCase().includes(kw)) return false;
      return true;
    });
  }, [files, search, cat]);

  const stats = useMemo(
    () => ({
      total: files.length,
      indexed: files.filter((f) => f.status === 'indexed').length,
      processing: files.filter((f) => f.status === 'processing').length,
      totalChunks: files.reduce((s, f) => s + f.chunks, 0),
      totalRefs: files.reduce((s, f) => s + f.refs, 0),
    }),
    [files],
  );

  function uploadFile() {
    if (!draft || !draft.file) {
      toast('请选择要上传的文件', 'danger');
      return;
    }
    if (!draft.name.trim()) {
      toast('请填写文件名称', 'danger');
      return;
    }
    const ext = draft.file.name.split('.').pop()?.toLowerCase() as KnowledgeBaseFile['type'];
    if (!['pdf', 'docx', 'txt', 'xlsx', 'pptx', 'md'].includes(ext)) {
      toast('不支持的文件格式，仅支持 PDF / Word / Excel / PPT / TXT / Markdown', 'danger');
      return;
    }
    const id = `kb-${Date.now().toString().slice(-6)}`;
    const newFile: KnowledgeBaseFile = {
      id,
      name: draft.name.trim(),
      type: ext,
      size: Math.round(draft.file.size / 1024),
      category: draft.category,
      uploadedBy: '平台管理员',
      uploadedAt: today(),
      status: 'processing',
      chunks: 0,
      refs: 0,
    };
    update((d) => ({ knowledgeFiles: [newFile, ...d.knowledgeFiles] }));
    addOpLog({
      operator: '平台管理员',
      module: '知识管理',
      action: '上传知识库文件',
      target: newFile.name,
      result: 'success',
      ip: '10.1.28.16',
      detail: `${newFile.type.toUpperCase()} · ${newFile.size}KB · ${newFile.category}`,
    });
    toast(`${newFile.name} 上传成功，正在解析与向量化…`, 'info');
    setDraft(null);

    // 模拟异步解析完成
    setTimeout(() => {
      const chunks = Math.round(20 + Math.random() * 150);
      update((d) => ({ knowledgeFiles: d.knowledgeFiles.map((f) => (f.id === id ? { ...f, status: 'indexed', chunks } : f)) }));
      toast(`${newFile.name} 已完成解析，生成 ${chunks} 个向量切片`, 'success');
    }, 2500);
  }

  function deleteFile(f: KnowledgeBaseFile) {
    if (!confirmDangerousAction(`确认删除知识库文件「${f.name}」？相关向量切片和引用关系将被移除。`)) return;
    update((d) => ({ knowledgeFiles: d.knowledgeFiles.filter((x) => x.id !== f.id) }));
    addOpLog({
      operator: '平台管理员',
      module: '知识管理',
      action: '删除知识库文件',
      target: f.name,
      result: 'success',
      ip: '10.1.28.16',
      detail: `${f.category} · ${f.chunks} 个切片已移除`,
    });
    toast(`${f.name} 已从知识库删除`, 'danger');
    if (viewing?.id === f.id) setViewing(null);
  }

  function reindex(f: KnowledgeBaseFile) {
    update((d) => ({ knowledgeFiles: d.knowledgeFiles.map((x) => (x.id === f.id ? { ...x, status: 'processing', chunks: 0 } : x)) }));
    addOpLog({ operator: '平台管理员', module: '知识管理', action: '重新索引文件', target: f.name, result: 'success', ip: '10.1.28.16', detail: `触发重新解析与向量化` });
    toast(`${f.name} 正在重新解析…`, 'info');
    setTimeout(() => {
      const chunks = Math.round(20 + Math.random() * 150);
      update((d) => ({ knowledgeFiles: d.knowledgeFiles.map((x) => (x.id === f.id ? { ...x, status: 'indexed', chunks } : x)) }));
      toast(`${f.name} 重新索引完成`, 'success');
    }, 2200);
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>知识管理</h1>
          <p>企业知识库文件上传、向量化与检索管理。支持 PDF / Word / Excel / PPT / Markdown 等文档格式，自动切片并构建语义索引，供智能体智能检索引用。</p>
        </div>
        <div className="head-actions">
          <button className="primary-btn" onClick={() => setDraft(emptyDraft())}>
            + 上传文件
          </button>
        </div>
      </div>

      <div className="info-banner">上传的文件将自动解析为文本、切片、向量化后存入知识库。智能体在对话时可通过语义检索召回相关知识，引用次数实时统计。</div>

      <div className="five-cols stats-grid">
        <div className="stat-card accent">
          <span>知识库文件</span>
          <strong>{stats.total}</strong>
          <em>已上传文档数</em>
        </div>
        <div className="stat-card">
          <span>已入库</span>
          <strong>{stats.indexed}</strong>
          <em>可供检索引用</em>
        </div>
        <div className="stat-card">
          <span>解析中</span>
          <strong>{stats.processing}</strong>
          <em>向量化处理中</em>
        </div>
        <div className="stat-card">
          <span>向量切片总数</span>
          <strong>{stats.totalChunks}</strong>
          <em>语义检索粒度</em>
        </div>
        <div className="stat-card">
          <span>累计引用次数</span>
          <strong>{stats.totalRefs}</strong>
          <em>被智能体召回</em>
        </div>
      </div>

      <div className="toolbar-card">
        <div className="search-row">
          <input placeholder="搜索文件名 / 分类 / 上传者…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className="chip-group">
          {CATEGORIES.map((c) => (
            <button key={c} className={`chip${cat === c ? ' active' : ''}`} onClick={() => setCat(c)}>
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
                <th>文件名</th>
                <th>格式</th>
                <th>大小</th>
                <th>分类</th>
                <th>上传者</th>
                <th>上传时间</th>
                <th>状态</th>
                <th>向量切片</th>
                <th>引用次数</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((f) => (
                <tr key={f.id}>
                  <td style={{ fontWeight: 500 }}>{f.name}</td>
                  <td>
                    <span className="tag-pill">{FILE_EXTS[f.type]}</span>
                  </td>
                  <td className="subtle">{f.size} KB</td>
                  <td>
                    <span className="tag-pill">{f.category}</span>
                  </td>
                  <td>{f.uploadedBy}</td>
                  <td className="subtle">{f.uploadedAt}</td>
                  <td>
                    <span className={`status-tag ${STATUS_LABEL[f.status].tag}`}>{STATUS_LABEL[f.status].label}</span>
                  </td>
                  <td>{f.chunks > 0 ? f.chunks : '—'}</td>
                  <td>{f.refs}</td>
                  <td>
                    <button className="text-btn" onClick={() => setViewing(f)}>
                      详情
                    </button>
                    {'　'}
                    {f.status === 'indexed' && (
                      <button className="text-btn" onClick={() => reindex(f)}>
                        重新索引
                      </button>
                    )}
                    {f.status === 'failed' && (
                      <button className="text-btn" onClick={() => reindex(f)}>
                        重试
                      </button>
                    )}
                    {'　'}
                    <button className="text-btn danger-text" onClick={() => deleteFile(f)}>
                      删除
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={10} className="subtle" style={{ textAlign: 'center', padding: '28px 0' }}>
                    没有匹配的文件
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Modal
        open={!!draft}
        title="上传知识库文件"
        onClose={() => setDraft(null)}
        footer={
          <>
            <button className="ghost-btn" onClick={() => setDraft(null)}>
              取消
            </button>
            <button className="primary-btn" onClick={uploadFile}>
              上传
            </button>
          </>
        }
      >
        {draft && (
          <>
            <div className="info-banner">支持 PDF / Word / Excel / PPT / TXT / Markdown 格式。上传后自动解析、切片并向量化，供智能体语义检索。</div>
            <div className="form-grid two-cols">
              <label>
                文件名称
                <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="如：产品手册v2.0" />
              </label>
              <label>
                分类
                <Select value={draft.category} options={FORM_CATEGORIES.map((c) => ({ value: c, label: c }))} onChange={(val) => setDraft({ ...draft, category: val })} />
              </label>
              <label className="full">
                选择文件
                <input
                  type="file"
                  accept=".pdf,.docx,.txt,.xlsx,.pptx,.md"
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
                <p className="subtle" style={{ marginTop: 8 }}>
                  已选择：{draft.file.name} ({Math.round(draft.file.size / 1024)} KB)
                </p>
              )}
            </div>
          </>
        )}
      </Modal>

      <Modal
        open={!!viewing}
        title={viewing ? `文件详情 · ${viewing.name}` : '文件详情'}
        wide
        onClose={() => setViewing(null)}
        footer={
          <button className="ghost-btn" onClick={() => setViewing(null)}>
            关闭
          </button>
        }
      >
        {viewing && (
          <>
            <div className="form-grid two-cols">
              <label>
                文件名
                <input value={viewing.name} readOnly />
              </label>
              <label>
                格式
                <input value={FILE_EXTS[viewing.type]} readOnly />
              </label>
              <label>
                大小
                <input value={`${viewing.size} KB`} readOnly />
              </label>
              <label>
                分类
                <input value={viewing.category} readOnly />
              </label>
              <label>
                上传者
                <input value={viewing.uploadedBy} readOnly />
              </label>
              <label>
                上传时间
                <input value={viewing.uploadedAt} readOnly />
              </label>
              <label>
                状态
                <input value={STATUS_LABEL[viewing.status].label} readOnly />
              </label>
              <label>
                向量切片数
                <input value={viewing.chunks > 0 ? String(viewing.chunks) : '解析中'} readOnly />
              </label>
            </div>
            <h4 className="section-title">引用统计</h4>
            <div className="summary-metrics">
              <div>
                <span>累计引用次数</span>
                <strong>{viewing.refs}</strong>
              </div>
              <div>
                <span>引用智能体数</span>
                <strong>{Math.max(1, Math.round(viewing.refs / 12))}</strong>
              </div>
              <div>
                <span>平均每次召回</span>
                <strong>{viewing.chunks > 0 ? Math.ceil((viewing.refs / viewing.chunks) * 10) / 10 : '—'}</strong>
              </div>
              <div>
                <span>最近被引用</span>
                <strong>{viewing.refs > 0 ? '2 小时前' : '—'}</strong>
              </div>
            </div>
          </>
        )}
      </Modal>
    </div>
  );
}
