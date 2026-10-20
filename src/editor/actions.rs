//! Zed-style editing on top of `EditorState`: multiple cursors, undo/redo and the editor
//! actions bound to Zed's default keys (moving and duplicating lines, comments, selecting
//! the next match...).
//!
//! The primary cursor is the `text_editor`'s own; the others live in `EditorState::extra`.
//! An edit with several cursors runs once per cursor, from the last one in the text to the
//! first, so an edit never moves the cursors still to be edited. The cursors already edited
//! are kept as distances from the end of the text, which edits above them do not change.

use std::sync::Arc;
use std::time::{Duration, Instant};

use iced::Task;
use iced::widget::scrollable;
use iced::widget::text_editor::{self, Action, Cursor, Edit, Motion, Position};

use super::{EditKey, EditorState, Fold, Outcome, scroll_id};
use crate::widget::PyMsg;

/// Consecutive typing within this time is undone in one step.
const GROUP: Duration = Duration::from_millis(1000);
const MAX_UNDO: usize = 1000;

/// A named editor action (Zed's name, in snake case). Most have a default key, all of them can
/// be run from Python with `Command.editor_action`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EditorAction {
    Undo,
    Redo,
    AddCursorAbove,
    AddCursorBelow,
    SelectNext,
    SelectPrevious,
    SelectAllMatches,
    SplitSelectionIntoLines,
    UndoSelection,
    Cancel,
    MoveLineUp,
    MoveLineDown,
    DuplicateLineUp,
    DuplicateLineDown,
    DuplicateSelection,
    DeleteLine,
    NewlineBelow,
    NewlineAbove,
    Indent,
    Outdent,
    SelectLine,
    JoinLines,
    ToggleComments,
    MoveToEnclosingBracket,
    DeleteToPreviousWordStart,
    DeleteToNextWordEnd,
    MoveToBeginningOfLine,
    SelectToBeginningOfLine,
    ConvertToUpperCase,
    ConvertToLowerCase,
    SortLines,
    Copy,
    Cut,
    LineUp,
    LineDown,
}

impl EditorAction {
    pub const ALL: [EditorAction; 35] = [
        Self::Undo,
        Self::Redo,
        Self::AddCursorAbove,
        Self::AddCursorBelow,
        Self::SelectNext,
        Self::SelectPrevious,
        Self::SelectAllMatches,
        Self::SplitSelectionIntoLines,
        Self::UndoSelection,
        Self::Cancel,
        Self::MoveLineUp,
        Self::MoveLineDown,
        Self::DuplicateLineUp,
        Self::DuplicateLineDown,
        Self::DuplicateSelection,
        Self::DeleteLine,
        Self::NewlineBelow,
        Self::NewlineAbove,
        Self::Indent,
        Self::Outdent,
        Self::SelectLine,
        Self::JoinLines,
        Self::ToggleComments,
        Self::MoveToEnclosingBracket,
        Self::DeleteToPreviousWordStart,
        Self::DeleteToNextWordEnd,
        Self::MoveToBeginningOfLine,
        Self::SelectToBeginningOfLine,
        Self::ConvertToUpperCase,
        Self::ConvertToLowerCase,
        Self::SortLines,
        Self::Copy,
        Self::Cut,
        Self::LineUp,
        Self::LineDown,
    ];

    pub fn name(self) -> &'static str {
        match self {
            Self::Undo => "undo",
            Self::Redo => "redo",
            Self::AddCursorAbove => "add_selection_above",
            Self::AddCursorBelow => "add_selection_below",
            Self::SelectNext => "select_next",
            Self::SelectPrevious => "select_previous",
            Self::SelectAllMatches => "select_all_matches",
            Self::SplitSelectionIntoLines => "split_selection_into_lines",
            Self::UndoSelection => "undo_selection",
            Self::Cancel => "cancel",
            Self::MoveLineUp => "move_line_up",
            Self::MoveLineDown => "move_line_down",
            Self::DuplicateLineUp => "duplicate_line_up",
            Self::DuplicateLineDown => "duplicate_line_down",
            Self::DuplicateSelection => "duplicate_selection",
            Self::DeleteLine => "delete_line",
            Self::NewlineBelow => "newline_below",
            Self::NewlineAbove => "newline_above",
            Self::Indent => "indent",
            Self::Outdent => "outdent",
            Self::SelectLine => "select_line",
            Self::JoinLines => "join_lines",
            Self::ToggleComments => "toggle_comments",
            Self::MoveToEnclosingBracket => "move_to_enclosing_bracket",
            Self::DeleteToPreviousWordStart => "delete_to_previous_word_start",
            Self::DeleteToNextWordEnd => "delete_to_next_word_end",
            Self::MoveToBeginningOfLine => "move_to_beginning_of_line",
            Self::SelectToBeginningOfLine => "select_to_beginning_of_line",
            Self::ConvertToUpperCase => "convert_to_upper_case",
            Self::ConvertToLowerCase => "convert_to_lower_case",
            Self::SortLines => "sort_lines_case_sensitive",
            Self::Copy => "copy",
            Self::Cut => "cut",
            Self::LineUp => "line_up",
            Self::LineDown => "line_down",
        }
    }

    pub fn parse(name: &str) -> Option<Self> {
        let name = name.trim().trim_start_matches("editor::");
        Self::ALL.into_iter().find(|a| {
            a.name() == name || a.name().replace('_', "") == name.to_lowercase().replace('_', "")
        })
    }
}

/// What an action needs from the editor's props.
#[derive(Debug, Clone, Default)]
pub struct ActionContext {
    /// Python-style indentation width (`None`: the editor does not manage indentation).
    pub size: Option<usize>,
    pub pairs: bool,
    /// The line comment prefix of the language (`#`, `//`...).
    pub comment: Option<Arc<str>>,
    pub on_change: Option<PyMsg>,
    pub on_cursor: Option<PyMsg>,
    /// Called with the action's name after it runs.
    pub on_action: Option<PyMsg>,
}

#[derive(Clone)]
pub(crate) struct Snapshot {
    text: String,
    folds: Vec<Fold>,
    primary: Cursor,
    extra: Vec<Cursor>,
}

/// The kinds of edit that are grouped into one undo step when they follow each other.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(crate) enum EditKind {
    Typing,
    Deleting,
    Other,
}

#[derive(Default)]
pub(crate) struct History {
    undo: Vec<Snapshot>,
    redo: Vec<Snapshot>,
    last: Option<(Instant, EditKind)>,
    /// The cursors before each action that added or replaced cursors (for `undo_selection`).
    selections: Vec<(Cursor, Vec<Cursor>)>,
}

impl History {
    pub(crate) fn clear(&mut self) {
        *self = Self::default();
    }
}

fn pos(line: usize, column: usize) -> Position {
    Position { line, column }
}

fn order(p: Position) -> (usize, usize) {
    (p.line, p.column)
}

/// The start and end of a cursor's selection (both the position for an empty one).
pub(crate) fn range(c: &Cursor) -> (Position, Position) {
    let anchor = c.selection.unwrap_or(c.position);
    if order(anchor) <= order(c.position) {
        (anchor, c.position)
    } else {
        (c.position, anchor)
    }
}

fn has_selection(c: &Cursor) -> bool {
    c.selection.is_some_and(|s| s != c.position)
}

fn collapsed(p: Position) -> Cursor {
    Cursor {
        position: p,
        selection: None,
    }
}

fn selected(start: Position, end: Position) -> Cursor {
    Cursor {
        position: end,
        selection: (start != end).then_some(start),
    }
}

