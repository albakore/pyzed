//! The code editor: iced's `text_editor` plus a gutter with line numbers, git markers and fold
//! chevrons, horizontal scrolling, soft wrap (with line numbers that follow wrapped lines),
//! Zed-style autoscroll that keeps the cursor visible, auto-closing brackets and quotes, code
//! folding, a minimap, a configurable cursor and, in `actions`, multiple cursors, undo/redo and
//! Zed's editing actions and keys.
//!
//! Folding hides lines by taking them out of the `text_editor` content (the editor only ever
//! holds the visible lines); `Fold`s keep the hidden text, so callbacks and commands always see
//! and use real line numbers.

use std::cell::{Cell, RefCell};
use std::collections::HashMap;
use std::hash::{Hash, Hasher};
use std::sync::Arc;

use iced::advanced::text::{self as core_text, Paragraph as _, Wrapping};
use iced::widget::text::LineHeight;
use iced::widget::text_editor::{self, Binding, Motion};
use iced::widget::{self, Space, column, container, responsive, row, scrollable, text};
use iced::{
    Background, Border, Color, Element, Font, Length, Padding, Pixels, Rectangle, Size, Task,
    Theme, keyboard,
};

mod actions;
pub mod keymap;

pub(crate) use actions::EditKind;
pub use actions::{ActionContext, EditorAction};

use crate::app::Message;
use crate::editor_widgets::{self, Boxes, Caret, EditorInput, Minimap};
use crate::highlighter::{self, Highlighter};
use crate::sticky::{Probe, StickyLeft};
use crate::widget::EditorProps;

type Paragraph = <iced::Renderer as core_text::Renderer>::Paragraph;

pub const PAD_Y: f32 = 4.0;
pub const PAD_LEFT: f32 = 4.0;
const PAD_RIGHT: f32 = 12.0;
/// Width of the editor's scrollbars.
const SCROLLBAR: f32 = 8.0;
const MARKER_WIDTH: f32 = 3.0;
/// Width of the fold chevrons column, taken from the right padding of the line numbers.
const FOLD_WIDTH: f32 = 14.0;
const ICONS: Font = Font::with_name(crate::style::ICONS);
const CHEVRON_DOWN: char = '\u{e06d}';
const CHEVRON_RIGHT: char = '\u{e06f}';

/// A range of real lines and byte columns, `(line, column, end_line, end_column)`, with an
/// exclusive end: 0-based inside the editor, 1-based in Python.
pub type TextRange = (usize, usize, usize, usize);
/// A range and the text that replaces it.
pub type RangeEdit = (TextRange, String);

/// Layout facts captured while rendering, used to keep the cursor in view.
#[derive(Default, Clone)]
pub(crate) struct Metrics {
    ready: bool,
    /// Width of the gutter (markers + numbers); text starts after it plus `PAD_LEFT`.
    left: f32,
    line_height: f32,
    size: f32,
    font: Font,
    wrap_width: Option<f32>,
    /// `starts[i]` = visual rows before logical line `i` (has `line_count + 1` entries).
    pub(crate) starts: Vec<u32>,
}

#[derive(Default)]
struct Measure {
    key: u64,
    widths: HashMap<u64, f32>,
    rows: HashMap<u64, u32>,
}

/// A key the editor handles itself (see `EditorState::key`).
#[derive(Debug, Clone, Copy)]
pub enum EditKey {
    Tab,
    Enter,
    Backspace,
    /// A typed bracket or quote (auto-closing).
    Char(char),
}

/// What the editor does with its folds.
#[derive(Debug, Clone, Copy)]
pub enum FoldOp {
    /// Folds or unfolds the block that starts at the given visible line.
    Toggle(usize),
    /// Folds (`true`) or unfolds the block that starts at the given real line.
    Line(usize, bool),
    /// Folds the innermost block around the cursor.
    AtCursor,
    /// Unfolds the fold on the cursor's line.
    UnfoldAtCursor,
    /// Unfolds the cursor's line if it is folded, or folds the block around the cursor.
    ToggleAtCursor,
    FoldAll,
    UnfoldAll,
}

/// Lines hidden under the (visible) line `header`.
#[derive(Debug, Clone)]
struct Fold {
    header: usize,
    hidden: Vec<String>,
}

/// Minimap colors per line: `(column, length, color)` runs of non-blank text.
#[derive(Default)]
pub(crate) struct MinimapCache {
    key: u64,
    pub(crate) lines: Vec<Vec<(u16, u16, Color)>>,
}

/// The persistent state of one editor (keyed by its `id`).
pub struct EditorState {
    pub content: text_editor::Content,
    /// Folded blocks, sorted by header line.
    folds: Vec<Fold>,
    pub(crate) metrics: RefCell<Metrics>,
    measure: RefCell<Measure>,
    /// The visible area of the scrollable, in content coordinates (updated every frame).
    pub(crate) viewport: Cell<Option<Rectangle>>,
    /// Whether the text editor has focus (recorded while drawing it).
    pub(crate) focused: Cell<bool>,
    pub(crate) minimap: RefCell<MinimapCache>,
    /// The other cursors (the primary one is the `text_editor`'s), in visible lines.
    pub(crate) extra: Vec<text_editor::Cursor>,
    pub(crate) history: actions::History,
    /// Keyboard modifiers, tracked by `EditorInput` (Alt+click adds a cursor).
    pub(crate) modifiers: Cell<keyboard::Modifiers>,
    /// Ctrl+K was pressed and the next key completes the chord.
    pub(crate) chord: Cell<bool>,
    /// An input method (IME) is composing text: its preedit is drawn at the cursor, so the
    /// caret is hidden. Tracked by `EditorInput`.
    pub(crate) composing: Cell<bool>,
    /// The next paste is text the input method committed, recorded as typing for undo.
    pub(crate) ime_commit: Cell<bool>,
    /// The action context of the last render, for actions run from Python commands.
    pub(crate) context: RefCell<Option<Arc<ActionContext>>>,
}

impl EditorState {
    pub fn new(text: &str) -> Self {
        Self {
            content: text_editor::Content::with_text(text),
            folds: Vec::new(),
            metrics: RefCell::default(),
            measure: RefCell::default(),
            viewport: Cell::new(None),
            focused: Cell::new(false),
            minimap: RefCell::default(),
            extra: Vec::new(),
            history: actions::History::default(),
            modifiers: Cell::new(keyboard::Modifiers::default()),
            chord: Cell::new(false),
            composing: Cell::new(false),
            ime_commit: Cell::new(false),
            context: RefCell::new(None),
        }
    }

    pub fn reset(&mut self, text: &str) {
        self.content = text_editor::Content::with_text(text);
        self.folds.clear();
        self.extra.clear();
        self.history.clear();
    }

    /// The whole text, folded lines included.
    pub fn text(&self) -> String {
        if self.folds.is_empty() {
            return self.content.text();
        }
        self.real_lines().join("\n")
    }

    fn visible_lines(&self) -> Vec<String> {
        self.content.lines().map(|l| l.text.into_owned()).collect()
    }

    fn real_lines(&self) -> Vec<String> {
        let mut out = Vec::with_capacity(self.content.line_count());
        let mut folds = self.folds.iter().peekable();
        for (i, line) in self.content.lines().enumerate() {
            out.push(line.text.into_owned());
            while let Some(fold) = folds.next_if(|f| f.header == i) {
                out.extend(fold.hidden.iter().cloned());
            }
        }
        out
    }

    /// The real (0-based) line number of a visible line.
    pub fn real_line(&self, visible: usize) -> usize {
        visible
            + self
                .folds
                .iter()
                .take_while(|f| f.header < visible)
                .map(|f| f.hidden.len())
                .sum::<usize>()
    }

    /// The visible line showing a real line, and whether that line is hidden in a fold.
    pub fn visible_line(&self, real: usize) -> (usize, bool) {
        let mut offset = 0;
        for fold in &self.folds {
            let header = fold.header + offset;
            if real <= header {
                break;
            }
            if real <= header + fold.hidden.len() {
                return (fold.header, true);
            }
            offset += fold.hidden.len();
        }
        (real - offset, false)
    }

    fn real_position(&self, p: text_editor::Position) -> text_editor::Position {
        text_editor::Position {
            line: self.real_line(p.line),
            column: p.column,
        }
    }

    pub fn is_folded(&self, visible: usize) -> bool {
        self.folds.iter().any(|f| f.header == visible)
    }

    /// Replaces the visible lines (after a fold change), moving the cursor with `map`.
    fn rebuild(
        &mut self,
        lines: &[String],
        map: impl Fn(text_editor::Position) -> text_editor::Position,
    ) {
        let cursor = self.content.cursor();
        self.content = text_editor::Content::with_text(&lines.join("\n"));
        self.content.move_to(text_editor::Cursor {
            position: map(cursor.position),
            selection: cursor.selection.map(&map),
        });
        for c in &mut self.extra {
            c.position = map(c.position);
            c.selection = c.selection.map(&map);
        }
    }

    /// The lines folded under `line` (by indentation), as an inclusive range of visible lines.
    fn fold_range(&self, lines: &[String], line: usize) -> Option<(usize, usize)> {
        let base = indent_of(lines.get(line)?)?;
        let mut end = None;
        for (i, text) in lines.iter().enumerate().skip(line + 1) {
            match indent_of(text) {
                None => continue,
                Some(indent) if indent > base => end = Some(i),
                Some(_) => break,
            }
        }
        end.map(|end| (line + 1, end))
    }

    fn fold(&mut self, line: usize) -> bool {
        if self.is_folded(line) {
            return false;
        }
        let lines = self.visible_lines();
        let Some((start, end)) = self.fold_range(&lines, line) else {
            return false;
        };
        // Nested folds are absorbed: their hidden lines go back in place.
        let mut hidden = Vec::new();
        let mut kept = Vec::new();
        for fold in std::mem::take(&mut self.folds) {
            if fold.header >= start && fold.header <= end {
                kept.push(fold);
            } else {
                self.folds.push(fold);
            }
        }
        let mut nested = kept.into_iter().peekable();
        for (i, text) in lines.iter().enumerate().take(end + 1).skip(start) {
            hidden.push(text.clone());
            while let Some(fold) = nested.next_if(|f| f.header == i) {
                hidden.extend(fold.hidden);
            }
        }
        let count = end - start + 1;
        for fold in &mut self.folds {
            if fold.header > end {
                fold.header -= count;
            }
        }
        let header_len = lines[line].chars().count();
        let at = self.folds.partition_point(|f| f.header < line);
        self.folds.insert(
            at,
            Fold {
                header: line,
                hidden,
            },
        );
        let mut rest = lines;
        rest.drain(start..=end);
        self.rebuild(&rest, |p| {
            if p.line >= start && p.line <= end {
                text_editor::Position {
                    line,
                    column: header_len,
                }
            } else if p.line > end {
                text_editor::Position {
                    line: p.line - count,
                    column: p.column,
                }
            } else {
                p
            }
        });
        true
    }

