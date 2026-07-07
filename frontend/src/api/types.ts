import type { AxiosRequestConfig } from 'axios';
import type { LogEntry } from '../store/types';

export type QueryValue = string | number | boolean | Array<string | number | boolean> | undefined | null;

export interface AstronClawRequestConfig extends Omit<AxiosRequestConfig, 'url' | 'baseURL' | 'params' | 'data'> {
  query?: Record<string, QueryValue>;
  body?: unknown;
  data?: unknown;
  timeoutMs?: number;
  skipAuthRedirect?: boolean;
}
export interface ApiResponse<T> {
  code: number;
  message?: string;
  data: T;
  requestId?: string;
}

export interface PageResult<T> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
}

export type AgentStatus = 'draft' | 'running' | 'stopped' | 'abnormal' | 'deploying' | 'upgrading' | 'stopping' | 'archived' | 'violation_offline';
export type AgentAction = 'deploy' | 'start' | 'stop' | 'restart' | 'upgrade' | 'archive';
export type BatchTaskType = AgentAction | 'delete' | 'switch_model' | 'sync_skill';

export interface NameRef {
  id: string;
  name: string;
}

export interface AgentSummary {
  id: string;
  botId: string;
  instanceId: string;
  name: string;
  type: 'astronclaw';
  status: AgentStatus;
  version: string;
  department: NameRef;
  owner: NameRef;
  containerCount: number;
  skillCount: number;
  knowledgeBaseCount: number;
  primaryModel: NameRef;
  backupModel: NameRef;
  cpu: number | string;
  memory: string;
  storage: string;
  gpu: number | string;
  concurrencyLimit: number;
  dailyCallLimit: number;
  timeoutMs: number;
  currentUsers: number;
  maxUsers: number;
  qps: number;
  createdAt: string;
  updatedAt: string;
  description?: string;
  skillNames?: string[];
  runtimeLogs?: LogEntry[];
}

export interface CreateAgentPayload {
  name: string;
  type: 'astronclaw';
  departmentId: string;
  ownerId: string;
  description?: string;
  resourceSpec: { cpu: number; memory: string; storage: string; gpu: number | string };
  primaryModelId: string;
  backupModelId: string;
  concurrencyLimit: number;
  dailyCallLimit: number;
  timeoutMs: number;
  skillIds: string[];
  knowledgeBaseIds: string[];
  memoryPolicy: string;
  messageChannelIds: string[];
}

export interface CreateAgentResult {
  id: string;
  botId: string;
  status: AgentStatus;
  deployTaskId: string;
}

export interface TaskResult {
  taskId: string;
  status: string;
}

export interface AgentTask {
  id: string;
  agentId: string;
  action: string;
  status: string;
  phase?: string;
  progress?: number;
  node?: string;
  startedAt?: string;
  endedAt?: string | null;
  errorCode?: string | null;
  errorMessage?: string | null;
  retryAdvice?: string | null;
}

export interface RuntimeLog {
  id?: string;
  ts?: string;
  time?: string;
  level?: string;
  message: string;
}

export interface AgentHistory {
  id?: string;
  version?: string;
  action?: string;
  status?: string;
  operator?: NameRef | string;
  createdAt?: string;
  startedAt?: string;
  endedAt?: string;
  message?: string;
}

export interface AgentSkill {
  id: string;
  name: string;
  version?: string;
  status?: string;
  category?: string;
}

export interface AgentKnowledgeBase {
  id: string;
  name: string;
  fileCount?: number;
  status?: string;
}

export interface AgentAlert {
  id: string;
  level: string;
  type?: string;
  message?: string;
  status?: string;
  triggeredAt?: string;
}

export interface AgentAuditLog {
  id: string;
  ts?: string;
  createdAt?: string;
  operator?: string | NameRef;
  action: string;
  result?: string;
  detail?: string;
}

export interface AgentCallStats {
  todayCalls?: number;
  todayTokens?: number;
  successRate?: number;
  avgLatencyMs?: number;
  peakQps?: number;
  [key: string]: unknown;
}

export interface AgentDetail {
  basic: AgentSummary;
  runtime?: { logs?: RuntimeLog[]; cpuUsage?: number; memoryUsage?: number; storageUsage?: number };
  skills?: AgentSkill[];
  knowledgeBases?: AgentKnowledgeBase[];
  deployHistory?: AgentHistory[];
  versionHistory?: AgentHistory[];
  stateEvents?: Record<string, unknown>[];
  runtimeConfig?: Record<string, unknown>;
  callStats?: AgentCallStats;
  alerts?: AgentAlert[];
  auditLogs?: AgentAuditLog[];
}

export interface BatchTaskPayload {
  type: BatchTaskType;
  scopeType: 'selected' | 'filter' | 'all';
  targetIds: string[];
  strategy: { batchSize: number; pauseOnFailure: boolean; grayPercent: number | null };
  reason: string;
}

export interface BatchTask {
  id: string;
  type: BatchTaskType;
  status: string;
  total: number;
  successCount: number;
  failedCount: number;
  skippedCount: number;
  progress: number;
  operator?: NameRef;
  approvalId?: string | null;
  createdAt: string;
}

export type AgentLogType = 'runtime' | 'deploy' | 'upgrade' | 'container' | 'model_call';

export interface AgentSyncResult {
  status: AgentStatus;
  lastSyncAt: string;
  syncError?: string | null;
}

export interface AgentLogQuery {
  [key: string]: QueryValue;
  logType?: AgentLogType;
  keyword?: string;
  startTime?: string;
  endTime?: string;
  page?: number;
  pageSize?: number;
}

export interface RuntimeConfigPayload {
  concurrencyLimit: number;
  dailyCallLimit: number;
  timeoutMs: number;
  resourceSpec: {
    cpu: number;
    memory: string;
    storage: string;
    gpu: number | string;
  };
  primaryModelId: string;
  backupModelId: string;
}

export interface SkillEnvVarsPayload {
  skillId: string;
  env: Record<string, string>;
  restartAfterUpdated: boolean;
}

export interface DevFileSavePayload {
  path: string;
  content: string;
  etag?: string;
}

export interface CronPayload {
  name: string;
  expression: string;
  type: 'cron' | 'at' | string;
  task: string;
  timeZone: string;
  channel: string;
}

export interface BackupTaskResult {
  taskId: string;
  proxyTaskId?: string;
  status: string;
}

export interface ApprovalPayload {
  type: string;
  riskLevel: string;
  reason: string;
  payload: Record<string, unknown>;
}

export interface ShareGrantPayload {
  scopeType: string;
  scopeId: string;
  permission: string;
  expiresAt?: string;
  reason?: string;
}

export interface AuthLoginPayload {
  username: string;
  password: string;
  captcha?: string;
}

export interface AuthLoginResult {
  accessToken?: string;
  token?: string;
  expiresAt?: string;
  user?: Record<string, unknown>;
  roles?: string[];
  permissions?: string[];
}
