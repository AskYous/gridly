"""Editing values: one cell, one dropdown choice, or a whole row."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, Select, Static, TextArea

from ..coltypes import ColumnType, ValidationError, color_style, display, parse
from ..store import Column, Comment, Row, Sheet

CLEAR_OPTION = "— clear —"


def build_editor(column: Column, value: Any, field_id: str):
    """The right widget for a column's type, pre-filled with `value`."""
    if column.computed is not None:
        # Shown, so the row reads whole, but there is nothing to type here.
        return Input(
            value=display(column.type, value, column.format),
            disabled=True,
            id=field_id,
        )
    if column.type is ColumnType.BOOLEAN:
        return Select(
            [("Yes", "yes"), ("No", "no")],
            value="yes" if value else "no" if value is not None else Select.NULL,
            prompt="(not set)",
            id=field_id,
        )
    if column.type is ColumnType.SELECT:
        return Select(
            [(option, option) for option in column.options],
            value=value if value in column.options else Select.NULL,
            prompt="(not set)",
            id=field_id,
        )
    if column.type is ColumnType.TEXT:
        # Text may contain newlines — a single-line Input would hide all but the first.
        return TextArea(
            display(column.type, value, column.format), soft_wrap=True, id=field_id
        )
    return Input(
        value=display(column.type, value, column.format),
        placeholder=column.type.hint,
        id=field_id,
    )


def read_editor(field) -> str:
    """The raw text a `build_editor` widget is holding."""
    return field.text if isinstance(field, TextArea) else field.value

class CellEditScreen(ModalScreen[tuple[bool, Any]]):
    """Editor for text, number and date cells."""

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, column: Column, value: Any) -> None:
        super().__init__()
        self.column = column
        self.value = value
        # Text can hold newlines, so it needs an editor that can show them.
        self.multiline = column.type is ColumnType.TEXT

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(f"{self.column.name}  [dim]{self.column.type.label}[/]")
            yield build_editor(self.column, self.value, "value")
            yield Static("", id="error", classes="error")
            save_key = "ctrl+s" if self.multiline else "enter"
            yield Static(
                f"[dim]{save_key} save · esc cancel · empty clears the cell[/]",
                classes="dialog-help",
            )

    def on_mount(self) -> None:
        editor = self.query_one("#value")
        editor.focus()
        # Start where you would carry on typing, not in front of what is there.
        if isinstance(editor, Input):
            editor.cursor_position = len(editor.value)
        elif isinstance(editor, TextArea):
            editor.move_cursor(editor.document.end)

    @on(Input.Submitted)
    def action_save(self) -> None:
        try:
            parsed = parse(
                self.column.type,
                read_editor(self.query_one("#value")),
                self.column.options,
                self.column.format,
            )
        except ValidationError as error:
            self.query_one("#error", Static).update(f"[red]{error}[/]")
            return
        self.dismiss((True, parsed))

    def action_cancel(self) -> None:
        self.dismiss((False, None))


