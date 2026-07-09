/** AI 测试质量评估中心 — 共享常量。 */

/** 评测维度中文标签（单点维护，Dashboard + Detail 共用）。 */
export const DIMENSION_LABELS: Record<string, string> = {
  coverage: "覆盖率",
  assertion_quality: "断言质量",
  executability: "可执行性",
  consistency: "一致性",
  robustness: "鲁棒性",
  hallucination: "幻觉检测",
  hallucination_risk: "幻觉风险",
};

/** 评测运行状态标签。 */
export const STATUS_LABELS: Record<string, string> = {
  pending: "待执行",
  running: "执行中",
  completed: "已完成",
  failed: "失败",
};
