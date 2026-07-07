import { request } from './request';
import type * as ApiTypes from './types';

/** 智能体接口：实例、生命周期、运行配置、开发文件、定时任务、团队任务与备份恢复。 */
export const agentsApi = {
  /** 查询智能体列表，支持筛选和分页。 */
  list(params: { keyword?: string; status?: ApiTypes.AgentStatus; departmentId?: string; ownerId?: string; modelId?: string; page?: number; pageSize?: number }) {
    return request<ApiTypes.PageResult<ApiTypes.AgentSummary>>('/agents', { query: params });
  },
  /** 创建 AstronClaw 智能体并启动部署。 */
  create(payload: ApiTypes.CreateAgentPayload) {
    return request<ApiTypes.CreateAgentResult>('/agents', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 查询智能体完整详情。 */
  detail(agentId: string) {
    return request<ApiTypes.AgentDetail>(`/agents/${encodeURIComponent(agentId)}`);
  },
  /** 执行启动、停止、重启、升级或归档等生命周期动作。 */
  lifecycle(agentId: string, action: ApiTypes.AgentAction) {
    return request<ApiTypes.TaskResult>(`/agents/${encodeURIComponent(agentId)}/${action}`, { method: 'POST' });
  },
  /** 删除智能体实例。 */
  remove(agentId: string) {
    return request<ApiTypes.TaskResult>(`/agents/${encodeURIComponent(agentId)}`, { method: 'DELETE' });
  },
  /** 切换主备模型配置。 */
  switchModel(agentId: string, payload: { primaryModelId: string; backupModelId: string }) {
    return request<ApiTypes.TaskResult>(`/agents/${encodeURIComponent(agentId)}/model`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 查询智能体任务状态。 */
  task(taskId: string) {
    return request<ApiTypes.AgentTask>(`/agent-tasks/${encodeURIComponent(taskId)}`);
  },
  /** 同步最新运行状态。 */
  sync(agentId: string) {
    return request<ApiTypes.AgentSyncResult>(`/agents/${encodeURIComponent(agentId)}/sync`, { method: 'POST' });
  },
  /** 查询运行、部署、升级、容器或模型调用日志。 */
  logs(agentId: string, params: ApiTypes.AgentLogQuery = {}) {
    return request<ApiTypes.PageResult<ApiTypes.RuntimeLog>>(`/agents/${encodeURIComponent(agentId)}/logs`, { query: params });
  },
  /** 更新并发、限额、超时、资源和模型配置。 */
  updateRuntimeConfig(agentId: string, payload: ApiTypes.RuntimeConfigPayload) {
    return request<ApiTypes.TaskResult>(`/agents/${encodeURIComponent(agentId)}/runtime-config`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 查询智能体运行时加载的技能。 */
  runtimeSkills(agentId: string) {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/runtime-skills`);
  },
  /** 查询技能环境变量。 */
  skillEnvVars(agentId: string) {
    return request<{ items: Array<Record<string, unknown>> }>(`/agents/${encodeURIComponent(agentId)}/skill-env-vars`);
  },
  /** 更新技能环境变量。 */
  updateSkillEnvVars(agentId: string, payload: ApiTypes.SkillEnvVarsPayload) {
    return request<Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/skill-env-vars`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 删除技能环境变量。 */
  deleteSkillEnvVars(agentId: string, payload: { skillId?: string; envNames?: string[] } = {}) {
    return request<Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/skill-env-vars`, { method: 'DELETE', body: JSON.stringify(payload) });
  },
  /** 查询智能体开发文件列表。 */
  devFiles(agentId: string, params: { path?: string; page?: number; pageSize?: number } = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>(`/agents/${encodeURIComponent(agentId)}/dev-files`, { query: params });
  },
  /** 搜索智能体开发文件。 */
  searchDevFiles(agentId: string, params: { keyword: string; path?: string }) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>(`/agents/${encodeURIComponent(agentId)}/dev-files/search`, { query: params });
  },
  /** 查询开发文件元信息。 */
  devFileMeta(agentId: string, path: string) {
    return request<Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/dev-file/meta`, { query: { path } });
  },
  /** 读取开发文件内容。 */
  readDevFile(agentId: string, path: string) {
    return request<Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/dev-file/content`, { query: { path } });
  },
  /** 保存开发文件内容。 */
  saveDevFile(agentId: string, payload: ApiTypes.DevFileSavePayload) {
    return request<Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/dev-file/content`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 下载开发文件。 */
  devFileDownload(agentId: string, path: string) {
    return request<{ downloadUrl?: string } | Blob>(`/agents/${encodeURIComponent(agentId)}/dev-file/download`, { query: { path }, responseType: 'blob' });
  },
  /** 预览智能体记忆数据。 */
  memoryPreview(agentId: string) {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/memory-preview`);
  },
  /** 查询 AstronMem 插件状态。 */
  astronmemPlugin(agentId: string) {
    return request<Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/plugins/astronmem`);
  },
  /** 启用或禁用 AstronMem 插件。 */
  setAstronmemPlugin(agentId: string, action: 'enable' | 'disable') {
    return request<Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/plugins/astronmem`, { method: 'POST', body: JSON.stringify({ action }) });
  },
  /** 创建智能体定时任务。 */
  createCron(agentId: string, payload: ApiTypes.CronPayload) {
    return request<Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/crons`, { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 查询智能体定时任务列表。 */
  crons(agentId: string) {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/crons`);
  },
  /** 更新智能体定时任务。 */
  updateCron(agentId: string, cronId: string, payload: ApiTypes.CronPayload) {
    return request<Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/crons/${encodeURIComponent(cronId)}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 删除智能体定时任务。 */
  deleteCron(agentId: string, cronId: string) {
    return request<Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/crons/${encodeURIComponent(cronId)}`, { method: 'DELETE' });
  },
  /** 查询定时任务执行记录。 */
  cronRuns(agentId: string, cronId: string, limit = 100) {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/crons/${encodeURIComponent(cronId)}/runs`, {
      query: { limit },
    });
  },
  /** 查询智能体团队任务列表。 */
  teams(agentId: string, sessionId?: string) {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/teams`, { query: { sessionId } });
  },
  /** 查询团队任务进度。 */
  teamProgress(agentId: string, teamId: string, sessionId?: string) {
    return request<Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/teams/${encodeURIComponent(teamId)}/progress`, { query: { sessionId } });
  },
  /** 查询团队任务中间产物。 */
  teamOutputs(agentId: string, teamId: string, sessionId?: string) {
    return request<Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/teams/${encodeURIComponent(teamId)}/outputs`, { query: { sessionId } });
  },
  /** 查询团队任务最终结果。 */
  teamResult(agentId: string, teamId: string, sessionId?: string) {
    return request<Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/teams/${encodeURIComponent(teamId)}/result`, { query: { sessionId } });
  },
  /** 启动智能体备份任务。 */
  startBackup(agentId: string) {
    return request<ApiTypes.BackupTaskResult>(`/agents/${encodeURIComponent(agentId)}/backups`, { method: 'POST' });
  },
  /** 查询备份任务状态。 */
  backupStatus(agentId: string, taskId: string) {
    return request<ApiTypes.BackupTaskResult>(`/agents/${encodeURIComponent(agentId)}/backups/${encodeURIComponent(taskId)}`);
  },
  /** 启动智能体恢复任务。 */
  restoreBackup(agentId: string) {
    return request<ApiTypes.BackupTaskResult>(`/agents/${encodeURIComponent(agentId)}/backup-restore`, { method: 'POST' });
  },
  /** 查询恢复任务状态。 */
  restoreStatus(agentId: string, taskId: string) {
    return request<ApiTypes.BackupTaskResult>(`/agents/${encodeURIComponent(agentId)}/backup-restore/${encodeURIComponent(taskId)}`);
  },
  /** 删除智能体备份数据。 */
  deleteBackups(agentId: string) {
    return request<Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/backups`, { method: 'DELETE' });
  },
};
