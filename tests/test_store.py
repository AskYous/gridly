import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()  # keep the real config out of it
import tempfile, datetime, pathlib
from gridly.store import Sheet
from gridly.coltypes import ColumnType, parse, ValidationError


def test_store():
    d = tempfile.mkdtemp()
    p = pathlib.Path(d) / "t.gridly"
    s = Sheet(p)
    print("seeded cols:", [(c.name, c.type.value) for c in s.columns()], "rows:", len(s.rows()))

    name, done = s.columns()
    prio = s.add_column("Priority", ColumnType.SELECT, ["Low", "High"])
    qty  = s.add_column("Qty", ColumnType.NUMBER)
    due  = s.add_column("Due", ColumnType.DATE)

    r1 = s.rows()[0].id
    r2 = s.add_row()
    s.set_cell(r1, name.id, "Milk"); s.set_cell(r1, done.id, True)
    s.set_cell(r1, prio.id, "High"); s.set_cell(r1, qty.id, 3); s.set_cell(r1, due.id, datetime.date(2026,9,9))
    s.set_cell(r2, name.id, "Bread"); s.set_cell(r2, qty.id, 1.5)

    # reopen from disk -> persistence check
    s.close()
    s = Sheet(p)
    for r in s.rows():
        print("row", r.position, {c.name: r.values.get(c.id) for c in s.columns()})

    # retype number -> text (lossless), then text -> number (lossy on "Milk")
    qty = [c for c in s.columns() if c.name == "Qty"][0]
    print("num->text dropped:", s.update_column(qty.id, "Qty", ColumnType.TEXT))
    nm = [c for c in s.columns() if c.name == "Name"][0]
    print("text->number dropped:", s.update_column(nm.id, "Name", ColumnType.NUMBER))
    print("after retype:", [{c.name: r.values.get(c.id) for c in s.columns()} for r in s.rows()])

    # narrowing dropdown options drops the now-invalid value
    s.update_column(nm.id, "Name", ColumnType.TEXT)
    pr = [c for c in s.columns() if c.name == "Priority"][0]
    print("dropdown narrow dropped:", s.update_column(pr.id, "Priority", ColumnType.SELECT, ["Low"]))

    # delete + reorder
    s.delete_column(due.id)
    s.move_column(pr.id, -1)
    print("cols now:", [c.name for c in s.columns()])
    s.delete_row(r2)
    print("rows now:", len(s.rows()), "counts:", s.counts())

    # insert-below keeps ordering
    a = s.add_row(); b = s.add_row(after_position=s.rows()[0].position)
    print("positions:", [r.position for r in s.rows()], "ids:", [r.id for r in s.rows()])

    for t, raw in [(ColumnType.NUMBER,"1,200"),(ColumnType.BOOLEAN,"Y"),(ColumnType.DATE,"2026-01-02"),
                   (ColumnType.DATE,"today"),(ColumnType.TEXT,"  hi "),(ColumnType.NUMBER,"")]:
        print("parse", t.value, repr(raw), "->", repr(parse(t, raw, ["Low"])))
    for t, raw in [(ColumnType.NUMBER,"abc"),(ColumnType.BOOLEAN,"maybe"),(ColumnType.DATE,"nope"),(ColumnType.SELECT,"Mid")]:
        try: parse(t, raw, ["Low"]); print("NO ERROR", t, raw)
        except ValidationError as e: print("rejected", t.value, repr(raw), "->", e)
    print("ALL STORE TESTS DONE")

