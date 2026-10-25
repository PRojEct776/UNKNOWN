/**
 * UNKNOWN Research Platform — Export and Download Utilities
 *
 * Provides functions for:
 * 1. Exporting individual analysis results to Markdown (.md) and styled Printable HTML (.html / PDF via print)
 * 2. Exporting complete research session histories
 * 3. Exporting Graph and Mind Map topologies (JSON / SVG)
 * 4. User-isolated download history tracking persisted in localStorage
 */

import type { WorkspaceResult, WorkspaceHistoryItem } from '../types/query';
import type { KnowledgeDNA, MindMapNode } from '../types/knowledge';

// ---------------------------------------------------------------------------
// Download History Types & Helpers (User-Scoped)
// ---------------------------------------------------------------------------

export interface DownloadHistoryEntry {
  id: string;
  timestamp: string;
  query: string;
  tool: string;
  format: 'markdown' | 'html' | 'json' | 'svg' | 'png';
  filename: string;
  sizeBytes: number;
}

export function getDownloadHistory(userId: string = 'default_user'): DownloadHistoryEntry[] {
  try {
    const key = `unknown_download_history_${userId}`;
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    return JSON.parse(raw) as DownloadHistoryEntry[];
  } catch {
    return [];
  }
}

export function recordDownload(
  userId: string = 'default_user',
  entry: Omit<DownloadHistoryEntry, 'id' | 'timestamp'>,
): void {
  try {
    const key = `unknown_download_history_${userId}`;
    const existing = getDownloadHistory(userId);
    const newEntry: DownloadHistoryEntry = {
      ...entry,
      id: `dl_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      timestamp: new Date().toISOString(),
    };
    const updated = [newEntry, ...existing].slice(0, 50); // Keep last 50
    localStorage.setItem(key, JSON.stringify(updated));
  } catch (err) {
    console.error('Failed to record download in history:', err);
  }
}

export function clearDownloadHistory(userId: string = 'default_user'): void {
  try {
    const key = `unknown_download_history_${userId}`;
    localStorage.removeItem(key);
  } catch (err) {
    console.error('Failed to clear download history:', err);
  }
}

// ---------------------------------------------------------------------------
// File Trigger Helper
// ---------------------------------------------------------------------------

function triggerBrowserDownload(filename: string, content: string, mimeType: string): number {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
  return blob.size;
}

// ---------------------------------------------------------------------------
// Individual Result Export — Markdown (.md)
// ---------------------------------------------------------------------------

export function exportResultToMarkdown(result: WorkspaceResult, researcherName: string = 'Researcher'): void {
  const dateStr = new Date().toLocaleString();
  const safeTitle = result.request.query.slice(0, 40).replace(/[^a-zA-Z0-9_-]/g, '_');
  const filename = `unknown_${result.request.mode}_${safeTitle}_${Date.now()}.md`;

  const lines: string[] = [
    `# UNKNOWN Research Report: ${result.request.query}`,
    ``,
    `**Tool Mode:** ${result.request.mode.toUpperCase()}`,
    `**Researcher:** ${researcherName}`,
    `**Generated:** ${dateStr}`,
    `**Engine / Origin:** ${result.origin === 'backend' ? 'Verified FastAPI Backend (Hybrid BM25 + FAISS)' : 'Local Simulation / Demo'}`,
    result.confidence !== undefined && result.confidence !== null
      ? `**Overall Confidence:** ${typeof result.confidence === 'object' ? result.confidence.score : result.confidence}%`
      : '',
    ``,
    `---`,
    ``,
    `## Research Synthesis & Findings`,
    ``,
    result.answer,
    ``,
  ];

  if (result.detailedAnswer && result.detailedAnswer !== result.answer) {
    lines.push(`### Detailed Analysis`, ``, result.detailedAnswer, ``);
  }

  // Tool-specific sections
  if (result.request.mode === 'verify' && result.verification?.length) {
    lines.push(`## Claim Verifications`, ``);
    result.verification.forEach((v, idx) => {
      lines.push(
        `### Claim ${idx + 1}: ${v.claim}`,
        `- **Assessment:** ${v.assessment}`,
        `- **Explanation:** ${v.explanation}`,
        ``,
      );
    });
  }

  if (result.request.mode === 'compare' && result.comparison?.length) {
    lines.push(`## Comparative Analysis Matrix`, ``);
    if (result.comparisonEntities?.length) {
      lines.push(`**Compared Entities:** ${result.comparisonEntities.join(', ')}`, ``);
    }
    lines.push(`| Criterion | Left Value | Right Value |`, `|---|---|---|`);
    result.comparison.forEach((row) => {
      lines.push(`| **${row.criterion}** | ${row.leftValue} | ${row.rightValue} |`);
    });
    lines.push(``);
  }

  if (result.request.mode === 'gaps' && result.researchGap) {
    lines.push(
      `## Research Gaps & Literature Boundaries`,
      ``,
      `**Current Knowledge:** ${result.researchGap.currentKnowledge}`,
      `**Identified Limitation:** ${result.researchGap.missingConnection}`,
      `**Potential Research Direction:** ${result.researchGap.potentialGap}`,
      ``,
    );
  }

  if (result.request.mode === 'debate' && result.debate) {
    lines.push(
      `## Dialectical Debate`,
      ``,
      `### Positions & Arguments`,
      ``,
    );
    result.debate.positions.forEach((p) => {
      lines.push(`#### Position: ${p.title}`, `${p.claim}`, ``);
    });
    lines.push(`### Synthesis Verdict`, ``, result.debate.conclusion, ``);
  }

  if (result.request.mode === 'knowledge-dna' && result.knowledgeDNA) {
    const dna = result.knowledgeDNA;
    lines.push(
      `## Knowledge DNA Profile`,
      ``,
      `**Research Area:** ${dna.researchArea || 'Multidisciplinary'}`,
      `**Core Topics:** ${dna.coreTopics?.join(', ') || 'N/A'}`,
      `**Key Concepts:** ${dna.keyConcepts?.join(', ') || 'N/A'}`,
      `**Methodologies:** ${dna.methods?.join(', ') || 'N/A'}`,
      `**Key Findings:** ${dna.findings?.join('; ') || 'N/A'}`,
      `**Limitations:** ${dna.limitations?.join('; ') || 'N/A'}`,
      ``,
    );
  }

  // Evidence snippets
  if (result.evidence?.length) {
    lines.push(`## Evidence Trail (${result.evidence.length} passages)`, ``);
    result.evidence.forEach((ev, idx) => {
      lines.push(
        `> **[${idx + 1}]** ${ev.text}`,
        `> *Document:* \`${ev.documentName}\` ${ev.page ? `(Page ${ev.page})` : ''} | *Chunk:* \`${ev.chunkId || 'N/A'}\``,
        ``,
      );
    });
  }

  // Citations / Sources
  if (result.sources?.length) {
    lines.push(`## Source Citations`, ``);
    result.sources.forEach((s, idx) => {
      lines.push(
        `${idx + 1}. **${s.documentName}** — Page ${s.page ?? '1'} (Rank #${s.rank ?? idx + 1})` +
        (s.score !== undefined ? ` [Score: ${s.score.toFixed(3)}]` : '') +
        (s.bm25Score !== undefined ? ` [BM25: ${s.bm25Score.toFixed(3)}]` : '') +
        (s.faissScore !== undefined ? ` [FAISS: ${s.faissScore.toFixed(3)}]` : ''),
      );
    });
    lines.push(``);
  }

  lines.push(`---`, `*Report exported from UNKNOWN Academic Research Assistant.*`);

  const content = lines.filter(Boolean).join('\n');
  const size = triggerBrowserDownload(filename, content, 'text/markdown;charset=utf-8');

  recordDownload(researcherName, {
    query: result.request.query,
    tool: result.request.mode,
    format: 'markdown',
    filename,
    sizeBytes: size,
  });
}

// ---------------------------------------------------------------------------
// Individual Result Export — Styled Printable HTML (.html / PDF Print)
// ---------------------------------------------------------------------------

export function exportResultToPrintableHtml(result: WorkspaceResult, researcherName: string = 'Researcher'): void {
  const dateStr = new Date().toLocaleString();
  const safeTitle = result.request.query.slice(0, 40).replace(/[^a-zA-Z0-9_-]/g, '_');
  const filename = `unknown_${result.request.mode}_${safeTitle}_${Date.now()}.html`;

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>UNKNOWN Research Report — ${escapeHtml(result.request.query)}</title>
  <style>
    @page { size: letter; margin: 1in; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      color: #1a202c;
      line-height: 1.6;
      max-width: 820px;
      margin: 0 auto;
      padding: 24px;
    }
    .header {
      border-bottom: 2px solid #e2e8f0;
      padding-bottom: 16px;
      margin-bottom: 24px;
    }
    .badge {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 11px;
      font-family: monospace;
      text-transform: uppercase;
      font-weight: 600;
      background: #edf2f7;
      color: #4a5568;
    }
    .badge-tool { background: #fee2e2; color: #991b1b; }
    .badge-verified { background: #dcfce7; color: #166534; }
    h1 { font-size: 22px; color: #0f172a; margin-top: 12px; margin-bottom: 6px; }
    .meta { font-size: 12px; color: #64748b; margin-bottom: 8px; }
    .meta strong { color: #334155; }
    .section-title {
      font-size: 15px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #334155;
      border-bottom: 1px solid #cbd5e1;
      padding-bottom: 6px;
      margin-top: 24px;
      margin-bottom: 12px;
    }
    .answer-box {
      background: #f8fafc;
      border-left: 4px solid #d2434e;
      padding: 16px;
      border-radius: 0 8px 8px 0;
      white-space: pre-wrap;
      font-size: 14px;
      margin-bottom: 20px;
    }
    .evidence-item {
      background: #f1f5f9;
      border-radius: 6px;
      padding: 12px 14px;
      margin-bottom: 10px;
      font-size: 13px;
    }
    .evidence-meta {
      font-size: 11px;
      color: #64748b;
      margin-top: 6px;
      font-family: monospace;
    }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
    th, td { border: 1px solid #e2e8f0; padding: 8px 12px; text-align: left; }
    th { background: #f8fafc; font-weight: 600; }
    .footer {
      margin-top: 40px;
      padding-top: 16px;
      border-top: 1px solid #e2e8f0;
      font-size: 11px;
      color: #94a3b8;
      text-align: center;
    }
    @media print {
      body { padding: 0; }
      .no-print { display: none; }
    }
  </style>
</head>
<body>
  <div class="no-print" style="margin-bottom: 20px; text-align: right;">
    <button onclick="window.print()" style="padding: 8px 16px; background: #d2434e; color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer;">Print / Save as PDF</button>
  </div>
  <div class="header">
    <span class="badge badge-tool">${escapeHtml(result.request.mode)}</span>
    <span class="badge ${result.origin === 'backend' ? 'badge-verified' : ''}">${escapeHtml(result.origin === 'backend' ? 'Backend Verified' : 'Demo Mode')}</span>
    <h1>${escapeHtml(result.request.query)}</h1>
    <div class="meta">
      <strong>Researcher:</strong> ${escapeHtml(researcherName)} &nbsp;|&nbsp;
      <strong>Date:</strong> ${escapeHtml(dateStr)} &nbsp;|&nbsp;
      <strong>Engine:</strong> UNKNOWN Hybrid Semantic Engine (BM25 + FAISS)
      ${result.confidence !== undefined && result.confidence !== null ? `&nbsp;|&nbsp; <strong>Confidence:</strong> ${typeof result.confidence === 'object' ? result.confidence.score : result.confidence}%` : ''}
    </div>
  </div>

  <div class="section-title">Synthesis & Findings</div>
  <div class="answer-box">${escapeHtml(result.answer)}</div>

  ${result.detailedAnswer && result.detailedAnswer !== result.answer ? `
    <div class="section-title">Detailed Analysis</div>
    <div style="font-size: 13px; white-space: pre-wrap; margin-bottom: 20px;">${escapeHtml(result.detailedAnswer)}</div>
  ` : ''}

  ${result.verification?.length ? `
    <div class="section-title">Claim Verifications</div>
    ${result.verification.map((v, i) => `
      <div class="evidence-item">
        <strong>Claim ${i + 1}:</strong> ${escapeHtml(v.claim)}<br/>
        <span class="badge ${v.assessment.toLowerCase().includes('supported') ? 'badge-verified' : 'badge-tool'}">${escapeHtml(v.assessment)}</span>
        <p style="margin: 6px 0 0 0; font-size: 13px;">${escapeHtml(v.explanation)}</p>
      </div>
    `).join('')}
  ` : ''}

  ${result.comparison?.length ? `
    <div class="section-title">Comparative Analysis Matrix</div>
    <table>
      <thead><tr><th>Criterion</th><th>Left</th><th>Right</th></tr></thead>
      <tbody>
        ${result.comparison.map((row) => `
          <tr>
            <td><strong>${escapeHtml(row.criterion)}</strong></td>
            <td>${escapeHtml(row.leftValue)}</td>
            <td>${escapeHtml(row.rightValue)}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  ` : ''}

  ${result.request.mode === 'knowledge-dna' && result.knowledgeDNA ? `
    <div class="section-title">Knowledge DNA Architecture Topology</div>
    <div style="text-align: center; margin: 16px 0; overflow-x: auto;">
      ${generateKnowledgeDnaSvg(result.knowledgeDNA, 770, 420)}
    </div>
  ` : ''}

  ${result.mindMap && (result.request.mode === 'knowledge-map' || result.mindMap.children?.length) ? `
    <div class="section-title">Knowledge Mind Map Relational Hierarchy</div>
    <div style="text-align: center; margin: 16px 0; overflow-x: auto;">
      ${generateMindMapSvg(result.mindMap, 770)}
    </div>
  ` : ''}

  ${result.evidence?.length ? `
    <div class="section-title">Evidence Passages (${result.evidence.length})</div>
    ${result.evidence.map((ev) => `
      <div class="evidence-item">
        <em>"${escapeHtml(ev.text)}"</em>
        <div class="evidence-meta">Source: ${escapeHtml(ev.documentName)} ${ev.page ? `(Page ${ev.page})` : ''} | Chunk ID: ${escapeHtml(ev.chunkId || 'N/A')}</div>
      </div>
    `).join('')}
  ` : ''}

  ${result.sources?.length ? `
    <div class="section-title">Cited Literature Sources (${result.sources.length})</div>
    <table>
      <thead><tr><th>#</th><th>Document</th><th>Page</th><th>Chunk</th><th>Scores</th></tr></thead>
      <tbody>
        ${result.sources.map((s, i) => `
          <tr>
            <td>${i + 1}</td>
            <td><strong>${escapeHtml(s.documentName || s.document || 'Unknown')}</strong></td>
            <td>${s.page ?? '1'}</td>
            <td style="font-family: monospace; font-size: 11px;">${escapeHtml(s.chunkId || '—')}</td>
            <td style="font-size: 11px; color: #64748b;">
              ${s.score !== undefined ? `Score: ${s.score.toFixed(3)} ` : ''}
              ${s.bm25Score !== undefined ? `BM25: ${s.bm25Score.toFixed(3)} ` : ''}
              ${s.faissScore !== undefined ? `FAISS: ${s.faissScore.toFixed(3)}` : ''}
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  ` : ''}

  <div class="footer">
    Generated by UNKNOWN Academic Research Assistant &bull; Confidential Research Documentation
  </div>
</body>
</html>`;

  const size = triggerBrowserDownload(filename, html, 'text/html;charset=utf-8');

  recordDownload(researcherName, {
    query: result.request.query,
    tool: result.request.mode,
    format: 'html',
    filename,
    sizeBytes: size,
  });
}

// ---------------------------------------------------------------------------
// Complete Research Session Export (Markdown & HTML)
// ---------------------------------------------------------------------------

export function exportSessionToMarkdown(history: WorkspaceHistoryItem[], researcherName: string = 'Researcher'): void {
  if (!history.length) return;
  const dateStr = new Date().toLocaleString();
  const filename = `unknown_session_export_${Date.now()}.md`;

  const lines: string[] = [
    `# UNKNOWN Research Session Archive`,
    ``,
    `**Researcher:** ${researcherName}`,
    `**Session Exported:** ${dateStr}`,
    `**Total Analyses:** ${history.length}`,
    ``,
    `---`,
    ``,
  ];

  history.forEach((item, index) => {
    lines.push(
      `## [${index + 1}] ${item.query}`,
      ``,
      `**Tool:** \`${item.mode.toUpperCase()}\` | **Submitted:** ${item.timestamp} | **Origin:** ${item.result.origin}`,
      ``,
      `### Answer`,
      ``,
      item.result.answer,
      ``,
    );

    if (item.result.sources?.length) {
      lines.push(`**Sources:** ${item.result.sources.map((s) => `\`${s.documentName}\` (P.${s.page ?? 1})`).join(', ')}`, ``);
    }

    lines.push(`---`, ``);
  });

  const content = lines.join('\n');
  const size = triggerBrowserDownload(filename, content, 'text/markdown;charset=utf-8');

  recordDownload(researcherName, {
    query: `Complete Session (${history.length} analyses)`,
    tool: 'session-archive',
    format: 'markdown',
    filename,
    sizeBytes: size,
  });
}

export function exportSessionToHtml(history: WorkspaceHistoryItem[], researcherName: string = 'Researcher'): void {
  if (!history.length) return;
  const dateStr = new Date().toLocaleString();
  const filename = `unknown_session_export_${Date.now()}.html`;

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>UNKNOWN Research Session Archive</title>
  <style>
    @page { size: letter; margin: 1in; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      color: #1a202c;
      line-height: 1.6;
      max-width: 860px;
      margin: 0 auto;
      padding: 24px;
    }
    h1 { font-size: 24px; color: #0f172a; margin-bottom: 6px; }
    .session-meta { font-size: 13px; color: #64748b; margin-bottom: 24px; padding-bottom: 12px; border-bottom: 2px solid #e2e8f0; }
    .card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin-bottom: 20px; page-break-inside: avoid; }
    .card-title { font-size: 16px; font-weight: 700; color: #1e293b; margin-top: 0; margin-bottom: 6px; }
    .badge { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-family: monospace; font-weight: 600; background: #e2e8f0; color: #334155; margin-right: 6px; }
    .badge-mode { background: #fee2e2; color: #991b1b; }
    .answer-text { white-space: pre-wrap; font-size: 14px; margin-top: 10px; color: #334155; }
    .sources-list { margin-top: 12px; font-size: 12px; color: #64748b; }
    @media print {
      body { padding: 0; }
      .no-print { display: none; }
    }
  </style>
</head>
<body>
  <div class="no-print" style="margin-bottom: 20px; text-align: right;">
    <button onclick="window.print()" style="padding: 8px 16px; background: #d2434e; color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer;">Print / Save as PDF</button>
  </div>
  <h1>UNKNOWN Research Session Archive</h1>
  <div class="session-meta">
    <strong>Researcher:</strong> ${escapeHtml(researcherName)} &bull;
    <strong>Exported:</strong> ${escapeHtml(dateStr)} &bull;
    <strong>Analyses:</strong> ${history.length} completed queries
  </div>

  ${history.map((item, idx) => `
    <div class="card">
      <div style="margin-bottom: 8px;">
        <span class="badge badge-mode">${escapeHtml(item.mode.toUpperCase())}</span>
        <span class="badge">${escapeHtml(item.result.origin)}</span>
        <span style="font-size: 11px; color: #94a3b8;">#${idx + 1} &bull; ${escapeHtml(item.timestamp)}</span>
      </div>
      <h2 class="card-title">${escapeHtml(item.query)}</h2>
      <div class="answer-text">${escapeHtml(item.result.answer)}</div>
      ${item.result.sources?.length ? `
        <div class="sources-list">
          <strong>Citations (${item.result.sources.length}):</strong>
          ${item.result.sources.map((s) => `${escapeHtml(s.documentName || s.document || 'Unknown')} (P.${s.page ?? 1})`).join(', ')}
        </div>
      ` : ''}
    </div>
  `).join('')}

  <div style="text-align: center; font-size: 11px; color: #94a3b8; margin-top: 30px;">
    Exported from UNKNOWN Academic Research Assistant
  </div>
</body>
</html>`;

  const size = triggerBrowserDownload(filename, html, 'text/html;charset=utf-8');

  recordDownload(researcherName, {
    query: `Complete Session (${history.length} analyses)`,
    tool: 'session-archive',
    format: 'html',
    filename,
    sizeBytes: size,
  });
}

// ---------------------------------------------------------------------------
// Mind Map & Knowledge DNA Visual Export (JSON, SVG, PNG)
// ---------------------------------------------------------------------------

export function exportMindMapToJson(result: WorkspaceResult, researcherName: string = 'Researcher'): void {
  const data = result.mindMap || result.rawResponse;
  if (!data) return;
  const filename = `unknown_mindmap_${Date.now()}.json`;
  const content = JSON.stringify(data, null, 2);
  const size = triggerBrowserDownload(filename, content, 'application/json');

  recordDownload(researcherName, {
    query: result.request.query,
    tool: 'mind-map-topology',
    format: 'json',
    filename,
    sizeBytes: size,
  });
}

/**
 * Generate a standalone, fully-styled vector SVG for Knowledge DNA.
 */
export function generateKnowledgeDnaSvg(data: KnowledgeDNA, width: number = 800, height: number = 440): string {
  const coreTopics = data?.coreTopics || [];
  const keyConcepts = data?.keyConcepts || [];
  const methods = data?.methods || [];
  const findings = data?.findings || [];
  const limitations = data?.limitations || [];

  const nodeTypes = [
    { items: coreTopics.slice(0, 4), type: 'TOPIC', color: '#3b82f6', label: 'Topic' },
    { items: keyConcepts.slice(0, 5), type: 'CONCEPT', color: '#10b981', label: 'Concept' },
    { items: methods.slice(0, 4), type: 'METHOD', color: '#f59e0b', label: 'Method' },
    { items: findings.slice(0, 4), type: 'FINDING', color: '#8b5cf6', label: 'Finding' },
    { items: limitations.slice(0, 3), type: 'LIMITATION', color: '#ef4444', label: 'Limitation' },
  ];

  const allSignals: Array<{ id: string; name: string; type: string; color: string; x: number; y: number }> = [];
  const totalNodes = nodeTypes.reduce((acc, t) => acc + t.items.length, 0);
  const centerX = width / 2;
  const centerY = height / 2 + 10;
  const radiusX = Math.min(width * 0.38, 280);
  const radiusY = Math.min(height * 0.35, 140);

  let nodeIndex = 0;
  nodeTypes.forEach((group) => {
    group.items.forEach((name) => {
      const angle = (nodeIndex / (totalNodes || 1)) * 2 * Math.PI;
      const x = Math.round(centerX + Math.cos(angle) * radiusX);
      const y = Math.round(centerY + Math.sin(angle) * radiusY);
      allSignals.push({
        id: `node_${nodeIndex}`,
        name: typeof name === 'string' ? name : String(name),
        type: group.type,
        color: group.color,
        x,
        y,
      });
      nodeIndex++;
    });
  });

  const linesSvg = allSignals
    .map(
      (node) =>
        `<line x1="${centerX}" y1="${centerY}" x2="${node.x}" y2="${node.y}" stroke="${node.color}" stroke-opacity="0.4" stroke-width="1.5" stroke-dasharray="3,3" />`,
    )
    .join('\n    ');

  const nodesSvg = allSignals
    .map((node) => {
      const safeName = escapeHtml(node.name.length > 30 ? `${node.name.slice(0, 28)}...` : node.name);
      return `    <g class="dna-node">
      <circle cx="${node.x}" cy="${node.y}" r="17" fill="#0b1219" stroke="${node.color}" stroke-width="2" />
      <text x="${node.x}" y="${node.y + 4}" text-anchor="middle" fill="${node.color}" font-size="9" font-weight="bold" font-family="monospace">${escapeHtml(node.type[0])}</text>
      <text x="${node.x}" y="${node.y + 28}" text-anchor="middle" fill="#f3faf0" font-size="10" font-weight="500" font-family="system-ui, -apple-system, sans-serif">${safeName}</text>
    </g>`;
    })
    .join('\n');

  const researchAreaLabel = escapeHtml(data?.researchArea || 'Multidisciplinary Domain');

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" style="background-color: #070b0f; border-radius: 8px;">
  <defs>
    <radialGradient id="dnaCoreGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#d2434e" stop-opacity="0.4" />
      <stop offset="100%" stop-color="#d2434e" stop-opacity="0" />
    </radialGradient>
  </defs>
  <rect width="${width}" height="${height}" fill="#070b0f" rx="8" />

  <!-- Header -->
  <text x="24" y="32" fill="#ffffff" font-size="14" font-weight="bold" font-family="system-ui, -apple-system, sans-serif">UNKNOWN Knowledge DNA Architecture</text>
  <text x="24" y="50" fill="#a7d0d2" font-size="11" font-family="monospace">Domain: ${researchAreaLabel}</text>

  <!-- Legend -->
  <g transform="translate(${Math.max(24, width - 420)}, 22)" font-size="10" font-family="monospace" fill="#f3faf0">
    <circle cx="0" cy="5" r="4" fill="#3b82f6" /><text x="8" y="9">Topic</text>
    <circle cx="65" cy="5" r="4" fill="#10b981" /><text x="73" y="9">Concept</text>
    <circle cx="145" cy="5" r="4" fill="#f59e0b" /><text x="153" y="9">Method</text>
    <circle cx="215" cy="5" r="4" fill="#8b5cf6" /><text x="223" y="9">Finding</text>
    <circle cx="285" cy="5" r="4" fill="#ef4444" /><text x="293" y="9">Limitation</text>
  </g>

  <!-- Connecting Lines -->
  <g>
    ${linesSvg}
  </g>

  <!-- Central Hub Core -->
  <circle cx="${centerX}" cy="${centerY}" r="55" fill="url(#dnaCoreGlow)" />
  <circle cx="${centerX}" cy="${centerY}" r="32" fill="#141d26" stroke="#d2434e" stroke-width="2.5" />
  <text x="${centerX}" y="${centerY + 4}" text-anchor="middle" fill="#ffffff" font-size="11" font-weight="bold" font-family="monospace">DNA CORE</text>

  <!-- Satellite Nodes -->
  ${nodesSvg}
</svg>`;
}

/**
 * Generate a standalone, fully-styled vector SVG for Knowledge Mind Map.
 */
export function generateMindMapSvg(root: MindMapNode, minWidth: number = 860): string {
  if (!root) {
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 200" width="600" height="200" style="background:#070b0f;"><rect width="600" height="200" fill="#070b0f"/><text x="300" y="105" text-anchor="middle" fill="#98a6b0" font-size="13" font-family="system-ui, sans-serif">No mind map data available.</text></svg>`;
  }

  const children = root.children || [];
  const numBranches = Math.max(children.length, 1);
  const branchWidth = 240;
  const branchGap = 24;
  const totalWidth = Math.max(minWidth, numBranches * (branchWidth + branchGap) - branchGap + 80);

  // Compute depth and heights
  let maxBranchBottom = 230;
  children.forEach((child) => {
    const subCount = child.children?.length || 0;
    const branchBottom = 170 + 50 + subCount * 54;
    if (branchBottom > maxBranchBottom) {
      maxBranchBottom = branchBottom;
    }
  });

  const totalHeight = Math.max(480, maxBranchBottom + 50);
  const rootX = Math.round(totalWidth / 2 - 130);
  const rootCenterX = Math.round(totalWidth / 2);

  const paths: string[] = [];
  const nodesMarkup: string[] = [];

  children.forEach((child, idx) => {
    const branchX = 40 + idx * (branchWidth + branchGap);
    const branchCenterX = branchX + Math.round(branchWidth / 2);
    const branchY = 170;

    // Curved connector from root bottom to branch top
    paths.push(
      `<path d="M ${rootCenterX} 96 C ${rootCenterX} 133, ${branchCenterX} 133, ${branchCenterX} ${branchY}" stroke="#4d728e" stroke-width="1.8" fill="none" />`,
    );

    // Branch card
    const branchLabel = escapeHtml(child.label.length > 32 ? `${child.label.slice(0, 30)}...` : child.label);
    const branchDesc = escapeHtml(child.description ? (child.description.length > 36 ? `${child.description.slice(0, 34)}...` : child.description) : '');

    nodesMarkup.push(`
    <g class="mindmap-branch">
      <rect x="${branchX}" y="${branchY}" width="${branchWidth}" height="50" rx="8" fill="#0b1219" stroke="#4d728e" stroke-width="1.5" />
      <text x="${branchCenterX}" y="${branchY + 23}" text-anchor="middle" fill="#ffffff" font-size="11" font-weight="bold" font-family="system-ui, -apple-system, sans-serif">${branchLabel}</text>
      ${branchDesc ? `<text x="${branchCenterX}" y="${branchY + 39}" text-anchor="middle" fill="#a7d0d2" font-size="9" font-family="system-ui, -apple-system, sans-serif">${branchDesc}</text>` : ''}
    </g>`);

    // Sub-children
    if (child.children?.length) {
      child.children.forEach((sub, subIdx) => {
        const subY = 240 + subIdx * 54;
        const subX = branchX + 30;
        const subWidth = branchWidth - 30;

        // Connector line from branch
        paths.push(
          `<path d="M ${branchX + 16} 220 V ${subY + 20} H ${subX}" stroke="#4d728e" stroke-width="1.4" stroke-opacity="0.6" fill="none" />`,
        );

        const subLabel = escapeHtml(sub.label.length > 32 ? `${sub.label.slice(0, 30)}...` : sub.label);
        const subDesc = escapeHtml(sub.description ? (sub.description.length > 32 ? `${sub.description.slice(0, 30)}...` : sub.description) : '');

        nodesMarkup.push(`
      <g class="mindmap-subnode">
        <rect x="${subX}" y="${subY}" width="${subWidth}" height="40" rx="6" fill="#141d26" stroke="#4d728e" stroke-opacity="0.5" stroke-width="1" />
        <text x="${subX + 10}" y="${subY + 18}" fill="#a7d0d2" font-size="10" font-weight="600" font-family="system-ui, -apple-system, sans-serif">${subLabel}</text>
        ${subDesc ? `<text x="${subX + 10}" y="${subY + 31}" fill="#f3faf0" fill-opacity="0.6" font-size="8" font-family="system-ui, -apple-system, sans-serif">${subDesc}</text>` : ''}
      </g>`);
      });
    }
  });

  const rootTitle = escapeHtml(root.label.length > 38 ? `${root.label.slice(0, 36)}...` : root.label);
  const rootDesc = escapeHtml(root.description ? (root.description.length > 38 ? `${root.description.slice(0, 36)}...` : root.description) : 'Synthesized Knowledge Hierarchy');

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${totalWidth} ${totalHeight}" width="${totalWidth}" height="${totalHeight}" style="background-color: #070b0f; border-radius: 8px;">
  <rect width="${totalWidth}" height="${totalHeight}" fill="#070b0f" rx="8" />

  <!-- Header -->
  <text x="30" y="28" fill="#ffffff" font-size="13" font-weight="bold" font-family="system-ui, -apple-system, sans-serif">UNKNOWN Knowledge Mind Map Topology</text>
  <text x="30" y="44" fill="#a7d0d2" font-size="10" font-family="monospace">Interactive Relational Concept Hierarchy</text>

  <!-- Connectors -->
  <g>
    ${paths.join('\n    ')}
  </g>

  <!-- Root Concept Box -->
  <g class="mindmap-root">
    <rect x="${rootX}" y="40" width="240" height="56" rx="8" fill="#141d26" stroke="#d2434e" stroke-width="2" />
    <text x="${rootCenterX}" y="65" text-anchor="middle" fill="#ffffff" font-size="12" font-weight="bold" font-family="system-ui, -apple-system, sans-serif">${rootTitle}</text>
    <text x="${rootCenterX}" y="82" text-anchor="middle" fill="#a7d0d2" font-size="9" font-family="monospace">${rootDesc}</text>
  </g>

  <!-- Branches and Nodes -->
  ${nodesMarkup.join('\n')}
</svg>`;
}

/**
 * Trigger standalone browser download of an SVG file and record in download history.
 */
export function downloadSvgFile(
  filename: string,
  svgContent: string,
  userId: string = 'default_user',
  query: string = 'Visualization',
): number {
  const safeFilename = filename.endsWith('.svg') ? filename : `${filename}.svg`;
  const size = triggerBrowserDownload(safeFilename, svgContent, 'image/svg+xml;charset=utf-8');
  recordDownload(userId, {
    query,
    tool: 'svg-export',
    format: 'svg',
    filename: safeFilename,
    sizeBytes: size,
  });
  return size;
}

/**
 * Convert an SVG string to a high-DPI PNG via HTML Canvas and trigger browser download.
 * Falls back safely to SVG download if canvas rasterization fails in constrained environments.
 */
export async function downloadSvgAsPngFile(
  filename: string,
  svgContent: string,
  width: number,
  height: number,
  userId: string = 'default_user',
  query: string = 'Visualization',
): Promise<void> {
  const safeFilename = filename.endsWith('.png') ? filename : `${filename}.png`;

  return new Promise((resolve, reject) => {
    try {
      const scale = 2; // 2x high-resolution rendering
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(width * scale, 1200);
      canvas.height = Math.max(height * scale, 600);
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        throw new Error('Canvas 2D rendering context not available');
      }

      const svgBlob = new Blob([svgContent], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(svgBlob);
      const img = new Image();

      img.onload = () => {
        ctx.fillStyle = '#070b0f';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        URL.revokeObjectURL(url);

        canvas.toBlob((pngBlob) => {
          if (!pngBlob) {
            fallbackToSvg();
            reject(new Error('Failed to create PNG blob from canvas'));
            return;
          }
          const pngUrl = URL.createObjectURL(pngBlob);
          const anchor = document.createElement('a');
          anchor.href = pngUrl;
          anchor.download = safeFilename;
          document.body.appendChild(anchor);
          anchor.click();
          document.body.removeChild(anchor);
          URL.revokeObjectURL(pngUrl);

          recordDownload(userId, {
            query,
            tool: 'png-export',
            format: 'png',
            filename: safeFilename,
            sizeBytes: pngBlob.size,
          });
          resolve();
        }, 'image/png');
      };

      const fallbackToSvg = () => {
        downloadSvgFile(safeFilename.replace(/\.png$/, '.svg'), svgContent, userId, query);
      };

      img.onerror = (e) => {
        URL.revokeObjectURL(url);
        fallbackToSvg();
        reject(new Error(`Failed to rasterize SVG into PNG: ${e}`));
      };

      img.src = url;
    } catch (err) {
      downloadSvgFile(safeFilename.replace(/\.png$/, '.svg'), svgContent, userId, query);
      reject(err);
    }
  });
}

// ---------------------------------------------------------------------------
// HTML Entity Escape Utility
// ---------------------------------------------------------------------------

function escapeHtml(str: string): string {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

