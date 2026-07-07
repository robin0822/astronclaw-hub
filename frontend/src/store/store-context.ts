import { createContext, useContext } from 'react';
import type { Agent, Alert, Channel, Department, InspectionReport, Knowledge, KnowledgeBaseFile, Member, ModelEntry, OpLog, Role, Seat, SecurityPolicy, Skill } from './types';

/**
 * 前端本地业务状态的完整结构。
 *
 * 当前项目还没有把所有页面都接到真实后端列表接口，所以这里暂时承担页面之间共享数据、
 * 操作日志、toast 反馈等职责。真正后端接入后，推荐按页面逐步把“服务端数据”迁移到各自 API 查询结果，
 * 这里只保留跨页面确实需要共享的轻量状态。
 */
export interface StoreData {
  /** 智能体实例列表。 */
  agents: Agent[];
  /** 组织部门树的扁平数据。 */
  departments: Department[];
  /** 企业成员列表。 */
  members: Member[];
  /** 角色及权限配置。 */
  roles: Role[];
  /** 本地操作留痕，用于审计页和通知弹层展示。 */
  opLogs: OpLog[];
  /** 模型接入与运行指标。 */
  models: ModelEntry[];
  /** 监控告警。 */
  alerts: Alert[];
  /** Skill 插件/技能包。 */
  skills: Skill[];
  /** 记忆共享或知识条目。 */
  knowledge: Knowledge[];
  /** 知识库文件。 */
  knowledgeFiles: KnowledgeBaseFile[];
  /** 席位包。 */
  seats: Seat[];
  /** 安全策略开关。 */
  securityPolicies: SecurityPolicy[];
  /** 消息渠道和业务系统入口。 */
  channels: Channel[];
  /** 运维巡检报告。 */
  inspection: InspectionReport;
}

export type ToastKind = 'info' | 'success' | 'danger' | 'warning';

/** 页面通过 useStore 拿到的数据与通用动作。 */
export interface StoreContextValue extends StoreData {
  /** 合并更新部分业务数据；写入前会统一经过 normalizeStoreData 修正。 */
  update: (patch: Partial<StoreData> | ((d: StoreData) => Partial<StoreData>)) => void;
  /** 追加一条本地操作日志。 */
  addOpLog: (entry: Omit<OpLog, 'id' | 'ts'>) => void;
  /** 清空所有本地业务数据。 */
  resetAll: () => void;
  /** 显示右上角 toast 提示。 */
  toast: (msg: string, kind?: ToastKind) => void;
}

export const StoreContext = createContext<StoreContextValue | null>(null);

/** 生成审计日志使用的本地时间戳。 */
export function nowStamp(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

/** 读取前端业务 store；必须在 StoreProvider 内使用。 */
export function useStore(): StoreContextValue {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error('useStore must be used within StoreProvider');
  return ctx;
}
