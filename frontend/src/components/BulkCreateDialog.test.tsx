/** ترتیب و دسته‌بندی نتایج ساخت دسته‌ای.
 *
 * در فهرستی که می‌تواند دویست ردیف باشد، تنها چیزی که واقعاً کاری از HR می‌خواهد
 * سه ردیفِ «مسدود» است. اگر ترتیب یا رنگ‌بندی اشتباه شود، آن سه ردیف بی‌سروصدا
 * وسط فهرست گم می‌شوند و کسی خبردار نمی‌شود که چند نفر ارزیابی نگرفته‌اند.
 */
import { describe, expect, it } from "vitest";
import { isBlocked, sortResults } from "./BulkCreateDialog";

const row = (full_name: string, outcome: string) => ({
  personnel_id: full_name.length,
  full_name,
  org_unit: "واحد",
  outcome,
  reason: outcome,
  evaluation_id: null,
  evaluation_code: null,
});

describe("isBlocked", () => {
  it("«مسدود» را از «رد شد» جدا می‌کند", () => {
    // مسدود یعنی کاری لازم بود و نشد؛ رد شد یعنی کاری لازم نبود.
    expect(isBlocked("blocked_no_access_row")).toBe(true);
    expect(isBlocked("blocked_inactive")).toBe(true);
    expect(isBlocked("skipped_already_open")).toBe(false);
    expect(isBlocked("created")).toBe(false);
  });
});

describe("sortResults", () => {
  it("ردیف‌هایی که اقدام می‌خواهند اول می‌آیند", () => {
    const sorted = sortResults([
      row("الف", "created"),
      row("ب", "skipped_already_open"),
      row("پ", "blocked_no_supervisor"),
    ]);
    expect(sorted.map((r) => r.outcome)).toEqual([
      "blocked_no_supervisor",
      "created",
      "skipped_already_open",
    ]);
  });

  it("درون هر دسته، ترتیب الفبایی فارسی است", () => {
    const sorted = sortResults([
      row("یوسف", "blocked_inactive"),
      row("احمد", "blocked_inactive"),
    ]);
    expect(sorted.map((r) => r.full_name)).toEqual(["احمد", "یوسف"]);
  });

  it("ورودی را تغییر نمی‌دهد", () => {
    // پاسخ سرور در state می‌نشیند؛ مرتب‌کردن درجا یعنی رندر بعدی ترتیب دیگری
    // ببیند بدون اینکه چیزی عوض شده باشد.
    const input = [row("الف", "created"), row("ب", "blocked_inactive")];
    sortResults(input);
    expect(input.map((r) => r.outcome)).toEqual(["created", "blocked_inactive"]);
  });
});
