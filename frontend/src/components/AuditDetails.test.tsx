import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuditDetails, auditLines } from "./AuditDetails";

/** نمونه‌های واقعیِ همان چیزی که در ستون «جزئیات» دیده می‌شد. */
describe("AuditDetails — نمونه‌های واقعی", () => {
  it("ورود: {\"ip\":\"127.0.0.1\"}", () => {
    render(<AuditDetails oldValue={null} newValue={{ ip: "127.0.0.1" }} />);
    expect(screen.getByText("نشانی IP:")).toBeInTheDocument();
    expect(screen.getByText("127.0.0.1")).toBeInTheDocument();
  });

  it('ذخیرهٔ پیش‌نویس: {"scored_indicators":1}', () => {
    render(<AuditDetails oldValue={null} newValue={{ scored_indicators: 1 }} />);
    expect(screen.getByText("تعداد شاخص امتیازگرفته:")).toBeInTheDocument();
    expect(screen.getByText("۱")).toBeInTheDocument();
  });

  it("نهایی‌شدن: درصدها با ٪ و توصیه با متن کامل", () => {
    render(
      <AuditDetails
        oldValue={null}
        newValue={{
          recommendation: "تمدید مشروط به برنامه بهبود مکتوب",
          general_score_pct: 60,
          final_weighted_pct: 60,
          specialized_score_pct: 60,
        }}
      />,
    );
    expect(screen.getByText("امتیاز نهایی وزنی:")).toBeInTheDocument();
    expect(screen.getAllByText("۶۰٪").length).toBe(3);
    expect(screen.getByText("تمدید مشروط به برنامه بهبود مکتوب")).toBeInTheDocument();
  });

  it("اجرای یادآوری‌های خودکار: هر شمارنده برچسب فارسی می‌گیرد", () => {
    render(
      <AuditDetails
        oldValue={null}
        newValue={{
          sla_reminder: 0,
          orphaned_case: 0,
          contract_expiry: 2,
          improvement_review: 0,
          stale_login_attempts_purged: 0,
        }}
      />,
    );
    expect(screen.getByText("یادآوری مهلت:")).toBeInTheDocument();
    expect(screen.getByText("قرارداد رو به انقضا:")).toBeInTheDocument();
    expect(screen.getByText("۲")).toBeInTheDocument();
  });
});

describe("AuditDetails — تفاوت", () => {
  it("وقتی هم مقدار پیشین هست هم جدید، «قبلی ← جدید» نشان می‌دهد نه دو بلوک جدا", () => {
    render(
      <AuditDetails
        oldValue={{ status: "draft" }}
        newValue={{ status: "submitted" }}
      />,
    );
    // هر دو وضعیت با برچسب فارسی، نه با نام فنی
    expect(screen.getByText("پیش‌نویس")).toBeInTheDocument();
    expect(screen.getByText("ثبت‌شده")).toBeInTheDocument();
  });

  it("کلیدی که فقط در یک طرف است، بدون فلش نمایش داده می‌شود", () => {
    const lines = auditLines({ title: "قدیم" }, { title: "جدید", reason: "چون" });
    expect(lines.find((l) => l.key === "title")).toMatchObject({
      before: "قدیم",
      after: "جدید",
    });
    expect(lines.find((l) => l.key === "reason")).toMatchObject({ after: "چون" });
    expect(lines.find((l) => l.key === "reason")?.before).toBeUndefined();
  });
});

describe("AuditDetails — قالب‌بندی مقادیر", () => {
  it("بولین فارسی می‌شود", () => {
    render(<AuditDetails oldValue={null} newValue={{ is_active: false, is_done: true }} />);
    expect(screen.getByText("خیر")).toBeInTheDocument();
    expect(screen.getByText("بله")).toBeInTheDocument();
  });

  it("نقش با برچسب فارسی می‌آید", () => {
    render(<AuditDetails oldValue={null} newValue={{ role: "unit_supervisor" }} />);
    expect(screen.getByText("مسئول واحد")).toBeInTheDocument();
  });

  it("شیء تودرتو (filters) باز می‌شود، نه اینکه JSON بماند", () => {
    render(
      <AuditDetails
        oldValue={null}
        newValue={{ filters: { org_unit: "فروش" }, row_count: 12 }}
      />,
    );
    expect(screen.getByText(/فروش/)).toBeInTheDocument();
    expect(screen.queryByText(/\{/)).not.toBeInTheDocument();
  });

  it("کلید ناشناخته پنهان نمی‌شود — مدرک نباید به‌خاطر نبودِ برچسب گم شود", () => {
    render(<AuditDetails oldValue={null} newValue={{ some_future_field: "مقدار" }} />);
    expect(screen.getByText("some_future_field:")).toBeInTheDocument();
    expect(screen.getByText("مقدار")).toBeInTheDocument();
  });

  it("ردیف بدون جزئیات، خط تیره می‌دهد نه قاب خالی", () => {
    render(<AuditDetails oldValue={null} newValue={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