    fn unfold(&mut self, header: usize) -> bool {
        let Some(index) = self.folds.iter().position(|f| f.header == header) else {
            return false;
        };
        let fold = self.folds.remove(index);
        let count = fold.hidden.len();
        for f in &mut self.folds {
            if f.header > header {
                f.header += count;
            }
        }
        let mut lines = self.visible_lines();
        let at = (header + 1).min(lines.len());
        lines.splice(at..at, fold.hidden);
        self.rebuild(&lines, |p| {
            if p.line > header {
                text_editor::Position {
                    line: p.line + count,
                    column: p.column,
                }
            } else {
                p
            }
        });
        true
    }

    /// Applies a fold operation; the outcome reports the cursor if it moved.
    pub fn fold_op(&mut self, id: &str, op: FoldOp) -> Outcome {
        let before = self.real_position(self.content.cursor().position);
        match op {
            FoldOp::Toggle(line) => {
                if !self.unfold(line) {
                    self.fold(line);
                }
            }
            FoldOp::Line(real, fold) => {
                let (line, hidden) = self.visible_line(real);
                if !hidden {
                    if fold {
                        self.fold(line);
                    } else {
                        self.unfold(line);
                    }
                }
            }
            FoldOp::AtCursor => {
                let lines = self.visible_lines();
                let cursor = self.content.cursor().position.line;
                let target = (0..=cursor).rev().find(|&l| {
                    !self.is_folded(l)
                        && self
                            .fold_range(&lines, l)
                            .is_some_and(|(_, end)| l == cursor || end >= cursor)
                });
                if let Some(line) = target {
                    self.fold(line);
                }
            }
            FoldOp::UnfoldAtCursor => {
                let line = self.content.cursor().position.line;
                self.unfold(line);
            }
            FoldOp::ToggleAtCursor => {
                let line = self.content.cursor().position.line;
                if !self.unfold(line) {
                    return self.fold_op(id, FoldOp::AtCursor);
                }
            }
            FoldOp::FoldAll => {
                let mut line = 0;
                while line < self.content.line_count() {
                    self.fold(line);
                    line += 1;
                }
            }
            FoldOp::UnfoldAll => {
                if !self.folds.is_empty() {
                    let real = before;
                    let text = self.text();
                    let history = std::mem::take(&mut self.history);
                    self.reset(&text);
                    self.history = history;
                    self.content.move_to(text_editor::Cursor {
                        position: real,
                        selection: None,
                    });
                }
            }
        }
        let after = self.real_position(self.content.cursor().position);
        Outcome {
            edited: false,
            cursor_moved: before != after,
            cursor: (after.line, after.column),
            text: String::new(),
            scroll: if before != after {
                self.autoscroll(id)
            } else {
                Task::none()
            },
            action: None,
            clipboard: None,
        }
    }

    /// Before an edit: unfolds the folds the edit could break (`safe` edits stay on one line)
    /// and returns what `end_edit` needs to move the folds below it.
    fn begin_edit(&mut self, safe: bool) -> (usize, usize) {
        let range = |content: &text_editor::Content| {
            let cursor = content.cursor();
            let anchor = cursor.selection.unwrap_or(cursor.position);
            (
                cursor.position.line.min(anchor.line),
                cursor.position.line.max(anchor.line),
            )
        };
        if self.folds.is_empty() {
            return (usize::MAX, self.content.line_count());
        }
        if !safe {
            let (lo, hi) = range(&self.content);
            let touched: Vec<usize> = self
                .folds
                .iter()
                .map(|f| f.header)
                .filter(|h| *h + 1 >= lo && *h <= hi)
                .collect();
            for header in touched.into_iter().rev() {
                self.unfold(header);
            }
        }
        (range(&self.content).1, self.content.line_count())
    }

    fn end_edit(&mut self, (hi, before): (usize, usize)) {
        let delta = self.content.line_count() as isize - before as isize;
        if delta == 0 {
            return;
        }
        for fold in &mut self.folds {
            if fold.header > hi {
                fold.header = (fold.header as isize + delta).max(0) as usize;
            }
        }
    }
}

/// Indentation width of a line (a tab counts as 4), or `None` if it is blank.
fn indent_of(line: &str) -> Option<usize> {
    let mut width = 0;
    for ch in line.chars() {
        match ch {
            ' ' => width += 1,
            '\t' => width += 4,
            _ => return Some(width),
        }
    }
    None
}

fn closing_of(c: char) -> Option<char> {
    Some(match c {
        '(' => ')',
        '[' => ']',
        '{' => '}',
        '"' => '"',
        '\'' => '\'',
        '`' => '`',
        _ => return None,
    })
}

fn is_quote(c: char) -> bool {
    matches!(c, '"' | '\'' | '`')
}

/// The characters the editor intercepts to auto-close pairs.
pub fn is_pair_char(c: char) -> bool {
    closing_of(c).is_some() || matches!(c, ')' | ']' | '}')
}

/// Whether typing `open` between `prev` and `next` should insert its closing pair too
/// (like VS Code and Zed: before whitespace, a closer or punctuation; quotes not inside words,
/// except after a string prefix such as `f` or `rb`).
fn should_close(open: char, head: &str, next: Option<char>) -> bool {
    let next_ok = match next {
        None => true,
        Some(n) => n.is_whitespace() || matches!(n, ')' | ']' | '}' | ',' | ';' | ':'),
    };
    if !next_ok {
        return false;
    }
    if !is_quote(open) {
        return true;
    }
    let word: String = head
        .chars()
        .rev()
        .take_while(|c| c.is_alphanumeric() || *c == '_')
        .collect();
    let prefix = matches!(
        word.to_lowercase().as_str(),
        "f" | "r" | "b" | "u" | "rb" | "br" | "fr" | "rf" | "t"
    );
    let prev = head.chars().last();
    (word.is_empty() || prefix) && prev != Some(open)
}

pub fn hash_of(bytes: &[u8]) -> u64 {
    hash(bytes)
}

fn hash<T: Hash + ?Sized>(value: &T) -> u64 {
    let mut hasher = std::collections::hash_map::DefaultHasher::new();
    value.hash(&mut hasher);
    hasher.finish()
}

fn paragraph(
    content: &str,
    font: Font,
    size: f32,
    line_height: f32,
    width: Option<f32>,
) -> Paragraph {
    Paragraph::with_text(core_text::Text {
        content,
        bounds: Size::new(width.unwrap_or(f32::INFINITY), f32::INFINITY),
        size: Pixels(size),
        line_height: LineHeight::Absolute(Pixels(line_height)),
        font,
        align_x: core_text::Alignment::Default,
        align_y: iced::alignment::Vertical::Top,
        shaping: core_text::Shaping::Advanced,
        wrapping: if width.is_some() {
            Wrapping::WordOrGlyph
        } else {
            Wrapping::None
        },
    })
}

impl Measure {
    fn reset_if(&mut self, key: u64) {
        if self.key != key {
            self.key = key;
            self.widths.clear();
            self.rows.clear();
        }
        // Keep memory bounded for long editing sessions.
        if self.widths.len() > 50_000 {
            self.widths.clear();
        }
        if self.rows.len() > 50_000 {
            self.rows.clear();
        }
    }

    fn width(&mut self, line: &str, font: Font, size: f32, lh: f32) -> f32 {
        if line.is_empty() {
            return 0.0;
        }
        *self
            .widths
            .entry(hash(line))
            .or_insert_with(|| paragraph(line, font, size, lh, None).min_bounds().width)
    }

    fn rows(&mut self, line: &str, font: Font, size: f32, lh: f32, width: f32) -> u32 {
        if line.is_empty() {
            return 1;
        }
        *self.rows.entry(hash(line)).or_insert_with(|| {
            let height = paragraph(line, font, size, lh, Some(width))
                .min_bounds()
                .height;
            ((height / lh).round() as u32).max(1)
        })
    }
}

/// Result of applying an action to an editor.
pub struct Outcome {
    pub edited: bool,
    pub cursor_moved: bool,
    pub cursor: (usize, usize),
    pub text: String,
    pub scroll: Task<Message>,
    /// The name of the editor action that ran (for `on_action`).
    pub action: Option<&'static str>,
    /// Text to put in the clipboard (copy and cut with several cursors).
    pub clipboard: Option<String>,
}

pub fn scroll_id(id: &str) -> String {
    format!("{id}::scroll")
}

impl EditorState {
    pub fn perform(&mut self, id: &str, action: text_editor::Action) -> Outcome {
        use text_editor::{Action, Edit};
        let before = self.real_position(self.content.cursor().position);
        let is_edit = action.is_edit();
        let follows = !matches!(action, Action::Scroll { .. });
        let mut edited = is_edit;
        match action {
            Action::Click(_) if self.modifiers.get().alt() => self.alt_click(action),
            Action::Click(_) | Action::SelectAll => {
                self.extra.clear();
                self.content.perform(action);
            }
            Action::Edit(edit) => {
                let committed = self.ime_commit.take();
                let kind = match &edit {
                    Edit::Insert(c) if c.is_alphanumeric() || *c == '_' => EditKind::Typing,
                    // Text from an input method (Chinese, Japanese, Korean...) arrives as a paste.
                    Edit::Paste(_) if committed => EditKind::Typing,
                    Edit::Backspace | Edit::Delete if self.content.cursor().selection.is_none() => {
                        EditKind::Deleting
                    }
                    _ => EditKind::Other,
                };
                self.record(kind);
                edited = match edit {
                    Edit::Paste(text) => self.paste(text),
                    edit => self.each_cursor(|s, _| s.perform_one(Action::Edit(edit.clone()))),
                };
                if !edited {
                    self.unrecord();
                }
            }
            Action::Move(_) | Action::Select(_) if !self.extra.is_empty() => {
                self.each_cursor(|s, _| s.perform_one(action.clone()));
            }
            action => self.content.perform(action),
        }
        self.outcome(id, before, edited, follows)
    }

    /// Alt+click adds a cursor where it clicks, or removes the cursor that is there.
    fn alt_click(&mut self, action: text_editor::Action) {
        self.remember_selections();
        let previous = self.primary();
        self.content.perform(action);
        let clicked = self.content.cursor().position;
        if let Some(i) = self.extra.iter().position(|c| c.position == clicked) {
            self.extra.remove(i);
            self.set_cursor(previous);
        } else if clicked == previous.position {
            if let Some(next) = self.extra.pop() {
                self.set_cursor(next);
            }
        } else {
            self.extra.push(previous);
        }
    }

