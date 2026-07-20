const styles = {
  paragraph: "mt-0 mb-2 last:mb-0",
  heading: "mt-2.5 mb-1.5 text-[15px]",
  list: "mt-0 mb-2 list-disc pl-[18px] last:mb-0",
  inlineCode: "rounded-[5px] bg-[var(--foa-soft)] px-[5px] py-px font-mono text-[90%]",
  codeBlock: "m-0 overflow-auto whitespace-pre-wrap font-mono",
  tableWrap: "my-2 max-w-full overflow-x-auto rounded-xl border border-[var(--foa-border)] bg-[rgba(255,255,255,0.5)]",
  table: "w-full border-collapse text-[13px]",
  cell: "border border-[var(--foa-border)] px-[9px] py-1.5 text-left",
  horizontalRule: "my-3 h-px w-full border-0 bg-[var(--foa-border)]",
};

export function renderMarkdown(value: string): string {
  let html = escapeHtml(value || "");
  html = html.replace(
    /```([\s\S]*?)```/g,
    (_match, code: string) => `<pre class="${styles.codeBlock}"><code>${code.replace(/^\n/, "")}</code></pre>`,
  );
  html = renderTables(html);
  html = html.replace(
    /^[ \t]{0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$/gm,
    `\n\n<hr class="${styles.horizontalRule}" />\n\n`,
  );
  html = html.replace(/`([^`\n]+)`/g, `<code class="${styles.inlineCode}">$1</code>`);
  html = html.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  html = html
    .replace(/^###\s+(.*)$/gm, `<h3 class="${styles.heading}">$1</h3>`)
    .replace(/^##\s+(.*)$/gm, `<h2 class="${styles.heading}">$1</h2>`);
  html = html.replace(
    /(?:^|\n)((?:- .*(?:\n|$))+)/g,
    (_match, list: string) =>
      `<ul class="${styles.list}">${list
        .trim()
        .split("\n")
        .map((line) => `<li>${line.replace(/^- /, "")}</li>`)
        .join("")}</ul>`,
  );
  return html
    .split(/\n{2,}/)
    .filter(Boolean)
    .map((block) => (/^<(h\d|ul|pre|div|hr)/.test(block) ? block : `<p class="${styles.paragraph}">${block.replace(/\n/g, "<br />")}</p>`))
    .join("");
}

function renderTables(html: string): string {
  return html.replace(/(^|\n)((?:[^\n]*\|[^\n]*(?:\n|$))+)/g, (_whole, lead: string, block: string) => {
    const lines = block.trim().split(/\n/);
    if (lines.length < 2 || !lines[1].includes("---")) return lead + block;
    const split = (line: string) => line.replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim());
    const header = split(lines[0]);
    const rows = lines.slice(2).map(split);
    return `${lead}<div class="${styles.tableWrap}"><table class="${styles.table}"><thead><tr>${header.map((cell) => `<th class="${styles.cell}">${cell}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td class="${styles.cell}">${cell}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  });
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char] || char);
}