fn is_word(c: char) -> bool {
    c.is_alphanumeric() || c == '_'
}

/// The largest char boundary of `line` at or before byte `column`.
pub(crate) fn floor(line: &str, column: usize) -> usize {
    let mut column = column.min(line.len());
    while !line.is_char_boundary(column) {
        column -= 1;
    }
    column
}

/// Byte offset of a position in `lines` joined with `\n`.
pub(crate) fn offset_of(lines: &[String], p: Position) -> usize {
    let line = p.line.min(lines.len().saturating_sub(1));
    lines[..line].iter().map(|l| l.len() + 1).sum::<usize>()
        + floor(lines.get(line).map_or("", |l| l), p.column)
}

/// The position of a byte offset in `lines` joined with `\n`.
pub(crate) fn position_at(lines: &[String], offset: usize) -> Position {
    let mut rest = offset;
    for (i, line) in lines.iter().enumerate() {
        if rest <= line.len() {
            return pos(i, floor(line, rest));
        }
        rest -= line.len() + 1;
    }
    let last = lines.len().saturating_sub(1);
    pos(last, lines.get(last).map_or(0, |l| l.len()))
}

/// The word around byte `column` of `line`, as a byte range.
fn word_at(line: &str, column: usize) -> Option<(usize, usize)> {
    let column = floor(line, column);
    let start = line[..column]
        .char_indices()
        .rev()
        .take_while(|(_, c)| is_word(*c))
        .last()
        .map_or(column, |(i, _)| i);
    let end = column
        + line[column..]
            .char_indices()
            .take_while(|(_, c)| is_word(*c))
            .last()
            .map_or(0, |(i, c)| i + c.len_utf8());
    (start < end).then_some((start, end))
}

/// Merged, sorted, inclusive line ranges covered by the cursors (a selection that ends at
/// the start of a line does not include that line).
fn line_ranges(cursors: &[Cursor]) -> Vec<(usize, usize)> {
    let mut ranges: Vec<(usize, usize)> = cursors
        .iter()
        .map(|c| {
            let (s, e) = range(c);
            let last = if e.line > s.line && e.column == 0 {
                e.line - 1
            } else {
                e.line
            };
            (s.line, last)
        })
        .collect();
    ranges.sort();
    let mut merged: Vec<(usize, usize)> = Vec::new();
    for (s, e) in ranges {
        match merged.last_mut() {
            Some(last) if s <= last.1 + 1 => last.1 = last.1.max(e),
            _ => merged.push((s, e)),
        }
    }
    merged
}

/// The bracket matching the one at byte `at` of `text`, skipping nested pairs.
pub(crate) fn matching_bracket(text: &[u8], at: usize) -> Option<usize> {
    let (open, close, forward) = match text.get(at)? {
        b'(' => (b'(', b')', true),
        b'[' => (b'[', b']', true),
        b'{' => (b'{', b'}', true),
        b')' => (b'(', b')', false),
        b']' => (b'[', b']', false),
        b'}' => (b'{', b'}', false),
        _ => return None,
    };
    let mut depth = 0usize;
    if forward {
        for (i, &b) in text.iter().enumerate().skip(at) {
            if b == open {
                depth += 1;
            } else if b == close {
                depth -= 1;
                if depth == 0 {
                    return Some(i);
                }
            }
        }
    } else {
        for i in (0..=at).rev() {
            let b = text[i];
            if b == close {
                depth += 1;
            } else if b == open {
                depth -= 1;
                if depth == 0 {
                    return Some(i);
                }
            }
        }
    }
    None
}

/// The opening bracket enclosing byte `at` of `text`.
fn enclosing_bracket(text: &[u8], at: usize) -> Option<usize> {
    let mut depth = [0i32; 3];
    for i in (0..at.min(text.len())).rev() {
        let kind = match text[i] {
            b'(' | b')' => 0,
            b'[' | b']' => 1,
            b'{' | b'}' => 2,
            _ => continue,
        };
        if matches!(text[i], b')' | b']' | b'}') {
            depth[kind] += 1;
        } else if depth[kind] == 0 {
            return Some(i);
        } else {
            depth[kind] -= 1;
        }
    }
    None
}

/// Where a whole-word or plain match of `needle` starts in `text`, from byte `from` (wrapping
/// around), skipping the starts in `taken`. Searches backwards with `back`.
fn find_match(
    text: &str,
    needle: &str,
    whole_word: bool,
    from: usize,
    back: bool,
    taken: &[usize],
) -> Option<usize> {
    let matches = all_matches(text, needle, whole_word);
    let free = |s: &&usize| !taken.contains(s);
    if back {
        matches
            .iter()
            .rev()
            .filter(free)
            .find(|s| **s + needle.len() <= from)
            .or_else(|| matches.iter().rev().find(free))
            .copied()
    } else {
        matches
            .iter()
            .filter(free)
            .find(|s| **s >= from)
            .or_else(|| matches.iter().find(free))
            .copied()
    }
}

/// Starts of the non-overlapping matches of `needle` in `text`.
pub(crate) fn all_matches(text: &str, needle: &str, whole_word: bool) -> Vec<usize> {
    if needle.is_empty() {
        return Vec::new();
    }
    let mut out = Vec::new();
    let mut from = 0;
    while let Some(i) = text[from..].find(needle) {
        let start = from + i;
        let end = start + needle.len();
        let ok = !whole_word
            || (!text[..start].chars().next_back().is_some_and(is_word)
                && !text[end..].chars().next().is_some_and(is_word));
        if ok {
            out.push(start);
            from = end;
        } else {
            from = start + needle.chars().next().map_or(1, char::len_utf8);
        }
    }
    out
}

/// Whether the selection `start..end` of `text` is a whole word (the search for the next
/// match then only takes whole words, like Zed).
fn is_whole_word(text: &str, start: usize, end: usize) -> bool {
    let inner = &text[start..end];
    !inner.is_empty()
        && inner.chars().all(is_word)
        && !text[..start].chars().next_back().is_some_and(is_word)
        && !text[end..].chars().next().is_some_and(is_word)
}

impl EditorState {
    // -----------------------------------------------------------------------------------
    // Cursors
    // -----------------------------------------------------------------------------------

    /// The primary cursor with its real selection (a double or triple click selects a word or
    /// lines, which `text_editor::Content::cursor` reports as the click point).
    pub(crate) fn primary(&self) -> Cursor {
        let cursor = self.content.cursor();
        let Some(anchor) = cursor.selection else {
            return cursor;
        };
        let Some(selection) = self.content.selection() else {
            return collapsed(cursor.position);
        };
        let lines = self.visible_lines();
        let (s, e) = range(&cursor);
        let (a, b) = (offset_of(&lines, s), offset_of(&lines, e));
        let joined = lines.join("\n");
        if joined.get(a..b) == Some(selection.as_str()) {
            return cursor;
        }
        if anchor == cursor.position && !selection.contains('\n') {
            let line = &lines[cursor.position.line];
            if let Some((ws, we)) = word_at(line, cursor.position.column)
                && line[ws..we] == selection
            {
                return selected(pos(cursor.position.line, ws), pos(cursor.position.line, we));
            }
        }
        // Whole lines.
        let start = pos(s.line, 0);
        let end = pos(e.line, lines[e.line].len());
        if order(cursor.position) >= order(anchor) {
            selected(start, end)
        } else {
            Cursor {
                position: start,
                selection: Some(end),
            }
        }
    }