    /// Applies one action to the primary cursor, keeping the folds intact; `true` if it edited.
    fn perform_one(&mut self, action: text_editor::Action) -> bool {
        use text_editor::{Action, Edit};
        let is_edit = action.is_edit();
        if is_edit {
            let cursor = self.content.cursor();
            let column = cursor.position.column;
            let len = self
                .content
                .line(cursor.position.line)
                .map(|l| l.text.chars().count())
                .unwrap_or(0);
            let safe = cursor.selection.is_none()
                && match &action {
                    Action::Edit(Edit::Insert(c)) => *c != '\n',
                    Action::Edit(Edit::Paste(text)) => !text.contains('\n'),
                    Action::Edit(Edit::Backspace) => column > 0,
                    Action::Edit(Edit::Delete) => column < len,
                    Action::Edit(Edit::Indent | Edit::Unindent) => true,
                    _ => false,
                };
            let edit = self.begin_edit(safe);
            self.content.perform(action);
            self.end_edit(edit);
        } else {
            self.content.perform(action);
        }
        is_edit
    }

    /// Keys the editor handles itself, computed on the text as it is when the key arrives.
    ///
    /// With `size` (Python-style indentation) Tab inserts spaces up to the next multiple of
    /// `size`, Enter keeps the indentation (one level more after `:`) and Backspace in leading
    /// spaces removes a whole level. With `pairs`, typing an opening bracket or quote also
    /// inserts its closing one (or wraps the selection), typing a closer that is already next
    /// steps over it, Backspace between an empty pair deletes both and Enter between brackets
    /// opens an indented line.
    pub fn key(&mut self, id: &str, key: EditKey, size: Option<usize>, pairs: bool) -> Outcome {
        let before = self.real_position(self.content.cursor().position);
        let kind = match key {
            EditKey::Char(_) => EditKind::Typing,
            EditKey::Backspace => EditKind::Deleting,
            EditKey::Tab | EditKey::Enter => EditKind::Other,
        };
        let text = self.content.text();
        self.record(kind);
        let mut edited = self.each_cursor(|s, _| s.key_one(key, size, pairs));
        // Typing a closer that is already there steps over it.
        if edited && self.content.text() == text {
            edited = false;
        }
        if !edited {
            self.unrecord();
        }
        self.outcome(id, before, edited, true)
    }

    fn key_one(&mut self, key: EditKey, size: Option<usize>, pairs: bool) -> bool {
        use text_editor::{Action, Edit};
        let cursor = self.content.cursor();
        let line = self
            .content
            .line(cursor.position.line)
            .map(|l| l.text.into_owned())
            .unwrap_or_default();
        let head: String = line.chars().take(cursor.position.column).collect();
        let column = head.chars().count();
        let prev = head.chars().last();
        let next = line.chars().nth(column);
        let selecting = cursor.selection.is_some();
        let step = size.unwrap_or(4);
        let safe = !selecting
            && match key {
                EditKey::Enter => false,
                EditKey::Backspace => column > 0,
                EditKey::Tab | EditKey::Char(_) => true,
            };
        let edit = self.begin_edit(safe);
        let content = &mut self.content;
        let run = |content: &mut text_editor::Content, action: Action, n: usize| {
            for _ in 0..n {
                content.perform(action.clone());
            }
        };
        let mut edited = true;
        match key {
            EditKey::Tab => run(
                content,
                Action::Edit(Edit::Insert(' ')),
                step - column % step,
            ),
            EditKey::Enter => {
                let mut indent = head.chars().take_while(|c| *c == ' ').count();
                let between = pairs
                    && !selecting
                    && matches!(
                        (prev, next),
                        (Some('('), Some(')')) | (Some('['), Some(']')) | (Some('{'), Some('}'))
                    );
                if size.is_some() && head.trim_end().ends_with(':') || between {
                    indent += step;
                }
                content.perform(Action::Edit(Edit::Enter));
                run(content, Action::Edit(Edit::Insert(' ')), indent);
                if between {
                    content.perform(Action::Edit(Edit::Enter));
                    run(content, Action::Edit(Edit::Insert(' ')), indent - step);
                    content.perform(Action::Move(Motion::Up));
                    content.perform(Action::Move(Motion::End));
                }
            }
            EditKey::Backspace => {
                let pair = pairs
                    && !selecting
                    && prev
                        .and_then(closing_of)
                        .is_some_and(|close| next == Some(close));
                if pair {
                    content.perform(Action::Edit(Edit::Backspace));
                    content.perform(Action::Edit(Edit::Delete));
                } else {
                    let n = if size.is_some()
                        && !selecting
                        && column > 0
                        && head.chars().all(|c| c == ' ')
                    {
                        (column - 1) % step + 1
                    } else {
                        1
                    };
                    run(content, Action::Edit(Edit::Backspace), n);
                }
            }
            EditKey::Char(c) => {
                let close = closing_of(c).filter(|_| pairs);
                if let (Some(close), true) = (close, selecting) {
                    // Wrap the selection, keeping it selected.
                    let selected = content.selection().unwrap_or_default();
                    let wrapped = format!("{c}{selected}{close}");
                    content.perform(Action::Edit(Edit::Paste(Arc::new(wrapped))));
                    content.perform(Action::Move(Motion::Left));
                    run(
                        content,
                        Action::Select(Motion::Left),
                        selected.chars().count(),
                    );
                } else if pairs
                    && !selecting
                    && next == Some(c)
                    && (is_quote(c) || matches!(c, ')' | ']' | '}'))
                {
                    content.perform(Action::Move(Motion::Right));
                    edited = false;
                } else if let Some(close) = close.filter(|_| should_close(c, &head, next)) {
                    content.perform(Action::Edit(Edit::Insert(c)));
                    content.perform(Action::Edit(Edit::Insert(close)));
                    content.perform(Action::Move(Motion::Left));
                } else {
                    content.perform(Action::Edit(Edit::Insert(c)));
                }
            }
        }
        self.end_edit(edit);
        edited
    }

    /// Moves the cursor by a page (iced's own page motion assumes a fixed-height editor).
    pub fn page(&mut self, id: &str, down: bool, select: bool) -> Outcome {
        let before = self.real_position(self.content.cursor().position);
        let lh = self.metrics.borrow().line_height.max(1.0);
        let height = self.viewport.get().map(|v| v.height).unwrap_or(lh * 20.0);
        let lines = ((height / lh).floor() as usize).saturating_sub(1).max(1);
        let motion = if down { Motion::Down } else { Motion::Up };
        self.each_cursor(|s, _| {
            for _ in 0..lines {
                s.content.perform(if select {
                    text_editor::Action::Select(motion)
                } else {
                    text_editor::Action::Move(motion)
                });
            }
            false
        });
        self.outcome(id, before, false, true)
    }

    /// Moves the cursor to a real position, unfolding the fold that hides it.
    pub fn move_to(&mut self, id: &str, position: text_editor::Position) -> Task<Message> {
        let (mut line, mut hidden) = self.visible_line(position.line);
        while hidden && self.unfold(line) {
            (line, hidden) = self.visible_line(position.line);
        }
        self.extra.clear();
        self.set_cursor(text_editor::Cursor {
            position: text_editor::Position {
                line,
                column: position.column,
            },
            selection: None,
        });
        self.autoscroll(id)
    }

    /// Selects real ranges `(line, column, end_line, end_column)` (0-based, exclusive end),
    /// one cursor each; the first one is the primary cursor.
    pub fn select_ranges(&mut self, id: &str, ranges: &[TextRange]) -> Task<Message> {
        if ranges.is_empty() {
            return Task::none();
        }
        for &(line, _, end, _) in ranges {
            for real in [line, end] {
                let (mut visible, mut hidden) = self.visible_line(real);
                while hidden && self.unfold(visible) {
                    (visible, hidden) = self.visible_line(real);
                }
            }
        }
        let cursors = ranges
            .iter()
            .map(|&(line, column, end, end_column)| text_editor::Cursor {
                position: text_editor::Position {
                    line: self.visible_line(end).0,
                    column: end_column,
                },
                selection: Some(text_editor::Position {
                    line: self.visible_line(line).0,
                    column,
                }),
            })
            .collect();
        self.extra.clear();
        self.set_cursors(cursors);
        self.autoscroll(id)
    }

    /// Replaces real ranges `(line, column, end_line, end_column)` with texts, as one undo step.
    pub fn replace_ranges(&mut self, id: &str, edits: &[RangeEdit]) -> Outcome {
        let before = self.real_position(self.content.cursor().position);
        if edits.is_empty() {
            return self.outcome(id, before, false, false);
        }
        let ranges: Vec<_> = edits.iter().map(|(r, _)| *r).collect();
        let _ = self.select_ranges(id, &ranges);
        self.record(EditKind::Other);
        // `each_cursor` visits the cursors in text order through their index.
        let mut texts: Vec<(usize, Arc<String>)> = edits
            .iter()
            .map(|((line, column, _, _), text)| (line * 1_000_000 + column, Arc::new(text.clone())))
            .collect();
        texts.sort_by_key(|(k, _)| *k);
        let edited = self.each_cursor(|s, i| {
            s.perform_one(text_editor::Action::Edit(text_editor::Edit::Paste(
                texts[i].1.clone(),
            )))
        });
        self.extra.clear();
        self.outcome(id, before, edited, true)
    }

    /// `before` is the real cursor position before the change.
    fn outcome(
        &mut self,
        id: &str,
        before: text_editor::Position,
        edited: bool,
        follows: bool,
    ) -> Outcome {
        let after = self.real_position(self.content.cursor().position);
        let cursor_moved = before != after || edited;
        Outcome {
            edited,
            cursor_moved,
            cursor: (after.line, after.column),
            text: if edited { self.text() } else { String::new() },
            scroll: if cursor_moved && follows {
                self.autoscroll(id)
            } else {
                Task::none()
            },
            action: None,
            clipboard: None,
        }
    }

