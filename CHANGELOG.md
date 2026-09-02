# Changelog

## 0.2.3 - 2026-09-02
- sumdiff now follows the ecosystem-wide ZX fresh-install default in both TUI and `--gui` mode.
- Updated coordinated UI dependency floors.

## 0.2.2 - 2026-09-02

- Added the common `--gui`, `--tui` and `--ui-backend` presentation selector. `sumdiff --gui` presents the same compare/parallel editing application rather than a second GUI implementation.
- The same panes, diff model, editors, menus, focus, keyboard and mouse behavior are retained across presentations.
- Updated dependencies to sumUI 0.1.0a4, sumTUI 0.8.0a5 and optional sumGUI 0.2.0a6.

## 0.2.0 - 2026-09-01

- Promoted the compare/parallel editor to the current Sum editor baseline and now requires `sumTUI >= 0.7.0`.
- All comparison panes inherit `Alt+W` / `Ctrl+Alt+W`, selected-block `Tab` / `Shift+Tab`, configurable indentation widths, and whole-document tabs/spaces conversion from the common editor engine.
- Window remains on `Alt+I`, so `Alt+W` is never stolen from text editing.
- Preserved live-buffer integration used by `sumedit`/`sumIDE`/language launchers: unsaved host text can be compared without touching disk, and saved paths are reported back to the host for safe reload.
- `sumdiff` remains an optional separate application depending on `sumTUI`; `sumTUI` does not depend on `sumdiff`, and `sumdiff` does not depend on `sumIDE`.

## 0.1.0a3

- Adopted sumTUI 0.6.1 Alt+W / Ctrl+Alt+W deletion and block Tab/Shift+Tab indentation in every comparison pane.
- Reassigned Window to **Alt+I** and disabled automatic menu mnemonics so Alt+W remains an editor command.
- Added active-document Tabs -> N spaces and N spaces -> Tabs conversions plus a shared 2/4/8 tab-width selector.
- Updated dependency to `sumtui>=0.6.1`. Regression suite: 15 tests.

## 0.1.0a2

- Updated the dependency to `sumTUI >= 0.6.0` for integrated editor/IDE handoff.
- `SumDiffApp` accepts per-path `text_overrides`, allowing sumedit/sumIDE/sumBASIC/sumX to compare their current unsaved in-memory buffers without first writing them to disk.
- Added `saved_paths` tracking so a host editor knows exactly which source files were written from inside sumdiff and can safely reload only those buffers.
- Added regression coverage for live-buffer overrides and saved-path reporting. Regression suite: 14 tests.

## 0.1.0a1

Initial `sumdiff` alpha.

- Separate lightweight project built on `sumTUI >= 0.5.29`.
- Two-file Compare mode and N-document Parallel Documents mode.
- Default Compare for two files; default Parallel Documents for three or more.
- Editable source panes with syntax highlighting, line numbers, scrollbars and independent saving.
- Line-level diff gutter for additions, deletions and replacements.
- Diff hunks, next/previous difference navigation and two-way current-hunk transfer for two documents.
- Synchronized scrolling across any number of panes.
- Diff-based line mapping in Compare mode.
- Markdown outline/section-relative mapping in Parallel Documents mode.
- F2 Program Map / Document Outline opens on the symbol/section containing the active cursor.
- Markdown Preview plus HTML/PDF export for the active Markdown document.
- Side-by-side and grid arrangements using movable/resizable `sumTUI` workspace windows.
- Independent persistent `sumdiff` workspace geometry.
- Unsaved-change confirmation on exit.
- Core API exposes intraline spans for future character-level painting.
