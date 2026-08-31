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
from dataclasses import dataclass, field;
from difflib import SequenceMatcher;
from pathlib import Path;

from sumtui.symbols import build_symbol_map, detect_language, symbol_index_for_line;


@dataclass(frozen=True)
class DiffHunk:
    tag: str;
    a_start: int;
    a_end: int;
    b_start: int;
    b_end: int;

    @property
    def a_line(self):
        return self.a_start + 1;

    @property
    def b_line(self):
        return self.b_start + 1;

    @property
    def label(self):
        return "{} A:{}-{} B:{}-{}".format(self.tag.upper(), self.a_start + 1, max(self.a_start + 1, self.a_end), self.b_start + 1, max(self.b_start + 1, self.b_end));


@dataclass
class DiffResult:
    a_lines: list;
    b_lines: list;
    opcodes: list;
    hunks: list;
    a_marks: dict = field(default_factory=dict);
    b_marks: dict = field(default_factory=dict);

    def map_line(self, line, reverse=False):
        if reverse:
            swapped = DiffResult(self.b_lines, self.a_lines, [(tag, j1, j2, i1, i2) for tag, i1, i2, j1, j2 in self.opcodes], [], self.b_marks, self.a_marks);
            return swapped.map_line(line, reverse=False);
        source_count = max(1, len(self.a_lines));
        target_count = max(1, len(self.b_lines));
        index = max(0, min(source_count - 1, int(line) - 1));
        for tag, i1, i2, j1, j2 in self.opcodes:
            if i1 <= index < i2:
                if tag == "equal":
                    return max(1, min(target_count, j1 + (index - i1) + 1));
                source_span = max(1, i2 - i1);
                target_span = j2 - j1;
                if target_span <= 0:
                    return max(1, min(target_count, j1 + 1));
                relative = (index - i1) / max(1, source_span - 1);
                mapped = j1 + int(round(relative * max(0, target_span - 1)));
                return max(1, min(target_count, mapped + 1));
        ratio = index / max(1, source_count - 1);
        return max(1, min(target_count, int(round(ratio * max(0, target_count - 1))) + 1));

    def hunk_for_line(self, line, side="a"):
        index = max(0, int(line) - 1);
        for position, hunk in enumerate(self.hunks):
            start = hunk.a_start if side == "a" else hunk.b_start;
            end = hunk.a_end if side == "a" else hunk.b_end;
            if start <= index < max(start + 1, end):
                return position;
        return None;

    def next_hunk_index(self, line, side="a", direction=1):
        if not self.hunks:
            return None;
        current = max(0, int(line) - 1);
        starts = [hunk.a_start if side == "a" else hunk.b_start for hunk in self.hunks];
        if int(direction) >= 0:
            for index, start in enumerate(starts):
                if start > current:
                    return index;
            return 0;
        for index in range(len(starts) - 1, -1, -1):
            if starts[index] < current:
                return index;
        return len(starts) - 1;


def compare_texts(a_text, b_text, ignore_whitespace=False):
    a_lines = str(a_text or "").split("\n");
    b_lines = str(b_text or "").split("\n");
    a_compare = [line.strip() if ignore_whitespace else line for line in a_lines];
    b_compare = [line.strip() if ignore_whitespace else line for line in b_lines];
    matcher = SequenceMatcher(None, a_compare, b_compare, autojunk=False);
    opcodes = list(matcher.get_opcodes());
    hunks = [];
    a_marks = {};
    b_marks = {};
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            continue;
        hunks.append(DiffHunk(tag, i1, i2, j1, j2));
        if tag == "replace":
            for line in range(i1, i2):
                a_marks[line] = "~";
            for line in range(j1, j2):
                b_marks[line] = "~";
        elif tag == "delete":
            for line in range(i1, i2):
                a_marks[line] = "-";
        elif tag == "insert":
            for line in range(j1, j2):
                b_marks[line] = "+";
    return DiffResult(a_lines, b_lines, opcodes, hunks, a_marks, b_marks);


def intraline_spans(a_line, b_line):
    matcher = SequenceMatcher(None, str(a_line), str(b_line), autojunk=False);
    left = [];
    right = [];
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue;
        if i1 != i2:
            left.append((i1, i2, tag));
        if j1 != j2:
            right.append((j1, j2, tag));
    return left, right;


