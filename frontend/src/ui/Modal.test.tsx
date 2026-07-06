import { useState } from "react";
import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Modal } from "./Modal";

function Harness({ initiallyOpen = true }: { initiallyOpen?: boolean }) {
  const [open, setOpen] = useState(initiallyOpen);
  return (
    <div>
      <button onClick={() => setOpen(true)}>باز کردن</button>
      {open && (
        <Modal title="عنوان" onClose={() => setOpen(false)} footer={<button>ذخیره</button>}>
          <input placeholder="فیلد" />
        </Modal>
      )}
    </div>
  );
}

describe("Modal focus trap", () => {
  it("moves focus into the dialog on open and traps Tab within it", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const dialog = await screen.findByRole("dialog");
    // فوکوس اولیه باید داخل مودال باشد (نه روی دکمه‌ای که هنوز در صفحه پشت است)
    await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true));

    const closeButton = screen.getByRole("button", { name: "بستن" });
    const input = screen.getByPlaceholderText("فیلد");
    const saveButton = screen.getByRole("button", { name: "ذخیره" });

    // چرخهٔ Tab: بسته -> فیلد -> ذخیره -> (Tab بعدی برمی‌گردد به بسته)
    closeButton.focus();
    await user.tab();
    expect(input).toHaveFocus();
    await user.tab();
    expect(saveButton).toHaveFocus();
    await user.tab();
    expect(closeButton).toHaveFocus();

    // Shift+Tab از اولین عنصر باید به آخرین برود
    await user.tab({ shift: true });
    expect(saveButton).toHaveFocus();
  });

  it("restores focus to the triggering element on close", async () => {
    const user = userEvent.setup();
    render(<Harness initiallyOpen={false} />);

    const openButton = screen.getByRole("button", { name: "باز کردن" });
    await user.click(openButton);

    const closeButton = await screen.findByRole("button", { name: "بستن" });
    await user.click(closeButton);

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(openButton).toHaveFocus();
  });
});
