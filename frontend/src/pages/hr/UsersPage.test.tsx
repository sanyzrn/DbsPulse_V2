import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { EditUserModal } from "./UsersPage";
import type { AppUser, Personnel, UserRole } from "../../types";

const mocks = vi.hoisted(() => ({ patch: vi.fn(), refreshUser: vi.fn() }));
vi.mock("../../api/client", () => ({ apiClient: { patch: mocks.patch }, extractErrorMessage: () => "Error" }));
vi.mock("../../auth/AuthContext", () => ({ useAuth: () => ({ user: { id: 78 }, refreshUser: mocks.refreshUser }) }));
vi.mock("../../components/Toast", () => ({ useToast: () => ({ showSuccess: vi.fn(), showError: vi.fn() }) }));
const person = { id: 60, full_name: "علی قاسمی", personnel_code: "2000290" } as Personnel;
function setup(role: UserRole, personnelId: number | null = 60) {
  const user = { id: 78, username: "a.ghasemi", role, full_name: "علی قاسمی", personnel_id: personnelId } as AppUser;
  render(<QueryClientProvider client={new QueryClient()}><EditUserModal user={user} personnel={[person]} onClose={vi.fn()} /></QueryClientProvider>);
  return userEvent.setup();
}
beforeEach(() => { mocks.patch.mockReset().mockResolvedValue({ data: {} }); mocks.refreshUser.mockReset().mockResolvedValue(undefined); });

it.each(["hr", "unit_supervisor", "support"] as const)("preserves personnel linkage when editing the name of a %s account", async (role) => {
  const user = setup(role);
  expect(screen.getByRole("combobox", { name: /پرسنل متناظر/ })).toHaveValue("60");
  await user.type(screen.getByRole("textbox", { name: /نام و سِمَت/ }), " جدید");
  await user.click(screen.getByRole("button", { name: "ذخیره" }));
  await waitFor(() => expect(mocks.patch).toHaveBeenCalled());
  const payload = mocks.patch.mock.calls[0]![1];
  expect(payload).not.toHaveProperty("personnel_id");
  expect(payload).not.toHaveProperty("role");
  await waitFor(() => expect(mocks.refreshUser).toHaveBeenCalled());
});

it("links an HR account and refreshes its current identity", async () => {
  const user = setup("hr", null);
  await user.selectOptions(screen.getByRole("combobox", { name: /پرسنل متناظر/ }), "60");
  await user.click(screen.getByRole("button", { name: "ذخیره" }));
  await waitFor(() => expect(mocks.patch).toHaveBeenCalledWith("/users/78", expect.objectContaining({ personnel_id: 60 })));
  await waitFor(() => expect(mocks.refreshUser).toHaveBeenCalled());
});
