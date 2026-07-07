/**
 * AstronClaw 管理台本地 store 类型定义。
 *
 * 这里描述的是页面运行时需要展示或编辑的前端状态模型，不等同于后端接口 DTO。
 * 后端接口类型放在 src/api/types.ts；如果接口返回结构和页面展示结构不同，应在页面或适配函数里显式转换。
 */

// 智能体实例与运行日志。
export type AgentStatus = 'draft' | 'running' | 'stopped' | 'abnormal' | 'deploying' | 'upgrading' | 'stopping' | 'archived' | 'violation_offline';
export type AgentType = 'official';

export interface LogEntry {
  id: string;
  ts: string;
  level: 'info' | 'warn' | 'error' | 'success';
  message: string;
}

export interface Agent {
  id: string;
  instanceId?: string;
  name: string;
  type: AgentType;
  engine: string;
  status: AgentStatus;
  version: string;
  department: string;
  owner: string;
  containers: number;
  skills: number;
  skillList: string[];
  userUsed: number;
  userMax: number;
  qps: number;
  model: string;
  fallbackModel: string;
  cpu: number;
  memory: number;
  storage: number;
  gpu: string;
  concurrency: number;
  dailyLimit: number;
  timeout: number;
  description: string;
  createdAt: string;
  logs: LogEntry[];
}

// 组织、成员、角色与权限。
export interface Department {
  id: string;
  name: string;
  parentId: string | null;
  manager: string;
}

export interface Member {
  id: string;
  name: string;
  empNo: string;
  deptId: string;
  roleId: string;
  email: string;
  status: 'active' | 'frozen' | 'pending';
  seat: 'assigned' | 'unassigned';
  lastLogin: string;
  sso: boolean;
}

export interface Role {
  id: string;
  name: string;
  desc: string;
  dataScope: string;
  instanceScope: string;
  permissions: string[];
  memberCount: number;
  builtIn: boolean;
}

// 审计操作日志。
export interface OpLog {
  id: string;
  ts: string;
  operator: string;
  module: string;
  action: string;
  target: string;
  result: 'success' | 'fail';
  ip: string;
  detail: string;
}

// 模型接入、调用统计与密钥录入状态。
export interface ModelEntry {
  id: string;
  name: string;
  provider?: string;
  model: string; // 模型标识，如 gpt-4, claude-3-opus
  apiEndpoint: string; // 接口地址
  apiKey?: string; // 仅作为录入表单的临时字段，保存前必须剔除
  description: string; // 模型描述
  status: 'available' | 'maintenance' | 'offline';
  price: number; // per 1M tokens, RMB (每百万 token)
  todayCalls: number;
  todayTokens: number; // in thousands
  errorRate: number;
  avgLatency: number;
  containerCost: number; // 容器成本，RMB/day
}

// 监控告警。
export interface Alert {
  id: string;
  level: 'critical' | 'warning' | 'info';
  source: string;
  errorCode: string;
  category: string;
  type: string;
  triggeredAt: string;
  owner: string;
  status: 'pending' | 'claimed' | 'processing' | 'resolved';
  impact: string;
  detail: string; // 详细告警信息
  rootCause?: string; // 根因分析
  suggestion?: string; // 建议措施
}

// Skill 技能包。
export interface Skill {
  id: string;
  name: string;
  packageName?: string;
  packageUrl?: string;
  source: string;
  version: string;
  status: 'enabled' | 'disabled' | 'reviewing';
  boundAgents: number;
  creator: string;
  updatedAt: string;
  category: string;
  allowedRoles: string[]; // 允许使用的角色 ID 列表
}

// 记忆、知识库与知识文件。
export interface Knowledge {
  id: string;
  title: string;
  level: string;
  owner: string;
  tags: string[];
  refs: number;
  updatedAt: string;
  shareStatus: 'shared' | 'pending' | 'private';
}

// 记忆、知识库与知识文件。
export interface KnowledgeBaseFile {
  id: string;
  name: string;
  type: 'pdf' | 'docx' | 'txt' | 'xlsx' | 'pptx' | 'md';
  size: number; // KB
  category: string;
  uploadedBy: string;
  uploadedAt: string;
  status: 'processing' | 'indexed' | 'failed';
  chunks: number;
  refs: number;
}

// 记忆、知识库与知识文件。
export interface KnowledgeBase {
  id: string;
  filename: string;
  fileType: 'pdf' | 'docx' | 'txt' | 'md';
  size: number; // bytes
  status: 'processing' | 'ready' | 'failed';
  chunks: number; // 向量化分块数
  boundAgents: string[]; // 关联的智能体实例 ID
  uploadedBy: string;
  uploadedAt: string;
}

// 席位、策略、渠道与巡检报告。
export interface Seat {
  id: string;
  pkg: string;
  total: number;
  used: number;
  dept: string;
  expireAt: string;
}

export interface SecurityPolicy {
  id: string;
  name: string;
  desc: string;
  enabled: boolean;
}

export interface Channel {
  id: string;
  name: string;
  type: string;
  status: 'connected' | 'disconnected' | 'error';
  boundAgent: string;
  messages: number;
  updatedAt: string;
}

export interface InspectionItem {
  id: string;
  category: string;
  name: string;
  result: 'pass' | 'warn' | 'fail';
  detail: string;
  suggestion: string;
}

export interface InspectionReport {
  id: string;
  ts: string;
  scope: string;
  total: number;
  pass: number;
  warn: number;
  fail: number;
  items: InspectionItem[];
}