    /// Moves the primary cursor (and its selection) exactly to `cursor`.
    pub(crate) fn set_cursor(&mut self, cursor: Cursor) {
        if self.content.cursor().selection.is_some() {
            // Any motion drops the selection first.
            self.content.perform(Action::Move(Motion::Home));
        }
        let selection = cursor.selection.filter(|s| *s != cursor.position);
        self.content.move_to(Cursor {
            position: cursor.position,
            selection,
        });
    }

    /// Every cursor: the primary first.
    pub(crate) fn cursors(&self) -> Vec<Cursor> {
        let mut all = vec![self.primary()];
        all.extend(self.extra.iter().copied());
        all
    }

    /// Replaces every cursor, merging the ones that overlap. `cursors[0]` is the primary.
    pub(crate) fn set_cursors(&mut self, cursors: Vec<Cursor>) {
        let lines = self.visible_lines();
        let clamp = |p: Position| {
            let line = p.line.min(lines.len().saturating_sub(1));
            pos(line, floor(lines.get(line).map_or("", |l| l), p.column))
        };
        let mut all: Vec<(Cursor, bool)> = cursors
            .into_iter()
            .enumerate()
            .map(|(i, c)| {
                (
                    Cursor {
                        position: clamp(c.position),
                        selection: c.selection.map(clamp),
                    },
                    i == 0,
                )
            })
            .collect();
        if all.is_empty() {
            return;
        }
        all.sort_by_key(|(c, _)| order(range(c).0));
        let mut merged: Vec<(Cursor, bool)> = Vec::new();
        for (c, primary) in all {
            if let Some((last, last_primary)) = merged.last_mut() {
                let (ls, le) = range(last);
                let (s, e) = range(&c);
                let overlaps = if has_selection(last) || has_selection(&c) {
                    order(s) < order(le)
                } else {
                    s == le
                };
                if overlaps {
                    let end = if order(e) > order(le) { e } else { le };
                    *last = selected(ls, end);
                    *last_primary |= primary;
                    continue;
                }
            }
            merged.push((c, primary));
        }
        let index = merged.iter().position(|(_, p)| *p).unwrap_or(0);
        let (primary, _) = merged.remove(index);
        self.extra = merged.into_iter().map(|(c, _)| c).collect();
        self.set_cursor(primary);
    }

    pub(crate) fn remember_selections(&mut self) {
        let saved = (self.primary(), self.extra.clone());
        self.history.selections.push(saved);
        if self.history.selections.len() > MAX_UNDO {
            self.history.selections.remove(0);
        }
    }

    /// Runs `f` once per cursor, with that cursor as the primary one, from the last cursor
    /// in the text to the first. Returns whether any run edited the text.
    pub(crate) fn each_cursor(&mut self, mut f: impl FnMut(&mut Self, usize) -> bool) -> bool {
        if self.extra.is_empty() {
            return f(self, 0);
        }
        let mut all: Vec<(Cursor, bool)> = vec![(self.primary(), true)];
        all.extend(self.extra.drain(..).map(|c| (c, false)));
        all.sort_by_key(|(c, _)| std::cmp::Reverse(order(range(c).1)));
        let count = all.len();
        let mut edited = false;
        // Results as distances from the end of the text (edits above do not change them).
        let mut results: Vec<(usize, Option<usize>, bool)> = Vec::with_capacity(count);
        for (i, (cursor, primary)) in all.into_iter().enumerate() {
            self.set_cursor(cursor);
            edited |= f(self, count - 1 - i);
            let after = self.primary();
            let lines = self.visible_lines();
            let total = lines.iter().map(|l| l.len() + 1).sum::<usize>() - 1;
            results.push((
                total - offset_of(&lines, after.position),
                after.selection.map(|s| total - offset_of(&lines, s)),
                primary,
            ));
        }
        let lines = self.visible_lines();
        let total = lines.iter().map(|l| l.len() + 1).sum::<usize>() - 1;
        let mut cursors: Vec<Cursor> = Vec::with_capacity(count);
        let mut primary_cursor = None;
        for (p, s, primary) in results {
            let cursor = Cursor {
                position: position_at(&lines, total.saturating_sub(p)),
                selection: s.map(|s| position_at(&lines, total.saturating_sub(s))),
            };
            if primary {
                primary_cursor = Some(cursor);
            } else {
                cursors.push(cursor);
            }
        }
        if let Some(primary) = primary_cursor {
            cursors.insert(0, primary);
        }
        self.set_cursors(cursors);
        edited
    }

    // -----------------------------------------------------------------------------------
    // Undo
    // -----------------------------------------------------------------------------------

    fn snapshot(&self) -> Snapshot {
        Snapshot {
            text: self.content.text(),
            folds: self.folds.clone(),
            primary: self.primary(),
            extra: self.extra.clone(),
        }
    }

    fn restore(&mut self, snapshot: Snapshot) {
        self.content = text_editor::Content::with_text(&snapshot.text);
        self.folds = snapshot.folds;
        self.extra.clear();
        let mut cursors = vec![snapshot.primary];
        cursors.extend(snapshot.extra);
        self.set_cursors(cursors);
    }

    /// Saves the text before an edit, unless it continues the edit before it (typing).
    pub(crate) fn record(&mut self, kind: EditKind) {
        let now = Instant::now();
        let grouped = kind != EditKind::Other
            && self
                .history
                .last
                .is_some_and(|(at, last)| last == kind && now.duration_since(at) < GROUP);
        if !grouped {
            let snapshot = self.snapshot();
            self.history.undo.push(snapshot);
            if self.history.undo.len() > MAX_UNDO {
                self.history.undo.remove(0);
            }
        }
        self.history.redo.clear();
        self.history.last = Some((now, kind));
    }

    /// Drops the last saved state when the edit it was saved for changed nothing.
    pub(crate) fn unrecord(&mut self) {
        if let Some(last) = self.history.undo.last()
            && last.text == self.content.text()
        {
            self.history.undo.pop();
        }
    }

    fn undo(&mut self) -> bool {
        let Some(snapshot) = self.history.undo.pop() else {
            return false;
        };
        let current = self.snapshot();
        self.history.redo.push(current);
        self.restore(snapshot);
        self.history.last = None;
        true
    }

    fn redo(&mut self) -> bool {
        let Some(snapshot) = self.history.redo.pop() else {
            return false;
        };
        let current = self.snapshot();
        self.history.undo.push(current);
        self.restore(snapshot);
        self.history.last = None;
        true
    }

    // -----------------------------------------------------------------------------------
    // Line operations
    // -----------------------------------------------------------------------------------

    /// Unfolds the folds on and next to the lines the cursors cover, so line operations
    /// never split or move a fold.
    fn unfold_lines(&mut self) {
        loop {
            let ranges = line_ranges(&self.cursors());
            let header = self
                .folds
                .iter()
                .map(|f| f.header)
                .find(|h| ranges.iter().any(|(s, e)| *h + 1 >= *s && *h <= e + 1));
            match header {
                Some(header) => {
                    self.unfold(header);
                }
                None => break,
            }
        }
    }

    /// Replaces the visible lines after a line operation: `map[i]` is the new line of old
    /// line `i` (for the fold headers) and `cursors` the new cursors.
    fn replace_lines(&mut self, lines: Vec<String>, map: &[usize], cursors: Vec<Cursor>) {
        for fold in &mut self.folds {
            if let Some(line) = map.get(fold.header) {
                fold.header = *line;
            }
        }
        self.folds.sort_by_key(|f| f.header);
        let lines = if lines.is_empty() {
            vec![String::new()]
        } else {
            lines
        };
        self.content = text_editor::Content::with_text(&lines.join("\n"));
        self.extra.clear();
        self.set_cursors(cursors);
    }

