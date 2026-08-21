import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import React from "react";

afterEach(() => {
  cleanup();
  document.body.innerHTML = "";
});

if (!window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

if (!window.ResizeObserver) {
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  Object.defineProperty(window, "ResizeObserver", {
    writable: true,
    value: ResizeObserverMock,
  });
}

if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = vi.fn();
}

if (!Element.prototype.getAnimations) {
  Element.prototype.getAnimations = vi.fn(() => []);
}

if (!window.requestAnimationFrame) {
  window.requestAnimationFrame = (cb: FrameRequestCallback) =>
    setTimeout(() => cb(Date.now()), 0) as unknown as number;
}

if (!window.cancelAnimationFrame) {
  window.cancelAnimationFrame = (id: number) => clearTimeout(id);
}

if (!window.PointerEvent) {
  class PointerEventMock extends MouseEvent {
    constructor(type: string, params: Partial<MouseEventInit> = {}) {
      super(type, params);
    }
  }
  Object.defineProperty(window, "PointerEvent", {
    writable: true,
    value: PointerEventMock,
  });
}

vi.mock("next/link", () => {
  const ReactMock = React;
  return {
    default: ({
      href,
      children,
      ...props
    }: {
      href: string | { pathname?: string; query?: Record<string, unknown> };
      children?: React.ReactNode;
      [key: string]: unknown;
    }) => {
      const resolved =
        typeof href === "string" ? href : (href.pathname ?? "#");
      return ReactMock.createElement("a", { href: resolved, ...props }, children);
    },
  };
});