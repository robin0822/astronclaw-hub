# 实现阶段 TDD 与质量门禁

本文说明如何把文章中的“实现阶段由 Agent 自主编码、TDD 推进、pre-push quality gate 硬卡口”落到本仓库。

## 角色映射

文章中的角色在本仓库中这样对应：

| 文章角色 | 本仓库实现 |
| --- | --- |
| `superai-execute` | `.agent/skills/code-execute/SKILL.md`，负责按已确认 `requirements.md` 和 `plan.md` 做 TDD 实现 |
| `superai-code-review` | `.agent/skills/cr-collaboration/SKILL.md` 加 `scripts/agent-code-review.cjs`，负责结构化内部 review |
| PMD | 后端 `ruff`、前端 `oxlint/typecheck`，即按语言替换成自动静态规则检查 |
| 覆盖率门禁 | 后端 `pytest --cov`，前端沿用 `review:ci` 的测试、lint、类型检查和构建 |
| git pre-push hook | 根目录 `.githooks/pre-push` 调用 `scripts/quality-gate.sh` |

## 实现阶段流程

```text
requirements.md 已确认
  -> plan.md 已确认
  -> code-execute 进入实现
  -> 先按验收标准写失败测试
  -> 再改生产代码让测试通过
  -> 更新 progress.md 和必要文档
  -> 执行 scripts/quality-gate.sh
  -> git push 触发 .githooks/pre-push
```

这里的关键点是测试必须先约束业务行为，而不是代码写完后补覆盖率。Agent 在实现时要从 `plan.md` 的验收标准、状态机、接口契约、错误码和审计要求中抽测试用例。

## pre-push quality gate

根级 hook 入口：

```text
.githooks/pre-push
```

它只做一件事：调用统一质量门禁脚本。

```text
scripts/quality-gate.sh
```

当前门禁包含四类检查：

| 门禁 | 实现 | 失败后处理 |
| --- | --- | --- |
| diff-to-test 映射 | `scripts/diff-to-test-map.cjs` | 给生产代码补测试，或维护 `quality/test-map.json` 的稳定测试锚点 |
| PMD / lint | 后端 `ruff check`，前端 `npm run review:ci` | 回到实现阶段修规则类问题 |
| 覆盖率 | 后端 `pytest --cov=app --cov-fail-under=70` | 补行为测试，不接受只为覆盖率而断言实现细节 |
| Agent 内部 review | `scripts/agent-code-review.cjs` | 修复可执行问题后重跑门禁 |

## diff-to-test 映射

`scripts/diff-to-test-map.cjs` 会检查本次 push 相对 upstream 的生产代码变更：

- `backend/app/**/*.py`
- `frontend/src/**/*.ts`
- `frontend/src/**/*.tsx`

每个生产代码变更必须找到具体测试锚点。锚点来源有两种：

- 本次 diff 中同时修改了相关测试文件。
- `quality/test-map.json` 中声明了稳定测试锚点。

示例：

```json
{
  "backend/app/api/v1/routes.py": [
    "backend/tests/api/test_core_api.py"
  ],
  "frontend/src/api/request.ts": [
    "frontend/src/api/__tests__/request.test.ts",
    "frontend/e2e/api-contract.spec.ts"
  ]
}
```

这道门禁不是证明“跑过一次回归”，而是要求每个行为变化都能说明由哪个测试约束。

## Agent 内部 review

`scripts/agent-code-review.cjs` 会对完整待 push diff 做结构化检查，当前硬规则包括：

- 前端不得直接调用 Claw Proxy `/api/v1/bot`、`CLAW_PROXY` 或 bridge token。
- 生产代码不得提交疑似模型密钥、token、password、secret。
- 不允许提交未豁免的 `.env` 运行文件。
- 后端变更会输出 RBAC、审计、错误映射、幂等、事务边界 review 焦点。
- 前端变更会输出加载、错误、空状态、权限、API 失败和窄屏布局 review 焦点。

发现 actionable 问题时脚本直接失败，Agent 必须修复后重跑。

## 启用方式

首次克隆或换机器后执行：

```bash
scripts/install-git-hooks.sh
```

后端开发机需要先安装开发依赖：

```bash
python3 -m pip install -r backend/requirements-dev.txt
```

前端开发机需要先安装依赖：

```bash
npm --prefix frontend ci
```

它会设置：

```bash
git config core.hooksPath .githooks
```

手动演示门禁：

```bash
scripts/quality-gate.sh
```

强制全量执行：

```bash
QUALITY_GATE_SCOPE=all scripts/quality-gate.sh
```

调整后端覆盖率阈值：

```bash
BACKEND_COVERAGE_MIN=80 scripts/quality-gate.sh
```

## 演示口径

演示时可以按下面顺序讲：

1. 先打开 `.agent/memory/active/LOBSTER-0001/requirements.md`，说明需求已确认。
2. 打开 `.agent/memory/active/LOBSTER-0001/plan.md`，说明验收标准和实现边界已确认。
3. 打开 `.agent/skills/code-execute/SKILL.md`，说明实现阶段要求先写测试再写代码。
4. 打开 `scripts/diff-to-test-map.cjs` 和 `quality/test-map.json`，说明每个生产代码变更必须有测试锚点。
5. 打开 `.githooks/pre-push` 和 `scripts/quality-gate.sh`，说明 `git push` 绕不过门禁。
6. 打开 `scripts/agent-code-review.cjs`，说明内部 review 不靠口头约束，而是脚本化检查。
