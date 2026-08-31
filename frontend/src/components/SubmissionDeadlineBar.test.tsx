/** نوارِ مهلتِ ثبت.
 *
 * دو چیزی که این‌جا قفل می‌شود، هر دو از آن‌هایی‌اند که خرابی‌شان بی‌صداست:
 *
 * ۱. مقایسهٔ تاریخ باید *محلی* باشد. با `new Date(deadline) < new Date()` مهلتِ
 *    امروز در ساعت‌های اولِ صبح «گذشته» خوانده می‌شود، چون رشتهٔ تاریخ به نیمه‌شبِ
 *    UTC تفسیر می‌شود و ایران جلوتر است. کاربر یک روز زودتر در را بسته می‌بیند.
 *
 * ۲. دکمهٔ تمدید فقط برای منابع انسانی، و فقط روی پرونده‌ای که هنوز در مرحلهٔ
 *    ثبت است. تمدیدِ پرونده‌ای که از این مرحله گذشته، چیزی را باز نمی‌کند و فقط
 *    یک تاریخِ گمراه‌کننده در پرونده می‌گذارد.
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ToastProvider } from "./Toast";
import { SubmissionDeadlineBar } from "./SubmissionDeadlineBar";
import type { EvaluationDetail } from "../types";

function renderWithProviders(ui: React.ReactElement) {
  return render(<ToastProvider>{ui}</ToastProvider>);
}

function localDay(offsetDays: number): string {
  const day = new Date();
  day.setDate(day.getDate() + offsetDays);
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(
    day.getDate()
  ).padStart(2, "0")}`;
}

function evaluation(overrides: Partial<EvaluationDetail> = {}): EvaluationDetail {
  return {
    id: 1,
    evaluation_code: "EVL-0001",
    subject_personnel_id: 1,
    subject_full_name: "کارمند",
    period_id: 1,
    unit_supervisor_user_id: 2,
    deputy_user_id: 3,
    ceo_user_id: 4,
    status: "draft",
    general_score_pct: null,
    specialized_score_pct: null,
    final_weighted_pct: null,
    recommendation: null,
    evaluator_comment: null,
    created_at: new Date().toISOString(),
    finalized_at: null,
    scores: [],
    comments: [],
    self_assessment: null,
    indicator_ids: [],
    submission_deadline: localDay(3),
    submission_deadline_extended: false,
    ...overrides,
  } as unknown as EvaluationDetail;
}

describe("SubmissionDeadlineBar", () => {
  it("پرونده‌ای که به دوره‌ای وصل نیست، نوار مهلت ندارد", () => {
    // نوارِ خالی فقط نویز است — و بدتر، القا می‌کند مهلتی هست که نیست.
    renderWithProviders(
      <SubmissionDeadlineBar
        evaluation={evaluation({ submission_deadline: null })}
        isHr
        onChanged={() => {}}
      />
    );
    expect(screen.queryByText(/مهلت ثبت/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "تمدید مهلت" })).not.toBeInTheDocument();
  });

  it("مهلتِ امروز هنوز «گذشته» نیست", () => {
    // ریشهٔ اشکالِ یک‌روز‌زودتر: رشتهٔ تاریخ نباید به نیمه‌شبِ UTC تفسیر شود.
    renderWithProviders(
      <SubmissionDeadlineBar
        evaluation={evaluation({ submission_deadline: localDay(0) })}
        isHr={false}
        onChanged={() => {}}
      />
    );
    expect(screen.getByText(/^مهلت ثبت/)).toBeInTheDocument();
    expect(screen.queryByText(/مهلت ثبت گذشته است/)).not.toBeInTheDocument();
  });

  it("مهلتِ دیروز گذشته اعلام می‌شود", () => {
    renderWithProviders(
      <SubmissionDeadlineBar
        evaluation={evaluation({ submission_deadline: localDay(-1) })}
        isHr={false}
        onChanged={() => {}}
      />
    );
    expect(screen.getByText(/مهلت ثبت گذشته است/)).toBeInTheDocument();
  });

  it("دکمهٔ تمدید فقط برای منابع انسانی است", () => {
    renderWithProviders(
      <SubmissionDeadlineBar
        evaluation={evaluation({ submission_deadline: localDay(-1) })}
        isHr={false}
        onChanged={() => {}}
      />
    );
    expect(screen.queryByRole("button", { name: "تمدید مهلت" })).not.toBeInTheDocument();
  });

  it("منابع انسانی روی پروندهٔ در حال ثبت، دکمهٔ تمدید دارد", () => {
    renderWithProviders(
      <SubmissionDeadlineBar
        evaluation={evaluation({ submission_deadline: localDay(-1), status: "draft" })}
        isHr
        onChanged={() => {}}
      />
    );
    expect(screen.getByRole("button", { name: "تمدید مهلت" })).toBeInTheDocument();
  });

  it("پرونده‌ای که از مرحلهٔ ثبت گذشته، تمدید نمی‌شود", () => {
    renderWithProviders(
      <SubmissionDeadlineBar
        evaluation={evaluation({ submission_deadline: localDay(-1), status: "submitted" })}
        isHr
        onChanged={() => {}}
      />
    );
    expect(screen.queryByRole("button", { name: "تمدید مهلت" })).not.toBeInTheDocument();
  });

  it("مهلتِ تمدیدشده برچسب می‌گیرد و دلیلش را نشان می‌دهد", () => {
    renderWithProviders(
      <SubmissionDeadlineBar
        evaluation={evaluation({
          submission_deadline: localDay(2),
          submission_deadline_extended: true,
          submission_extension_reason: "فرد در مرخصی استعلاجی بود",
        })}
        isHr
        onChanged={() => {}}
      />
    );
    expect(screen.getByText("تمدیدشده")).toBeInTheDocument();
    expect(screen.getByText(/مرخصی استعلاجی/)).toBeInTheDocument();
  });
});
