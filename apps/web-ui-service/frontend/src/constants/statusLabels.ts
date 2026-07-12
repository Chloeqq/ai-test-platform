/** Shared status → display label mappings. Single source of truth for all status tags. */

export const PARSE_STATUS_LABELS: Record<string, { text: string; cls: string }> = {
  parsed: { text: "已解析", cls: "aiw-tag-green" },
  pending: { text: "待处理", cls: "aiw-tag-gray" },
  partial: { text: "部分成功", cls: "aiw-tag-yellow" },
  failed: { text: "失败", cls: "aiw-tag-red" },
};
