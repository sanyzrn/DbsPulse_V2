import { Fragment, type ReactNode } from "react";

/**
 * رندرِ سبکِ مارک‌داون — همان چیزی که پاسخِ همکار لازم دارد و نه بیشتر:
 * سرتیتر، پررنگ، کدِ درون‌خطی و بلوکی، فهرست، جدول و لینک.
 *
 * چرا کتابخانهٔ بیرونی نه: زبانِ سامانه فارسی و RTL است و رندرهای آماده در
 * وسطِ جمله‌های فارسی با نیم‌فاصله و جهت‌ها دردسر می‌سازند. این‌جا همهٔ
 * متن‌ها در همان جریانِ RTL می‌مانند و بستهٔ اضافه‌ای به باندل نمی‌رود.
 *
 * امنیت: هیچ HTML خامی تفسیر نمی‌شود — همه‌چیز رشتهٔ React است.
 */

function renderInline(text: string): ReactNode {
  // ترتیب مهم است: کدِ درون‌خطی اول، تا ستاره‌ها و براکت‌های داخل کد دست‌نخورده بمانند
  const pattern =
    /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*\n]+\*)|(\[[^\]]+\]\([^)\s]+\))/g;
  const nodes: ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) {
      nodes.push(<Fragment key={key++}>{text.slice(last, match.index)}</Fragment>);
    }
    const token = match[0];
    if (token.startsWith("`")) {
      nodes.push(
        <code
          key={key++}
          dir="auto"
          className="mx-0.5 rounded-md bg-gray-100 px-1.5 py-0.5 font-mono text-[0.85em] text-gray-800"
        >
          {token.slice(1, -1)}
        </code>,
      );
    } else if (token.startsWith("**")) {
      nodes.push(
        <strong key={key++} className="font-bold text-gray-900">
          {token.slice(2, -2)}
        </strong>,
      );
    } else if (token.startsWith("[")) {
      const linkMatch = /\[([^\]]+)\]\(([^)\s]+)\)/.exec(token);
      nodes.push(
        <a
          key={key++}
          href={linkMatch?.[2] ?? "#"}
          target="_blank"
          rel="noreferrer"
          className="text-pulse-600 underline decoration-pulse-200 underline-offset-2 hover:decoration-pulse-500"
        >
          {linkMatch?.[1] ?? token}
        </a>,
      );
    } else {
      nodes.push(
        <em key={key++} className="italic">
          {token.slice(1, -1)}
        </em>,
      );
    }
    last = match.index + token.length;
  }
  if (last < text.length) {
    nodes.push(<Fragment key={key++}>{text.slice(last)}</Fragment>);
  }
  return nodes;
}

type Block =
  | { kind: "p"; lines: string[] }
  | { kind: "h"; level: number; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "code"; text: string }
  | { kind: "table"; header: string[]; rows: string[][] };

function parseBlocks(src: string): Block[] {
  const lines = (src ?? "").split("\n");
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  let code: string[] | null = null;
  let table: { header: string[]; rows: string[][] } | null = null;

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ kind: "p", lines: paragraph });
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list) {
      blocks.push({ kind: list.ordered ? "ol" : "ul", items: list.items });
      list = null;
    }
  };
  const flushTable = () => {
    if (table) {
      blocks.push({ kind: "table", header: table.header, rows: table.rows });
      table = null;
    }
  };
  const flushAll = () => {
    flushParagraph();
    flushList();
    flushTable();
  };

  for (const raw of lines) {
    const line = raw.trimEnd();

    if (line.trim().startsWith("```")) {
      if (code) {
        blocks.push({ kind: "code", text: code.join("\n") });
        code = null;
      } else {
        flushAll();
        code = [];
      }
      continue;
    }
    if (code) {
      code.push(raw);
      continue;
    }

    const heading = /^(#{1,4})\s+(.*)$/.exec(line.trim());
    if (heading) {
      flushAll();
      blocks.push({ kind: "h", level: heading[1]?.length ?? 1, text: heading[2] ?? "" });
      continue;
    }

    // جدول: ردیفی که با | شروع/پایان می‌شود؛ خطِ جداکنندهٔ --- را می‌پریم
    if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
      const cells = line
        .trim()
        .slice(1, -1)
        .split("|")
        .map((cell) => cell.trim());
      const isSeparator = cells.every((cell) => /^:?-{2,}:?$/.test(cell) || cell === "");
      if (isSeparator) continue;
      flushParagraph();
      flushList();
      if (!table) {
        table = { header: cells, rows: [] };
      } else {
        table.rows.push(cells);
      }
      continue;
    }
    flushTable();

    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    if (bullet || numbered) {
      flushParagraph();
      const ordered = Boolean(numbered);
      const itemText = (bullet?.[1] ?? numbered?.[1] ?? "").trim();
      if (!list || list.ordered !== ordered) {
        flushList();
        list = { ordered, items: [] };
      }
      list.items.push(itemText);
      continue;
    }
    flushList();

    if (line.trim() === "") {
      flushParagraph();
      continue;
    }
    paragraph.push(line.trim());
  }
  flushAll();
  if (code) blocks.push({ kind: "code", text: code.join("\n") });
  return blocks;
}

export function Markdown({ text }: { text: string }) {
  const blocks = parseBlocks(text ?? "");
  return (
    <div className="space-y-2 leading-relaxed">
      {blocks.map((block, index) => {
        switch (block.kind) {
          case "h": {
            const size = block.level <= 2 ? "text-base font-bold" : "text-sm font-bold";
            return (
              <p key={index} className={`${size} text-gray-900`}>
                {renderInline(block.text)}
              </p>
            );
          }
          case "code":
            return (
              <pre
                key={index}
                dir="auto"
                className="overflow-x-auto rounded-xl bg-gray-900 p-3 text-left text-xs text-gray-100"
              >
                <code>{block.text}</code>
              </pre>
            );
          case "ul":
            return (
              <ul key={index} className="list-disc space-y-1 ps-5">
                {block.items.map((item, i) => (
                  <li key={i}>{renderInline(item)}</li>
                ))}
              </ul>
            );
          case "ol":
            return (
              <ol key={index} className="list-decimal space-y-1 ps-5">
                {block.items.map((item, i) => (
                  <li key={i}>{renderInline(item)}</li>
                ))}
              </ol>
            );
          case "table":
            return (
              <div key={index} className="overflow-x-auto rounded-xl border border-gray-200">
                <table className="w-full border-collapse text-xs">
                  <thead>
                    <tr className="bg-gray-50">
                      {block.header.map((cell, i) => (
                        <th
                          key={i}
                          className="border-b border-gray-200 px-2.5 py-2 text-start font-bold text-gray-700"
                        >
                          {cell}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {block.rows.map((row, r) => (
                      <tr key={r} className="odd:bg-white even:bg-gray-50/60">
                        {block.header.map((_, c) => (
                          <td key={c} className="border-b border-gray-100 px-2.5 py-1.5 text-gray-700">
                            {renderInline(row[c] ?? "")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          case "p":
          default:
            return (
              <p key={index} className="whitespace-pre-wrap">
                {block.lines.map((line, i) => (
                  <Fragment key={i}>
                    {i > 0 && <br />}
                    {renderInline(line)}
                  </Fragment>
                ))}
              </p>
            );
        }
      })}
    </div>
  );
}
