import { expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { MyEvaluationsPanel } from "./MyEvaluationsPage";

const mocks = vi.hoisted(() => ({ refreshUser: vi.fn(), personalQuery: vi.fn() }));
vi.mock("../../auth/AuthContext", () => ({ useAuth: () => ({ user: { id: 78, username: "a.ghasemi", role: "hr", personnel_id: null }, loading: false, refreshUser: mocks.refreshUser }) }));
vi.mock("../../auth/PermissionsContext", () => ({ usePermissions: () => ({ can: () => true, moduleEnabled: () => true, loading: false }) }));
vi.mock("../../api/queries", () => ({
  useMyCurrentSelfAssessment: mocks.personalQuery, useMySelfAssessments: mocks.personalQuery,
  useMyEvaluations: mocks.personalQuery, useMyOpenEvaluations: mocks.personalQuery,
  useMyImprovementPlans: mocks.personalQuery, useIndicators: mocks.personalQuery,
}));

it("shows a repair path without making failing personal requests for an unlinked account", async () => {
  render(<MemoryRouter><MyEvaluationsPanel /></MemoryRouter>);
  expect(mocks.personalQuery).not.toHaveBeenCalled();
  expect(screen.getByRole("link", { name: "ویرایش اتصال حساب من" })).toHaveAttribute("href", "/hr/people/accounts?q=a.ghasemi");
  expect(screen.queryByText("هنوز خودارزیابی‌ای برای شما فعال یا ثبت نشده است.")).not.toBeInTheDocument();
  await userEvent.setup().click(screen.getByRole("button", { name: "بررسی مجدد اتصال" }));
  expect(mocks.refreshUser).toHaveBeenCalledOnce();
});
