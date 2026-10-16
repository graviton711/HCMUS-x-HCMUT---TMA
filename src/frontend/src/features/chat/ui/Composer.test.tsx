// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PreferencesProvider } from "../../../shared/preferences";
import { Composer } from "./Composer";

afterEach(cleanup);

function renderComposer(busy = false, onSend = vi.fn()) {
  const view = render(
    <PreferencesProvider>
      <Composer busy={busy} onSend={onSend} />
    </PreferencesProvider>,
  );
  const box = screen.getByLabelText("Nhắn cho TourLens") as HTMLTextAreaElement;
  return { ...view, box, onSend };
}

describe("Composer focus", () => {
  it("keeps focus in the box after sending", () => {
    const { box, onSend } = renderComposer();
    fireEvent.change(box, { target: { value: "Đà Lạt" } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
    expect(onSend).toHaveBeenCalledWith("Đà Lạt");
    expect(document.activeElement).toBe(box);
  });

  it("refocuses the box when a turn finishes", () => {
    const { box, rerender } = renderComposer(false);
    box.blur();
    expect(document.activeElement).not.toBe(box);
    rerender(
      <PreferencesProvider>
        <Composer busy onSend={vi.fn()} />
      </PreferencesProvider>,
    );
    rerender(
      <PreferencesProvider>
        <Composer busy={false} onSend={vi.fn()} />
      </PreferencesProvider>,
    );
    expect(document.activeElement).toBe(box);
  });

  it("does not steal focus on mount", () => {
    const { box } = renderComposer(false);
    expect(document.activeElement).not.toBe(box);
  });
});
