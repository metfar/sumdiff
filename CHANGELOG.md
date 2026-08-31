# Changelog

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