@dataclass
class DocumentState:
    path: object;
    text: str;
    language: str = "auto";

    def __post_init__(self):
        self.path = Path(self.path).expanduser() if self.path is not None else None;
        filename = self.path.name if self.path is not None else None;
        self.language = detect_language(filename=filename, language=self.language);

    @property
    def name(self):
        return self.path.name if self.path is not None else "Untitled";

    @property
    def lines(self):
        return self.text.split("\n");

    def symbols(self):
        filename = self.path.name if self.path is not None else None;
        return build_symbol_map(self.text, language=self.language, filename=filename);


class ComparisonSession:
    def __init__(self, documents, mode="compare", ignore_whitespace=False):
        self.documents = list(documents or []);
        if len(self.documents) < 2:
            raise ValueError("sumdiff requires at least two documents");
        self.mode = str(mode or "compare").lower();
        if self.mode not in ("compare", "parallel"):
            raise ValueError("mode must be compare or parallel");
        self.ignore_whitespace = bool(ignore_whitespace);
        self._diff_cache = {};

    def update_text(self, index, text):
        self.documents[int(index)].text = str(text);
        self._diff_cache = {};
        return True;

    def diff(self, source_index, target_index):
        source_index = int(source_index);
        target_index = int(target_index);
        key = (source_index, target_index, self.ignore_whitespace);
        if key not in self._diff_cache:
            source = self.documents[source_index];
            target = self.documents[target_index];
            self._diff_cache[key] = compare_texts(source.text, target.text, ignore_whitespace=self.ignore_whitespace);
        return self._diff_cache[key];

    def set_ignore_whitespace(self, enabled):
        self.ignore_whitespace = bool(enabled);
        self._diff_cache = {};
        return self.ignore_whitespace;

    def map_line(self, source_index, target_index, line):
        source_index = int(source_index);
        target_index = int(target_index);
        if source_index == target_index:
            return max(1, int(line));
        source = self.documents[source_index];
        target = self.documents[target_index];
        if self.mode == "compare":
            return self.diff(source_index, target_index).map_line(line);
        if source.language == "markdown" and target.language == "markdown":
            return self._map_markdown_line(source, target, line);
        return self._map_ratio_line(source, target, line);

    @staticmethod
    def _map_ratio_line(source, target, line):
        source_count = max(1, len(source.lines));
        target_count = max(1, len(target.lines));
        index = max(0, min(source_count - 1, int(line) - 1));
        ratio = index / max(1, source_count - 1);
        return max(1, min(target_count, int(round(ratio * max(0, target_count - 1))) + 1));

    @staticmethod
    def _map_markdown_line(source, target, line):
        source_symbols = source.symbols();
        target_symbols = target.symbols();
        if not source_symbols or not target_symbols:
            return ComparisonSession._map_ratio_line(source, target, line);
        source_index = symbol_index_for_line(source_symbols, line);
        target_index = min(source_index, len(target_symbols) - 1);
        source_start = int(source_symbols[source_index].line);
        source_end = int(source_symbols[source_index + 1].line) - 1 if source_index + 1 < len(source_symbols) else len(source.lines);
        target_start = int(target_symbols[target_index].line);
        target_end = int(target_symbols[target_index + 1].line) - 1 if target_index + 1 < len(target_symbols) else len(target.lines);
        source_span = max(1, source_end - source_start);
        relative = max(0.0, min(1.0, (int(line) - source_start) / source_span));
        target_line = target_start + int(round(relative * max(0, target_end - target_start)));
        return max(1, min(len(target.lines), target_line));

    def current_hunk(self, source_index, target_index, line):
        result = self.diff(source_index, target_index);
        return result.hunk_for_line(line, side="a");

    def next_difference(self, source_index, target_index, line, direction=1):
        result = self.diff(source_index, target_index);
        index = result.next_hunk_index(line, side="a", direction=direction);
        if index is None:
            return None;
        return result.hunks[index].a_start + 1, result.map_line(result.hunks[index].a_start + 1), index;

    def apply_hunk(self, source_index, target_index, hunk_index):
        source_index = int(source_index);
        target_index = int(target_index);
        result = self.diff(source_index, target_index);
        if hunk_index is None or not (0 <= int(hunk_index) < len(result.hunks)):
            return False;
        hunk = result.hunks[int(hunk_index)];
        source_lines = self.documents[source_index].text.split("\n");
        target_lines = self.documents[target_index].text.split("\n");
        replacement = source_lines[hunk.a_start:hunk.a_end];
        target_lines[hunk.b_start:hunk.b_end] = replacement;
        self.update_text(target_index, "\n".join(target_lines));
        return True;