    /// Runs a line operation over the merged line ranges of the cursors. `op` gets the lines
    /// and the ranges and returns, for each old line, its new line (`usize::MAX` if removed),
    /// and how each cursor's line and column change: `(range index, line, column) -> position`.
    fn line_op(
        &mut self,
        op: impl FnOnce(&mut Vec<String>, &[(usize, usize)]) -> Vec<usize>,
        cursor: impl Fn(&[String], usize, Position) -> Position,
    ) -> bool {
        self.unfold_lines();
        let cursors = self.cursors();
        let ranges = line_ranges(&cursors);
        let mut lines = self.visible_lines();
        let before = lines.clone();
        let map = op(&mut lines, &ranges);
        if lines == before {
            return false;
        }
        let index_of = |line: usize| {
            ranges
                .iter()
                .position(|(s, e)| line >= *s && line <= *e)
                .unwrap_or(0)
        };
        let moved = cursors
            .iter()
            .map(|c| {
                let r = index_of(c.position.line);
                Cursor {
                    position: cursor(&lines, r, c.position),
                    selection: c
                        .selection
                        .map(|s| cursor(&lines, index_of(s.line).max(r), s)),
                }
            })
            .collect();
        self.replace_lines(lines, &map, moved);
        true
    }

    fn move_lines(&mut self, up: bool) -> bool {
        self.unfold_lines();
        let ranges = line_ranges(&self.cursors());
        let count = self.content.line_count();
        let can = |(s, e): (usize, usize)| if up { s > 0 } else { e + 1 < count };
        let movable: Vec<bool> = ranges.iter().map(|r| can(*r)).collect();
        self.line_op(
            |lines, ranges| {
                let mut map: Vec<usize> = (0..lines.len()).collect();
                for (&(s, e), ok) in ranges.iter().zip(&movable) {
                    if !ok {
                        continue;
                    }
                    if up {
                        lines[s - 1..=e].rotate_left(1);
                        for m in map.iter_mut().take(e + 1).skip(s) {
                            *m -= 1;
                        }
                        map[s - 1] = e;
                    } else {
                        lines[s..=e + 1].rotate_right(1);
                        for m in map.iter_mut().take(e + 1).skip(s) {
                            *m += 1;
                        }
                        map[e + 1] = s;
                    }
                }
                map
            },
            |_, r, p| {
                if !movable[r] {
                    p
                } else if up {
                    pos(p.line - 1, p.column)
                } else {
                    pos(p.line + 1, p.column)
                }
            },
        )
    }

    fn duplicate_lines(&mut self, up: bool) -> bool {
        self.unfold_lines();
        let ranges = line_ranges(&self.cursors());
        // Lines inserted before each range.
        let shift: Vec<usize> = ranges
            .iter()
            .scan(0, |acc, (s, e)| {
                let before = *acc;
                *acc += e - s + 1;
                Some(before)
            })
            .collect();
        let sizes: Vec<usize> = ranges.iter().map(|(s, e)| e - s + 1).collect();
        self.line_op(
            |lines, ranges| {
                let old = lines.len();
                for &(s, e) in ranges.iter().rev() {
                    let copy: Vec<String> = lines[s..=e].to_vec();
                    lines.splice(e + 1..e + 1, copy);
                }
                (0..old)
                    .map(|i| {
                        i + ranges
                            .iter()
                            .filter(|(_, e)| *e < i)
                            .map(|(s, e)| e - s + 1)
                            .sum::<usize>()
                    })
                    .collect()
            },
            |_, r, p| {
                let line = p.line + shift[r] + if up { 0 } else { sizes[r] };
                pos(line, p.column)
            },
        )
    }

    /// Zed's and VS Code's "duplicate selection": every cursor's selected text is copied right
    /// after it (and the copy selected, so pressing again copies it again); a cursor without a
    /// selection duplicates its line below, keeping its column.
    fn duplicate_selection(&mut self) -> bool {
        self.unfold_lines();
        let cursors = self.cursors();
        let lines = self.visible_lines();
        let text = lines.join("\n");
        // One insertion per cursor (cursors on the same line without a selection share theirs):
        // (offset, text), and where each cursor goes as (insertion, offset into the inserted
        // text of its position, of its selection).
        let mut inserts: Vec<(usize, String)> = Vec::new();
        let mut targets: Vec<(usize, usize, Option<usize>)> = Vec::with_capacity(cursors.len());
        for c in &cursors {
            let (s, e) = range(c);
            let (a, b) = (offset_of(&lines, s), offset_of(&lines, e));
            let insert = if has_selection(c) {
                (b, text[a..b].to_owned())
            } else {
                let line = &lines[c.position.line];
                let end = offset_of(&lines, pos(c.position.line, line.len()));
                (end, format!("\n{line}"))
            };
            let index = match inserts.iter().position(|i| *i == insert) {
                Some(index) => index,
                None => {
                    inserts.push(insert);
                    inserts.len() - 1
                }
            };
            let len = inserts[index].1.len();
            targets.push(if has_selection(c) {
                let forward = order(c.position) >= order(c.selection.unwrap_or(c.position));
                if forward {
                    (index, len, Some(0))
                } else {
                    (index, 0, Some(len))
                }
            } else {
                (
                    index,
                    1 + floor(&lines[c.position.line], c.position.column),
                    None,
                )
            });
        }
        let mut order_of: Vec<usize> = (0..inserts.len()).collect();
        order_of.sort_by_key(|&i| (inserts[i].0, i));
        // Where each insertion lands in the new text.
        let mut landed = vec![0; inserts.len()];
        let mut out =
            String::with_capacity(text.len() + inserts.iter().map(|i| i.1.len()).sum::<usize>());
        let mut from = 0;
        for &i in &order_of {
            let (at, ref piece) = inserts[i];
            out.push_str(&text[from..at]);
            landed[i] = out.len();
            out.push_str(piece);
            from = at;
        }
        out.push_str(&text[from..]);
        let new_lines: Vec<String> = out.split('\n').map(str::to_owned).collect();
        let map: Vec<usize> = (0..lines.len())
            .map(|line| {
                let start = offset_of(&lines, pos(line, 0));
                line + inserts
                    .iter()
                    .filter(|(at, _)| *at <= start)
                    .map(|(_, t)| t.matches('\n').count())
                    .sum::<usize>()
            })
            .collect();
        let moved = targets
            .iter()
            .map(|&(i, p, sel)| Cursor {
                position: position_at(&new_lines, landed[i] + p),
                selection: sel.map(|s| position_at(&new_lines, landed[i] + s)),
            })
            .collect();
        self.replace_lines(new_lines, &map, moved);
        true
    }

    fn delete_lines(&mut self) -> bool {
        self.unfold_lines();
        let ranges = line_ranges(&self.cursors());
        let removed_before: Vec<usize> = ranges
            .iter()
            .scan(0, |acc, (s, e)| {
                let before = *acc;
                *acc += e - s + 1;
                Some(before)
            })
            .collect();
        let starts: Vec<usize> = ranges.iter().map(|(s, _)| *s).collect();
        self.line_op(
            |lines, ranges| {
                let old = lines.len();
                for &(s, e) in ranges.iter().rev() {
                    lines.drain(s..=e);
                }
                (0..old)
                    .map(|i| {
                        if ranges.iter().any(|(s, e)| i >= *s && i <= *e) {
                            usize::MAX
                        } else {
                            i - ranges
                                .iter()
                                .filter(|(_, e)| *e < i)
                                .map(|(s, e)| e - s + 1)
                                .sum::<usize>()
                        }
                    })
                    .collect()
            },
            |lines, r, p| {
                let line = (starts[r] - removed_before[r]).min(lines.len().saturating_sub(1));
                let len = lines.get(line).map_or(0, |l| l.len());
                pos(line, p.column.min(len))
            },
        )
    }

