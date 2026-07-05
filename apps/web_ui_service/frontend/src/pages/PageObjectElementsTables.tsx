import { Link } from "react-router-dom";

import { BulkActionBar } from "../components/BulkActionBar";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime } from "../lib/datetime";

type Row = Record<string, unknown>;
type ElementDetailMode = "detail" | "semantic" | "aliases" | "locators" | "refs";

interface FormalElementsTableProps {
  rows: Row[];
  selectedCodes: string[];
  visibleCodes: string[];
  allSelected: boolean;
  busy: boolean;
  normalizedPageCode: string;
  labels: {
    stability: Record<string, string>;
    review: Record<string, string>;
  };
  text: (value: unknown) => string;
  elementApiCode: (item: Row) => string;
  elementCodePolicyHint: (
    value: unknown,
    pageCode: string,
    businessType: unknown,
    locatorSource?: unknown,
    locatorType?: unknown,
    testidValue?: unknown,
  ) => string;
  inferDisplayElementCode: (pageCode: string, item: Row) => string;
  inferDisplayElementName: (item: Row) => string;
  buildElementDetailLink: (code: string, mode: ElementDetailMode) => string;
  toggleSelection: (value: string, selectedValues: string[], setter: (values: string[]) => void) => void;
  toggleAllSelection: (values: string[], checked: boolean, setter: (values: string[]) => void) => void;
  setSelectedCodes: (values: string[]) => void;
  batchRemoveElements: () => void;
  openElementPanel: (item: Row, mode: "detail") => void;
}

