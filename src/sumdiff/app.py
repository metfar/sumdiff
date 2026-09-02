#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#pylint:disable=W0301
#  
#  Copyright 2018- William Martinez Bas <metfar@gmail.com>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#
import math;
import os;
from pathlib import Path;

from rich.segment import Segment;
from rich.text import Text;

from sumtui import Application, Button, Dialog, FileDialog, HBox, Label, ListView, MarkdownView, MarkdownViewPane, Menu, MenuBar, MenuDesktop, MenuItem, ScrollBar, Separator, StatusBar, TextEditor, TextInput, VBox, Widget, Workspace, WorkspaceWindow;
from sumtui.document import TextDocument;
from sumtui.markdown_export import export_html, export_pdf;
from sumtui.symbols import build_symbol_map, symbol_index_for_line;

from .core import ComparisonSession, DocumentState;


def default_config_dir():
    base = os.environ.get("XDG_CONFIG_HOME");
    if base:
        return Path(base).expanduser() / "sumdiff";
    return Path("~/.config/sumdiff").expanduser();


class DiffMarkerBar(Widget):
    def __init__(self, editor, marks=None, theme=None):
        super().__init__(theme=theme);
        self.editor = editor;
        self.marks = dict(marks or {});

    def set_marks(self, marks):
        self.marks = dict(marks or {});
        return self;

    def __rich_console__(self, console, options):
        height = max(1, int(options.height or options.max_height or console.height));
        output = Text();
        for visible in range(height):
            line_index = self.editor.y_offset + visible;
            mark = self.marks.get(line_index, " ");
            if mark == "+":
                style = "bold {}".format(self.theme.color("button"));
            elif mark == "-":
                style = "bold {}".format(self.theme.color("error"));
            elif mark == "~":
                style = "bold {}".format(self.theme.color("title"));
            else:
                style = self.theme.style("muted");
            output.append(mark, style=style);
            output.append(" ");
            if visible + 1 < height:
                output.append("\n");
        yield output;


class EditorVScroll(ScrollBar):
    def __init__(self, editor, **kwargs):
        self.editor = editor;
        kwargs.setdefault("on_change", self._changed);
        super().__init__(orientation="vertical", **kwargs);

    def _changed(self, _scrollbar, value):
        self.editor.y_offset = max(0, int(value));
        self.editor._clamp_viewport();
        return True;

    def __rich_console__(self, console, options):
        self.page = max(1, self.editor.page_height);
        total = self.editor.visual_line_count(max(1, self.editor.page_width - self.editor._gutter_width()));
        self.maximum = max(0, total - self.page);
        self.value = max(0, min(self.maximum, self.editor.y_offset));
        yield from super().__rich_console__(console, options);


class EditorHScroll(ScrollBar):
    def __init__(self, editor, **kwargs):
        self.editor = editor;
        kwargs.setdefault("on_change", self._changed);
        super().__init__(orientation="horizontal", **kwargs);

    def _changed(self, _scrollbar, value):
        if self.editor.line_wrapping == 0:
            self.editor.x_offset = max(0, int(value));
            self.editor._clamp_viewport();
        return True;

    def __rich_console__(self, console, options):
        gutter = self.editor._gutter_width();
        self.page = max(1, self.editor.page_width - gutter);
        longest = max([len(line) for line in self.editor.lines] or [0]);
        self.maximum = max(0, longest - self.page);
        self.value = max(0, min(self.maximum, self.editor.x_offset));
        yield from super().__rich_console__(console, options);


class DocumentPane:
    def __init__(self, app, document, state, index):
        self.app = app;
        self.document = document;
        self.state = state;
        self.index = int(index);
        self.editor = TextEditor(document.text, line_numbers=True, command_shortcuts=True, syntax_highlighting=True, syntax_language="auto", syntax_filename=state.name, line_wrapping=0, on_change=self._changed, on_cursor=self._cursor);
        self.marker = DiffMarkerBar(self.editor);
        self.vscroll = EditorVScroll(self.editor);
        self.hscroll = EditorHScroll(self.editor);
        self.widget = VBox(HBox(self.marker, self.editor, self.vscroll, sizes=[2, None, 1]), self.hscroll, sizes=[None, 1]);
        self.window = None;

    def _changed(self, _editor):
        self.state.text = self.editor.text;
        self.document.text = self.editor.text;
        self.app.session.update_text(self.index, self.editor.text);
        self.app.refresh_diff_marks();
        self.app.update_status();
        return True;

    def _cursor(self, _editor):
        self.app.update_status();
        return True;

    def save(self):
        if self.document.path is None:
            raise ValueError("No file path specified");
        self.document.save(text=self.editor.text);
        self.state.path = self.document.path;
        self.state.text = self.editor.text;
        self.editor.mark_saved();
        return self.document.path;


