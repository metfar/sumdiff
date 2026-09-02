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
import argparse;
import sys;
from pathlib import Path;

from sumui import add_backend_arguments, backend_from_args;

from . import __version__;
from .app import SumDiffApp;


def build_parser():
    parser = argparse.ArgumentParser(prog="sumdiff", description="Multi-document compare, merge and parallel editing for text files.");
    group = parser.add_mutually_exclusive_group();
    group.add_argument("--compare", action="store_true", help="compare documents and show line differences");
    group.add_argument("--parallel", action="store_true", help="link related documents without treating translations as textual differences");
    parser.add_argument("--ignore-whitespace", action="store_true", help="ignore leading/trailing whitespace while comparing");
    parser.add_argument("--theme", default=None, help="Sum theme name");
    add_backend_arguments(parser);
    parser.add_argument("--version", action="version", version="%(prog)s {}".format(__version__));
    parser.add_argument("files", nargs="+", help="two or more text files");
    return parser;


def choose_mode(args):
    if args.compare:
        return "compare";
    if args.parallel:
        return "parallel";
    return "compare" if len(args.files) == 2 else "parallel";


def main(argv=None):
    parser = build_parser();
    args = parser.parse_args(argv);
    ui_backend = backend_from_args(args);
    if len(args.files) < 2:
        parser.error("sumdiff requires at least two files");
    paths = [Path(item).expanduser() for item in args.files];
    missing = [str(path) for path in paths if not path.exists()];
    if missing:
        parser.error("file not found: {}".format(", ".join(missing)));
    try:
        application = SumDiffApp(paths, mode=choose_mode(args), theme=args.theme, ignore_whitespace=args.ignore_whitespace);
        return application.run(backend=ui_backend);
    except KeyboardInterrupt:
        return 130;
    except Exception as exc:
        print("sumdiff: {}".format(exc), file=sys.stderr);
        return 1;


if __name__ == "__main__":
    raise SystemExit(main());