    fn indent_lines(&mut self, step: usize, outdent: bool) -> bool {
        let cursors = self.cursors();
        let ranges = line_ranges(&cursors);
        let lines = self.visible_lines();
        // Change of leading spaces per line.
        let mut delta: Vec<isize> = vec![0; lines.len()];
        for &(s, e) in &ranges {
            for (i, line) in lines.iter().enumerate().take(e + 1).skip(s) {
                let lead = line.chars().take_while(|c| *c == ' ').count();
                if outdent {
                    let remove = if lead == 0 { 0 } else { (lead - 1) % step + 1 };
                    delta[i] = -(remove as isize);
                } else if !line.trim().is_empty() || s == e {
                    delta[i] = (step - lead % step) as isize;
                }
            }
        }
        if delta.iter().all(|d| *d == 0) {
            return false;
        }
        let new_lines: Vec<String> = lines
            .iter()
            .zip(&delta)
            .map(|(line, d)| {
                if *d >= 0 {
                    format!("{}{line}", " ".repeat(*d as usize))
                } else {
                    line[(-*d) as usize..].to_string()
                }
            })
            .collect();
        let shift = |p: Position| {
            let d = delta[p.line];
            let column = if d >= 0 {
                p.column + d as usize
            } else {
                p.column.saturating_sub((-d) as usize)
            };
            pos(p.line, column)
        };
        let moved = cursors
            .iter()
            .map(|c| Cursor {
                position: shift(c.position),
                selection: c.selection.map(shift),
            })
            .collect();
        let map: Vec<usize> = (0..lines.len()).collect();
        self.replace_lines(new_lines, &map, moved);
        true
    }

    fn toggle_comments(&mut self, prefix: &str) -> bool {
        let cursors = self.cursors();
        let ranges = line_ranges(&cursors);
        let lines = self.visible_lines();
        let marker = prefix.trim_end();
        // (column, inserted (+) or removed (-) bytes) per line.
        let mut change: Vec<(usize, isize)> = vec![(0, 0); lines.len()];
        for &(s, e) in &ranges {
            let body: Vec<usize> = (s..=e).filter(|i| !lines[*i].trim().is_empty()).collect();
            if body.is_empty() {
                continue;
            }
            let commented = body
                .iter()
                .all(|i| lines[*i].trim_start().starts_with(marker));
            if commented {
                for i in body {
                    let line = &lines[i];
                    let at = line.len() - line.trim_start().len();
                    let mut len = marker.len();
                    if line[at + len..].starts_with(' ') {
                        len += 1;
                    }
                    change[i] = (at, -(len as isize));
                }
            } else {
                let at = body
                    .iter()
                    .map(|i| lines[*i].len() - lines[*i].trim_start().len())
                    .min()
                    .unwrap_or(0);
                for i in body {
                    change[i] = (at, prefix.len() as isize);
                }
            }
        }
        if change.iter().all(|(_, d)| *d == 0) {
            return false;
        }
        let new_lines: Vec<String> = lines
            .iter()
            .zip(&change)
            .map(|(line, (at, d))| {
                if *d > 0 {
                    format!("{}{prefix}{}", &line[..*at], &line[*at..])
                } else if *d < 0 {
                    format!("{}{}", &line[..*at], &line[*at + (-*d) as usize..])
                } else {
                    line.clone()
                }
            })
            .collect();
        let shift = |p: Position| {
            let (at, d) = change[p.line];
            if d == 0 || p.column < at {
                return p;
            }
            let column = if d > 0 {
                p.column + d as usize
            } else {
                at.max(p.column.saturating_sub((-d) as usize))
            };
            pos(p.line, column)
        };
        let moved = cursors
            .iter()
            .map(|c| Cursor {
                position: shift(c.position),
                selection: c.selection.map(shift),
            })
            .collect();
        let map: Vec<usize> = (0..lines.len()).collect();
        self.replace_lines(new_lines, &map, moved);
        true
    }

    fn join_lines(&mut self) -> bool {
        self.unfold_lines();
        let count = self.content.line_count();
        let ranges: Vec<(usize, usize)> = line_ranges(&self.cursors())
            .into_iter()
            .map(|(s, e)| (s, if s == e { (e + 1).min(count - 1) } else { e }))
            .filter(|(s, e)| e > s)
            .collect();
        if ranges.is_empty() {
            return false;
        }
        let lines = self.visible_lines();
        let mut new_lines = Vec::with_capacity(lines.len());
        let mut map = Vec::with_capacity(lines.len());
        let mut cursors = Vec::new();
        let mut i = 0;
        while i < lines.len() {
            match ranges.iter().find(|(s, _)| *s == i) {
                Some(&(s, e)) => {
                    let mut joined = lines[s].trim_end().to_string();
                    let mut at = joined.len();
                    for (k, next) in lines.iter().enumerate().take(e + 1).skip(s + 1) {
                        let next = next.trim_start();
                        if !next.is_empty() && !joined.is_empty() {
                            joined.push(' ');
                        }
                        if k == s + 1 {
                            at = joined.len();
                        }
                        joined.push_str(next);
                    }
                    let line = new_lines.len();
                    for _ in s..=e {
                        map.push(line);
                    }
                    cursors.push(collapsed(pos(line, at.saturating_sub(1))));
                    new_lines.push(joined);
                    i = e + 1;
                }
                None => {
                    map.push(new_lines.len());
                    new_lines.push(lines[i].clone());
                    i += 1;
                }
            }
        }
        // The cursor goes to the join point (before the inserted space, like Zed).
        let cursors = cursors
            .into_iter()
            .map(|c: Cursor| {
                let line = &new_lines[c.position.line];
                let column = floor(line, c.position.column + 1);
                let column = if line[..column].ends_with(' ') {
                    column - 1
                } else {
                    column
                };
                collapsed(pos(c.position.line, column))
            })
            .collect();
        self.replace_lines(new_lines, &map, cursors);
        true
    }

    fn sort_lines(&mut self) -> bool {
        self.line_op(
            |lines, ranges| {
                for &(s, e) in ranges {
                    lines[s..=e].sort();
                }
                (0..lines.len()).collect()
            },
            |_, _, p| p,
        )
    }

    fn select_lines(&mut self) {
        let lines = self.visible_lines();
        let last = lines.len() - 1;
        let cursors = self
            .cursors()
            .into_iter()
            .map(|c| {
                let (s, e) = range(&c);
                let whole = s.column == 0
                    && (e.column == 0 && e.line > s.line || e == pos(last, lines[last].len()));
                let end_line = if whole && e.column == 0 {
                    e.line
                } else {
                    e.line + 1
                };
                let end = if end_line > last {
                    pos(last, lines[last].len())
                } else {
                    pos(end_line, 0)
                };
                selected(pos(s.line, 0), end)
            })
            .collect();
        self.set_cursors(cursors);
    }

    // -----------------------------------------------------------------------------------
    // Multiple cursors
    // -----------------------------------------------------------------------------------