    /// Scrolls just enough to reveal the cursor (like Zed's autoscroll).
    fn autoscroll(&self, id: &str) -> Task<Message> {
        let metrics = self.metrics.borrow();
        let Some(viewport) = self.viewport.get() else {
            return Task::none();
        };
        if !metrics.ready {
            return Task::none();
        }
        let position = self.content.cursor().position;
        let lh = metrics.line_height;
        let line = self
            .content
            .line(position.line)
            .map(|l| l.text.into_owned())
            .unwrap_or_default();
        let prefix: String = line.chars().take(position.column).collect();
        let mut measure = self.measure.borrow_mut();
        let row_start = metrics
            .starts
            .get(position.line)
            .copied()
            .unwrap_or(position.line as u32);
        let intra = match metrics.wrap_width {
            Some(width) if !prefix.is_empty() => {
                // Rows taken by the text before the cursor, minus the row it is on.
                let rows = paragraph(&prefix, metrics.font, metrics.size, lh, Some(width))
                    .min_bounds()
                    .height
                    / lh;
                (rows.round() as u32).saturating_sub(1)
            }
            _ => 0,
        };
        let top = PAD_Y + (row_start + intra) as f32 * lh;
        let bottom = top + lh;
        let margin = lh;
        let y = if top - margin < viewport.y {
            Some((top - margin).max(0.0))
        } else if bottom + margin > viewport.y + viewport.height {
            Some(bottom + margin - viewport.height)
        } else {
            None
        };
        let x = if metrics.wrap_width.is_none() {
            let char_width = metrics.size * 0.6;
            let cx =
                metrics.left + PAD_LEFT + measure.width(&prefix, metrics.font, metrics.size, lh);
            let visible_left = viewport.x + metrics.left + PAD_LEFT;
            let visible_right = viewport.x + viewport.width - PAD_RIGHT;
            if cx - char_width * 4.0 < visible_left {
                Some((cx - metrics.left - PAD_LEFT - char_width * 4.0).max(0.0))
            } else if cx + char_width * 4.0 > visible_right {
                Some(cx + char_width * 4.0 + PAD_RIGHT - viewport.width)
            } else {
                None
            }
        } else {
            None
        };
        if x.is_none() && y.is_none() {
            return Task::none();
        }
        let mut moved = viewport;
        if let Some(x) = x {
            moved.x = x;
        }
        if let Some(y) = y {
            moved.y = y;
        }
        self.viewport.set(Some(moved));
        iced::widget::operation::scroll_to(scroll_id(id), scrollable::AbsoluteOffset { x, y })
    }
}

/// `top` drawn over an opaque `base`.
fn blend(base: Color, top: Color) -> Color {
    let a = top.a;
    Color::from_rgb(
        base.r * (1.0 - a) + top.r * a,
        base.g * (1.0 - a) + top.g * a,
        base.b * (1.0 - a) + top.b * a,
    )
}

fn with_alpha(color: Color, a: f32) -> Color {
    Color {
        a: color.a * a,
        ..color
    }
}

/// Builds the editor element. `state` lives as long as the view (it is owned by the
/// app's caches), so the closure below can borrow it.
pub fn view<'a>(state: &'a EditorState, props: &EditorProps) -> Element<'a, Message> {
    let props = Arc::new(props.clone());
    let bg = props.background;
    let padding = props.layout.padding.unwrap_or(Padding::ZERO);
    let width = props.layout.width.unwrap_or(Length::Fill);
    let mut height = props.layout.height.unwrap_or(Length::Fill);
    if height == Length::Shrink {
        // `responsive` needs a bounded height (it would be infinite inside a scrollable),
        // so a shrinking editor gets a fixed height that fits every line.
        let lines = state.content.line_count().max(1) as f32;
        let bar = if props.wrap { 0.0 } else { 10.0 };
        height = Length::Fixed(
            lines * props.line_height + 2.0 * PAD_Y + bar + padding.top + padding.bottom,
        );
    }
    container(responsive(move |size| body(state, &props, size)))
        .padding(padding)
        .width(width)
        .height(height)
        .style(move |_| container::Style {
            background: bg.map(Background::Color),
            ..Default::default()
        })
        .into()
}

/// The line comment prefix of a language (by file extension or name).
fn comment_prefix(language: &str) -> Option<&'static str> {
    Some(match language.to_lowercase().as_str() {
        "py" | "python" | "pyi" | "sh" | "bash" | "zsh" | "toml" | "yaml" | "yml" | "rb"
        | "ruby" | "r" | "pl" | "perl" | "ini" | "conf" | "dockerfile" | "makefile" | "cmake"
        | "nim" => "#",
        "rs" | "rust" | "js" | "javascript" | "ts" | "typescript" | "jsx" | "tsx" | "c" | "h"
        | "cpp" | "cc" | "hpp" | "cs" | "java" | "kt" | "kotlin" | "go" | "swift" | "dart"
        | "scala" | "zig" | "php" | "json5" | "jsonc" | "proto" | "glsl" | "wgsl" => "//",
        "sql" | "lua" | "hs" | "haskell" | "elm" => "--",
        "tex" | "latex" | "erl" | "erlang" => "%",
        "lisp" | "clj" | "clojure" | "scm" | "el" => ";",
        "vim" => "\"",
        _ => return None,
    })
}

/// What the second key of a Ctrl+K chord does.
enum Chord {
    Fold(FoldOp),
    Action(EditorAction),
}

/// Zed's Ctrl+K chords: Ctrl+K Ctrl+0 folds everything, Ctrl+K Ctrl+J unfolds everything,
/// Ctrl+K Ctrl+L toggles the fold at the cursor, Ctrl+K Ctrl+[ / ] fold and unfold, and
/// Ctrl+K Ctrl+C / Ctrl+U comment and uncomment (toggle).
fn chord_action(press: &text_editor::KeyPress) -> Option<Chord> {
    let keyboard::Key::Character(c) = press.key.as_ref() else {
        return None;
    };
    Some(match c.to_lowercase().as_str() {
        "0" => Chord::Fold(FoldOp::FoldAll),
        "j" => Chord::Fold(FoldOp::UnfoldAll),
        "l" => Chord::Fold(FoldOp::ToggleAtCursor),
        "[" => Chord::Fold(FoldOp::AtCursor),
        "]" => Chord::Fold(FoldOp::UnfoldAtCursor),
        "c" | "u" | "/" => Chord::Action(EditorAction::ToggleComments),
        _ => return None,
    })
}

/// Zed's default editor keys (Linux and Windows, with Cmd in place of Ctrl on macOS).
fn zed_action(press: &text_editor::KeyPress, state: &EditorState) -> Option<EditorAction> {
    use EditorAction as A;
    use keyboard::key::Named;
    let m = press.modifiers;
    let (ctrl, alt, shift) = (m.command(), m.alt(), m.shift());
    match press.key.as_ref() {
        keyboard::Key::Named(named) => Some(match (named, ctrl, alt, shift) {
            // Duplicate lines: Alt+Shift (VS Code) or Ctrl+Alt+Shift (Zed); Ctrl+Alt adds a cursor.
            (Named::ArrowUp, _, true, true) => A::DuplicateLineUp,
            (Named::ArrowDown, _, true, true) => A::DuplicateLineDown,
            (Named::ArrowUp, true, true, false) => A::AddCursorAbove,
            (Named::ArrowDown, true, true, false) => A::AddCursorBelow,
            (Named::ArrowUp, false, true, false) => A::MoveLineUp,
            (Named::ArrowDown, false, true, false) => A::MoveLineDown,
            (Named::ArrowUp, true, false, true) => A::SelectPrevious,
            (Named::ArrowDown, true, false, true) => A::SelectNext,
            (Named::ArrowUp, true, false, false) => A::LineUp,
            (Named::ArrowDown, true, false, false) => A::LineDown,
            (Named::Enter, true, false, false) => A::NewlineBelow,
            (Named::Enter, true, false, true) => A::NewlineAbove,
            (Named::Backspace, true, false, false) => A::DeleteToPreviousWordStart,
            (Named::Delete, true, false, false) => A::DeleteToNextWordEnd,
            (Named::Home, false, false, false) => A::MoveToBeginningOfLine,
            (Named::Home, false, false, true) => A::SelectToBeginningOfLine,
            (Named::Tab, false, false, true) => A::Outdent,
            (Named::Tab, false, false, false) => {
                let c = state.content.cursor();
                let multiline = c.selection.is_some_and(|s| s.line != c.position.line);
                if multiline {
                    A::Indent
                } else {
                    return None;
                }
            }
            (Named::F2, true, false, false) => A::SelectAllMatches,
            (Named::Escape, false, false, false) if state.can_cancel() => A::Cancel,
            _ => return None,
        }),
        keyboard::Key::Character(c) if ctrl => {
            let c = c.to_lowercase();
            Some(match (c.as_str(), alt, shift) {
                ("z", false, false) => A::Undo,
                ("y", false, false) | ("z", false, true) => A::Redo,
                ("d", false, false) => A::SelectNext,
                ("d", false, true) => A::DuplicateSelection,
                ("l", false, true) => A::SelectAllMatches,
                ("l", false, false) => A::SelectLine,
                ("u", false, false) => A::UndoSelection,
                ("k", false, true) => A::DeleteLine,
                ("j", false, true) => A::JoinLines,
                ("/", false, _) => A::ToggleComments,
                ("]", false, false) => A::Indent,
                ("[", false, false) => A::Outdent,
                ("m", false, false) | ("|", false, true) => A::MoveToEnclosingBracket,
                // Copy and cut take whole lines without a selection, and every cursor's text.
                ("c", false, false) | ("x", false, false)
                    if !state.extra.is_empty() || state.content.cursor().selection.is_none() =>
                {
                    if c == "c" { A::Copy } else { A::Cut }
                }
                _ => return None,
            })
        }
        keyboard::Key::Character(c) if alt && shift && !ctrl && c.eq_ignore_ascii_case("i") => {
            Some(A::SplitSelectionIntoLines)
        }
        _ => None,
    }
}

fn key_name(key: keyboard::key::Named) -> Option<&'static str> {
    use keyboard::key::Named;
    Some(match key {
        Named::ArrowUp => "up",
        Named::ArrowDown => "down",
        Named::ArrowLeft => "left",
        Named::ArrowRight => "right",
        Named::Enter => "enter",
        Named::Tab => "tab",
        Named::Escape => "escape",
        Named::PageUp => "pageup",
        Named::PageDown => "pagedown",
        Named::Home => "home",
        Named::End => "end",
        _ => return None,
    })
}

fn numbers<'a>(
    starts: &[u32],
    reals: &[usize],
    range: std::ops::Range<usize>,
    color: Color,
    props: &EditorProps,
) -> Element<'a, Message> {
    let lh = props.line_height;
    let mut content = String::new();
    for n in range.clone() {
        if n > range.start {
            content.push('\n');
        }
        content.push_str(&(reals[n] + 1).to_string());
        let rows = starts[n + 1] - starts[n];
        for _ in 1..rows {
            content.push('\n');
        }
    }
    let rows = starts[range.end] - starts[range.start];
    text(content)
        .font(props.font)
        .size(props.size)
        .line_height(LineHeight::Absolute(Pixels(lh)))
        .color(color)
        .width(Length::Fill)
        .height(Length::Fixed(rows as f32 * lh))
        .align_x(iced::alignment::Horizontal::Right)
        .wrapping(Wrapping::None)
        .into()
}