class SumDiffApp:
    def __init__(self, paths, mode="compare", theme=None, ignore_whitespace=False, text_overrides=None):
        self.paths = [Path(path).expanduser().resolve() for path in paths];
        if len(self.paths) < 2:
            raise ValueError("sumdiff requires at least two files");
        self.app = Application(title="sumdiff", theme=theme or "ZX", capture_control_keys=True, mouse=True);
        self.documents = [TextDocument.load(path) for path in self.paths];
        overrides = {Path(path).expanduser().resolve(): str(text) for path, text in dict(text_overrides or {}).items()};
        for document in self.documents:
            key = Path(document.path).expanduser().resolve();
            if key in overrides:
                document.text = overrides[key];
        self.saved_paths = set();
        states = [DocumentState(document.path, document.text) for document in self.documents];
        self.session = ComparisonSession(states, mode=mode, ignore_whitespace=ignore_whitespace);
        self.sync_scrolling = True;
        self.panes = [];
        self.status = StatusBar("Ready");
        self.workspace = Workspace(layout_id="sumdiff", layout_path=default_config_dir() / "workspaces.json", viewport_width=self.app.width, viewport_height=max(5, self.app.height - 2));
        for index, (document, state) in enumerate(zip(self.documents, states)):
            pane = DocumentPane(self, document, state, index);
            self.panes.append(pane);
            pane.window = WorkspaceWindow(pane.widget, title=self._window_title(pane), name="document-{}".format(index + 1), left=0, top=0, width=40, height=20, persistent=True, closable=True, content_style="viewer");
            self.workspace.add_window(pane.window, activate=index == 0);
        loaded = self.workspace.load_layout();
        if not loaded:
            self.arrange_side_by_side(clear_saved=False);
        self.workspace.on_activate = lambda _window: self.update_status();
        self.menu = self._build_menu();
        self.root = MenuDesktop(self.menu, VBox(self.workspace, self.status, sizes=[None, 1]));
        self.app.set_root(self.root);
        self._bind_keys();
        self._last_source_scroll = None;
        self.app.add_idle(self._idle_sync);
        self.refresh_diff_marks();
        self.update_status();

    def _window_title(self, pane):
        mode = str(pane.state.language or "text").upper();
        dirty = " *" if pane.editor.modified else "";
        return "{} [{}]{}".format(pane.state.name, mode, dirty);

    def active_index(self):
        active = self.workspace.active_window;
        for index, pane in enumerate(self.panes):
            if pane.window is active:
                return index;
        return 0;

    def active_pane(self):
        return self.panes[self.active_index()];

    def _peer_index(self):
        active = self.active_index();
        if len(self.panes) == 2:
            return 1 - active;
        return 1 if active == 0 else 0;

    def update_status(self, message=None):
        pane = self.active_pane();
        pane.window.title = self._window_title(pane);
        if message is None:
            message = "{} | {} | line {}:{} | {} docs | sync {}".format(self.session.mode.upper(), pane.state.name, pane.editor.cursor_line, pane.editor.cursor_column, len(self.panes), "ON" if self.sync_scrolling else "OFF");
        self.status.set(message);
        return True;

    def refresh_diff_marks(self):
        for pane in self.panes:
            pane.marker.set_marks({});
        if self.session.mode != "compare":
            return True;
        if len(self.panes) == 2:
            result = self.session.diff(0, 1);
            self.panes[0].marker.set_marks(result.a_marks);
            self.panes[1].marker.set_marks(result.b_marks);
            return True;
        reference_marks = {};
        for index in range(1, len(self.panes)):
            result = self.session.diff(0, index);
            reference_marks.update(result.a_marks);
            self.panes[index].marker.set_marks(result.b_marks);
        self.panes[0].marker.set_marks(reference_marks);
        return True;

    def _idle_sync(self):
        if not self.sync_scrolling or len(self.panes) < 2:
            return False;
        source_index = self.active_index();
        source = self.panes[source_index].editor;
        marker = (source_index, source.y_offset, source.row);
        if marker == self._last_source_scroll:
            return False;
        self._last_source_scroll = marker;
        source_line = source.row + 1;
        visual_row = max(0, source.row - source.y_offset);
        changed = False;
        for target_index, pane in enumerate(self.panes):
            if target_index == source_index:
                continue;
            mapped = self.session.map_line(source_index, target_index, source_line);
            target_offset = max(0, mapped - 1 - visual_row);
            if pane.editor.y_offset != target_offset:
                pane.editor.y_offset = target_offset;
                pane.editor._clamp_viewport();
                changed = True;
            if pane.editor.x_offset != source.x_offset:
                pane.editor.x_offset = max(0, source.x_offset);
                pane.editor._clamp_viewport();
                changed = True;
        return changed;

    def arrange_side_by_side(self, clear_saved=True):
        count = max(1, len(self.panes));
        width = max(12, int(self.workspace._last_width or self.app.width));
        height = max(5, int(self.workspace._last_height or max(5, self.app.height - 2)));
        base = max(12, width // count);
        left = 0;
        for index, pane in enumerate(self.panes):
            pane_width = width - left if index == count - 1 else base;
            pane.window.maximized = False;
            pane.window.set_position(left=left, top=0);
            pane.window.set_size(width=max(12, pane_width), height=height);
            left += base;
        if clear_saved:
            self.workspace.clear_saved_layout();
        self.update_status("Arranged side by side");
        return True;

    def arrange_grid(self):
        count = max(1, len(self.panes));
        columns = max(1, int(math.ceil(math.sqrt(count))));
        rows = max(1, int(math.ceil(count / columns)));
        width = max(12, int(self.workspace._last_width or self.app.width));
        height = max(5, int(self.workspace._last_height or max(5, self.app.height - 2)));
        cell_width = max(12, width // columns);
        cell_height = max(5, height // rows);
        for index, pane in enumerate(self.panes):
            row = index // columns;
            column = index % columns;
            left = column * cell_width;
            top = row * cell_height;
            pane.window.maximized = False;
            pane.window.set_position(left=left, top=top);
            pane.window.set_size(width=width - left if column == columns - 1 else cell_width, height=height - top if row == rows - 1 else cell_height);
        self.workspace.clear_saved_layout();
        self.update_status("Arranged as grid");
        return True;

    def reset_layout(self):
        return self.arrange_side_by_side(clear_saved=True);

    def switch_window(self):
        return self.workspace.next_window();

    def begin_move(self):
        return self.workspace.begin_move_active();

    def begin_resize(self):
        return self.workspace.begin_resize_active();

    def toggle_maximize(self):
        return self.workspace.toggle_maximize_active();

    def toggle_sync(self):
        self.sync_scrolling = not self.sync_scrolling;
        self._last_source_scroll = None;
        self.update_status();
        return True;

    def set_mode(self, mode):
        self.session.mode = str(mode).lower();
        self._last_source_scroll = None;
        self.refresh_diff_marks();
        self.update_status("Mode: {}".format(self.session.mode));
        return True;

    def toggle_ignore_whitespace(self):
        self.session.set_ignore_whitespace(not self.session.ignore_whitespace);
        self.refresh_diff_marks();
        self.update_status("Ignore whitespace: {}".format("ON" if self.session.ignore_whitespace else "OFF"));
        return True;

    def save_current(self):
        pane = self.active_pane();
        try:
            target = pane.save();
            self.saved_paths.add(Path(target).expanduser().resolve());
            self.update_status("Saved {}".format(target));
            return True;
        except Exception as exc:
            self.update_status("Save error: {}".format(exc));
            return False;

    def save_all(self):
        for pane in self.panes:
            if pane.editor.modified:
                try:
                    target = pane.save();
                    self.saved_paths.add(Path(target).expanduser().resolve());
                except Exception as exc:
                    self.update_status("Save error: {}".format(exc));
                    return False;
        self.update_status("All documents saved");
        return True;

    def _dirty_panes(self):
        return [pane for pane in self.panes if pane.editor.modified];

    def quit(self):
        dirty = self._dirty_panes();
        if not dirty:
            self.workspace.save_layout();
            self.app.stop();
            return True;
        names = ", ".join(pane.state.name for pane in dirty);
        def cancel(*_args):
            self.app.pop_modal();
            self.app.focus.set(self.active_pane().editor);
            self.app.invalidate();
            return True;
        def forget(*_args):
            self.app.pop_modal();
            self.workspace.save_layout();
            self.app.stop();
            return True;
        def save_then(*_args):
            self.app.pop_modal();
            if self.save_all():
                self.workspace.save_layout();
                self.app.stop();
            return True;
        body = VBox(Label("Unsaved: {}".format(names)), HBox(Button("SAVE_AND_EXIT", on_press=save_then, default=True), Button("FORGET_AND_EXIT", on_press=forget), Button("CANCEL", on_press=cancel), ratios=[1, 1, 1]), sizes=[1, None]);
        self.app.push_modal(Dialog(body, title="Unsaved changes", width=78, height=8, on_cancel=cancel, shadow=True));
        self.app.invalidate();
        return True;

    def symbol_map_dialog(self):
        pane = self.active_pane();
        filename = pane.state.path.name if pane.state.path is not None else None;
        symbols = build_symbol_map(pane.editor.text, language=pane.state.language, filename=filename);
        markdown = pane.state.language == "markdown";
        listing = ListView([(item.label, item) for item in symbols], title="Titles / Sections / Subsections" if markdown else "Functions / Classes / Main");
        listing.select(symbol_index_for_line(symbols, pane.editor.cursor_line));
        def close(*_args):
            self.app.pop_modal();
            self.app.focus.set(pane.editor);
            self.app.invalidate();
            return True;
        def activate(*_args):
            item = listing.current_value;
            if item is None:
                return False;
            close();
            pane.editor.goto_line(item.line, item.column);
            self.update_status("{} {} — line {}".format(item.kind.upper(), item.name, item.line));
            return True;
        listing.on_activate = activate;
        body = VBox(listing, HBox(Button("Go", on_press=activate, default=True), Button("Cancel", on_press=close), ratios=[1, 1]), sizes=[None, None]);
        self.app.push_modal(Dialog(body, title="Document outline" if markdown else "Program map", width=72, height=min(26, max(10, len(symbols) + 7)), on_cancel=close, shadow=True));
        self.app.focus.set(listing);
        self.app.invalidate();
        return True;

    def next_difference(self, direction=1):
        if self.session.mode != "compare":
            return self.update_status("Differences are available in Compare mode");
        source_index = self.active_index();
        target_index = self._peer_index();
        pane = self.panes[source_index];
        found = self.session.next_difference(source_index, target_index, pane.editor.cursor_line, direction=direction);
        if found is None:
            return self.update_status("No differences");
        source_line, target_line, hunk_index = found;
        pane.editor.goto_line(source_line);
        target = self.panes[target_index].editor;
        target.y_offset = max(0, target_line - 1);
        target._clamp_viewport();
        self.update_status("Difference {} at line {}".format(hunk_index + 1, source_line));
        return True;

    @staticmethod
    def _line_start_offset(lines, index):
        index = max(0, int(index));
        if index <= 0:
            return 0;
        if index >= len(lines):
            return len("\n".join(lines));
        return sum(len(line) + 1 for line in lines[:index]);

    def _apply_hunk(self, source_index, target_index):
        source = self.panes[source_index];
        target = self.panes[target_index];
        result = self.session.diff(source_index, target_index);
        hunk_index = result.hunk_for_line(source.editor.cursor_line, side="a");
        if hunk_index is None:
            return self.update_status("Cursor is not on a difference");
        hunk = result.hunks[hunk_index];
        source_lines = source.editor.text.split("\n");
        target_lines = target.editor.text.split("\n");
        start = self._line_start_offset(target_lines, hunk.b_start);
        end = self._line_start_offset(target_lines, hunk.b_end);
        replacement = "\n".join(source_lines[hunk.a_start:hunk.a_end]);
        if replacement and hunk.b_end < len(target_lines):
            replacement += "\n";
        target.editor.replace_offsets(start, end, replacement, kind="apply_hunk");
        self.session.update_text(target_index, target.editor.text);
        self.refresh_diff_marks();
        self.update_status("Applied difference {}: {} -> {}".format(hunk_index + 1, source.state.name, target.state.name));
        return True;

    def apply_active_to_other(self):
        if self.session.mode != "compare" or len(self.panes) != 2:
            return self.update_status("Hunk transfer currently requires two documents in Compare mode");
        source_index = self.active_index();
        return self._apply_hunk(source_index, 1 - source_index);

    def apply_other_to_active(self):
        if self.session.mode != "compare" or len(self.panes) != 2:
            return self.update_status("Hunk transfer currently requires two documents in Compare mode");
        target_index = self.active_index();
        source_index = 1 - target_index;
        source = self.panes[source_index];
        result = self.session.diff(source_index, target_index);
        mapped = result.map_line(self.panes[target_index].editor.cursor_line, reverse=True);
        source.editor.goto_line(mapped);
        return self._apply_hunk(source_index, target_index);

    def markdown_preview(self):
        pane = self.active_pane();
        if pane.state.language != "markdown":
            return self.update_status("Markdown preview is available for Markdown documents");
        view = MarkdownView(pane.editor.text, wrap=False, theme=self.app.theme);
        preview = MarkdownViewPane(view=view, theme=self.app.theme);
        def close(*_args):
            self.app.pop_modal();
            self.app.focus.set(pane.editor);
            self.app.invalidate();
            return True;
        def do_export(kind):
            suffix = ".pdf" if kind == "pdf" else ".html";
            entry = TextInput(str(pane.state.path.with_suffix(suffix)));
            def back(*_args):
                self.app.pop_modal();
                self.app.focus.set(view);
                self.app.invalidate();
                return True;
            def accepted(*_args):
                target = Path(entry.value).expanduser();
                try:
                    if kind == "pdf":
                        export_pdf(pane.editor.text, target, title=pane.state.path.stem, base_url=pane.state.path.parent);
                    else:
                        export_html(pane.editor.text, target, title=pane.state.path.stem);
                    back();
                    self.update_status("Exported {}".format(target));
                    return True;
                except Exception as exc:
                    back();
                    self.update_status("Export error: {}".format(exc));
                    return False;
            body = VBox(entry, HBox(Button("Export", on_press=accepted, default=True), Button("Cancel", on_press=back), ratios=[1, 1]), sizes=[1, None]);
            self.app.push_modal(Dialog(body, title="Export Markdown as {}".format(suffix[1:].upper()), width=76, height=7, on_cancel=back, shadow=True));
            self.app.focus.set(entry);
            return True;
        buttons = HBox(Button("Export HTML", on_press=lambda *_args: do_export("html")), Button("Export PDF", on_press=lambda *_args: do_export("pdf")), Button("Close", on_press=close, default=True), ratios=[1, 1, 1]);
        self.app.push_modal(Dialog(VBox(preview, buttons, sizes=[None, None]), title="Markdown Preview — {}".format(pane.state.name), width=100, height=30, on_cancel=close, shadow=True));
        self.app.focus.set(view);
        self.app.invalidate();
        return True;

    def _build_menu(self):
        compare_menu = Menu("Compare", [
            MenuItem("Compare mode", lambda: self.set_mode("compare"), radio=lambda: self.session.mode == "compare"),
            MenuItem("Parallel Documents", lambda: self.set_mode("parallel"), radio=lambda: self.session.mode == "parallel"),
            Separator(),
            MenuItem("Synchronize scrolling", self.toggle_sync, checked=lambda: self.sync_scrolling),
            MenuItem("Ignore whitespace", self.toggle_ignore_whitespace, checked=lambda: self.session.ignore_whitespace),
            Separator(),
            MenuItem("Apply active -> other", self.apply_active_to_other),
            MenuItem("Apply other -> active", self.apply_other_to_active),
        ]);
        window_items = [
            MenuItem("Next Window", self.switch_window, "F6"),
            MenuItem("Maximize / Restore", self.toggle_maximize, "F11"),
            MenuItem("Move...", self.begin_move, "Alt+M"),
            MenuItem("Resize...", self.begin_resize, "Alt+Z"),
            Separator(),
            MenuItem("Arrange Side by Side", self.arrange_side_by_side),
            MenuItem("Arrange Grid", self.arrange_grid),
            MenuItem("Reset Comparison Layout", self.reset_layout),
        ];
        return MenuBar([
            Menu("File", [MenuItem("Save current", self.save_current, "Ctrl+S"), MenuItem("Save all", self.save_all), Separator(), MenuItem("Exit", self.quit, "Ctrl+Q")]),
            Menu("Edit", [
                MenuItem("Undo", lambda: self.active_pane().editor.undo(), "Ctrl+Z"),
                MenuItem("Redo", lambda: self.active_pane().editor.redo(), "Ctrl+Y"),
                Separator(),
                MenuItem("Cut", lambda: self.active_pane().editor.cut(), "Ctrl+X"),
                MenuItem("Copy", lambda: self.active_pane().editor.copy(), "Ctrl+C"),
                MenuItem("Paste", lambda: self.active_pane().editor.paste(), "Ctrl+V"),
                Separator(),
                MenuItem("Tabs -> {} spaces".format(self.active_pane().editor.tab_size), self.tabs_to_spaces),
                MenuItem("{} spaces -> Tabs".format(self.active_pane().editor.tab_size), self.spaces_to_tabs),
                MenuItem("Tab width", submenu=Menu("Tab width", [
                    MenuItem("2", lambda: self.set_tab_width(2), radio=lambda: self.active_pane().editor.tab_size == 2),
                    MenuItem("4", lambda: self.set_tab_width(4), radio=lambda: self.active_pane().editor.tab_size == 4),
                    MenuItem("8", lambda: self.set_tab_width(8), radio=lambda: self.active_pane().editor.tab_size == 8),
                ])),
            ]),
            Menu("Navigate", [MenuItem("Program Map / Outline...", self.symbol_map_dialog, "F2"), Separator(), MenuItem("Next difference", lambda: self.next_difference(1), "F7"), MenuItem("Previous difference", lambda: self.next_difference(-1), "Shift+F7")]),
            compare_menu,
            Menu("View", [MenuItem("Markdown Preview...", self.markdown_preview), Separator(), MenuItem("Side by Side", self.arrange_side_by_side), MenuItem("Grid", self.arrange_grid)]),
            Menu("Window", window_items),
            Menu("Help", [MenuItem("About", self.about)]),
        ], mnemonics=False);

    def _open_menu(self, index):
        return self.menu.open(index);

    def _refresh_menu(self):
        rebuilt = self._build_menu();
        self.menu.menus = rebuilt.menus;
        self.app.invalidate();
        return True;

    def set_tab_width(self, width):
        width = max(1, int(width));
        for pane in self.panes:
            pane.editor.tab_size = width;
        self.update_status("Tab width {}".format(width));
        return self._refresh_menu();

    def tabs_to_spaces(self):
        editor = self.active_pane().editor;
        changed = editor.tabs_to_spaces();
        if changed:
            self.update_status("Converted tabs to {} spaces in {}".format(editor.tab_size, self.active_pane().state.name));
        return changed;

    def spaces_to_tabs(self):
        editor = self.active_pane().editor;
        changed = editor.spaces_to_tabs();
        if changed:
            self.update_status("Converted groups of {} spaces to tabs in {}".format(editor.tab_size, self.active_pane().state.name));
        return changed;

    def _bind_keys(self):
        bindings = {
            "ctrl+s": self.save_current,
            "ctrl+q": self.quit,
            "f2": self.symbol_map_dialog,
            "f6": self.switch_window,
            "f7": lambda: self.next_difference(1),
            "shift+f7": lambda: self.next_difference(-1),
            "f8": self.apply_active_to_other,
            "f11": self.toggle_maximize,
            "alt+m": self.begin_move,
            "alt+z": self.begin_resize,
            "alt+f": lambda: self._open_menu(0),
            "alt+e": lambda: self._open_menu(1),
            "alt+n": lambda: self._open_menu(2),
            "alt+c": lambda: self._open_menu(3),
            "alt+v": lambda: self._open_menu(4),
            "alt+i": lambda: self._open_menu(5),
            "alt+h": lambda: self._open_menu(6),
        };
        for key, callback in bindings.items():
            self.app.bind(key, callback);
        return True;

    def about(self):
        pane = self.active_pane();
        def close(*_args):
            self.app.pop_modal();
            self.app.focus.set(pane.editor);
            self.app.invalidate();
            return True;
        text = "sumdiff 0.2.0\nMulti-document Compare / Merge / Parallel Documents\nBuilt on sumTUI.";
        self.app.push_modal(Dialog(VBox(Label(text), Button("Close", on_press=close, default=True)), title="About sumdiff", width=62, height=9, on_cancel=close, shadow=True));
        self.app.invalidate();
        return True;

    def run(self, backend="tui"):
        self.app.focus.set(self.active_pane().editor);
        result = self.app.run(backend=backend);
        self.workspace.save_layout();
        return result;