    fn add_cursor(&mut self, below: bool) -> bool {
        let cursors = self.cursors();
        let goal = cursors[0].position.column;
        let edge = if below {
            cursors.iter().map(|c| c.position.line).max()
        } else {
            cursors.iter().map(|c| c.position.line).min()
        }
        .unwrap_or(0);
        let line = if below {
            edge + 1
        } else if edge == 0 {
            return false;
        } else {
            edge - 1
        };
        let Some(text) = self.content.line(line).map(|l| l.text.into_owned()) else {
            return false;
        };
        self.remember_selections();
        let mut all = vec![collapsed(pos(line, floor(&text, goal)))];
        all.extend(cursors);
        self.set_cursors(all);
        true
    }

    /// Selects the word under every cursor without a selection; `false` if there were none.
    fn select_words(&mut self) -> bool {
        let lines = self.visible_lines();
        let cursors = self.cursors();
        if cursors.iter().any(has_selection) {
            return false;
        }
        let words: Vec<Cursor> = cursors
            .iter()
            .filter_map(|c| {
                let line = &lines[c.position.line];
                word_at(line, c.position.column)
                    .map(|(s, e)| selected(pos(c.position.line, s), pos(c.position.line, e)))
            })
            .collect();
        if words.is_empty() {
            return false;
        }
        self.remember_selections();
        self.set_cursors(words);
        true
    }

    fn select_next(&mut self, back: bool) -> bool {
        if self.select_words() {
            return true;
        }
        let primary = self.primary();
        if !has_selection(&primary) {
            return false;
        }
        let lines = self.visible_lines();
        let text = lines.join("\n");
        let (s, e) = range(&primary);
        let (a, b) = (offset_of(&lines, s), offset_of(&lines, e));
        let needle = &text[a..b];
        let whole = is_whole_word(&text, a, b);
        let taken: Vec<usize> = self
            .cursors()
            .iter()
            .map(|c| offset_of(&lines, range(c).0))
            .collect();
        let from = if back { a } else { b };
        let Some(start) = find_match(&text, needle, whole, from, back, &taken) else {
            return false;
        };
        self.remember_selections();
        let found = selected(
            position_at(&lines, start),
            position_at(&lines, start + needle.len()),
        );
        let mut all = vec![found];
        all.extend(self.cursors());
        self.set_cursors(all);
        true
    }

    fn select_all_matches(&mut self) -> bool {
        self.select_words();
        let primary = self.primary();
        if !has_selection(&primary) {
            return false;
        }
        let lines = self.visible_lines();
        let text = lines.join("\n");
        let (s, e) = range(&primary);
        let (a, b) = (offset_of(&lines, s), offset_of(&lines, e));
        let needle = text[a..b].to_string();
        let whole = is_whole_word(&text, a, b);
        let starts = all_matches(&text, &needle, whole);
        if starts.len() <= 1 {
            return false;
        }
        self.remember_selections();
        let mut cursors: Vec<Cursor> = starts
            .iter()
            .map(|start| {
                selected(
                    position_at(&lines, *start),
                    position_at(&lines, start + needle.len()),
                )
            })
            .collect();
        if let Some(i) = starts.iter().position(|s| *s == a) {
            let primary = cursors.remove(i);
            cursors.insert(0, primary);
        }
        self.set_cursors(cursors);
        true
    }

    fn split_selection_into_lines(&mut self) -> bool {
        let lines = self.visible_lines();
        let mut out = Vec::new();
        let mut changed = false;
        for c in self.cursors() {
            let (s, e) = range(&c);
            if s.line == e.line {
                out.push(c);
                continue;
            }
            changed = true;
            for (line, text) in lines.iter().enumerate().take(e.line + 1).skip(s.line) {
                let start = if line == s.line { s.column } else { 0 };
                let end = if line == e.line { e.column } else { text.len() };
                out.push(selected(pos(line, start), pos(line, end)));
            }
        }
        if !changed {
            return false;
        }
        self.remember_selections();
        // The last line's selection becomes the primary one.
        if let Some(last) = out.pop() {
            out.insert(0, last);
        }
        self.set_cursors(out);
        true
    }

    fn undo_selection(&mut self) -> bool {
        let Some((primary, extra)) = self.history.selections.pop() else {
            return false;
        };
        let mut all = vec![primary];
        all.extend(extra);
        self.set_cursors(all);
        true
    }

    /// Escape: back to one cursor, then drops the selection.
    pub(crate) fn can_cancel(&self) -> bool {
        !self.extra.is_empty() || self.content.cursor().selection.is_some()
    }

    fn cancel(&mut self) -> bool {
        if !self.extra.is_empty() {
            self.remember_selections();
            self.extra.clear();
            return true;
        }
        let cursor = self.content.cursor();
        if cursor.selection.is_some() {
            self.set_cursor(collapsed(cursor.position));
            return true;
        }
        false
    }

    /// The selected text of every cursor, one per line (whole lines when nothing is selected,
    /// like Zed).
    fn copied(&self) -> String {
        let lines = self.visible_lines();
        let text = lines.join("\n");
        let mut cursors = self.cursors();
        cursors.sort_by_key(|c| order(range(c).0));
        if cursors.iter().all(|c| !has_selection(c)) {
            let mut seen = Vec::new();
            let mut out = String::new();
            for c in &cursors {
                if seen.contains(&c.position.line) {
                    continue;
                }
                seen.push(c.position.line);
                out.push_str(&lines[c.position.line]);
                out.push('\n');
            }
            return out;
        }
        cursors
            .iter()
            .filter(|c| has_selection(c))
            .map(|c| {
                let (s, e) = range(c);
                text[offset_of(&lines, s)..offset_of(&lines, e)].to_string()
            })
            .collect::<Vec<_>>()
            .join("\n")
    }

    fn cut(&mut self) -> bool {
        if self.cursors().iter().all(|c| !has_selection(c)) {
            return self.delete_lines();
        }
        self.each_cursor(|s, _| {
            if has_selection(&s.primary()) {
                s.perform_one(Action::Edit(Edit::Backspace))
            } else {
                false
            }
        })
    }

    /// Pastes `text`, one line per cursor when it has as many lines as there are cursors.
    pub(crate) fn paste(&mut self, text: Arc<String>) -> bool {
        let parts: Vec<&str> = text.split('\n').collect();
        let count = self.extra.len() + 1;
        let trailing = text.ends_with('\n') && parts.len() == count + 1;
        if count > 1 && (parts.len() == count || trailing) {
            let parts: Vec<Arc<String>> = parts
                .into_iter()
                .take(count)
                .map(|p| Arc::new(p.to_string()))
                .collect();
            return self
                .each_cursor(|s, i| s.perform_one(Action::Edit(Edit::Paste(parts[i].clone()))));
        }
        self.each_cursor(|s, _| s.perform_one(Action::Edit(Edit::Paste(text.clone()))))
    }

    // -----------------------------------------------------------------------------------
    // Per-cursor edits and motions
    // -----------------------------------------------------------------------------------

    fn line_text(&self, line: usize) -> String {
        self.content
            .line(line)
            .map(|l| l.text.into_owned())
            .unwrap_or_default()
    }

    fn home(&mut self, select: bool) -> bool {
        self.each_cursor(|s, _| {
            let c = s.primary();
            let line = s.line_text(c.position.line);
            let indent = line.len() - line.trim_start().len();
            let column = if c.position.column == indent {
                0
            } else {
                indent
            };
            let target = pos(c.position.line, column);
            let anchor = if select {
                c.selection.or(Some(c.position))
            } else {
                None
            };
            s.set_cursor(Cursor {
                position: target,
                selection: anchor,
            });
            false
        });
        true
    }