/// A column of fold chevrons for `lines` (visible lines), each on the first row of its line.
fn chevrons<'a>(
    lines: &[(usize, bool)],
    starts: &[u32],
    props: &Arc<EditorProps>,
    color: Color,
    hover: Color,
) -> Element<'a, Message> {
    let lh = props.line_height;
    let mut col = column![].width(Length::Fixed(FOLD_WIDTH)).padding(Padding {
        top: PAD_Y,
        ..Padding::ZERO
    });
    let mut row_at = 0u32;
    for &(line, folded) in lines {
        let gap = starts[line] - row_at;
        if gap > 0 {
            col = col.push(Space::new().height(Length::Fixed(gap as f32 * lh)));
        }
        let glyph = if folded { CHEVRON_RIGHT } else { CHEVRON_DOWN };
        let message = Message::EditorFold {
            id: props.id.clone(),
            op: FoldOp::Toggle(line),
            on_cursor: props.on_cursor.clone(),
        };
        col = col.push(
            widget::button(
                text(glyph.to_string())
                    .font(ICONS)
                    .size(props.size * 0.8)
                    .line_height(LineHeight::Absolute(Pixels(lh)))
                    .width(Length::Fill)
                    .align_x(iced::alignment::Horizontal::Center),
            )
            .on_press(message)
            .padding(0)
            .width(Length::Fixed(FOLD_WIDTH))
            .height(Length::Fixed(lh))
            .style(move |_, status| widget::button::Style {
                text_color: if matches!(status, widget::button::Status::Hovered) {
                    hover
                } else {
                    color
                },
                ..Default::default()
            }),
        );
        row_at = starts[line] + 1;
    }
    col.into()
}

/// Where a cursor at `position` is drawn, relative to the text area, as
/// `(x, y, glyph under it)`.
fn caret_position(
    _state: &EditorState,
    props: &EditorProps,
    lines: &[String],
    starts: &[u32],
    wrap_width: Option<f32>,
    position: text_editor::Position,
) -> (f32, f32, Option<char>) {
    let lh = props.line_height;
    let line = lines.get(position.line).map_or("", |l| l.as_str());
    let column = actions::floor(line, position.column);
    let prefix = &line[..column];
    let under = line[column..].chars().next();
    let row = starts.get(position.line).copied().unwrap_or(0);
    if prefix.is_empty() {
        return (0.0, row as f32 * lh, under);
    }
    let p = paragraph(prefix, props.font, props.size, lh, wrap_width);
    let rows = ((p.min_bounds().height / lh).round() as usize).max(1);
    let x = p
        .grapheme_position(rows - 1, usize::MAX)
        .map_or(0.0, |p| p.x);
    (x, (row as usize + rows - 1) as f32 * lh, under)
}

/// Where `position` is, relative to the text area (without wrapping the width is cached).
fn point_at(
    props: &EditorProps,
    lines: &[String],
    starts: &[u32],
    wrap_width: Option<f32>,
    measure: &mut Measure,
    position: text_editor::Position,
) -> (f32, f32) {
    let lh = props.line_height;
    let row = starts.get(position.line).copied().unwrap_or(0);
    let line = lines.get(position.line).map_or("", |l| l.as_str());
    let prefix = &line[..actions::floor(line, position.column)];
    match wrap_width {
        None => (
            measure.width(prefix, props.font, props.size, lh),
            row as f32 * lh,
        ),
        Some(_) if prefix.is_empty() => (0.0, row as f32 * lh),
        Some(width) => {
            let p = paragraph(prefix, props.font, props.size, lh, Some(width));
            let rows = ((p.min_bounds().height / lh).round() as usize).max(1);
            let x = p
                .grapheme_position(rows - 1, usize::MAX)
                .map_or(0.0, |p| p.x);
            (x, (row as usize + rows - 1) as f32 * lh)
        }
    }
}

/// The rectangles covering `start..end`, relative to the text layer (`right` is where full
/// rows end).
#[allow(clippy::too_many_arguments)]
fn span(
    props: &EditorProps,
    lines: &[String],
    starts: &[u32],
    wrap_width: Option<f32>,
    measure: &mut Measure,
    start: text_editor::Position,
    end: text_editor::Position,
    right: f32,
) -> Vec<Rectangle> {
    let lh = props.line_height;
    let (x0, y0) = point_at(props, lines, starts, wrap_width, measure, start);
    let (x1, y1) = point_at(props, lines, starts, wrap_width, measure, end);
    let rect = |x: f32, y: f32, w: f32, h: f32| {
        Rectangle::new(
            iced::Point::new(PAD_LEFT + x, PAD_Y + y),
            Size::new(w.max(0.0), h),
        )
    };
    if (y0 - y1).abs() < 0.5 {
        return vec![rect(x0, y0, x1 - x0, lh)];
    }
    let mut out = vec![rect(x0, y0, right - PAD_LEFT - x0, lh)];
    if y1 - y0 > lh + 0.5 {
        out.push(rect(0.0, y0 + lh, right - PAD_LEFT, y1 - y0 - lh));
    }
    out.push(rect(0.0, y1, x1, lh));
    out
}

/// What goes behind the text: search results (`highlights`), the other occurrences of the
/// selected text and the selections of the other cursors.
fn behind_text(
    state: &EditorState,
    props: &EditorProps,
    lines: &[String],
    starts: &[u32],
    wrap_width: Option<f32>,
    measure: &mut Measure,
    right: f32,
) -> Vec<editor_widgets::BoxRect> {
    use text_editor::Position;
    let mut rects = Vec::new();
    let line_count = lines.len();
    let found = props
        .highlight_color
        .unwrap_or(Color::from_rgba(0.95, 0.68, 0.22, 0.3));
    for &(line, column, end_line, end_column) in &props.highlights {
        if line == 0 || end_line == 0 {
            continue;
        }
        let (a, hidden_a) = state.visible_line(line - 1);
        let (b, hidden_b) = state.visible_line(end_line - 1);
        if hidden_a || hidden_b || a >= line_count || b >= line_count {
            continue;
        }
        let start = Position {
            line: a,
            column: column.saturating_sub(1),
        };
        let end = Position {
            line: b,
            column: end_column.saturating_sub(1),
        };
        for bounds in span(props, lines, starts, wrap_width, measure, start, end, right) {
            rects.push(editor_widgets::BoxRect {
                bounds,
                fill: Some(found),
                alpha: 1.0,
                border: None,
            });
        }
    }
    // Zed's selection highlight: the other places with the selected text.
    let primary = state.content.cursor();
    if props.selection_highlight
        && let Some(anchor) = primary.selection
        && anchor.line == primary.position.line
        && anchor != primary.position
    {
        let line = &lines[primary.position.line.min(line_count - 1)];
        let (a, b) = (
            actions::floor(line, anchor.column.min(primary.position.column)),
            actions::floor(line, anchor.column.max(primary.position.column)),
        );
        let needle = &line[a..b];
        if !needle.trim().is_empty() && needle.len() <= 200 {
            let text = lines.join("\n");
            let whole = needle.chars().all(|c| c.is_alphanumeric() || c == '_');
            let own = actions::offset_of(
                lines,
                Position {
                    line: primary.position.line,
                    column: a,
                },
            );
            let mut taken: Vec<usize> = vec![own];
            taken.extend(
                state
                    .extra
                    .iter()
                    .map(|c| actions::offset_of(lines, actions::range(c).0)),
            );
            for start in actions::all_matches(&text, needle, whole)
                .into_iter()
                .filter(|s| !taken.contains(s))
                .take(2000)
            {
                let s = actions::position_at(lines, start);
                let e = actions::position_at(lines, start + needle.len());
                for bounds in span(props, lines, starts, wrap_width, measure, s, e, right) {
                    rects.push(editor_widgets::BoxRect {
                        bounds,
                        fill: props.selection_color,
                        alpha: 0.45,
                        border: None,
                    });
                }
            }
        }
    }
    for c in &state.extra {
        let (s, e) = actions::range(c);
        if s == e {
            continue;
        }
        for bounds in span(props, lines, starts, wrap_width, measure, s, e, right) {
            rects.push(editor_widgets::BoxRect {
                bounds,
                fill: props.selection_color,
                alpha: 1.0,
                border: None,
            });
        }
    }
    rects
}

/// Outlines of the bracket next to the cursor and its match.
fn bracket_boxes(
    state: &EditorState,
    props: &EditorProps,
    lines: &[String],
    starts: &[u32],
    wrap_width: Option<f32>,
    measure: &mut Measure,
) -> Vec<editor_widgets::BoxRect> {
    let cursor = state.content.cursor();
    if cursor.selection.is_some() {
        return Vec::new();
    }
    let text = lines.join("\n");
    let bytes = text.as_bytes();
    let at = actions::offset_of(lines, cursor.position);
    let found = [Some(at), at.checked_sub(1)]
        .into_iter()
        .flatten()
        .find_map(|i| actions::matching_bracket(bytes, i).map(|m| (i, m)));
    let Some((a, b)) = found else {
        return Vec::new();
    };
    let tint = props
        .text_color
        .unwrap_or(Color::from_rgb8(0xd0, 0xd4, 0xda));
    [a, b]
        .into_iter()
        .map(|i| {
            let s = actions::position_at(lines, i);
            let e = text_editor::Position {
                line: s.line,
                column: s.column + 1,
            };
            let (x0, y) = point_at(props, lines, starts, wrap_width, measure, s);
            let (x1, _) = point_at(props, lines, starts, wrap_width, measure, e);
            editor_widgets::BoxRect {
                bounds: Rectangle::new(
                    iced::Point::new(PAD_LEFT + x0, PAD_Y + y + 1.0),
                    Size::new((x1 - x0).max(2.0), props.line_height - 2.0),
                ),
                fill: Some(tint),
                alpha: 0.08,
                border: Some(with_alpha(tint, 0.45)),
            }
        })
        .collect()
}

