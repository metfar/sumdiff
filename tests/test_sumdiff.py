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
import tempfile;
import unittest;
from pathlib import Path;

from sumdiff.app import SumDiffApp;
from sumdiff.core import ComparisonSession, DocumentState, compare_texts, intraline_spans;
from sumdiff.__main__ import build_parser, choose_mode;


class DiffCoreTests(unittest.TestCase):
    def test_compare_marks_and_hunks(self):
        result = compare_texts("one\ntwo\nthree", "one\nTWO\nthree\nfour");
        self.assertEqual(len(result.hunks), 2);
        self.assertEqual(result.a_marks[1], "~");
        self.assertEqual(result.b_marks[1], "~");
        self.assertEqual(result.b_marks[3], "+");

    def test_line_mapping_tracks_insertions(self):
        result = compare_texts("a\nb\nc\nd", "a\nx\nb\nc\nd");
        self.assertEqual(result.map_line(1), 1);
        self.assertEqual(result.map_line(2), 3);
        self.assertEqual(result.map_line(4), 5);

    def test_intraline_spans(self):
        left, right = intraline_spans("result = total", "result = sum");
        self.assertTrue(left);
        self.assertTrue(right);

    def test_markdown_parallel_mapping_uses_section_ordinal(self):
        left = DocumentState("fr.md", "# Unité 5\nintro\n## Vocabulaire\na\nb\nc\n## Grammaire\nx");
        right = DocumentState("es.md", "# Unidad 5\nintro\nintro2\n## Vocabulario\nuno\ndos\ntres\ncuatro\ncinco\n## Gramática\nx");
        session = ComparisonSession([left, right], mode="parallel");
        mapped = session.map_line(0, 1, 5);
        self.assertGreaterEqual(mapped, 5);
        self.assertLess(mapped, 10);

    def test_parallel_ratio_for_non_markdown(self):
        left = DocumentState("a.txt", "1\n2\n3\n4\n5");
        right = DocumentState("b.txt", "a\nb\nc\nd\ne\nf\ng\nh\ni");
        session = ComparisonSession([left, right], mode="parallel");
        self.assertEqual(session.map_line(0, 1, 3), 5);

    def test_apply_hunk(self):
        left = DocumentState("a.txt", "alpha\nbeta\ngamma");
        right = DocumentState("b.txt", "alpha\nBETA\ngamma");
        session = ComparisonSession([left, right], mode="compare");
        self.assertTrue(session.apply_hunk(0, 1, 0));
        self.assertEqual(session.documents[1].text, session.documents[0].text);


class AppConstructionTests(unittest.TestCase):
    def test_three_markdown_documents_default_parallel_cli(self):
        parser = build_parser();
        args = parser.parse_args(["fr.md", "es.md", "en.md"]);
        self.assertEqual(choose_mode(args), "parallel");

    def test_two_documents_default_compare_cli(self):
        parser = build_parser();
        args = parser.parse_args(["old.py", "new.py"]);
        self.assertEqual(choose_mode(args), "compare");

    def test_application_constructs_multiple_windows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);
            paths = [];
            for name, text in (("fr.md", "# Bonjour\ntexte"), ("es.md", "# Hola\ntexto"), ("en.md", "# Hello\ntext")):
                path = root / name;
                path.write_text(text, encoding="utf-8");
                paths.append(path);
            application = SumDiffApp(paths, mode="parallel");
            self.assertEqual(len(application.panes), 3);
            self.assertEqual(len(application.workspace.windows), 3);
            self.assertTrue(application.sync_scrolling);

    def test_parallel_idle_sync_uses_cursor_section(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);
            left = root / "fr.md";
            right = root / "es.md";
            left.write_text("# U\nintro\n## A\na\nb\n## B\nx\ny\n", encoding="utf-8");
            right.write_text("# U\nintro\nintro2\n## A\nuno\ndos\ntres\n## B\nx\ny\n", encoding="utf-8");
            application = SumDiffApp([left, right], mode="parallel");
            application.workspace.activate(application.panes[0].window);
            application.panes[0].editor.goto_line(5);
            application.panes[0].editor.y_offset = 2;
            application.panes[0].editor.x_offset = 3;
            self.assertTrue(application._idle_sync());
            self.assertGreaterEqual(application.panes[1].editor.y_offset, 2);
            self.assertEqual(application.panes[1].editor.x_offset, 3);

    def test_compare_mode_marks_both_editors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);
            left = root / "left.py";
            right = root / "right.py";
            left.write_text("x = 1\nprint(x)\n", encoding="utf-8");
            right.write_text("x = 2\nprint(x)\n", encoding="utf-8");
            application = SumDiffApp([left, right], mode="compare");
            self.assertIn(0, application.panes[0].marker.marks);
            self.assertIn(0, application.panes[1].marker.marks);

    def test_reset_layout_is_side_by_side(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);
            paths = [];
            for index in range(3):
                path = root / "{}.txt".format(index);
                path.write_text(str(index), encoding="utf-8");
                paths.append(path);
            application = SumDiffApp(paths, mode="parallel");
            application.arrange_side_by_side();
            lefts = [pane.window.left for pane in application.panes];
            self.assertEqual(lefts, sorted(lefts));
            self.assertEqual(len(set(lefts)), 3);


if __name__ == "__main__":
    unittest.main();

class HostIntegrationTests(unittest.TestCase):
    def test_text_override_uses_live_host_buffer_without_touching_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);
            left = root / "left.md";
            right = root / "right.md";
            left.write_text("saved left\n", encoding="utf-8");
            right.write_text("saved right\n", encoding="utf-8");
            application = SumDiffApp([left, right], text_overrides={left: "live left\n"});
            self.assertEqual(application.panes[0].editor.text, "live left\n");
            self.assertEqual(left.read_text(encoding="utf-8"), "saved left\n");

    def test_saved_paths_records_files_changed_inside_sumdiff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);
            left = root / "left.txt";
            right = root / "right.txt";
            left.write_text("one\n", encoding="utf-8");
            right.write_text("two\n", encoding="utf-8");
            application = SumDiffApp([left, right]);
            application.workspace.activate(application.panes[0].window);
            application.panes[0].editor.set_text("changed\n", modified=True);
            self.assertTrue(application.save_current());
            self.assertIn(left.resolve(), application.saved_paths);
            self.assertEqual(left.read_text(encoding="utf-8"), "changed\n");
