import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { CurrentSelfAssessment, Indicator } from "../../types";
import { ContractSelfAssessmentCard } from "./ContractSelfAssessmentCard";
import { SelfAssessmentScores } from "./SelfAssessmentScores";

const mocks = vi.hoisted(() => ({ indicators: [] as Indicator[] }));
vi.mock("../../api/queries", () => ({ useIndicators: () => ({ data: mocks.indicators }) }));
vi.mock("../../auth/AuthContext", () => ({ useAuth: () => ({ user: { id: 1, personnel_id: 1 } }) }));
vi.mock("../ConfirmDialog", () => ({ useConfirm: () => vi.fn() }));
vi.mock("../Toast", () => ({ useToast: () => ({ showSuccess: vi.fn(), showError: vi.fn() }) }));

const general: Indicator = { id: 1, section: "general", category: "رفتار حرفه‌ای", description: "همکاری با همکاران", display_order: 1, is_active: true, usage_count: 0, created_at: "", updated_at: "" };
const specialized: Indicator = { ...general, id: 2, section: "specialized", category: "مهارت شغلی", description: "کیفیت انجام کار" };
const replacement: Indicator = { ...general, id: 3, description: "شاخص عمومی جدید" };
const item: CurrentSelfAssessment = { assessment_id: 1, personnel_id: 1, personnel_name: "کارمند", contract_start_date: "2026-01-01", contract_end_date: "2026-12-31", state: "pending", eligible: true, open: true, indicator_ids: [1, 2], submitted_at: null, note: null, scores: [] };

beforeEach(() => {
  localStorage.clear();
  mocks.indicators = [general, specialized, replacement];
});

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = (value: CurrentSelfAssessment) => <QueryClientProvider client={client}><ContractSelfAssessmentCard item={value} /></QueryClientProvider>;
  const result = render(view(item));
  return { ...result, view, user: userEvent.setup() };
}

it("updates questions on refetch while retaining answers for unchanged indicators", async () => {
  const { user, rerender, view } = setup();
  await user.click(screen.getByRole("button", { name: "ثبت خودارزیابی" }));
  const generalGroup = within(screen.getByRole("region", { name: "شاخص‌های عمومی" }));
  const specializedGroup = within(screen.getByRole("region", { name: "شاخص‌های تخصصی" }));
  expect(generalGroup.getByRole("group", { name: general.description })).toBeInTheDocument();
  expect(specializedGroup.getByRole("group", { name: specialized.description })).toBeInTheDocument();
  await user.click(generalGroup.getByRole("button", { name: "امتیاز ۴" }));
  await user.click(specializedGroup.getByRole("button", { name: "امتیاز ۵" }));
  expect(screen.getByRole("button", { name: "ثبت نهایی خودارزیابی" })).toBeEnabled();
  rerender(view({ ...item, indicator_ids: [2, 3] }));
  expect(screen.queryByRole("group", { name: general.description })).not.toBeInTheDocument();
  expect(screen.getByRole("group", { name: replacement.description })).toBeInTheDocument();
  expect(specializedGroup.getByRole("button", { name: "امتیاز ۵" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "ثبت نهایی خودارزیابی" })).toBeDisabled();
});

it("cannot submit when some required indicator details have not loaded", async () => {
  mocks.indicators = [general];
  const { user } = setup();
  await user.click(screen.getByRole("button", { name: "ثبت خودارزیابی" }));
  await user.click(screen.getByRole("button", { name: "امتیاز ۴" }));
  expect(screen.getByRole("button", { name: "ثبت نهایی خودارزیابی" })).toBeDisabled();
});

it("shows submitted results from refreshed props with sections separated", () => {
  const { rerender, view } = setup();
  rerender(view({ ...item, open: false, state: "submitted", submitted_at: "2026-09-05T12:00:00Z", scores: [{ indicator_id: 1, score: 4, note: "توضیح محفوظ" }, { indicator_id: 2, score: 5, note: null }] }));
  expect(screen.queryByRole("button", { name: "ثبت خودارزیابی" })).not.toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "شاخص‌های عمومی" })).getByText("توضیح محفوظ")).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "شاخص‌های تخصصی" })).getByText("۵ از ۵")).toBeInTheDocument();
});

it("keeps historical scores visible even when an indicator is unavailable", () => {
  render(<SelfAssessmentScores indicators={[general]} scores={[{ indicator_id: 99, score: 3, note: "سابقه" }]} />);
  expect(within(screen.getByRole("region", { name: "سایر شاخص‌ها" })).getByText("سابقه")).toBeInTheDocument();
});