fn body<'a>(state: &'a EditorState, props: &Arc<EditorProps>, size: Size) -> Element<'a, Message> {
    let lh = props.line_height;
    let line_count = state.content.line_count().max(1);
    let cursor_line = state.content.cursor().position.line.min(line_count - 1);
    // The minimap sits left of the vertical scrollbar, so it reserves the bar's width too.
    let bar_width = if props.scrollbar { SCROLLBAR } else { 0.0 };
    let minimap_width = props.minimap.map_or(0.0, |m| m.width + bar_width);

    // Real line number of each visible line.
    let mut reals = Vec::with_capacity(line_count);
    {
        let mut folds = state.folds.iter().peekable();
        let mut offset = 0;
        for i in 0..line_count {
            reals.push(i + offset);
            while let Some(fold) = folds.next_if(|f| f.header == i) {
                offset += fold.hidden.len();
            }
        }
    }

    let gutter_width = if props.gutter {
        let digits = (reals[line_count - 1] + 1).to_string().len().max(2) as f32;
        props
            .gutter_width
            .unwrap_or(digits * props.size * 0.62 + 28.0)
    } else {
        0.0
    };
    let left = if props.gutter {
        MARKER_WIDTH + gutter_width
    } else {
        0.0
    };
    let wrap_width = props
        .wrap
        .then(|| (size.width - left - PAD_LEFT - PAD_RIGHT - minimap_width).max(props.size * 4.0));

    // Measure every line once (results are cached per line text).
    let mut starts = Vec::with_capacity(line_count + 1);
    starts.push(0u32);
    let mut max_width = 0.0f32;
    let mut lines: Vec<String> = Vec::with_capacity(line_count);
    {
        let mut measure = state.measure.borrow_mut();
        measure.reset_if(hash(&(
            props.font,
            props.size.to_bits(),
            lh.to_bits(),
            wrap_width.map(f32::to_bits),
        )));
        let mut total = 0u32;
        for line in state.content.lines() {
            let rows = match wrap_width {
                Some(width) => measure.rows(&line.text, props.font, props.size, lh, width),
                None => {
                    max_width =
                        max_width.max(measure.width(&line.text, props.font, props.size, lh));
                    1
                }
            };
            total += rows;
            starts.push(total);
            lines.push(line.text.into_owned());
        }
        while starts.len() < line_count + 1 {
            total += 1;
            starts.push(total);
            lines.push(String::new());
        }
    }

    let editor_width = match wrap_width {
        Some(_) => (size.width - left - minimap_width).max(1.0),
        None => (max_width + PAD_LEFT + PAD_RIGHT + props.size * 2.0)
            .max(size.width - left - minimap_width),
    };

    *state.metrics.borrow_mut() = Metrics {
        ready: true,
        left,
        line_height: lh,
        size: props.size,
        font: props.font,
        wrap_width,
        starts: starts.clone(),
    };

    let id = props.id.clone();
    let on_change = props.on_change.clone();
    let on_cursor = props.on_cursor.clone();
    let (sel, placeholder_color) = (props.selection_color, props.placeholder_color);

    let theme_id = highlighter::theme_id(&props.syntax);
    let token = if highlighter::has_syntax(&props.language) {
        props.language.clone()
    } else {
        "txt".into()
    };

    let page_id = props.id.clone();
    let page_cursor = props.on_cursor.clone();
    let indent_size = props.tab_size;
    let pairs = props.auto_close;
    let folding = props.folding;
    let readonly = props.readonly;
    let key_props = props.clone();
    let capture = props.capture_keys.clone();
    // Captured keys with modifiers (`"alt-z"`) are left to the app only with exactly those modifiers.
    let capture_strokes: Vec<keymap::Keystroke> = capture
        .iter()
        .filter(|k| k.contains(['-', '+']))
        .filter_map(|k| keymap::Keystroke::parse(k))
        .collect();
    let ctx = Arc::new(ActionContext {
        size: props.tab_size,
        pairs: props.auto_close,
        comment: comment_prefix(&props.language).map(Arc::from),
        on_change: props.on_change.clone(),
        on_cursor: props.on_cursor.clone(),
        on_action: props.on_action.clone(),
    });
    *state.context.borrow_mut() = Some(ctx.clone());
    let focused = &state.focused;
    let (editor_bg, active_line) = (props.background, props.active_line);
    let mut editor = widget::text_editor(&state.content)
        .id(props.id.to_string())
        .font(props.font)
        .size(props.size)
        .line_height(LineHeight::Absolute(Pixels(lh)))
        .padding(Padding {
            top: PAD_Y,
            bottom: PAD_Y,
            left: PAD_LEFT,
            right: PAD_RIGHT,
        })
        .width(editor_width)
        .wrapping(if props.wrap {
            Wrapping::WordOrGlyph
        } else {
            Wrapping::None
        })
        .height(Length::Shrink)
        .on_action(move |action| {
            if readonly && action.is_edit() {
                return Message::Noop;
            }
            Message::Editor {
                id: id.clone(),
                action,
                on_change: on_change.clone(),
                on_cursor: on_cursor.clone(),
            }
        })
        .key_binding(move |press| {
            let props = &key_props;
            if readonly {
                // Selecting and copying only: the edits these keys make are dropped by `on_action`.
                return Binding::from_key_press(press);
            }
            let page = |down: bool, select: bool| {
                Some(Binding::Custom(Message::EditorPage {
                    id: page_id.clone(),
                    down,
                    select,
                    on_cursor: page_cursor.clone(),
                }))
            };
            let edit = |key: EditKey| {
                Some(Binding::Custom(Message::EditorIndent {
                    id: props.id.clone(),
                    key,
                    size: indent_size,
                    pairs,
                    on_change: props.on_change.clone(),
                    on_cursor: props.on_cursor.clone(),
                }))
            };
            if !matches!(press.status, text_editor::Status::Focused { .. }) {
                return Binding::from_key_press(press);
            }
            let plain =
                !(press.modifiers.control() || press.modifiers.alt() || press.modifiers.logo());
            // Shift+Enter always breaks the line, even when the app takes Enter (a chat box sends with it).
            let shift_enter = press.modifiers.shift()
                && press.key == keyboard::Key::Named(keyboard::key::Named::Enter);
            if let keyboard::Key::Named(named) = press.key.as_ref()
                && plain
                && !shift_enter
                && capture.iter().any(|k| key_name(named) == Some(k.as_str()))
            {
                return None;
            }
            if capture_strokes.iter().any(|k| k.matches(&press)) {
                return None;
            }
            let run = |action: EditorAction| {
                Some(Binding::Custom(Message::EditorAction {
                    id: props.id.clone(),
                    action,
                    ctx: ctx.clone(),
                }))
            };
            let fold = |op: FoldOp| {
                Some(Binding::Custom(Message::EditorFold {
                    id: props.id.clone(),
                    op,
                    on_cursor: props.on_cursor.clone(),
                }))
            };
            if matches!(
                press.key.as_ref(),
                keyboard::Key::Named(
                    keyboard::key::Named::Control
                        | keyboard::key::Named::Shift
                        | keyboard::key::Named::Alt
                        | keyboard::key::Named::Super
                )
            ) {
                return Binding::from_key_press(press);
            }
            let target = |target: Option<keymap::Target>| match target {
                Some(keymap::Target::Action(action)) => run(action),
                Some(keymap::Target::Fold(op)) if folding => fold(op),
                _ => Some(Binding::Custom(Message::Noop)),
            };
            if state.chord.replace(false) {
                // Second key of a Ctrl+K chord.
                if let Some(bound) = keymap::lookup(&props.keymap, &press, true) {
                    return target(bound);
                }
                let action = chord_action(&press);
                return match action {
                    Some(Chord::Fold(op)) if folding => fold(op),
                    Some(Chord::Action(action)) => run(action),
                    _ => Some(Binding::Custom(Message::Noop)),
                };
            }
            match keymap::lookup(&props.keymap, &press, false) {
                Some(None) => return Binding::from_key_press(press),
                Some(bound) => return target(bound),
                None => {}
            }
            if press.modifiers.command()
                && !press.modifiers.alt()
                && !press.modifiers.shift()
                && matches!(press.key.as_ref(), keyboard::Key::Character("k"))
            {
                state.chord.set(true);
                return Some(Binding::Custom(Message::Noop));
            }
            if let Some(action) = zed_action(&press, state) {
                return run(action);
            }
            let select = press.modifiers.shift();
            // Zoom (Ctrl/Cmd with + - 0) and folding (Ctrl/Cmd+Shift with [ ]).
            if press.modifiers.command()
                && !press.modifiers.alt()
                && let keyboard::Key::Character(c) = press.key.as_ref()
            {
                if let Some(cb) = &props.on_zoom {
                    let step = match c {
                        "=" | "+" => Some(1.0),
                        "-" | "_" => Some(-1.0),
                        "0" => Some(0.0),
                        _ => None,
                    };
                    if let Some(step) = step {
                        return Some(Binding::Custom(Message::Slide(cb.clone(), step)));
                    }
                }
                if folding && select {
                    let op = match c {
                        "[" | "{" => Some(FoldOp::AtCursor),
                        "]" | "}" => Some(FoldOp::UnfoldAtCursor),
                        _ => None,
                    };
                    if let Some(op) = op {
                        return Some(Binding::Custom(Message::EditorFold {
                            id: props.id.clone(),
                            op,
                            on_cursor: props.on_cursor.clone(),
                        }));
                    }
                }
            }
            match press.key.as_ref() {
                keyboard::Key::Named(keyboard::key::Named::PageDown) => page(true, select),
                keyboard::Key::Named(keyboard::key::Named::PageUp) => page(false, select),
                keyboard::Key::Named(named) if plain && !select => match named {
                    keyboard::key::Named::Tab if indent_size.is_some() => edit(EditKey::Tab),
                    keyboard::key::Named::Enter if indent_size.is_some() || pairs => {
                        edit(EditKey::Enter)
                    }
                    keyboard::key::Named::Backspace if indent_size.is_some() || pairs => {
                        edit(EditKey::Backspace)
                    }
                    _ => Binding::from_key_press(press),
                },
                _ if pairs && plain => {
                    let typed = press.text.as_deref().and_then(|t| {
                        let mut chars = t.chars();
                        chars.next().filter(|_| chars.next().is_none())
                    });
                    match typed {
                        Some(c) if is_pair_char(c) => edit(EditKey::Char(c)),
                        _ => Binding::from_key_press(press),
                    }
                }
                _ => Binding::from_key_press(press),
            }
        })
        .style(move |theme: &Theme, status| {
            focused.set(matches!(status, text_editor::Status::Focused { .. }));
            let mut out = text_editor::default(theme, status);
            out.background = Background::Color(Color::TRANSPARENT);
            out.border = Border::default();
            // The cursor is drawn by `Caret`. iced draws its own in `value`, which only matters
            // for its alpha (it scales the text's) since every highlight span sets a color, so
            // it gets the color under the cursor (the active line over the background).
            let base = editor_bg.unwrap_or(theme.palette().background);
            out.value = match active_line {
                Some(band) => blend(base, band),
                None => Color { a: 1.0, ..base },
            };
            if let Some(c) = sel {
                out.selection = c;
            }
            if let Some(c) = placeholder_color {
                out.placeholder = c;
            }
            out
        });
    if let Some(p) = &props.placeholder {
        editor = editor.placeholder(p.clone());
    }
    let editor = editor.highlight_with::<Highlighter>(
        highlighter::Settings {
            token: token.clone(),
            theme: theme_id,
            font: props.font,
            default: props.text_color,
        },
        highlighter::Highlight::to_format,
    );

    let total_height = 2.0 * PAD_Y + starts[starts.len() - 1] as f32 * lh;
    let mut layers: Vec<Element<'a, Message>> = Vec::new();

    // The active line is highlighted with a band drawn underneath the text. The band is there (and
    // transparent) without `active_line` too: a stack takes the size of its first child, so it gives
    // the editor its size; without it the stack would shrink to nothing and the text would not show.
    {
        let band_color = props.active_line;
        let top = PAD_Y + starts[cursor_line] as f32 * lh;
        let rows = starts[cursor_line + 1] - starts[cursor_line];
        let band = column![
            Space::new().height(Length::Fixed(top)),
            container(Space::new())
                .width(Length::Fixed(editor_width))
                .height(Length::Fixed(rows as f32 * lh))
                .style(move |_| container::Style {
                    background: band_color.map(Background::Color),
                    ..Default::default()
                }),
        ]
        .height(Length::Fixed(total_height));
        layers.push(band.into());
    }
    let right = editor_width - PAD_RIGHT;
    {
        let mut measure = state.measure.borrow_mut();
        let rects = behind_text(
            state,
            props,
            &lines,
            &starts,
            wrap_width,
            &mut measure,
            right,
        );
        // Always there, even empty, so the editor's widget state (its focus) keeps its place.
        layers.push(Boxes { rects }.into());
    }
    layers.push(editor.into());

    // Visible whitespace: a copy of the text where only spaces and tabs are drawn.
    if let (Some(color), None) = (props.whitespace, wrap_width) {
        let mut dots = String::new();
        for (i, line) in lines.iter().enumerate() {
            if i > 0 {
                dots.push('\n');
            }
            let mut col = 0usize;
            for ch in line.chars() {
                match ch {
                    ' ' => {
                        dots.push('·');
                        col += 1;
                    }
                    '\t' => {
                        // cosmic-text puts tab stops every 8 columns.
                        let next = (col / 8 + 1) * 8;
                        dots.push('→');
                        dots.extend(std::iter::repeat_n(' ', next - col - 1));
                        col = next;
                    }
                    _ => {
                        dots.push(' ');
                        col += 1;
                    }
                }
            }
        }
        layers.push(
            container(
                text(dots)
                    .font(props.font)
                    .size(props.size)
                    .line_height(LineHeight::Absolute(Pixels(lh)))
                    .color(color)
                    .wrapping(Wrapping::None),
            )
            .padding(Padding {
                top: PAD_Y,
                bottom: PAD_Y,
                left: PAD_LEFT,
                right: PAD_RIGHT,
            })
            .into(),
        );
    }

    let fallback = props
        .gutter_color
        .unwrap_or(Color::from_rgb8(0x6b, 0x72, 0x80));
    let mut measure = state.measure.borrow_mut();
    // Where a note goes after line `index`: after its last glyph, or right-aligned on the last
    // row of a wrapped line.
    let end_of = |measure: &mut Measure, index: usize, extra: f32, label_width: f32| {
        let rows = starts[index + 1] - starts[index];
        match wrap_width {
            Some(width) if rows > 1 => (PAD_LEFT + width - label_width, starts[index + 1] - 1),
            _ => (
                PAD_LEFT
                    + measure.width(&lines[index], props.font, props.size, lh)
                    + props.size * 0.6
                    + extra,
                starts[index],
            ),
        }
    };

    // Folded lines end with a `⋯` button that unfolds them.
    let fold_marker = props.size * 2.2;
    for fold in &state.folds {
        let (x, y) = end_of(&mut measure, fold.header, 0.0, fold_marker);
        let id = props.id.clone();
        let on_cursor = props.on_cursor.clone();
        let tint = props.text_color.unwrap_or(fallback);
        layers.push(
            widget::pin(
                widget::button(
                    text("⋯")
                        .font(props.font)
                        .size(props.size)
                        .line_height(LineHeight::Absolute(Pixels(lh - 4.0)))
                        .align_x(iced::alignment::Horizontal::Center),
                )
                .on_press(Message::EditorFold {
                    id,
                    op: FoldOp::Toggle(fold.header),
                    on_cursor,
                })
                .padding(0)
                .width(Length::Fixed(fold_marker))
                .height(Length::Fixed(lh - 4.0))
                .style(move |_, status| {
                    let a = if matches!(status, widget::button::Status::Hovered) {
                        0.3
                    } else {
                        0.16
                    };
                    widget::button::Style {
                        background: Some(Background::Color(with_alpha(tint, a))),
                        text_color: with_alpha(tint, 0.8),
                        border: Border::default().rounded(4.0),
                        ..Default::default()
                    }
                }),
            )
            .x(x)
            .y(PAD_Y + y as f32 * lh + 2.0)
            .into(),
        );
    }

    // End-of-line annotations (diagnostics, code lens), placed after the last glyph.
    for (line, label, color) in &props.annotations {
        if *line == 0 || label.is_empty() {
            continue;
        }
        let (index, hidden) = state.visible_line(line - 1);
        if hidden || index >= line_count {
            continue;
        }
        let extra = if state.is_folded(index) {
            fold_marker + props.size * 0.6
        } else {
            props.size * 1.4
        };
        let label_width = measure.width(label, props.font, props.size * 0.9, lh);
        let (x, y) = end_of(&mut measure, index, extra, label_width);
        layers.push(
            widget::pin(
                text(label.clone())
                    .font(props.font)
                    .size(props.size * 0.9)
                    .line_height(LineHeight::Absolute(Pixels(lh)))
                    .color(color.unwrap_or(fallback))
                    .wrapping(Wrapping::None),
            )
            .x(x)
            .y(PAD_Y + y as f32 * lh)
            .into(),
        );
    }

    // The bracket matching the one next to the cursor.
    if props.match_brackets {
        let rects = bracket_boxes(state, props, &lines, &starts, wrap_width, &mut measure);
        if !rects.is_empty() {
            layers.push(Boxes { rects }.into());
        }
    }

    // The cursors, drawn by us so they can take any shape.
    let caret_color = props
        .cursor
        .color
        .or(props.text_color)
        .unwrap_or(Color::WHITE);
    let primary = state.content.cursor();
    let mut carets = vec![(primary.position, primary.selection.is_some())];
    carets.extend(
        state
            .extra
            .iter()
            .map(|c| (c.position, c.selection.is_some_and(|s| s != c.position))),
    );
    for (position, selecting) in carets {
        let (cx, cy, under) = caret_position(state, props, &lines, &starts, wrap_width, position);
        let char_width = under
            .filter(|c| !c.is_whitespace())
            .map(|c| measure.width(&c.to_string(), props.font, props.size, lh))
            .unwrap_or(props.size * 0.6)
            .max(props.size * 0.3);
        layers.push(
            Caret {
                state,
                origin: iced::Point::new(PAD_LEFT + cx, PAD_Y + cy),
                char_width,
                line_height: lh,
                shape: props.cursor.shape,
                width: props.cursor.width,
                blink: props.cursor.blink,
                color: caret_color,
                under: under.filter(|c| !c.is_whitespace()),
                under_color: props.background.unwrap_or(Color::BLACK),
                font: props.font,
                size: props.size,
                selecting,
            }
            .into(),
        );
    }
    drop(measure);

    let code: Element<'a, Message> = widget::Stack::with_children(layers).into();

    let body: Element<'_, Message> = if props.gutter {
        let dim = props
            .gutter_color
            .unwrap_or(Color::from_rgb8(0x4e, 0x5a, 0x5f));
        let active = props
            .gutter_active_color
            .unwrap_or(Color::from_rgb8(0xd0, 0xd4, 0xda));
        let numbers_width = if folding {
            gutter_width - FOLD_WIDTH
        } else {
            gutter_width
        };
        let mut gutter = column![]
            .width(Length::Fixed(numbers_width))
            .padding(Padding {
                top: PAD_Y,
                bottom: PAD_Y,
                left: 0.0,
                right: if folding { 4.0 } else { 14.0 },
            });
        if cursor_line > 0 {
            gutter = gutter.push(numbers(&starts, &reals, 0..cursor_line, dim, props));
        }
        gutter = gutter.push(numbers(
            &starts,
            &reals,
            cursor_line..cursor_line + 1,
            active,
            props,
        ));
        if cursor_line + 1 < line_count {
            gutter = gutter.push(numbers(
                &starts,
                &reals,
                cursor_line + 1..line_count,
                dim,
                props,
            ));
        }

        // Git-style change markers drawn as thin bars on the left edge of the gutter.
        let mut markers: Vec<(usize, Color)> = props
            .markers
            .iter()
            .filter(|(line, _)| *line > 0)
            .filter_map(|(line, color)| {
                let (index, hidden) = state.visible_line(line - 1);
                (!hidden).then_some((index + 1, *color))
            })
            .collect();
        markers.sort_by_key(|(line, _)| *line);
        let mut bars = column![]
            .width(Length::Fixed(MARKER_WIDTH))
            .padding(Padding {
                top: PAD_Y,
                ..Padding::ZERO
            });
        let mut next = 1usize;
        for (line, color) in markers {
            if line < next || line > line_count {
                continue;
            }
            if line > next {
                let gap = starts[line - 1] - starts[next - 1];
                bars = bars.push(Space::new().height(Length::Fixed(gap as f32 * lh)));
            }
            let rows = starts[line] - starts[line - 1];
            bars = bars.push(
                container(Space::new())
                    .width(Length::Fixed(MARKER_WIDTH))
                    .height(Length::Fixed(rows as f32 * lh))
                    .style(move |_| container::Style {
                        background: Some(Background::Color(color)),
                        ..Default::default()
                    }),
            );
            next = line + 1;
        }
        let gutter: Element<'a, Message> = if folding {
            // Folded lines always show their chevron; the others only while hovering the gutter.
            let mut folded = Vec::new();
            let mut foldable = Vec::new();
            let indents: Vec<Option<usize>> = lines.iter().map(|l| indent_of(l)).collect();
            let mut next_indent: Option<usize> = None;
            let mut can_fold = vec![false; line_count];
            for i in (0..line_count).rev() {
                if let (Some(own), Some(below)) = (indents[i], next_indent) {
                    can_fold[i] = below > own;
                }
                if indents[i].is_some() {
                    next_indent = indents[i];
                }
            }
            for (i, foldable_line) in can_fold.into_iter().enumerate() {
                if state.is_folded(i) {
                    folded.push((i, true));
                } else if foldable_line {
                    foldable.push((i, false));
                }
            }
            let hover = active;
            let left_part = MARKER_WIDTH + numbers_width;
            widget::hover(
                row![bars, gutter, chevrons(&folded, &starts, props, dim, hover)],
                row![
                    Space::new().width(Length::Fixed(left_part)),
                    chevrons(&foldable, &starts, props, dim, hover)
                ],
            )
        } else {
            row![bars, gutter].into()
        };
        let gutter_bg = props.background.or(Some(Color::TRANSPARENT));
        StickyLeft::new(gutter, code, gutter_bg).into()
    } else {
        code
    };

    let bar = if props.scrollbar {
        scrollable::Scrollbar::new()
            .width(SCROLLBAR)
            .scroller_width(SCROLLBAR)
    } else {
        scrollable::Scrollbar::hidden()
    };
    let direction = if props.wrap {
        scrollable::Direction::Vertical(bar)
    } else {
        scrollable::Direction::Both {
            vertical: bar,
            horizontal: bar,
        }
    };
    let scroller_color = props.scrollbar_color;
    let mut scroller = widget::Scrollable::with_direction(
        Probe::new(body, &state.viewport).keep_wheel(),
        direction,
    )
    .id(scroll_id(&props.id));
    if let Some(cb) = props.on_scroll.clone() {
        scroller = scroller.on_scroll(move |viewport| Message::Scrolled(cb.clone(), viewport));
    }
    let scroller: Element<'a, Message> = scroller
        .style(move |theme: &Theme, status| {
            let mut out = scrollable::default(theme, status);
            let color = scroller_color.unwrap_or(with_alpha(
                theme.extended_palette().background.strong.color,
                0.6,
            ));
            for rail in [&mut out.vertical_rail, &mut out.horizontal_rail] {
                rail.background = None;
                rail.border = Border::default();
                rail.scroller.background = Background::Color(color);
                rail.scroller.border = Border::default();
            }
            out
        })
        .width(Length::Fill)
        .height(Length::Fill)
        .into();

    let scroller: Element<'a, Message> =
        EditorInput::new(scroller, state, props.on_zoom.clone()).into();
    match props.minimap {
        Some(minimap) => {
            update_minimap(state, &lines, &token, theme_id, props);
            // Over the right edge of the scrollable, just left of its vertical scrollbar (a `row`
            // would give the scrollable finite limits and let the gutter fill them).
            let bar = if props.wrap || !props.scrollbar {
                0.0
            } else {
                SCROLLBAR
            };
            let height = (size.height - bar).max(0.0);
            let minimap = Minimap {
                state,
                id: props.id.clone(),
                width: minimap.width,
                height,
                line_height: lh,
                thumb: minimap.thumb,
                background: props.background,
            };
            widget::Stack::with_children([
                scroller,
                widget::pin(minimap)
                    .x((size.width - minimap_width).max(0.0))
                    .into(),
            ])
            .width(Length::Fill)
            .height(Length::Fill)
            .into()
        }
        None => scroller,
    }
}