class PickScreen(ModalScreen[tuple[bool, Any]]):
    """Option picker for dropdown cells."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, column: Column, value: Any) -> None:
        super().__init__()
        self.column = column
        self.value = value

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(f"{self.column.name}  [dim]Dropdown[/]")
            yield OptionList(
                Text(CLEAR_OPTION, "dim"),
                *(
                    Text(option, color_style(self.column.color(option)))
                    for option in self.column.options
                ),
                id="options",
            )
            yield Static("[dim]enter pick · esc cancel[/]", classes="dialog-help")

    def on_mount(self) -> None:
        options = self.query_one("#options", OptionList)
        options.focus()
        if self.value in self.column.options:
            options.highlighted = self.column.options.index(self.value) + 1

    @on(OptionList.OptionSelected)
    def pick(self, event: OptionList.OptionSelected) -> None:
        if event.option_index == 0:
            self.dismiss((True, None))
        else:
            self.dismiss((True, self.column.options[event.option_index - 1]))

    def action_cancel(self) -> None:
        self.dismiss((False, None))


@dataclass
class RowChanges:
    """What the row form was saved with."""

    #: Every typed-in column's value, changed or not.
    values: dict[int, Any]
    #: What was still in the new comment box, not yet posted.
    comment: str = ""
    #: Comments still open for rewording, and what they say now, by id.
    reworded: dict[int, str] = field(default_factory=dict)
    #: Comments left open and emptied out, which has only one thing it can mean.
    removed: set[int] = field(default_factory=set)


class CommentBox(TextArea):
    """Somewhere to write a comment, where ctrl+s posts it instead of saving the row."""

    BINDINGS = [Binding("ctrl+s", "post", "Post", show=False)]

    class Posted(Message):
        """ctrl+s, in a comment box."""

        def __init__(self, box: CommentBox) -> None:
            super().__init__()
            self.box = box

        @property
        def control(self) -> CommentBox:
            return self.box

    def action_post(self) -> None:
        self.post_message(self.Posted(self))


class CommentView(Vertical, can_focus=True):
    """One comment, read as text until enter opens it for rewording.

    Like any comment thread, each change is made the moment it is asked for:
    ctrl+s in the box keeps new wording, backspace removes the comment. Neither
    waits for the row to be saved, and esc on the form does not take them back.
    """

    BINDINGS = [
        Binding("enter", "reword", "Edit", show=False),
        Binding("backspace,delete", "remove", "Remove", show=False),
        Binding("escape", "keep", "Keep the wording", show=False),
    ]

    class Changed(Message):
        """The comment was reworded, removed, or put back."""

    def __init__(self, comment: Comment, sheet: Sheet) -> None:
        super().__init__(classes="comment")
        self.comment = comment
        self.sheet = sheet
        #: Gone from the sheet, but still shown. backspace again puts it back.
        self.removed = False
        #: The box it is being reworded in, once enter has opened one.
        self.editor: CommentBox | None = None

    def compose(self) -> ComposeResult:
        yield Static(self._heading(), classes="comment-when")
        yield Static(self._body(), classes="comment-body")

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        # esc only belongs to a comment while it is open. The rest of the time
        # it passes on to the form, to close it.
        return self.editor is not None if action == "keep" else True

    def _heading(self) -> Text:
        when = self.comment.created[:16]  # to the minute, which is enough to read
        if self.comment.edited:
            when += " · edited"
        if self.removed:
            when += " · removed, backspace puts it back"
        return Text(when, "dim")

    def _body(self) -> Text:
        return Text(self.comment.body, "strike dim" if self.removed else "")

    def _redraw(self) -> None:
        self.query_one(".comment-when", Static).update(self._heading())
        for body in self.query(".comment-body").results(Static):
            body.update(self._body())

    async def action_reword(self) -> None:
        if self.removed:
            self._put_back()  # opening it for rewording means keeping it
        self.editor = CommentBox(self.comment.body, soft_wrap=True)
        await self.query_one(".comment-body").remove()
        await self.mount(self.editor)
        self._redraw()
        # The box takes the focus from here on, so tab does not stop twice.
        self.can_focus = False
        self.editor.focus()
        self.editor.move_cursor(self.editor.document.end)
        # It is taller than the text it replaced, and has no size until it has
        # been laid out — so it can only be brought into view after that.
        self.call_after_refresh(self.editor.scroll_visible)

    @on(CommentBox.Posted)
    async def reworded(self, event: CommentBox.Posted) -> None:
        event.stop()  # this comment's box, not the one for a new comment
        text = event.box.text.strip()
        if text:
            self.sheet.edit_comment(self.comment.id, text)
            self.comment = next(
                c for c in self.sheet.comments(self.comment.row_id)
                if c.id == self.comment.id
            )
        await self._close()
        if text:
            self.post_message(self.Changed())
        else:
            self.action_remove()  # emptied out, so there is nothing to keep

    async def action_keep(self) -> None:
        """esc, while it is open: leave the wording as it was."""
        await self._close()

    async def _close(self) -> None:
        """From the box back to the text it was opened from."""
        await self.editor.remove()
        self.editor = None
        await self.mount(Static(self._body(), classes="comment-body"))
        self._redraw()
        self.can_focus = True
        self.focus()

    def action_remove(self) -> None:
        if self.removed:
            self._put_back()
        else:
            self.sheet.delete_comment(self.comment.id)
            self.removed = True
        self._redraw()
        self.post_message(self.Changed())

    def _put_back(self) -> None:
        self.sheet.restore_comment(self.comment)
        self.removed = False


class RowFormScreen(ModalScreen[RowChanges | None]):
    """One row, one field per column — for when the grid is too cramped to think in.

    Under the fields sits the row's log: a box for a new comment, then the
    comments already made, newest first. The fields wait for ctrl+s and esc
    throws them away; a comment is posted, reworded or removed there and then.
    """

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self,
        columns: list[Column],
        row: Row,
        number: int,
        total: int,
        clash=lambda column, value: None,
        *,
        sheet: Sheet,
        commenting: bool = False,
    ) -> None:
        super().__init__()
        self.columns = columns
        self.row = row
        self.number = number
        self.total = total
        #: Given a column and a value, says why it cannot be saved, or nothing.
        self.clash = clash
        #: Where comments are written, since they do not wait for the form.
        self.sheet = sheet
        #: Start in the new comment box rather than the first field.
        self.commenting = commenting
        #: Whether a comment was posted, reworded or removed while it was open,
        #: which the grid has to hear about even if the form is cancelled.
        self.logged = False

    def compose(self) -> ComposeResult:
        comments = self.sheet.comments(self.row.id)
        with Vertical(classes="form"):
            with Vertical(classes="form-inner"):
                yield Label(
                    f"Row {self.number} of {self.total}", classes="dialog-title"
                )
                with VerticalScroll(classes="form-fields"):
                    for column in self.columns:
                        about = column.type.label
                        if column.computed is not None:
                            about += " · worked out"
                        yield Label(
                            f"{column.name}  [dim]{about}[/]", classes="field-label"
                        )
                        yield self._field(column)
                    yield Label(
                        _comments_heading(len(comments)),
                        id="comments-heading",
                        classes="field-label comments-heading",
                    )
                    yield CommentBox(
                        "", soft_wrap=True, id="new-comment",
                        placeholder="write a comment · ctrl+s posts it",
                    )
                    for comment in comments:
                        yield CommentView(comment, self.sheet)
                yield Static("", id="error", classes="error")
                yield Static(
                    "[dim]tab move · ctrl+s save · esc cancel[/]",
                    classes="dialog-help",
                )

    def _field(self, column: Column):
        return build_editor(
            column, self.row.values.get(column.id), f"field-{column.id}"
        )

    def on_mount(self) -> None:
        if self.commenting:
            self.query_one("#new-comment").focus()
            self.call_after_refresh(self._show_log)
        elif self.columns:
            self.query_one(f"#field-{self.columns[0].id}").focus()

    @on(CommentBox.Posted, "#new-comment")
    async def post(self, event: CommentBox.Posted) -> None:
        """Write the comment down straight away, and stay for another."""
        text = event.box.text.strip()
        if not text:
            return
        written = self.sheet.add_comment(self.row.id, text)
        comment = next(c for c in self.sheet.comments(self.row.id) if c.id == written)
        event.box.clear()
        await self.query_one(".form-fields").mount(
            CommentView(comment, self.sheet), after=event.box
        )
        self.noted()
        self.call_after_refresh(self._show_log)

    def _show_log(self) -> None:
        """The comments to the top, so the box and the latest ones are in view.

        Otherwise the box sits at the foot of the form and a comment posted
        from it lands out of sight, below.
        """
        self.query_one(".form-fields", VerticalScroll).scroll_to_widget(
            self.query_one("#comments-heading"), top=True, animate=False
        )

    @on(CommentView.Changed)
    def noted(self) -> None:
        self.logged = True
        standing = [view for view in self.query(CommentView) if not view.removed]
        self.query_one("#comments-heading", Label).update(
            _comments_heading(len(standing))
        )

    @on(Input.Submitted)
    def action_save(self) -> None:
        values: dict[int, Any] = {}
        for column in self.columns:
            if column.computed is not None:
                continue  # worked out, so there is nothing here to save
            field = self.query_one(f"#field-{column.id}")
            if isinstance(field, Select):
                chosen = None if field.value is Select.NULL else field.value
                if column.type is ColumnType.BOOLEAN:
                    values[column.id] = None if chosen is None else chosen == "yes"
                else:
                    values[column.id] = chosen
                continue
            try:
                values[column.id] = parse(
                    column.type, read_editor(field), column.options, column.format
                )
            except ValidationError as error:
                return self._refuse(field, f"{column.name}: {error}")

        for column in self.columns:
            if column.id not in values:
                continue
            complaint = self.clash(column, values[column.id])
            if complaint:
                return self._refuse(self.query_one(f"#field-{column.id}"), complaint)

        # Whatever was being written when the row was saved goes with it,
        # rather than being lost for not having had a ctrl+s of its own.
        changes = RowChanges(
            values, self.query_one("#new-comment", CommentBox).text.strip()
        )
        for view in self.query(CommentView):
            if view.editor is None:
                continue
            text = view.editor.text.strip()
            if not text:
                changes.removed.add(view.comment.id)
            elif text != view.comment.body:
                changes.reworded[view.comment.id] = text
        self.dismiss(changes)

    def _refuse(self, field, message: str) -> None:
        self.query_one("#error", Static).update(f"[red]{message}[/]")
        field.focus()

    def action_cancel(self) -> None:
        self.dismiss(None)


def _comments_heading(count: int) -> str:
    if not count:
        return "Comments  [dim]none yet[/]"
    return f"Comments  [dim]{count} · enter edits one, backspace removes it[/]"
