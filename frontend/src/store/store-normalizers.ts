import type { StoreData } from './store-context';
import type { InspectionReport } from './types';

const numberOr = (value: unknown, fallback = 0) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
};

const nonNegativeInt = (value: unknown, fallback = 0) => Math.max(0, Math.round(numberOr(value, fallback)));

const clamp = (value: unknown, min: number, max: number, fallback = min) => {
  const n = numberOr(value, fallback);
  return Math.min(max, Math.max(min, n));
};

function recountInspection(items: InspectionReport['items']) {
  return {
    total: items.length,
    pass: items.filter((item) => item.result === 'pass').length,
    warn: items.filter((item) => item.result === 'warn').length,
    fail: items.filter((item) => item.result === 'fail').length,
  };
}

/**
 * 统一修正写入 store 的数据，避免页面组件到处重复做边界判断。
 *
 * 主要处理：
 * - 数字字段兜底，避免 NaN、负数、超过范围的值进入页面。
 * - 由明细列表反算派生字段，例如 Skill 绑定数、角色成员数、巡检统计数。
 * - 清理敏感临时字段，例如模型 API Key 不允许长期留在前端状态中。
 * - 兼容后端返回名称或 ID 的历史数据，例如渠道绑定智能体。
 */
export function normalizeStoreData(input: StoreData): StoreData {
  const agents = input.agents.map((agent) => {
    const skillList = Array.from(new Set(agent.skillList ?? []));
    const userMax = Math.max(1, nonNegativeInt(agent.userMax, 1));
    return {
      ...agent,
      skillList,
      skills: skillList.length,
      containers: Math.max(1, nonNegativeInt(agent.containers, 1)),
      userMax,
      userUsed: Math.min(userMax, nonNegativeInt(agent.userUsed)),
      qps: clamp(agent.qps, 0, 100),
      cpu: Math.max(1, nonNegativeInt(agent.cpu, 1)),
      memory: Math.max(1, nonNegativeInt(agent.memory, 1)),
      storage: Math.max(1, nonNegativeInt(agent.storage, 1)),
      concurrency: Math.max(1, nonNegativeInt(agent.concurrency, 1)),
      dailyLimit: Math.max(1, nonNegativeInt(agent.dailyLimit, 1)),
      timeout: Math.max(100, nonNegativeInt(agent.timeout, 100)),
    };
  });

  const roleCounts = input.members.reduce<Record<string, number>>((acc, member) => {
    acc[member.roleId] = (acc[member.roleId] ?? 0) + 1;
    return acc;
  }, {});
  const roles = input.roles.map((role) => ({ ...role, memberCount: roleCounts[role.id] ?? 0 }));

  const skillCounts = agents.reduce<Record<string, number>>((acc, agent) => {
    agent.skillList.forEach((skillName) => {
      acc[skillName] = (acc[skillName] ?? 0) + 1;
    });
    return acc;
  }, {});
  const skills = input.skills.map((skill) => ({ ...skill, boundAgents: skillCounts[skill.name] ?? 0 }));

  const agentIdByName = new Map(agents.map((agent) => [agent.name, agent.id]));
  const agentIds = new Set(agents.map((agent) => agent.id));
  const channels = input.channels.map((channel) => ({
    ...channel,
    boundAgent: agentIds.has(channel.boundAgent) ? channel.boundAgent : (agentIdByName.get(channel.boundAgent) ?? channel.boundAgent),
    messages: nonNegativeInt(channel.messages),
  }));

  const seats = input.seats.map((seat) => {
    const total = nonNegativeInt(seat.total);
    return { ...seat, total, used: Math.min(total, nonNegativeInt(seat.used)) };
  });

  const models = input.models.map((model) => {
    const { apiKey: _apiKey, ...safeModel } = model;
    return {
      ...safeModel,
      apiKey: '',
      price: Math.max(0, numberOr(model.price)),
      todayCalls: nonNegativeInt(model.todayCalls),
      todayTokens: nonNegativeInt(model.todayTokens),
      errorRate: clamp(model.errorRate, 0, 100),
      avgLatency: nonNegativeInt(model.avgLatency),
      containerCost: Math.max(0, numberOr(model.containerCost)),
    };
  });

  const knowledgeFiles = input.knowledgeFiles.map((file) => ({
    ...file,
    size: nonNegativeInt(file.size),
    chunks: nonNegativeInt(file.chunks),
    refs: nonNegativeInt(file.refs),
  }));

  const securityPolicies = input.securityPolicies.map((policy) => ({ ...policy, enabled: Boolean(policy.enabled) }));
  const inspectionItems = input.inspection.items;

  return {
    ...input,
    agents,
    roles,
    skills,
    channels,
    seats,
    models,
    knowledgeFiles,
    securityPolicies,
    inspection: {
      ...input.inspection,
      scope: agents.length ? `全域 · ${agents.length} 个实例` : input.inspection.scope,
      items: inspectionItems,
      ...recountInspection(inspectionItems),
    },
  };
}