/// Recomputes the minimap's colored runs when the visible text or the theme changed.
fn update_minimap(
    state: &EditorState,
    lines: &[String],
    token: &str,
    theme_id: u64,
    props: &EditorProps,
) {
    use iced::advanced::text::Highlighter as _;
    let mut hasher = std::collections::hash_map::DefaultHasher::new();
    lines.hash(&mut hasher);
    token.hash(&mut hasher);
    theme_id.hash(&mut hasher);
    let key = hasher.finish();
    let mut cache = state.minimap.borrow_mut();
    if cache.key == key && !cache.lines.is_empty() {
        return;
    }
    let mut highlighter = Highlighter::new(&highlighter::Settings {
        token: token.to_owned(),
        theme: theme_id,
        font: props.font,
        default: props.text_color,
    });
    let fallback = props.text_color.unwrap_or(Color::WHITE);
    cache.key = key;
    cache.lines = lines
        .iter()
        .map(|line| {
            let mut runs: Vec<(u16, u16, Color)> = Vec::new();
            // Byte offset -> column, with tabs every 4 columns.
            let mut columns = Vec::with_capacity(line.len() + 1);
            let mut col = 0u16;
            for (i, ch) in line.char_indices() {
                while columns.len() <= i {
                    columns.push(col);
                }
                col = if ch == '\t' {
                    (col / 4 + 1) * 4
                } else {
                    col.saturating_add(1)
                };
            }
            while columns.len() <= line.len() {
                columns.push(col);
            }
            for (range, highlight) in highlighter.highlight_line(line) {
                let color = highlight.color().unwrap_or(fallback);
                let text = &line[range.clone()];
                // Split the span at whitespace so blank stretches stay empty.
                let mut start = None;
                for (i, ch) in text
                    .char_indices()
                    .chain(std::iter::once((text.len(), ' ')))
                {
                    let at = range.start + i;
                    match (ch.is_whitespace(), start) {
                        (false, None) => start = Some(at),
                        (true, Some(s)) => {
                            let (a, b) = (columns[s], columns[at]);
                            runs.push((a, b.saturating_sub(a).max(1), color));
                            start = None;
                        }
                        _ => {}
                    }
                }
            }
            runs
        })
        .collect();
}

