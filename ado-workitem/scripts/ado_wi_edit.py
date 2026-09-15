# -*- coding: utf-8 -*-
"""Rewrite a work item's description and/or title in place.

    python ado_wi_edit.py <id> --description desc.html [--title "..."] [--dry]

The description is HTML, read from a file so it never has to pass through a shell quote.
A --dry run prints the patch and writes nothing. Everything else - organisation, PAT -
follows ado_wi.py.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ado_wi as w                                   # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("id", type=int)
    p.add_argument("--description", help="path to an HTML file")
    p.add_argument("--title")
    p.add_argument("--dry", action="store_true")
    a = p.parse_args()

    patch = []
    if a.title:
        patch.append({"op": "replace", "path": "/fields/System.Title", "value": a.title})
    if a.description:
        html = Path(a.description).read_text(encoding="utf-8")
        patch.append({"op": "replace", "path": "/fields/System.Description", "value": html})
    if not patch:
        sys.exit("nothing to change: give --title and/or --description")

    if a.dry:
        for op in patch:
            v = str(op["value"])
            print("  {:<28} {}".format(op["path"].split("/")[-1], v[:90] + ("..." if len(v) > 90 else "")))
        return

    url = "{}/{}/_apis/wit/workitems/{}?api-version=7.1".format(w.ORG, w.PROJECT, a.id)
    updated = w.call("PATCH", url, patch, ctype="application/json-patch+json")
    f = updated["fields"]
    print("updated", a.id, "|", f.get("System.Title"))
    print("description:", len(f.get("System.Description") or ""), "chars")


if __name__ == "__main__":
    main()