export function FormalElementsTable({
  rows,
  selectedCodes,
  visibleCodes,
  allSelected,
  busy,
  normalizedPageCode,
  labels,
  text,
  elementApiCode,
  elementCodePolicyHint,
  inferDisplayElementCode,
  inferDisplayElementName,
  buildElementDetailLink,
  toggleSelection,
  toggleAllSelection,
  setSelectedCodes,
  batchRemoveElements,
  openElementPanel,
}: FormalElementsTableProps) {
  return (
    <DataTable
      title={`正式元素：${rows.length}`}
      actions={(
        <BulkActionBar selectedCount={selectedCodes.length}>
          <button type="button" className="button danger secondary" onClick={batchRemoveElements} disabled={busy || !selectedCodes.length}>
            批量删除
          </button>
        </BulkActionBar>
      )}
    >
      <table>
        <thead>
          <tr>
            <th>
              <input type="checkbox" checked={allSelected} onChange={(event) => toggleAllSelection(visibleCodes, event.target.checked, setSelectedCodes)} disabled={busy || !visibleCodes.length} />
            </th>
            <th>元素编码</th>
            <th>元素名称</th>
            <th>业务类型</th>
            <th>定位来源</th>
            <th>稳定等级</th>
            <th>审核状态</th>
            <th>关键元素</th>
            <th>引用次数</th>
            <th>更新时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.length ? (
            rows.map((item, index) => {
              const code = elementApiCode(item);
              const codeHint = elementCodePolicyHint(
                item.element_code,
                normalizedPageCode,
                item.business_type,
                item.locator_source,
                item.locator_type,
                item.testid_value || item.locator_value,
              );
              const isPendingReview = String(item.review_status || "").trim().toLowerCase() === "pending";
              return (
                <tr key={String(item.element_id || index)}>
                  <td>
                    <input type="checkbox" checked={Boolean(code && selectedCodes.includes(code))} onChange={() => toggleSelection(code, selectedCodes, setSelectedCodes)} disabled={busy || !code} />
                  </td>
                  <td className={`mono ${codeHint ? "element-code-invalid" : ""}`}>
                    <span>{text(inferDisplayElementCode(normalizedPageCode, item))}</span>
                    {codeHint ? <span className="code-repair-badge" title={codeHint}>需修复编码</span> : null}
                  </td>
                  <td>{text(inferDisplayElementName(item))}</td>
                  <td>{text(item.business_type)}</td>
                  <td>{text(item.locator_source || item.locator_type)}</td>
                  <td><StatusPill prefix="stability" value={item.stability_level} labels={labels.stability} /></td>
                  <td>
                    <StatusPill prefix="review" value={item.review_status} labels={labels.review} />
                    {isPendingReview && code ? (
                      <Link className="inline-action-link" to={buildElementDetailLink(code, "semantic")}>去审核</Link>
                    ) : null}
                  </td>
                  <td>{item.is_key_element ? <StatusPill prefix="key" value="true" labels={{ true: "关键" }} /> : <span className="muted">-</span>}</td>
                  <td>{text(item.reference_count)}</td>
                  <td>{formatDateTime(item.updated_at)}</td>
                  <td>
                    <div className="header-actions">
                      {code ? (
                        <>
                          <Link className="button secondary" to={buildElementDetailLink(code, "detail")}>查看详情</Link>
                          <Link className="button secondary" to={buildElementDetailLink(code, "semantic")}>编辑语义</Link>
                          <details className="action-menu">
                            <summary>更多</summary>
                            <Link to={buildElementDetailLink(code, "aliases")}>编辑别名</Link>
                            <Link to={buildElementDetailLink(code, "locators")}>查看定位器</Link>
                            <Link to={buildElementDetailLink(code, "refs")}>查看引用</Link>
                          </details>
                        </>
                      ) : (
                        <button type="button" className="button secondary" onClick={() => openElementPanel(item, "detail")} disabled={busy}>
                          查看详情
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })
          ) : (
            <tr>
              <td colSpan={11}>
                <EmptyState title="暂无符合筛选条件的正式元素" description="可以调整筛选条件，或先从候选元素中审核提升正式元素。" />
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </DataTable>
  );
}

interface CandidateGroupsTableProps {
  rows: Row[];
  selectedKeys: string[];
  visibleKeys: string[];
  allSelected: boolean;
  busy: boolean;
  canMerge: boolean;
  labels: {
    action: Record<string, string>;
    promotion: Record<string, string>;
  };
  text: (value: unknown) => string;
  qualityTone: (value: unknown) => "good" | "ok" | "warn" | "bad";
  buildCandidateGroupDetailLink: (groupKey: string) => string;
  toggleSelection: (value: string, selectedValues: string[], setter: (values: string[]) => void) => void;
  toggleAllSelection: (values: string[], checked: boolean, setter: (values: string[]) => void) => void;
  setSelectedKeys: (values: string[]) => void;
  batchRejectCandidateGroups: () => void;
  batchRemoveCandidateGroups: () => void;
  openPromote: (group: Row) => void;
  openMerge: (group: Row) => void;
  openReject: (group: Row) => void;
}

export function CandidateGroupsTable({
  rows,
  selectedKeys,
  visibleKeys,
  allSelected,
  busy,
  canMerge,
  labels,
  text,
  qualityTone,
  buildCandidateGroupDetailLink,
  toggleSelection,
  toggleAllSelection,
  setSelectedKeys,
  batchRejectCandidateGroups,
  batchRemoveCandidateGroups,
  openPromote,
  openMerge,
  openReject,
}: CandidateGroupsTableProps) {
  return (
    <DataTable
      title={`候选分组：${rows.length}`}
      actions={(
        <BulkActionBar selectedCount={selectedKeys.length}>
          <button type="button" className="button secondary" onClick={batchRejectCandidateGroups} disabled={busy || !selectedKeys.length}>批量拒绝</button>
          <button type="button" className="button danger secondary" onClick={batchRemoveCandidateGroups} disabled={busy || !selectedKeys.length}>批量删除</button>
        </BulkActionBar>
      )}
    >
      <table>
        <thead>
          <tr>
            <th>
              <input type="checkbox" checked={allSelected} onChange={(event) => toggleAllSelection(visibleKeys, event.target.checked, setSelectedKeys)} disabled={busy || !visibleKeys.length} />
            </th>
            <th>候选编码建议</th>
            <th>候选名称建议</th>
            <th>业务类型</th>
            <th>质量</th>
            <th>候选数</th>
            <th>会话数</th>
            <th>推荐动作</th>
            <th>匹配正式元素</th>
            <th>状态</th>
            <th>最近更新时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.length ? (
            rows.map((group, index) => {
              const groupKey = String(group.group_key || "").trim();
              return (
                <tr key={groupKey || String(index)}>
                  <td>
                    <input type="checkbox" checked={Boolean(groupKey && selectedKeys.includes(groupKey))} onChange={() => toggleSelection(groupKey, selectedKeys, setSelectedKeys)} disabled={busy || !groupKey} />
                  </td>
                  <td className="mono">{text(group.proposed_element_code)}</td>
                  <td>{text(group.proposed_element_name)}</td>
                  <td>{text(group.business_type_guess)}</td>
                  <td>
                    <span className={`quality-pill quality-${qualityTone(group.quality_tier)}`}>{text(group.quality_tier)}</span>
                    <span className="muted"> / {text(group.max_score)}</span>
                  </td>
                  <td>{text(group.candidate_count)}</td>
                  <td>{text(group.session_count)}</td>
                  <td><StatusPill prefix="action" value={group.recommended_action} labels={labels.action} /></td>
                  <td className="mono">{text(group.matched_existing_element_code)}</td>
                  <td><StatusPill prefix="promotion" value={group.promotion_status} labels={labels.promotion} /></td>
                  <td>{formatDateTime(group.updated_at)}</td>
                  <td>
                    <div className="header-actions">
                      {groupKey ? <Link className="button secondary" to={buildCandidateGroupDetailLink(groupKey)}>查看候选</Link> : <span className="muted">缺少 group_key</span>}
                      <button type="button" className="button secondary" onClick={() => openPromote(group)} disabled={busy || !groupKey}>提升</button>
                      <button type="button" className="button secondary" onClick={() => openMerge(group)} disabled={busy || !groupKey || !canMerge}>合并</button>
                      <button type="button" className="button secondary" onClick={() => openReject(group)} disabled={busy || !groupKey}>拒绝</button>
                    </div>
                  </td>
                </tr>
              );
            })
          ) : (
            <tr>
              <td colSpan={12}>
                <EmptyState title="暂无候选分组" description="停止页面录制后，系统会把录制元素聚合为候选分组，供你审核提升。" />
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </DataTable>
  );
}

interface RecorderHistoryTableProps {
  rows: Row[];
  selectedSessionIds: string[];
  visibleSessionIds: string[];
  allSelected: boolean;
  busy: boolean;
  recorderLink: string;
  labels: Record<string, string>;
  text: (value: unknown) => string;
  asRecord: (value: unknown) => Row;
  buildPlaybackDetailLink: (sessionId: string) => string;
  buildCandidateSessionLink: (sessionId: string) => string;
  toggleSelection: (value: string, selectedValues: string[], setter: (values: string[]) => void) => void;
  toggleAllSelection: (values: string[], checked: boolean, setter: (values: string[]) => void) => void;
  setSelectedSessionIds: (values: string[]) => void;
  batchRemoveHistoryRows: () => void;
}

export function RecorderHistoryTable({
  rows,
  selectedSessionIds,
  visibleSessionIds,
  allSelected,
  busy,
  recorderLink,
  labels,
  text,
  asRecord,
  buildPlaybackDetailLink,
  buildCandidateSessionLink,
  toggleSelection,
  toggleAllSelection,
  setSelectedSessionIds,
  batchRemoveHistoryRows,
}: RecorderHistoryTableProps) {
  return (
    <DataTable
      title={`录制历史：${rows.length}`}
      actions={(
        <>
          <BulkActionBar selectedCount={selectedSessionIds.length}>
            <button type="button" className="button danger secondary" onClick={batchRemoveHistoryRows} disabled={busy || !selectedSessionIds.length}>批量删除</button>
          </BulkActionBar>
          <Link className="button secondary" to={recorderLink}>打开录制页</Link>
        </>
      )}
    >
      <table>
        <thead>
          <tr>
            <th>
              <input type="checkbox" checked={allSelected} onChange={(event) => toggleAllSelection(visibleSessionIds, event.target.checked, setSelectedSessionIds)} disabled={busy || !visibleSessionIds.length} />
            </th>
            <th>session_id</th>
            <th>状态</th>
            <th>候选数</th>
            <th>候选组</th>
            <th>已提升</th>
            <th>已拒绝</th>
            <th>回放步骤数</th>
            <th>开始时间</th>
            <th>停止时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.length ? (
            rows.map((row, index) => {
              const sessionId = String(row.session_id || "").trim();
              const nestedSummary = asRecord(row.candidate_summary);
              const summary = Object.keys(nestedSummary).length ? nestedSummary : row;
              return (
                <tr key={sessionId || String(index)}>
                  <td>
                    <input type="checkbox" checked={Boolean(sessionId && selectedSessionIds.includes(sessionId))} onChange={() => toggleSelection(sessionId, selectedSessionIds, setSelectedSessionIds)} disabled={busy || !sessionId} />
                  </td>
                  <td className="mono">{text(sessionId)}</td>
                  <td><StatusPill prefix="recorder" value={row.status} labels={labels} /></td>
                  <td>{text(summary.candidate_count)}</td>
                  <td>{text(summary.candidate_group_count)}</td>
                  <td>{text(summary.promoted_count)}</td>
                  <td>{text(summary.rejected_count)}</td>
                  <td>{text(row.recorded_step_count)}</td>
                  <td>{formatDateTime(row.started_at)}</td>
                  <td>{formatDateTime(row.stopped_at)}</td>
                  <td>
                    <div className="header-actions">
                      {sessionId ? <Link className="button secondary" to={buildPlaybackDetailLink(sessionId)}>查看回放</Link> : null}
                      {sessionId ? <Link className="button secondary" to={buildCandidateSessionLink(sessionId)}>去候选审核</Link> : null}
                      {sessionId ? <Link className="button secondary" to={buildPlaybackDetailLink(sessionId)}>查看脚本</Link> : null}
                      {sessionId ? <Link className="button secondary" to={buildPlaybackDetailLink(sessionId)}>查看 stderr</Link> : null}
                    </div>
                  </td>
                </tr>
              );
            })
          ) : (
            <tr>
              <td colSpan={11}>
                <EmptyState title="暂无录制历史" description="可以从录制页启动一次页面对象录制，停止后会在这里看到历史和候选摘要。" />
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </DataTable>
  );
}

interface CandidateGroupDetailTableProps {
  group: Row;
  rows: Row[];
  routeGroupKey: string;
  detailLoading: boolean;
  selectedCandidateKeys: string[];
  visibleCandidateKeys: string[];
  allSelected: boolean;
  busy: boolean;
  canMerge: boolean;
  candidateListLink: string;
  labels: {
    candidate: Record<string, string>;
    action: Record<string, string>;
  };
  text: (value: unknown) => string;
  displayList: (value: unknown) => string;
  qualityTone: (value: unknown) => "good" | "ok" | "warn" | "bad";
  riskBar: (value: unknown) => JSX.Element;
  toggleSelection: (value: string, selectedValues: string[], setter: (values: string[]) => void) => void;
  toggleAllSelection: (values: string[], checked: boolean, setter: (values: string[]) => void) => void;
  setSelectedCandidateKeys: (values: string[]) => void;
  batchRemoveCandidateRows: () => void;
  openPromote: (group: Row) => void;
  openMerge: (group: Row) => void;
  openReject: (group: Row) => void;
  rejectOneCandidate: (candidate: Row) => void;
}

export function CandidateGroupDetailTable({
  group,
  rows,
  routeGroupKey,
  detailLoading,
  selectedCandidateKeys,
  visibleCandidateKeys,
  allSelected,
  busy,
  canMerge,
  candidateListLink,
  labels,
  text,
  displayList,
  qualityTone,
  riskBar,
  toggleSelection,
  toggleAllSelection,
  setSelectedCandidateKeys,
  batchRemoveCandidateRows,
  openPromote,
  openMerge,
  openReject,
  rejectOneCandidate,
}: CandidateGroupDetailTableProps) {
  return (
    <DataTable
      title={(
        <span>
          候选明细：{text(group.proposed_element_name)} / {rows.length}
          <p className="muted mono">{text(group.group_key || routeGroupKey)}</p>
        </span>
      )}
      actions={(
        <>
          {detailLoading ? <span className="muted">加载中...</span> : null}
          <BulkActionBar selectedCount={selectedCandidateKeys.length}>
            <button type="button" className="button danger secondary" onClick={batchRemoveCandidateRows} disabled={busy || !selectedCandidateKeys.length}>批量删除</button>
          </BulkActionBar>
          <button type="button" className="button secondary" onClick={() => openPromote(group)} disabled={busy || !group.group_key}>提升</button>
          <button type="button" className="button secondary" onClick={() => openMerge(group)} disabled={busy || !group.group_key || !canMerge}>合并</button>
          <button type="button" className="button secondary" onClick={() => openReject(group)} disabled={busy || !group.group_key}>拒绝</button>
          <Link className="button secondary" to={candidateListLink}>返回候选列表</Link>
        </>
      )}
    >
      <div className="summary-grid">
        <div>
          <strong>建议编码</strong>
          <span className="mono">{text(group.proposed_element_code)}</span>
        </div>
        <div>
          <strong>业务类型猜测</strong>
          <span>{text(group.business_type_guess)}</span>
        </div>
        <div>
          <strong>质量等级</strong>
          <span><span className={`quality-pill quality-${qualityTone(group.quality_tier)}`}>{text(group.quality_tier)}</span> / {text(group.max_score)}</span>
        </div>
        <div>
          <strong>推荐动作</strong>
          <span><StatusPill prefix="action" value={group.recommended_action} labels={labels.action} /></span>
        </div>
        <div>
          <strong>主候选定位器</strong>
          <span className="mono">{text(group.top_locator_type)} = {text(group.top_locator_value)}</span>
        </div>
        <div>
          <strong>样本文本</strong>
          <span>{displayList(group.sample_texts_json)}</span>
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>
              <input type="checkbox" checked={allSelected} onChange={(event) => toggleAllSelection(visibleCandidateKeys, event.target.checked, setSelectedCandidateKeys)} disabled={busy || !visibleCandidateKeys.length} />
            </th>
            <th>locator_type</th>
            <th>locator_value</th>
            <th>role</th>
            <th>route</th>
            <th>命中</th>
            <th>分数</th>
            <th>风险</th>
            <th>probe</th>
            <th>来源 session</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.length ? (
            rows.map((item, index) => {
              const candidateKey = String(item.candidate_key || "").trim();
              return (
                <tr key={candidateKey || String(index)}>
                  <td>
                    <input type="checkbox" checked={Boolean(candidateKey && selectedCandidateKeys.includes(candidateKey))} onChange={() => toggleSelection(candidateKey, selectedCandidateKeys, setSelectedCandidateKeys)} disabled={busy || !candidateKey} />
                  </td>
                  <td>{text(item.raw_locator_type)}</td>
                  <td className="mono">{text(item.raw_locator_value)}</td>
                  <td>{text(item.raw_role)}</td>
                  <td>{text(item.route)}</td>
                  <td>{text(item.step_hit_count)}</td>
                  <td>{riskBar(item.quality_score)}</td>
                  <td>{displayList(item.risk_tags_json)}</td>
                  <td><StatusPill prefix="probe" value={item.probe_status} /> / {text(item.probe_match_count)}</td>
                  <td className="mono">{text(item.session_id)}</td>
                  <td><StatusPill prefix="candidate" value={item.candidate_status} labels={labels.candidate} /></td>
                  <td>
                    <button type="button" className="button secondary" onClick={() => rejectOneCandidate(item)} disabled={busy}>拒绝</button>
                  </td>
                </tr>
              );
            })
          ) : (
            <tr>
              <td colSpan={12}>
                {detailLoading ? "正在加载候选明细..." : <EmptyState title="暂无候选明细" description="当前候选分组下没有可展示的候选元素。" />}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </DataTable>
  );
}