// The crate links against Python only when loaded by it, so run these with libpython:
// `cargo rustc --lib --profile test -- -l python3.13` and then the binary it builds
// (`target/debug/deps/_core-*`).
#[cfg(test)]
mod tests {
    use super::*;
    use text_editor::{Action, Edit, Position};

    fn at(text: &str, line: usize, column: usize) -> EditorState {
        let mut s = EditorState::new(text);
        s.content.move_to(text_editor::Cursor {
            position: Position { line, column },
            selection: None,
        });
        s
    }

    fn typed(s: &mut EditorState, text: &str) {
        for c in text.chars() {
            if is_pair_char(c) {
                s.key("e", EditKey::Char(c), Some(4), true);
            } else {
                s.perform("e", Action::Edit(Edit::Insert(c)));
            }
        }
    }

    fn cursor(s: &EditorState) -> (usize, usize) {
        let p = s.real_position(s.content.cursor().position);
        (p.line, p.column)
    }

    #[test]
    fn closes_brackets_and_quotes() {
        let mut s = at("", 0, 0);
        typed(&mut s, "print(");
        assert_eq!((s.text().as_str(), cursor(&s)), ("print()", (0, 6)));
        typed(&mut s, "\"hi");
        assert_eq!(s.text(), "print(\"hi\")");
        // Typing the closers steps over them.
        typed(&mut s, "\")");
        assert_eq!((s.text().as_str(), cursor(&s)), ("print(\"hi\")", (0, 11)));
    }

    #[test]
    fn quotes_inside_words_stay_single() {
        let mut s = at("don", 0, 3);
        typed(&mut s, "'");
        assert_eq!(s.text(), "don'");
        let mut s = at("x = f", 0, 5);
        typed(&mut s, "\"");
        assert_eq!(s.text(), "x = f\"\"");
        // Not before a word.
        let mut s = at("word", 0, 0);
        typed(&mut s, "(");
        assert_eq!(s.text(), "(word");
    }

    #[test]
    fn backspace_deletes_empty_pair_and_enter_opens_block() {
        let mut s = at("x = []", 0, 5);
        s.key("e", EditKey::Backspace, Some(4), true);
        assert_eq!(s.text(), "x = ");
        let mut s = at("    d = {}", 0, 9);
        s.key("e", EditKey::Enter, Some(4), true);
        assert_eq!(s.text(), "    d = {\n        \n    }");
        assert_eq!(cursor(&s), (1, 8));
    }

    #[test]
    fn wraps_selection() {
        let mut s = at("a word here", 0, 2);
        s.content.move_to(text_editor::Cursor {
            position: Position { line: 0, column: 6 },
            selection: Some(Position { line: 0, column: 2 }),
        });
        s.key("e", EditKey::Char('('), Some(4), true);
        assert_eq!(s.text(), "a (word) here");
        assert_eq!(s.content.selection().as_deref(), Some("word"));
    }

    const CODE: &str = "def a():\n    x = 1\n    if x:\n        y = 2\n\n    return x\nz = 3";

    #[test]
    fn folds_by_indentation_and_keeps_real_lines() {
        let mut s = at(CODE, 0, 0);
        s.fold_op("e", FoldOp::Toggle(0));
        assert_eq!(s.content.line_count(), 2);
        assert_eq!(s.text(), CODE);
        assert_eq!(s.real_line(1), 6);
        assert_eq!(s.visible_line(6), (1, false));
        assert_eq!(s.visible_line(3), (0, true));
        // Editing below the fold keeps it, and the text stays whole.
        s.content.move_to(text_editor::Cursor {
            position: Position { line: 1, column: 5 },
            selection: None,
        });
        typed(&mut s, "0");
        assert_eq!(s.text(), CODE.replace("z = 3", "z = 30"));
        assert_eq!(cursor(&s), (6, 6));
        assert!(s.is_folded(0));
        s.fold_op("e", FoldOp::Toggle(0));
        assert_eq!(s.content.line_count(), 7);
    }

    #[test]
    fn enter_on_a_folded_line_unfolds_it_and_lines_below_shift() {
        let mut s = at(CODE, 2, 0);
        s.fold_op("e", FoldOp::AtCursor);
        // The `if` block (line 2) is the innermost one around the cursor.
        assert!(s.is_folded(2));
        s.content.move_to(text_editor::Cursor {
            position: Position { line: 0, column: 8 },
            selection: None,
        });
        s.key("e", EditKey::Enter, Some(4), true);
        assert!(s.is_folded(3));
        assert_eq!(s.text(), CODE.replacen("def a():", "def a():\n    ", 1));
        s.content.move_to(text_editor::Cursor {
            position: Position { line: 3, column: 9 },
            selection: None,
        });
        s.key("e", EditKey::Enter, Some(4), true);
        assert!(s.folds.is_empty());
    }

    #[test]
    fn moving_into_a_fold_unfolds_it() {
        let mut s = at(CODE, 0, 0);
        s.fold_op("e", FoldOp::FoldAll);
        assert_eq!(s.content.line_count(), 2);
        let _ = s.move_to("e", Position { line: 3, column: 2 });
        assert_eq!(cursor(&s), (3, 2));
        s.fold_op("e", FoldOp::UnfoldAll);
        assert_eq!(s.content.line_count(), 7);
        assert_eq!(s.text(), CODE);
    }
}
