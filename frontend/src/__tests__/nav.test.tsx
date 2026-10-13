import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NavBar, systemFacts } from "../components/NavBar";
import { getActivity, resetActivity, setActivity } from "../lib/activity";
import { plural } from "../lib/format";
import type { Health } from "../types";
import { Logo } from "../ui/Logo";

const health = (over: Partial<Health> = {}): Health => ({
  version: "1.0.0",
  allow_edit: true,
  max_upload_mb: 25,
  ocr: { available: true, version: "tesseract 5.4.0.20240606", languages: ["eng", "osd", "rus"] },
  doc_types: [
    { id: "a", title: "A", fields: 7 },
    { id: "b", title: "B", fields: 7 },
    { id: "c", title: "C", fields: 7 },
  ],
  regulation: { name: "polozhenie.md", clauses: 25 },
  llm: { backend: "none" },
  ...over,
});

const noop = () => {};
const props = { route: "check" as const, onRoute: noop, health: health(), theme: "system" as const, onThemeSet: noop, onPalette: noop, onHelp: noop };
const openMenu = () => userEvent.click(screen.getByRole("button", { name: /^Меню/ }));

afterEach(() => resetActivity());

describe("plural", () => {
  it("declines Russian nouns by number", () => {
    const f: [string, string, string] = ["пункт", "пункта", "пунктов"];
    expect([1, 2, 5, 11, 12, 21, 25, 101, 112].map((n) => plural(n, f))).toEqual(["пункт", "пункта", "пунктов", "пунктов", "пунктов", "пункт", "пунктов", "пункт", "пунктов"]);
  });
});

describe("systemFacts", () => {
  it("lists OCR, regulation size and document types", () => {
    expect(systemFacts(health())).toEqual(["Tesseract 5.4.0 · eng+rus", "Положение: 25 пунктов", "3 типа документов", "Без внешних API"]);
  });
  it("reports an unavailable OCR and works before the server answers", () => {
    expect(systemFacts(health({ ocr: { available: false } }))[0]).toBe("OCR недоступен");
    expect(systemFacts(null)).toEqual(["Без внешних API"]);
  });
});

describe("activity store", () => {
  it("publishes changes once and resets", () => {
    setActivity({ busy: true, fraction: 0.4, label: "Чтение текста" });
    expect(getActivity()).toMatchObject({ busy: true, fraction: 0.4 });
    resetActivity();
    expect(getActivity().busy).toBe(false);
  });
});

describe("NavBar", () => {
  it("shows the three sections without counters and marks the current one", () => {
    render(<NavBar {...props} route="rules" />);
    const nav = screen.getByRole("navigation", { name: "Разделы" });
    expect(within(nav).getAllByRole("link")).toHaveLength(3);
    expect(within(nav).getByRole("link", { name: /Положение/ })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: /Стол/ })).not.toHaveAttribute("aria-current");
    expect(within(nav).queryByText("25")).not.toBeInTheDocument();
  });

  it("keeps the panel light: search and one menu instead of a row of buttons", () => {
    render(<NavBar {...props} />);
    const tools = document.querySelector(".tools")!;
    const visible = within(tools as HTMLElement).getAllByRole("button").filter((b) => !b.closest(".menu-panel")); // содержимое закрытого меню скрыто (inert)
    expect(visible).toHaveLength(2);
    expect(document.querySelector(".menu-panel")).toHaveAttribute("inert");
    expect(screen.getByRole("button", { name: /^Меню/ })).toHaveAttribute("aria-expanded", "false");
  });

  it("changes the theme from the menu", async () => {
    const onThemeSet = vi.fn();
    render(<NavBar {...props} onThemeSet={onThemeSet} />);
    await openMenu();
    const group = screen.getByRole("radiogroup", { name: "Тема оформления" });
    expect(within(group).getByRole("radio", { name: /Как в системе/ })).toHaveAttribute("aria-checked", "true");
    await userEvent.click(within(group).getByRole("radio", { name: /Тёмная/ }));
    expect(onThemeSet).toHaveBeenCalledWith("dark");
  });

  it("opens the command palette and the help", async () => {
    const onPalette = vi.fn();
    const onHelp = vi.fn();
    render(<NavBar {...props} onPalette={onPalette} onHelp={onHelp} />);
    await userEvent.click(screen.getByRole("button", { name: /Поиск и команды/ }));
    await openMenu();
    await userEvent.click(screen.getByRole("button", { name: /Горячие клавиши/ }));
    expect(onPalette).toHaveBeenCalledTimes(1);
    expect(onHelp).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: /^Меню/ })).toHaveAttribute("aria-expanded", "false"); // после действия меню закрывается
  });

  it("closes the menu with Escape and leads staff to the admin page", async () => {
    render(<NavBar {...props} />);
    await openMenu();
    expect(screen.getByRole("link", { name: /Вход для сотрудников/ })).toHaveAttribute("href", "/admin");
    await userEvent.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: /^Меню/ })).toHaveAttribute("aria-expanded", "false");
  });

  it("shows the live progress of a running check in the panel", () => {
    render(<NavBar {...props} />);
    expect(screen.queryByText("Чтение текста")).not.toBeInTheDocument();
    act(() => setActivity({ busy: true, fraction: 0.42, label: "Чтение текста" }));
    expect(screen.getByText("Чтение текста")).toBeInTheDocument();
    expect(screen.getByText("42%")).toBeInTheDocument();
    expect(document.querySelector(".nav")).toHaveAttribute("data-busy", "true");
  });

  it("shows the system state on the menu button and the details inside", async () => {
    render(<NavBar {...props} />);
    expect(screen.getByRole("button", { name: /система готова/ })).toBeInTheDocument();
    await openMenu();
    const menu = screen.getByRole("group", { name: "Меню" });
    expect(menu).toHaveTextContent("Готов к работе");
    expect(menu).toHaveTextContent("Положение: 25 пунктов");
    expect(menu).toHaveTextContent("Языковая модель: не используется");
  });

  it("warns when OCR is unavailable", () => {
    render(<NavBar {...props} health={health({ ocr: { available: false, reason: "tesseract не найден" } })} />);
    expect(screen.getByRole("button", { name: /OCR недоступен/ })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Меню", hidden: true })).toHaveTextContent("OCR недоступен: tesseract не найден");
  });
});

describe("Logo", () => {
  it("renders the seal, the sheet and the check", () => {
    const { container } = render(<Logo size={48} />);
    expect(container.querySelector(".logo-teeth")).not.toBeNull();
    expect(container.querySelector(".logo-sheet")).not.toBeNull();
    expect(container.querySelector(".logo-check")).not.toBeNull();
    expect(container.querySelector("svg")).toHaveAttribute("width", "48");
  });
  it("can be drawn without the tile background", () => {
    const { container } = render(<Logo bare />);
    expect(container.querySelectorAll("rect")).toHaveLength(0);
  });
});