    fn enclosing(&mut self) -> bool {
        let lines = self.visible_lines();
        let text = lines.join("\n");
        let bytes = text.as_bytes();
        self.each_cursor(|s, _| {
            let c = s.primary();
            let at = offset_of(&lines, c.position);
            let target = matching_bracket(bytes, at)
                .or_else(|| at.checked_sub(1).and_then(|b| matching_bracket(bytes, b)))
                .or_else(|| enclosing_bracket(bytes, at));
            if let Some(target) = target {
                s.set_cursor(collapsed(position_at(&lines, target)));
            }
            false
        });
        true
    }

    fn newline_below(&mut self, ctx: &ActionContext) -> bool {
        self.each_cursor(|s, _| {
            let line = s.primary().position.line;
            let len = s.line_text(line).len();
            s.set_cursor(collapsed(pos(line, len)));
            s.key_one(EditKey::Enter, ctx.size, false)
        })
    }

    fn newline_above(&mut self) -> bool {
        self.each_cursor(|s, _| {
            let line = s.primary().position.line;
            let text = s.line_text(line);
            let indent: String = text
                .chars()
                .take_while(|c| *c == ' ' || *c == '\t')
                .collect();
            s.set_cursor(collapsed(pos(line, 0)));
            s.perform_one(Action::Edit(Edit::Paste(Arc::new(format!("{indent}\n")))));
            s.set_cursor(collapsed(pos(line, indent.len())));
            true
        })
    }

    fn delete_word(&mut self, forward: bool) -> bool {
        self.each_cursor(|s, _| {
            if !has_selection(&s.primary()) {
                s.content.perform(Action::Select(if forward {
                    Motion::WordRight
                } else {
                    Motion::WordLeft
                }));
            }
            if s.content.cursor().selection.is_none() {
                return false;
            }
            s.perform_one(Action::Edit(Edit::Backspace))
        })
    }

    fn convert_case(&mut self, upper: bool) -> bool {
        self.each_cursor(|s, _| {
            let mut c = s.primary();
            if !has_selection(&c) {
                let line = s.line_text(c.position.line);
                let Some((a, b)) = word_at(&line, c.position.column) else {
                    return false;
                };
                c = selected(pos(c.position.line, a), pos(c.position.line, b));
                s.set_cursor(c);
            }
            let Some(text) = s.content.selection() else {
                return false;
            };
            let converted = if upper {
                text.to_uppercase()
            } else {
                text.to_lowercase()
            };
            if converted == text {
                return false;
            }
            let (start, _) = range(&c);
            s.perform_one(Action::Edit(Edit::Paste(Arc::new(converted.clone()))));
            // Keep the converted text selected.
            let lines = s.visible_lines();
            let a = offset_of(&lines, start);
            s.set_cursor(selected(start, position_at(&lines, a + converted.len())));
            true
        })
    }

    // -----------------------------------------------------------------------------------
    // Entry point
    // -----------------------------------------------------------------------------------

    /// Runs a named action.
    pub fn run(&mut self, id: &str, action: EditorAction, ctx: &ActionContext) -> Outcome {
        use EditorAction as A;
        let before = self.real_position(self.content.cursor().position);
        let text_before = self.content.text();
        let edits = matches!(
            action,
            A::MoveLineUp
                | A::MoveLineDown
                | A::DuplicateLineUp
                | A::DuplicateLineDown
                | A::DuplicateSelection
                | A::DeleteLine
                | A::NewlineBelow
                | A::NewlineAbove
                | A::Indent
                | A::Outdent
                | A::JoinLines
                | A::ToggleComments
                | A::DeleteToPreviousWordStart
                | A::DeleteToNextWordEnd
                | A::ConvertToUpperCase
                | A::ConvertToLowerCase
                | A::SortLines
                | A::Cut
        );
        if edits {
            self.record(EditKind::Other);
        }
        let step = ctx.size.unwrap_or(4);
        let mut clipboard = None;
        let mut scroll = Task::none();
        let mut done = match action {
            A::Undo => self.undo(),
            A::Redo => self.redo(),
            A::AddCursorAbove => self.add_cursor(false),
            A::AddCursorBelow => self.add_cursor(true),
            A::SelectNext => self.select_next(false),
            A::SelectPrevious => self.select_next(true),
            A::SelectAllMatches => self.select_all_matches(),
            A::SplitSelectionIntoLines => self.split_selection_into_lines(),
            A::UndoSelection => self.undo_selection(),
            A::Cancel => self.cancel(),
            A::MoveLineUp => self.move_lines(true),
            A::MoveLineDown => self.move_lines(false),
            A::DuplicateLineUp => self.duplicate_lines(true),
            A::DuplicateLineDown => self.duplicate_lines(false),
            A::DuplicateSelection => self.duplicate_selection(),
            A::DeleteLine => self.delete_lines(),
            A::NewlineBelow => self.newline_below(ctx),
            A::NewlineAbove => self.newline_above(),
            A::Indent => self.indent_lines(step, false),
            A::Outdent => self.indent_lines(step, true),
            A::SelectLine => {
                self.select_lines();
                true
            }
            A::JoinLines => self.join_lines(),
            A::ToggleComments => match ctx.comment.clone() {
                Some(prefix) => self.toggle_comments(&format!("{prefix} ")),
                None => false,
            },
            A::MoveToEnclosingBracket => self.enclosing(),
            A::DeleteToPreviousWordStart => self.delete_word(false),
            A::DeleteToNextWordEnd => self.delete_word(true),
            A::MoveToBeginningOfLine => self.home(false),
            A::SelectToBeginningOfLine => self.home(true),
            A::ConvertToUpperCase => self.convert_case(true),
            A::ConvertToLowerCase => self.convert_case(false),
            A::SortLines => self.sort_lines(),
            A::Copy => {
                clipboard = Some(self.copied());
                true
            }
            A::Cut => {
                clipboard = Some(self.copied());
                self.cut()
            }
            A::LineUp | A::LineDown => {
                let lh = self.metrics.borrow().line_height.max(1.0);
                let dy = if action == A::LineUp { -lh } else { lh };
                scroll = iced::widget::operation::scroll_by(
                    scroll_id(id),
                    scrollable::AbsoluteOffset { x: 0.0, y: dy },
                );
                true
            }
        };
        let edited =
            self.content.text() != text_before || matches!(action, A::Undo | A::Redo) && done;
        if edits && !edited {
            self.unrecord();
        }
        if edited {
            self.history.selections.clear();
        }
        if matches!(action, A::Undo | A::Redo) && !done {
            done = false;
        }
        let mut outcome = self.outcome(
            id,
            before,
            edited,
            !matches!(action, A::LineUp | A::LineDown),
        );
        // Moves without a real position change still count (selection changes).
        outcome.cursor_moved |= done;
        outcome.action = done.then_some(action.name());
        outcome.clipboard = clipboard;
        if !matches!(action, A::LineUp | A::LineDown) && done {
            outcome.scroll = Task::batch([outcome.scroll, self.autoscroll(id)]);
        } else {
            outcome.scroll = Task::batch([outcome.scroll, scroll]);
        }
        outcome
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn editor(text: &str) -> EditorState {
        EditorState::new(text)
    }

    fn ctx() -> ActionContext {
        ActionContext {
            size: Some(4),
            pairs: true,
            comment: Some("#".into()),
            ..Default::default()
        }
    }

    fn at(s: &mut EditorState, line: usize, column: usize) {
        s.set_cursor(collapsed(pos(line, column)));
    }

    fn run(s: &mut EditorState, a: EditorAction) {
        let _ = s.run("e", a, &ctx());
    }

    fn type_text(s: &mut EditorState, text: &str) {
        for c in text.chars() {
            let _ = s.perform("e", Action::Edit(Edit::Insert(c)));
        }
    }

    #[test]
    fn several_cursors_type_together() {
        let mut s = editor("a\nb\nc");
        at(&mut s, 0, 1);
        run(&mut s, EditorAction::AddCursorBelow);
        run(&mut s, EditorAction::AddCursorBelow);
        assert_eq!(s.extra.len(), 2);
        type_text(&mut s, "xy");
        assert_eq!(s.text(), "axy\nbxy\ncxy");
        let _ = s.perform("e", Action::Edit(Edit::Backspace));
        assert_eq!(s.text(), "ax\nbx\ncx");
        run(&mut s, EditorAction::Cancel);
        assert!(s.extra.is_empty());
    }

    #[test]
    fn select_next_and_all_matches() {
        let mut s = editor("foo bar foo\nfoobar foo");
        at(&mut s, 0, 1);
        run(&mut s, EditorAction::SelectNext);
        assert_eq!(s.content.selection().as_deref(), Some("foo"));
        run(&mut s, EditorAction::SelectNext);
        assert_eq!(s.extra.len(), 1);
        type_text(&mut s, "z");
        assert_eq!(s.text(), "z bar z\nfoobar foo");
        let mut s = editor("foo bar foo\nfoobar foo");
        at(&mut s, 0, 0);
        run(&mut s, EditorAction::SelectAllMatches);
        assert_eq!(s.extra.len(), 2, "whole words only");
    }

    #[test]
    fn undo_and_redo_group_typing() {
        let mut s = editor("x");
        at(&mut s, 0, 1);
        type_text(&mut s, "abc");
        run(&mut s, EditorAction::DuplicateLineDown);
        assert_eq!(s.text(), "xabc\nxabc");
        run(&mut s, EditorAction::Undo);
        assert_eq!(s.text(), "xabc");
        run(&mut s, EditorAction::Undo);
        assert_eq!(s.text(), "x");
        run(&mut s, EditorAction::Redo);
        assert_eq!(s.text(), "xabc");
    }

    #[test]
    fn duplicate_selection_on_every_cursor() {
        // Without a selection: each cursor's line, once per line, the cursor on the copy.
        let mut s = editor("one\ntwo");
        at(&mut s, 0, 1);
        run(&mut s, EditorAction::AddCursorBelow);
        run(&mut s, EditorAction::DuplicateSelection);
        assert_eq!(s.text(), "one\none\ntwo\ntwo");
        let mut at_ = s.cursors().iter().map(|c| c.position).collect::<Vec<_>>();
        at_.sort_by_key(|p| order(*p));
        assert_eq!(at_, vec![pos(1, 1), pos(3, 1)]);
        // With selections: each selected text right after it, the copy selected.
        let mut s = editor("foo bar foo");
        at(&mut s, 0, 0);
        run(&mut s, EditorAction::SelectNext);
        run(&mut s, EditorAction::SelectNext);
        run(&mut s, EditorAction::DuplicateSelection);
        assert_eq!(s.text(), "foofoo bar foofoo");
        let mut ranges = s.cursors().iter().map(range).collect::<Vec<_>>();
        ranges.sort_by_key(|(a, _)| order(*a));
        assert_eq!(
            ranges,
            vec![(pos(0, 3), pos(0, 6)), (pos(0, 14), pos(0, 17))]
        );
        run(&mut s, EditorAction::Undo);
        assert_eq!(s.text(), "foo bar foo");
    }

    #[test]
    fn duplicate_lines_on_every_cursor() {
        let mut s = editor("a\nb\nc");
        at(&mut s, 0, 0);
        run(&mut s, EditorAction::AddCursorBelow);
        run(&mut s, EditorAction::AddCursorBelow);
        run(&mut s, EditorAction::DuplicateLineDown);
        assert_eq!(s.text(), "a\nb\nc\na\nb\nc");
        let mut s = editor("a\nb\nc");
        at(&mut s, 0, 0);
        run(&mut s, EditorAction::DuplicateLineDown);
        at(&mut s, 3, 0);
        run(&mut s, EditorAction::DuplicateLineUp);
        assert_eq!(s.text(), "a\na\nb\nc\nc");
        assert_eq!(s.content.cursor().position, pos(3, 0));
    }

    #[test]
    fn line_operations() {
        let mut s = editor("one\ntwo\nthree");
        at(&mut s, 1, 1);
        run(&mut s, EditorAction::MoveLineUp);
        assert_eq!(s.text(), "two\none\nthree");
        assert_eq!(s.content.cursor().position, pos(0, 1));
        run(&mut s, EditorAction::MoveLineDown);
        run(&mut s, EditorAction::MoveLineDown);
        assert_eq!(s.text(), "one\nthree\ntwo");
        run(&mut s, EditorAction::DeleteLine);
        assert_eq!(s.text(), "one\nthree");
        at(&mut s, 0, 0);
        run(&mut s, EditorAction::JoinLines);
        assert_eq!(s.text(), "one three");
        assert_eq!(s.content.cursor().position, pos(0, 3));
    }

    #[test]
    fn comments_and_indentation() {
        let mut s = editor("def f():\n    return 1");
        at(&mut s, 0, 0);
        s.set_cursor(selected(pos(0, 0), pos(1, 3)));
        run(&mut s, EditorAction::ToggleComments);
        assert_eq!(s.text(), "# def f():\n#     return 1");
        run(&mut s, EditorAction::ToggleComments);
        assert_eq!(s.text(), "def f():\n    return 1");
        run(&mut s, EditorAction::Indent);
        assert_eq!(s.text(), "    def f():\n        return 1");
        run(&mut s, EditorAction::Outdent);
        run(&mut s, EditorAction::Outdent);
        assert_eq!(s.text(), "def f():\nreturn 1");
    }

    #[test]
    fn brackets_and_smart_home() {
        let mut s = editor("    f(a, [b])");
        at(&mut s, 0, 5);
        run(&mut s, EditorAction::MoveToEnclosingBracket);
        assert_eq!(s.content.cursor().position, pos(0, 12));
        run(&mut s, EditorAction::MoveToBeginningOfLine);
        assert_eq!(s.content.cursor().position, pos(0, 4));
        run(&mut s, EditorAction::MoveToBeginningOfLine);
        assert_eq!(s.content.cursor().position, pos(0, 0));
    }

    #[test]
    fn paste_distributes_lines_over_cursors() {
        let mut s = editor("a\nb");
        at(&mut s, 0, 1);
        run(&mut s, EditorAction::AddCursorBelow);
        let _ = s.perform("e", Action::Edit(Edit::Paste(Arc::new("1\n2".into()))));
        assert_eq!(s.text(), "a1\nb2");
    }

    #[test]
    fn input_method_text_undoes_like_typing() {
        let mut s = editor("x");
        at(&mut s, 0, 1);
        for text in ["你好", "吗"] {
            s.ime_commit.set(true);
            let _ = s.perform("e", Action::Edit(Edit::Paste(Arc::new(text.into()))));
        }
        assert_eq!(s.text(), "x你好吗");
        assert!(!s.ime_commit.get());
        run(&mut s, EditorAction::Undo);
        assert_eq!(s.text(), "x");
        // A real paste stays its own step.
        let _ = s.perform("e", Action::Edit(Edit::Paste(Arc::new("ab".into()))));
        let _ = s.perform("e", Action::Edit(Edit::Paste(Arc::new("cd".into()))));
        run(&mut s, EditorAction::Undo);
        assert_eq!(s.text(), "xab");
    }
}
