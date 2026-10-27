//! Vim's modal editing, like Zed's `vim_mode`. Normal mode moves and edits with Vim's keys
//! (counts, operators with motions and text objects, `.` to repeat the last change), Insert
//! mode types as usual and Visual and Visual Line modes select. What Vim does outside the
//! text (`/` and `?` search, `:` commands, `K` shows the documentation, `gd` goes to the
//! definition) is asked of the app with `on_action` and a `vim_` name, and every change of
//! mode is reported the same way (`"vim_normal"`, `"vim_insert"`, `"vim_visual"`,
//! `"vim_visual_line"`).
//!
//! Vim works on the visible lines (a fold counts as its header line) and on the primary
//! cursor.

use std::sync::Arc;

use iced::Task;
use iced::widget::text_editor::{Action, Cursor, Edit, Motion, Position};

use super::actions::{self, ActionContext, Case, EditKind};
use super::{EditKey, EditorAction, EditorState, FoldOp, Outcome};
use crate::app::Message;

/// A key as Vim reads it.
#[derive(Debug, Clone, PartialEq)]
pub enum VimKey {
    Char(char),
    Ctrl(char),
    Escape,
    Enter,
    Backspace,
    Delete,
    Tab,
    Left,
    Right,
    Up,
    Down,
    Home,
    End,
    PageUp,
    PageDown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum Mode {
    #[default]
    Normal,
    Insert,
    Visual,
    VisualLine,
}

impl Mode {
    /// The name `on_action` reports when Vim enters the mode.
    pub fn name(self) -> &'static str {
        match self {
            Self::Normal => "vim_normal",
            Self::Insert => "vim_insert",
            Self::Visual => "vim_visual",
            Self::VisualLine => "vim_visual_line",
        }
    }

    fn visual(self) -> bool {
        matches!(self, Self::Visual | Self::VisualLine)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Operator {
    Delete,
    Change,
    Yank,
    Indent,
    Outdent,
    Comment,
    Case(Case),
}

/// A command waiting for its next key.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Pending {
    /// `g` (`gg`, `gc`, `gu`...).
    G,
    /// `z` (`zz`, `zc`, `zo`...).
    Z,
    /// `f`, `t`, `F` or `T` and the character to find.
    Find(Find),
    /// `r` and the replacing character.
    Replace,
    /// `i` or `a` after an operator (or in Visual mode) and the text object.
    Object { around: bool },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Find {
    /// `f`: onto the character.
    To,
    /// `t`: up to the character.
    Till,
    /// `F`.
    ToBack,
    /// `T`.
    TillBack,
}

impl Find {
    fn reversed(self) -> Self {
        match self {
            Self::To => Self::ToBack,
            Self::Till => Self::TillBack,
            Self::ToBack => Self::To,
            Self::TillBack => Self::Till,
        }
    }
}

/// What a motion covers when an operator uses it.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Kind {
    Exclusive,
    Inclusive,
    Linewise,
}

#[derive(Debug, Clone, Copy, PartialEq)]
enum VimMotion {
    Left,
    Right,
    Up,
    Down,
    /// `w` / `W` (`true`: WORDs, separated by blanks only).
    WordStart(bool),
    /// `e` / `E`.
    WordEnd(bool),
    /// `b` / `B`.
    WordBack(bool),
    /// `0`.
    LineStart,
    /// `^`.
    FirstNonBlank,
    /// `$`.
    LineEnd,
    /// `gg` (or line `count`).
    FirstLine,
    /// `G` (or line `count`).
    LastLine,
    /// `{` / `}`.
    Paragraph(bool),
    /// `%`.
    Bracket,
    Find(Find, char),
    /// `+` and Enter / `-`.
    NextLine(bool),
}

/// Vim's state in one editor.
#[derive(Default)]
pub struct Vim {
    pub mode: Mode,
    count: Option<usize>,
    /// The operator typed and the count before it.
    operator: Option<(Operator, usize)>,
    pending: Option<Pending>,
    /// The last `f`/`t`/`F`/`T` (for `;` and `,`).
    find: Option<(Find, char)>,
    /// The unnamed register: its text and whether it holds whole lines.
    pub(crate) register: Option<(String, bool)>,
    /// Where Visual mode started and where its cursor is (the selection covers both).
    anchor: Position,
    head: Position,
    /// The keys of the command being typed.
    keys: Vec<VimKey>,
    /// The keys of the command that entered Insert mode, until it is left.
    insert_keys: Vec<VimKey>,
    /// Where Insert mode started (offset of the cursor, length of the text), to find what was typed.
    insert_start: Option<(usize, usize)>,
    /// The last change, for `.`: its keys and the text typed in Insert mode after them.
    last_change: Option<(Vec<VimKey>, String)>,
    replaying: bool,
    /// The word `*` and `#` searched for (`n` and `N` look for it again).
    search: Option<String>,
}

impl Vim {
    /// Nothing typed is waiting for more keys.
    pub fn idle(&self) -> bool {
        self.count.is_none() && self.operator.is_none() && self.pending.is_none()
    }

    fn reset(&mut self) {
        self.count = None;
        self.operator = None;
        self.pending = None;
    }

    fn take_count(&mut self) -> usize {
        self.count.take().unwrap_or(1)
    }
}

/// What handling a key asks besides the edit: an app request, the clipboard and scrolling.
#[derive(Default)]
struct Effects {
    request: Option<&'static str>,
    clipboard: Option<String>,
    scroll: Vec<Task<Message>>,
    recorded: bool,
}

fn is_word(c: char) -> bool {
    c.is_alphanumeric() || c == '_'
}

/// `0` blank, `1` word character, `2` punctuation (with `big`, everything not blank is `1`).
fn class(c: char, big: bool) -> u8 {
    if c.is_whitespace() {
        0
    } else if big || is_word(c) {
        1
    } else {
        2
    }
}

/// The text as characters with their byte offsets (plus the end).
struct Chars {
    chars: Vec<char>,
    offsets: Vec<usize>,
}

impl Chars {
    fn new(text: &str) -> Self {
        let mut chars = Vec::with_capacity(text.len());
        let mut offsets = Vec::with_capacity(text.len() + 1);
        for (i, c) in text.char_indices() {
            chars.push(c);
            offsets.push(i);
        }
        offsets.push(text.len());
        Self { chars, offsets }
    }

    fn len(&self) -> usize {
        self.chars.len()
    }

    /// The index of the character at byte `offset`.
    fn index(&self, offset: usize) -> usize {
        self.offsets.partition_point(|o| *o < offset)
    }

    fn offset(&self, index: usize) -> usize {
        self.offsets[index.min(self.chars.len())]
    }

    fn class(&self, i: usize, big: bool) -> u8 {
        class(self.chars[i], big)
    }

    fn next_word_start(&self, i: usize, big: bool) -> usize {
        let n = self.len();
        if i >= n {
            return n;
        }
        let mut j = i;
        let c = self.class(j, big);
        if c != 0 {
            while j < n && self.class(j, big) == c {
                j += 1;
            }
        }
        while j < n && self.class(j, big) == 0 {
            // An empty line is a word of its own.
            if self.chars[j] == '\n' && j + 1 < n && self.chars[j + 1] == '\n' {
                return j + 1;
            }
            j += 1;
        }
        j
    }

    fn word_end(&self, i: usize, big: bool) -> usize {
        let n = self.len();
        let mut j = i + 1;
        while j < n && self.class(j, big) == 0 {
            j += 1;
        }
        if j >= n {
            return n.saturating_sub(1);
        }
        let c = self.class(j, big);
        while j + 1 < n && self.class(j + 1, big) == c {
            j += 1;
        }
        j
    }

    fn word_back(&self, i: usize, big: bool) -> usize {
        if i == 0 {
            return 0;
        }
        let mut j = i - 1;
        while j > 0 && self.class(j, big) == 0 {
            j -= 1;
        }
        let c = self.class(j, big);
        while j > 0 && self.class(j - 1, big) == c {
            j -= 1;
        }
        j
    }
}

fn pos(line: usize, column: usize) -> Position {
    Position { line, column }
}

fn collapsed(p: Position) -> Cursor {
    Cursor {
        position: p,
        selection: None,
    }
}

fn indent_of(line: &str) -> usize {
    line.len() - line.trim_start().len()
}

/// The byte length of the character at byte `column` of `line` (0 at its end).
fn char_len(line: &str, column: usize) -> usize {
    line[actions::floor(line, column)..]
        .chars()
        .next()
        .map_or(0, char::len_utf8)
}

/// The start of the character before byte `column` of `line`.
fn char_before(line: &str, column: usize) -> usize {
    line[..actions::floor(line, column)]
        .char_indices()
        .next_back()
        .map_or(0, |(i, _)| i)
}

/// The column of the last character of `line` (where Normal mode's cursor stops).
fn last_column(line: &str) -> usize {
    char_before(line, line.len())
}

/// The pair of `open` and `close` around byte `at` of `text` (`at` may be on either), as the
/// offsets of both.
fn enclosing_pair(text: &str, at: usize, open: u8, close: u8) -> Option<(usize, usize)> {
    let bytes = text.as_bytes();
    let start = if bytes.get(at) == Some(&open) {
        at
    } else {
        let mut depth = 0usize;
        let mut found = None;
        let from = if bytes.get(at) == Some(&close) {
            at
        } else {
            at.min(bytes.len())
        };
        for i in (0..from).rev() {
            if bytes[i] == close {
                depth += 1;
            } else if bytes[i] == open {
                if depth == 0 {
                    found = Some(i);
                    break;
                }
                depth -= 1;
            }
        }
        found?
    };
    let mut depth = 0usize;
    for (i, &b) in bytes.iter().enumerate().skip(start) {
        if b == open {
            depth += 1;
        } else if b == close {
            depth -= 1;
            if depth == 0 {
                return Some((start, i));
            }
        }
    }
    None
}

impl EditorState {
    /// Handles a key in Vim's Normal or Visual mode (and Escape in Insert mode).
    pub fn vim_key(&mut self, id: &str, key: VimKey, ctx: &ActionContext) -> Outcome {
        let before = self.real_position(self.content.cursor().position);
        let text_before = self.content.text();
        let mode_before = self.vim.mode;
        let mut fx = Effects::default();
        let replaying = self.vim.replaying;
        if mode_before != Mode::Insert && !replaying {
            self.vim.keys.push(key.clone());
        }
        self.vim_handle(id, key, ctx, &mut fx);
        let edited = self.content.text() != text_before;
        if fx.recorded && !edited {
            self.unrecord();
        }
        if self.vim.mode == Mode::Normal {
            self.vim_clamp();
        }
        // A finished command: remember it for `.` if it changed the text.
        if self.vim.idle() && !replaying {
            let keys = std::mem::take(&mut self.vim.keys);
            if self.vim.mode == Mode::Insert && mode_before != Mode::Insert {
                self.vim.insert_keys = keys;
            } else if edited && mode_before == Mode::Normal {
                self.vim.last_change = Some((keys, String::new()));
            }
        }
        let mut outcome = self.outcome(id, before, edited, true);
        outcome.cursor_moved = true;
        outcome.action = fx
            .request
            .or_else(|| (self.vim.mode != mode_before).then(|| self.vim.mode.name()));
        outcome.clipboard = fx.clipboard;
        fx.scroll
            .push(std::mem::replace(&mut outcome.scroll, Task::none()));
        outcome.scroll = Task::batch(fx.scroll);
        outcome
    }

    /// Back to Normal mode with nothing pending (Vim turned on or off, or a new text).
    pub fn vim_reset(&mut self) {
        self.vim.reset();
        self.vim.mode = Mode::Normal;
    }

    fn vim_record(&mut self, fx: &mut Effects) {
        if !fx.recorded {
            self.record(EditKind::Other);
            fx.recorded = true;
        }
    }

    fn vim_cursor(&self) -> Position {
        if self.vim.mode.visual() {
            self.vim.head
        } else {
            self.content.cursor().position
        }
    }

    fn vim_move(&mut self, p: Position) {
        if self.vim.mode.visual() {
            self.vim.head = p;
            self.vim_select();
        } else {
            self.extra.clear();
            self.set_cursor(collapsed(p));
        }
    }

    /// Normal mode's cursor sits on a character, never after the last one.
    fn vim_clamp(&mut self) {
        let c = self.content.cursor();
        if c.selection.is_some() {
            self.set_cursor(collapsed(c.position));
        }
        let line = self.line_at(c.position.line);
        if !line.is_empty() && c.position.column >= line.len() {
            self.set_cursor(collapsed(pos(c.position.line, last_column(&line))));
        }
    }

    fn line_at(&self, line: usize) -> String {
        self.content
            .line(line)
            .map(|l| l.text.into_owned())
            .unwrap_or_default()
    }

    /// The selection of Visual mode, from its anchor to its cursor (both included), as a
    /// range of positions.
    fn vim_visual_range(&self) -> (Position, Position) {
        let (a, h) = (self.vim.anchor, self.vim.head);
        let (s, e) = if (a.line, a.column) <= (h.line, h.column) {
            (a, h)
        } else {
            (h, a)
        };
        if self.vim.mode == Mode::VisualLine {
            let end = self.line_at(e.line).len();
            return (pos(s.line, 0), pos(e.line, end));
        }
        let line = self.line_at(e.line);
        (s, pos(e.line, e.column + char_len(&line, e.column)))
    }

    fn vim_select(&mut self) {
        let (s, e) = self.vim_visual_range();
        let forward = (self.vim.head.line, self.vim.head.column)
            >= (self.vim.anchor.line, self.vim.anchor.column);
        self.extra.clear();
        self.set_cursor(if forward {
            Cursor {
                position: e,
                selection: Some(s),
            }
        } else {
            Cursor {
                position: s,
                selection: Some(e),
            }
        });
    }

    fn vim_enter_visual(&mut self, mode: Mode) {
        if !self.vim.mode.visual() {
            let p = self.content.cursor().position;
            self.vim.anchor = p;
            self.vim.head = p;
        }
        self.vim.mode = mode;
        self.vim_select();
    }

    fn vim_leave_visual(&mut self) {
        let head = self.vim.head;
        self.vim.mode = Mode::Normal;
        self.set_cursor(collapsed(head));
    }

    fn vim_enter_insert(&mut self) {
        self.vim.mode = Mode::Insert;
        self.vim.reset();
        let lines = self.visible_lines();
        let offset = actions::offset_of(&lines, self.content.cursor().position);
        self.vim.insert_start = Some((offset, self.content.text().len()));
    }

    fn vim_leave_insert(&mut self) {
        self.vim.mode = Mode::Normal;
        let lines = self.visible_lines();
        let cursor = self.content.cursor().position;
        if let Some((start, len)) = self.vim.insert_start.take()
            && !self.vim.replaying
        {
            let text = lines.join("\n");
            let offset = actions::offset_of(&lines, cursor);
            let typed =
                if offset >= start && text.len() >= len && text.len() - len == offset - start {
                    text[start..offset].to_owned()
                } else {
                    String::new()
                };
            let keys = std::mem::take(&mut self.vim.insert_keys);
            if !keys.is_empty() {
                self.vim.last_change = Some((keys, typed));
            }
        }
        // Like Vim, the cursor steps back onto the last typed character.
        let line = self.line_at(cursor.line);
        if cursor.column > 0 {
            self.set_cursor(collapsed(pos(
                cursor.line,
                char_before(&line, cursor.column),
            )));
        } else {
            self.set_cursor(collapsed(cursor));
        }
    }

    fn vim_handle(&mut self, id: &str, key: VimKey, ctx: &ActionContext, fx: &mut Effects) {
        use VimKey as K;
        if self.vim.mode == Mode::Insert {
            if matches!(key, K::Escape | K::Ctrl('[') | K::Ctrl('c')) {
                self.vim_leave_insert();
            }
            return;
        }
        if matches!(key, K::Escape | K::Ctrl('[') | K::Ctrl('c')) {
            let waiting = !self.vim.idle();
            self.vim.reset();
            if self.vim.mode.visual() {
                self.vim_leave_visual();
            } else if !waiting {
                let p = self.content.cursor().position;
                self.extra.clear();
                self.set_cursor(collapsed(p));
            }
            return;
        }
        if let Some(pending) = self.vim.pending.take() {
            let K::Char(c) = key else {
                self.vim.reset();
                return;
            };
            match pending {
                Pending::Find(find) => {
                    self.vim.find = Some((find, c));
                    self.vim_motion(id, ctx, VimMotion::Find(find, c), fx);
                }
                Pending::Replace => self.vim_replace_chars(c, fx),
                Pending::G => self.vim_g(id, ctx, c, fx),
                Pending::Z => self.vim_z(id, c, fx),
                Pending::Object { around } => self.vim_object(id, ctx, c, around, fx),
            }
            return;
        }
        // Counts: `3dw`, `d3w`; a lone `0` goes to the start of the line.
        if let K::Char(c @ '0'..='9') = key
            && (c != '0' || self.vim.count.is_some())
        {
            let digit = c as usize - '0' as usize;
            self.vim.count = Some(self.vim.count.unwrap_or(0).saturating_mul(10) + digit);
            return;
        }
        let motion = match &key {
            K::Char('h') | K::Left | K::Backspace => Some(VimMotion::Left),
            K::Char('l') | K::Right | K::Char(' ') => Some(VimMotion::Right),
            K::Char('k') | K::Up => Some(VimMotion::Up),
            K::Char('j') | K::Down => Some(VimMotion::Down),
            K::Char('w') => Some(VimMotion::WordStart(false)),
            K::Char('W') => Some(VimMotion::WordStart(true)),
            K::Char('e') => Some(VimMotion::WordEnd(false)),
            K::Char('E') => Some(VimMotion::WordEnd(true)),
            K::Char('b') => Some(VimMotion::WordBack(false)),
            K::Char('B') => Some(VimMotion::WordBack(true)),
            K::Char('0') | K::Home => Some(VimMotion::LineStart),
            K::Char('^') | K::Char('_') => Some(VimMotion::FirstNonBlank),
            K::Char('$') | K::End => Some(VimMotion::LineEnd),
            K::Char('G') => Some(VimMotion::LastLine),
            K::Char('{') => Some(VimMotion::Paragraph(false)),
            K::Char('}') => Some(VimMotion::Paragraph(true)),
            K::Char('%') => Some(VimMotion::Bracket),
            K::Char('+') | K::Enter => Some(VimMotion::NextLine(true)),
            K::Char('-') => Some(VimMotion::NextLine(false)),
            K::Char(';') | K::Char(',') => self.vim.find.map(|(find, c)| {
                let find = if key == K::Char(',') {
                    find.reversed()
                } else {
                    find
                };
                VimMotion::Find(find, c)
            }),
            _ => None,
        };
        if let Some(motion) = motion {
            self.vim_motion(id, ctx, motion, fx);
            return;
        }
        let pending = match key {
            K::Char('g') => Some(Pending::G),
            K::Char('z') => Some(Pending::Z),
            K::Char('f') => Some(Pending::Find(Find::To)),
            K::Char('t') => Some(Pending::Find(Find::Till)),
            K::Char('F') => Some(Pending::Find(Find::ToBack)),
            K::Char('T') => Some(Pending::Find(Find::TillBack)),
            K::Char('r') if !self.vim.mode.visual() && self.vim.operator.is_none() => {
                Some(Pending::Replace)
            }
            K::Char(c @ ('i' | 'a')) if self.vim.operator.is_some() || self.vim.mode.visual() => {
                Some(Pending::Object { around: c == 'a' })
            }
            _ => None,
        };
        if let Some(pending) = pending {
            self.vim.pending = Some(pending);
            return;
        }
        // `gcc`, `g~~`, `guu`, `gUU`: the operator's last key again works on lines.
        if let (Some((op, count)), K::Char(c)) = (self.vim.operator, &key)
            && matches!(
                (op, *c),
                (Operator::Comment, 'c')
                    | (Operator::Case(Case::Toggle), '~')
                    | (Operator::Case(Case::Lower), 'u')
                    | (Operator::Case(Case::Upper), 'U')
            )
        {
            let count = count * self.vim.take_count();
            self.vim.operator = None;
            self.vim_lines(id, ctx, op, count, fx);
            return;
        }
        let operator = match key {
            K::Char('d') => Some(Operator::Delete),
            K::Char('c') => Some(Operator::Change),
            K::Char('y') => Some(Operator::Yank),
            K::Char('>') => Some(Operator::Indent),
            K::Char('<') => Some(Operator::Outdent),
            _ => None,
        };
        if let Some(op) = operator {
            self.vim_operator(id, ctx, op, fx);
            return;
        }
        if self.vim.operator.is_some() {
            // Not a motion: the operator is cancelled.
            self.vim.reset();
            return;
        }
        if self.vim.mode.visual() {
            self.vim_visual_command(id, ctx, key, fx);
        } else {
            self.vim_normal_command(id, ctx, key, fx);
        }
    }

    /// An operator key: in Visual mode it acts on the selection, typed twice (`dd`, `>>`) on
    /// whole lines, else it waits for a motion or a text object.
    fn vim_operator(&mut self, id: &str, ctx: &ActionContext, op: Operator, fx: &mut Effects) {
        if self.vim.mode.visual() {
            let linewise = self.vim.mode == Mode::VisualLine;
            let (s, e) = self.vim_visual_range();
            self.vim.mode = Mode::Normal;
            self.vim_apply(id, ctx, op, s, e, linewise, fx);
            return;
        }
        match self.vim.operator {
            Some((pending, count)) if pending == op => {
                let count = count * self.vim.take_count();
                self.vim.operator = None;
                self.vim_lines(id, ctx, op, count, fx);
            }
            Some(_) => self.vim.reset(),
            None => {
                let count = self.vim.take_count();
                self.vim.operator = Some((op, count));
            }
        }
    }

    /// An operator on `count` whole lines from the cursor's.
    fn vim_lines(
        &mut self,
        id: &str,
        ctx: &ActionContext,
        op: Operator,
        count: usize,
        fx: &mut Effects,
    ) {
        let line = self.content.cursor().position.line;
        let last = (line + count - 1).min(self.content.line_count().saturating_sub(1));
        let end = self.line_at(last).len();
        self.vim_apply(id, ctx, op, pos(line, 0), pos(last, end), true, fx);
    }

    /// Where `motion` goes from the cursor `count` times, and what it covers.
    fn vim_target(
        &self,
        motion: VimMotion,
        count: usize,
        operating: bool,
    ) -> Option<(Position, Kind)> {
        let lines = self.visible_lines();
        let here = self.vim_cursor();
        let last_line = lines.len().saturating_sub(1);
        let line = &lines[here.line.min(last_line)];
        let first_non_blank = |l: usize| pos(l, indent_of(&lines[l]));
        Some(match motion {
            VimMotion::Left => {
                let mut column = here.column;
                for _ in 0..count {
                    if column == 0 {
                        break;
                    }
                    column = char_before(line, column);
                }
                (pos(here.line, column), Kind::Exclusive)
            }
            VimMotion::Right => {
                let mut column = here.column;
                for _ in 0..count {
                    let next = column + char_len(line, column);
                    // Normal mode stops on the last character, an operator may take it.
                    if next > line.len() || (!operating && next >= line.len()) {
                        break;
                    }
                    column = next;
                }
                (pos(here.line, column), Kind::Exclusive)
            }
            VimMotion::Up | VimMotion::Down => {
                let target = if motion == VimMotion::Up {
                    here.line.saturating_sub(count)
                } else {
                    (here.line + count).min(last_line)
                };
                let text = &lines[target];
                let column = actions::floor(text, here.column.min(last_column(text)));
                (pos(target, column), Kind::Linewise)
            }
            VimMotion::WordStart(big) | VimMotion::WordEnd(big) | VimMotion::WordBack(big) => {
                let text = lines.join("\n");
                let chars = Chars::new(&text);
                let mut i = chars.index(actions::offset_of(&lines, here));
                for _ in 0..count {
                    i = match motion {
                        VimMotion::WordStart(_) => chars.next_word_start(i, big),
                        VimMotion::WordEnd(_) => chars.word_end(i, big),
                        _ => chars.word_back(i, big),
                    };
                }
                let kind = if matches!(motion, VimMotion::WordEnd(_)) {
                    Kind::Inclusive
                } else {
                    Kind::Exclusive
                };
                let mut target = actions::position_at(&lines, chars.offset(i));
                // `dw` on the last word of a line stops at its end (Vim's special case).
                if operating && matches!(motion, VimMotion::WordStart(_)) && target.line > here.line
                {
                    target = pos(here.line, line.len());
                }
                (target, kind)
            }
            VimMotion::LineStart => (pos(here.line, 0), Kind::Exclusive),
            VimMotion::FirstNonBlank => (first_non_blank(here.line), Kind::Exclusive),
            VimMotion::LineEnd => {
                let target = (here.line + count - 1).min(last_line);
                let text = &lines[target];
                if text.is_empty() {
                    (pos(target, 0), Kind::Exclusive)
                } else {
                    (pos(target, last_column(text)), Kind::Inclusive)
                }
            }
            VimMotion::FirstLine | VimMotion::LastLine => {
                let target = match (self.vim.count, motion) {
                    (Some(_), _) => count.saturating_sub(1).min(last_line),
                    (None, VimMotion::FirstLine) => 0,
                    _ => last_line,
                };
                (first_non_blank(target), Kind::Linewise)
            }
            VimMotion::Paragraph(forward) => {
                let mut l = here.line;
                for _ in 0..count {
                    if forward {
                        while l < last_line && lines[l].trim().is_empty() {
                            l += 1;
                        }
                        while l < last_line && !lines[l].trim().is_empty() {
                            l += 1;
                        }
                    } else {
                        while l > 0 && lines[l].trim().is_empty() {
                            l -= 1;
                        }
                        while l > 0 && !lines[l].trim().is_empty() {
                            l -= 1;
                        }
                    }
                }
                let column = if forward && l == last_line && !lines[l].trim().is_empty() {
                    lines[l].len()
                } else {
                    0
                };
                (pos(l, column), Kind::Exclusive)
            }
            VimMotion::Bracket => {
                let text = lines.join("\n");
                let bytes = text.as_bytes();
                let at = actions::offset_of(&lines, here);
                let line_end = actions::offset_of(&lines, pos(here.line, line.len()));
                let start = (at..line_end).find(|i| b"()[]{}".contains(&bytes[*i]))?;
                let target = actions::matching_bracket(bytes, start)?;
                (actions::position_at(&lines, target), Kind::Inclusive)
            }
            VimMotion::Find(find, c) => {
                let mut column = here.column;
                for n in 0..count {
                    let found = match find {
                        Find::To | Find::Till => {
                            // `t` again right before the character looks past it.
                            let skip = if find == Find::Till && n == 0 {
                                char_len(line, column)
                            } else {
                                0
                            };
                            let from = (column + char_len(line, column) + skip).min(line.len());
                            line[from..].find(c).map(|i| from + i)
                        }
                        Find::ToBack | Find::TillBack => {
                            let mut upto = column;
                            if find == Find::TillBack && n == 0 && upto > 0 {
                                upto = char_before(line, upto);
                            }
                            line[..upto].rfind(c)
                        }
                    };
                    column = found?;
                }
                let column = match find {
                    Find::Till => char_before(line, column),
                    Find::TillBack => column + char_len(line, column),
                    _ => column,
                };
                let kind = if matches!(find, Find::To | Find::Till) {
                    Kind::Inclusive
                } else {
                    Kind::Exclusive
                };
                (pos(here.line, column), kind)
            }
            VimMotion::NextLine(down) => {
                let target = if down {
                    (here.line + count).min(last_line)
                } else {
                    here.line.saturating_sub(count)
                };
                (first_non_blank(target), Kind::Linewise)
            }
        })
    }

    fn vim_motion(&mut self, id: &str, ctx: &ActionContext, motion: VimMotion, fx: &mut Effects) {
        let count = self.vim.count.unwrap_or(1).max(1);
        let operator = self.vim.operator.take();
        let op_count = operator.map_or(1, |(_, c)| c);
        let mut motion = motion;
        // `cw` changes to the end of the word, like `ce`.
        if let (Some((Operator::Change, _)), VimMotion::WordStart(big)) = (operator, motion) {
            let here = self.content.cursor().position;
            let line = self.line_at(here.line);
            if line[actions::floor(&line, here.column)..]
                .chars()
                .next()
                .is_some_and(|c| !c.is_whitespace())
            {
                motion = VimMotion::WordEnd(big);
            }
        }
        let target = self.vim_target(motion, count * op_count, operator.is_some());
        self.vim.count = None;
        let Some((target, kind)) = target else {
            return;
        };
        let Some((op, _)) = operator else {
            // `j` and `k` keep the column they started from, as far as the line allows.
            if matches!(motion, VimMotion::Up | VimMotion::Down) && !self.vim.mode.visual() {
                let motion = if motion == VimMotion::Up {
                    Motion::Up
                } else {
                    Motion::Down
                };
                self.extra.clear();
                for _ in 0..count {
                    self.content.perform(Action::Move(motion));
                }
                return;
            }
            self.vim_move(target);
            return;
        };
        let here = self.vim_cursor();
        let (mut s, mut e) = if (target.line, target.column) < (here.line, here.column) {
            (target, here)
        } else {
            (here, target)
        };
        if kind == Kind::Inclusive {
            let line = self.line_at(e.line);
            e.column += char_len(&line, e.column);
        }
        if kind == Kind::Linewise {
            s.column = 0;
            e.column = self.line_at(e.line).len();
        }
        self.vim_apply(id, ctx, op, s, e, kind == Kind::Linewise, fx);
    }

    /// `i` / `a` and a text object, for an operator or to select in Visual mode.
    fn vim_object(
        &mut self,
        id: &str,
        ctx: &ActionContext,
        c: char,
        around: bool,
        fx: &mut Effects,
    ) {
        let lines = self.visible_lines();
        let text = lines.join("\n");
        let here = self.vim_cursor();
        let at = actions::offset_of(&lines, here);
        let line_start = actions::offset_of(&lines, pos(here.line, 0));
        let line = &lines[here.line];
        let mut linewise = false;
        let found: Option<(usize, usize)> = match c {
            'w' | 'W' => {
                let big = c == 'W';
                let chars = Chars::new(&text);
                let i = chars.index(at).min(chars.len().saturating_sub(1));
                if chars.len() == 0 {
                    None
                } else {
                    let kind = chars.class(i, big);
                    let (mut a, mut b) = (i, i + 1);
                    while a > 0 && chars.class(a - 1, big) == kind && chars.chars[a - 1] != '\n' {
                        a -= 1;
                    }
                    while b < chars.len() && chars.class(b, big) == kind && chars.chars[b] != '\n' {
                        b += 1;
                    }
                    if around && kind != 0 {
                        let mut t = b;
                        while t < chars.len() && chars.class(t, big) == 0 && chars.chars[t] != '\n'
                        {
                            t += 1;
                        }
                        if t > b {
                            b = t;
                        } else {
                            while a > 0
                                && chars.class(a - 1, big) == 0
                                && chars.chars[a - 1] != '\n'
                            {
                                a -= 1;
                            }
                        }
                    }
                    Some((chars.offset(a), chars.offset(b)))
                }
            }
            '"' | '\'' | '`' => {
                let quotes: Vec<usize> = line.match_indices(c).map(|(i, _)| i).collect();
                let column = here.column;
                quotes
                    .chunks(2)
                    .filter(|pair| pair.len() == 2)
                    .find(|pair| pair[1] >= column)
                    .map(|pair| {
                        let (o, q) = (line_start + pair[0], line_start + pair[1]);
                        if around { (o, q + 1) } else { (o + 1, q) }
                    })
            }
            '(' | ')' | 'b' | '[' | ']' | '{' | '}' | 'B' | '<' | '>' => {
                let (open, close) = match c {
                    '(' | ')' | 'b' => (b'(', b')'),
                    '[' | ']' => (b'[', b']'),
                    '{' | '}' | 'B' => (b'{', b'}'),
                    _ => (b'<', b'>'),
                };
                enclosing_pair(&text, at, open, close)
                    .map(|(o, q)| if around { (o, q + 1) } else { (o + 1, q) })
            }
            'p' => {
                linewise = true;
                let blank = |l: usize| lines[l].trim().is_empty();
                let kind = blank(here.line);
                let (mut a, mut b) = (here.line, here.line);
                while a > 0 && blank(a - 1) == kind {
                    a -= 1;
                }
                while b + 1 < lines.len() && blank(b + 1) == kind {
                    b += 1;
                }
                if around {
                    while b + 1 < lines.len() && blank(b + 1) {
                        b += 1;
                    }
                }
                Some((
                    actions::offset_of(&lines, pos(a, 0)),
                    actions::offset_of(&lines, pos(b, lines[b].len())),
                ))
            }
            _ => None,
        };
        let operator = self.vim.operator.take();
        self.vim.count = None;
        let Some((a, b)) = found else {
            return;
        };
        let (s, e) = (
            actions::position_at(&lines, a),
            actions::position_at(&lines, b),
        );
        if let Some((op, _)) = operator {
            self.vim_apply(id, ctx, op, s, e, linewise, fx);
        } else if self.vim.mode.visual() && b > a {
            self.vim.anchor = s;
            let end_line = &lines[e.line];
            self.vim.head = pos(e.line, char_before(end_line, e.column));
            if e.column == 0 && e.line > s.line {
                self.vim.head = pos(e.line - 1, last_column(&lines[e.line - 1]));
            }
            self.vim_select();
        }
    }

    /// Runs an operator over `s..e` (whole lines with `linewise`).
    #[allow(clippy::too_many_arguments)]
    fn vim_apply(
        &mut self,
        id: &str,
        ctx: &ActionContext,
        op: Operator,
        s: Position,
        e: Position,
        linewise: bool,
        fx: &mut Effects,
    ) {
        let lines = self.visible_lines();
        let text = lines.join("\n");
        let (mut a, mut b) = (actions::offset_of(&lines, s), actions::offset_of(&lines, e));
        if a > b {
            std::mem::swap(&mut a, &mut b);
        }
        let taken = if linewise {
            format!("{}\n", &text[a..b])
        } else {
            text[a..b].to_owned()
        };
        match op {
            Operator::Yank => {
                self.vim.register = Some((taken.clone(), linewise));
                fx.clipboard = Some(taken);
                let at = if linewise {
                    pos(
                        s.line,
                        self.content
                            .cursor()
                            .position
                            .column
                            .min(lines[s.line].len()),
                    )
                } else {
                    s
                };
                self.vim.mode = Mode::Normal;
                self.set_cursor(collapsed(at));
            }
            Operator::Delete | Operator::Change => {
                self.vim.register = Some((taken.clone(), linewise));
                fx.clipboard = Some(taken);
                self.vim_record(fx);
                if linewise && op == Operator::Change {
                    // `cc` keeps the line and its indentation.
                    let indent = indent_of(&lines[s.line]);
                    self.vim_replace(&lines, a + indent, b, "");
                    self.set_cursor(collapsed(pos(s.line, indent)));
                } else if linewise {
                    // Whole lines, with a line break (the one before them for the last line).
                    let (from, to) = if b < text.len() {
                        (a, b + 1)
                    } else {
                        (a.saturating_sub(1), b)
                    };
                    self.vim_replace(&lines, from, to, "");
                    let now = self.visible_lines();
                    let line = s.line.min(now.len().saturating_sub(1));
                    self.set_cursor(collapsed(pos(line, indent_of(&now[line]))));
                } else {
                    self.vim_replace(&lines, a, b, "");
                }
                if op == Operator::Change {
                    self.vim_enter_insert();
                } else {
                    self.vim.mode = Mode::Normal;
                }
            }
            Operator::Indent | Operator::Outdent | Operator::Comment => {
                self.vim.mode = Mode::Normal;
                self.extra.clear();
                self.set_cursor(Cursor {
                    position: pos(e.line, lines[e.line].len()),
                    selection: Some(pos(s.line, 0)),
                });
                let action = match op {
                    Operator::Indent => EditorAction::Indent,
                    Operator::Outdent => EditorAction::Outdent,
                    _ => EditorAction::ToggleComments,
                };
                let outcome = self.run(id, action, ctx);
                fx.scroll.push(outcome.scroll);
                let now = self.visible_lines();
                let line = s.line.min(now.len().saturating_sub(1));
                self.set_cursor(collapsed(pos(line, indent_of(&now[line]))));
            }
            Operator::Case(case) => {
                self.vim.mode = Mode::Normal;
                if a == b {
                    return;
                }
                self.vim_record(fx);
                let changed = match case {
                    Case::Upper => text[a..b].to_uppercase(),
                    Case::Lower => text[a..b].to_lowercase(),
                    Case::Toggle => toggled(&text[a..b]),
                };
                self.vim_replace(&lines, a, b, &changed);
                self.set_cursor(collapsed(s));
            }
        }
    }

    /// Replaces bytes `a..b` of `lines` (joined) with `with`, leaving the cursor after it.
    fn vim_replace(&mut self, lines: &[String], a: usize, b: usize, with: &str) {
        let s = actions::position_at(lines, a);
        let e = actions::position_at(lines, b);
        self.extra.clear();
        if a == b {
            self.set_cursor(collapsed(s));
            if !with.is_empty() {
                self.perform_one(Action::Edit(Edit::Paste(Arc::new(with.to_owned()))));
            }
            return;
        }
        self.set_cursor(Cursor {
            position: e,
            selection: Some(s),
        });
        if with.is_empty() {
            self.perform_one(Action::Edit(Edit::Backspace));
        } else {
            self.perform_one(Action::Edit(Edit::Paste(Arc::new(with.to_owned()))));
        }
    }

    /// `r` and a character: replaces `count` characters from the cursor.
    fn vim_replace_chars(&mut self, c: char, fx: &mut Effects) {
        let count = self.vim.take_count();
        let lines = self.visible_lines();
        let here = self.content.cursor().position;
        let line = &lines[here.line];
        let mut end = here.column;
        for _ in 0..count {
            if end >= line.len() {
                return;
            }
            end += char_len(line, end);
        }
        let a = actions::offset_of(&lines, here);
        let b = actions::offset_of(&lines, pos(here.line, end));
        self.vim_record(fx);
        self.vim_replace(&lines, a, b, &c.to_string().repeat(count));
        self.set_cursor(collapsed(pos(
            here.line,
            char_before(&self.line_at(here.line), end),
        )));
    }

    /// `p` (after the cursor) and `P` (before it) put the register: whole lines go below or
    /// above the cursor's line.
    fn vim_put(&mut self, after: bool, fx: &mut Effects) {
        let Some((text, linewise)) = self.vim.register.clone() else {
            return;
        };
        let count = self.vim.take_count();
        let lines = self.visible_lines();
        self.vim_record(fx);
        if self.vim.mode.visual() {
            let (s, e) = self.vim_visual_range();
            self.vim.mode = Mode::Normal;
            let (a, b) = (actions::offset_of(&lines, s), actions::offset_of(&lines, e));
            let body = if linewise {
                text.trim_end_matches('\n').to_owned()
            } else {
                text.clone()
            };
            self.vim_replace(&lines, a, b, &body.repeat(count));
            return;
        }
        let here = self.content.cursor().position;
        if linewise {
            let body = text.repeat(count);
            if after {
                let end = actions::offset_of(&lines, pos(here.line, lines[here.line].len()));
                let inserted = format!("\n{}", body.trim_end_matches('\n'));
                self.vim_replace(&lines, end, end, &inserted);
                let line = here.line + 1;
                self.set_cursor(collapsed(pos(line, indent_of(&self.line_at(line)))));
            } else {
                let start = actions::offset_of(&lines, pos(here.line, 0));
                self.vim_replace(&lines, start, start, &body);
                self.set_cursor(collapsed(pos(
                    here.line,
                    indent_of(&self.line_at(here.line)),
                )));
            }
            return;
        }
        let line = &lines[here.line];
        let column = if after && !line.is_empty() {
            here.column + char_len(line, here.column)
        } else {
            here.column
        };
        let at = actions::offset_of(&lines, pos(here.line, column));
        let body = text.repeat(count);
        self.vim_replace(&lines, at, at, &body);
        // On the last character put.
        let now = self.visible_lines();
        let end = actions::position_at(&now, at + body.len());
        let end_line = &now[end.line];
        self.set_cursor(collapsed(pos(end.line, char_before(end_line, end.column))));
    }

    /// `*` / `#` and `n` / `N`: the next (or previous) whole-word match of the search.
    fn vim_search(&mut self, word: &str, forward: bool) -> bool {
        let lines = self.visible_lines();
        let text = lines.join("\n");
        let at = actions::offset_of(&lines, self.vim_cursor());
        let matches = actions::all_matches(&text, word, true);
        let found = if forward {
            matches.iter().find(|s| **s > at).or(matches.first())
        } else {
            matches.iter().rev().find(|s| **s < at).or(matches.last())
        };
        match found {
            Some(&start) => {
                self.vim_move(actions::position_at(&lines, start));
                true
            }
            None => false,
        }
    }

    fn vim_g(&mut self, id: &str, ctx: &ActionContext, c: char, fx: &mut Effects) {
        let case = match c {
            '~' => Some(Case::Toggle),
            'u' => Some(Case::Lower),
            'U' => Some(Case::Upper),
            _ => None,
        };
        let operator = match (c, case) {
            ('c', _) => Some(Operator::Comment),
            (_, Some(case)) => Some(Operator::Case(case)),
            _ => None,
        };
        if let Some(op) = operator {
            // `gcc`, `g~~`, `guu`: the second key is the last one of the operator.
            match self.vim.operator {
                _ if self.vim.mode.visual() => self.vim_operator(id, ctx, op, fx),
                Some((pending, count)) if pending == op => {
                    let count = count * self.vim.take_count();
                    self.vim.operator = None;
                    self.vim_lines(id, ctx, op, count, fx);
                }
                Some(_) => self.vim.reset(),
                None => {
                    let count = self.vim.take_count();
                    self.vim.operator = Some((op, count));
                }
            }
            return;
        }
        match c {
            'g' => self.vim_motion(id, ctx, VimMotion::FirstLine, fx),
            'd' | 'D' => {
                self.vim.reset();
                fx.request = Some("go_to_definition");
            }
            'h' => {
                self.vim.reset();
                fx.request = Some("vim_hover");
            }
            '_' => self.vim_motion(id, ctx, VimMotion::LineEnd, fx),
            _ => self.vim.reset(),
        }
    }

    fn vim_z(&mut self, id: &str, c: char, fx: &mut Effects) {
        self.vim.reset();
        let op = match c {
            'z' => {
                fx.scroll.push(self.center_cursor(id));
                return;
            }
            'c' => FoldOp::AtCursor,
            'o' => FoldOp::UnfoldAtCursor,
            'a' => FoldOp::ToggleAtCursor,
            'M' => FoldOp::FoldAll,
            'R' => FoldOp::UnfoldAll,
            _ => return,
        };
        let outcome = self.fold_op(id, op);
        fx.scroll.push(outcome.scroll);
    }

    fn vim_normal_command(&mut self, id: &str, ctx: &ActionContext, key: VimKey, fx: &mut Effects) {
        use VimKey as K;
        let count = self.vim.take_count();
        let here = self.content.cursor().position;
        let line = self.line_at(here.line);
        let run = |s: &mut Self, action: EditorAction, fx: &mut Effects| {
            let outcome = s.run(id, action, ctx);
            fx.scroll.push(outcome.scroll);
            fx.clipboard = outcome.clipboard.or(fx.clipboard.take());
        };
        match key {
            K::Char('i') => self.vim_enter_insert(),
            K::Char('a') => {
                let column = (here.column + char_len(&line, here.column)).min(line.len());
                self.set_cursor(collapsed(pos(here.line, column)));
                self.vim_enter_insert();
            }
            K::Char('I') => {
                self.set_cursor(collapsed(pos(here.line, indent_of(&line))));
                self.vim_enter_insert();
            }
            K::Char('A') => {
                self.set_cursor(collapsed(pos(here.line, line.len())));
                self.vim_enter_insert();
            }
            K::Char('o') => {
                self.vim_record(fx);
                let len = line.len();
                self.set_cursor(collapsed(pos(here.line, len)));
                self.key_one(EditKey::Enter, ctx.indent, false);
                self.vim_enter_insert();
            }
            K::Char('O') => {
                self.vim_record(fx);
                let indent: String = line
                    .chars()
                    .take_while(|c| *c == ' ' || *c == '\t')
                    .collect();
                self.set_cursor(collapsed(pos(here.line, 0)));
                self.perform_one(Action::Edit(Edit::Paste(Arc::new(format!("{indent}\n")))));
                self.set_cursor(collapsed(pos(here.line, indent.len())));
                self.vim_enter_insert();
            }
            K::Char('v') => self.vim_enter_visual(Mode::Visual),
            K::Char('V') => self.vim_enter_visual(Mode::VisualLine),
            K::Char('x') | K::Delete => {
                self.vim.count = Some(count);
                self.vim.operator = Some((Operator::Delete, 1));
                self.vim_motion(id, ctx, VimMotion::Right, fx);
            }
            K::Char('X') => {
                self.vim.count = Some(count);
                self.vim.operator = Some((Operator::Delete, 1));
                self.vim_motion(id, ctx, VimMotion::Left, fx);
            }
            K::Char('s') => {
                self.vim.count = Some(count);
                self.vim.operator = Some((Operator::Change, 1));
                self.vim_motion(id, ctx, VimMotion::Right, fx);
            }
            K::Char('S') => self.vim_lines(id, ctx, Operator::Change, count, fx),
            K::Char('D') | K::Char('C') => {
                let op = if key == K::Char('D') {
                    Operator::Delete
                } else {
                    Operator::Change
                };
                self.vim.count = Some(count);
                self.vim.operator = Some((op, 1));
                self.vim_motion(id, ctx, VimMotion::LineEnd, fx);
            }
            K::Char('Y') => self.vim_lines(id, ctx, Operator::Yank, count, fx),
            K::Char('p') => self.vim_put(true, fx),
            K::Char('P') => self.vim_put(false, fx),
            K::Char('u') => {
                for _ in 0..count {
                    run(self, EditorAction::Undo, fx);
                }
            }
            K::Ctrl('r') => {
                for _ in 0..count {
                    run(self, EditorAction::Redo, fx);
                }
            }
            K::Char('J') => {
                let last = (here.line + count.max(2) - 1).min(self.content.line_count() - 1);
                self.set_cursor(Cursor {
                    position: pos(last, 0),
                    selection: Some(pos(here.line, 0)),
                });
                run(self, EditorAction::JoinLines, fx);
            }
            K::Char('~') => {
                if line.is_empty() {
                    return;
                }
                let mut end = here.column;
                for _ in 0..count {
                    if end >= line.len() {
                        break;
                    }
                    end += char_len(&line, end);
                }
                self.vim_apply(
                    id,
                    ctx,
                    Operator::Case(Case::Toggle),
                    here,
                    pos(here.line, end),
                    false,
                    fx,
                );
                let column = end.min(last_column(&line));
                self.set_cursor(collapsed(pos(here.line, column)));
            }
            K::Char('.') => self.vim_repeat(id, ctx, fx),
            K::Char('*') | K::Char('#') => {
                let column = actions::floor(&line, here.column);
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
                if end > start {
                    let word = line[start..end].to_owned();
                    self.set_cursor(collapsed(pos(here.line, start)));
                    self.vim_search(&word, key == K::Char('*'));
                    self.vim.search = Some(word);
                }
            }
            K::Char('n') | K::Char('N') => {
                let forward = key == K::Char('n');
                match self.vim.search.clone() {
                    Some(word) => {
                        self.vim_search(&word, forward);
                    }
                    None => {
                        fx.request = Some(if forward {
                            "vim_search_next"
                        } else {
                            "vim_search_previous"
                        });
                    }
                }
            }
            K::Char('/') | K::Char('?') => {
                self.vim.search = None;
                fx.request = Some(if key == K::Char('/') {
                    "vim_search"
                } else {
                    "vim_search_backward"
                });
            }
            K::Char(':') => fx.request = Some("vim_command"),
            K::Char('K') => fx.request = Some("vim_hover"),
            K::Ctrl('o') => fx.request = Some("vim_go_back"),
            K::Tab | K::Ctrl('i') => fx.request = Some("vim_go_forward"),
            K::Ctrl('d') | K::Ctrl('u') => {
                let lh = self.metrics.borrow().line_height.max(1.0);
                let height = self.viewport.get().map_or(lh * 20.0, |v| v.height);
                let half = ((height / lh / 2.0).floor() as usize).max(1);
                let motion = if key == K::Ctrl('d') {
                    Motion::Down
                } else {
                    Motion::Up
                };
                for _ in 0..half * count {
                    self.content.perform(Action::Move(motion));
                }
                fx.scroll.push(self.center_cursor(id));
            }
            K::Ctrl('f') | K::PageDown => {
                let outcome = self.page(id, true, false);
                fx.scroll.push(outcome.scroll);
            }
            K::Ctrl('b') | K::PageUp => {
                let outcome = self.page(id, false, false);
                fx.scroll.push(outcome.scroll);
            }
            K::Ctrl('e') => run(self, EditorAction::LineDown, fx),
            K::Ctrl('y') => run(self, EditorAction::LineUp, fx),
            _ => {}
        }
    }

    fn vim_visual_command(&mut self, id: &str, ctx: &ActionContext, key: VimKey, fx: &mut Effects) {
        use VimKey as K;
        let count = self.vim.take_count();
        let (s, e) = self.vim_visual_range();
        let linewise = self.vim.mode == Mode::VisualLine;
        match key {
            K::Char('v') | K::Char('V') => {
                let mode = if key == K::Char('v') {
                    Mode::Visual
                } else {
                    Mode::VisualLine
                };
                if self.vim.mode == mode {
                    self.vim_leave_visual();
                } else {
                    self.vim.mode = mode;
                    self.vim_select();
                }
            }
            K::Char('o') => {
                std::mem::swap(&mut self.vim.anchor, &mut self.vim.head);
                self.vim_select();
            }
            K::Char('x') | K::Delete => {
                self.vim.mode = Mode::Normal;
                self.vim_apply(id, ctx, Operator::Delete, s, e, linewise, fx);
            }
            K::Char('X') | K::Char('D') => {
                let end = self.line_at(e.line).len();
                self.vim.mode = Mode::Normal;
                self.vim_apply(
                    id,
                    ctx,
                    Operator::Delete,
                    pos(s.line, 0),
                    pos(e.line, end),
                    true,
                    fx,
                );
            }
            K::Char('s') => {
                self.vim.mode = Mode::Normal;
                self.vim_apply(id, ctx, Operator::Change, s, e, linewise, fx);
            }
            K::Char('S') | K::Char('C') | K::Char('R') => {
                let end = self.line_at(e.line).len();
                self.vim.mode = Mode::Normal;
                self.vim_apply(
                    id,
                    ctx,
                    Operator::Change,
                    pos(s.line, 0),
                    pos(e.line, end),
                    true,
                    fx,
                );
            }
            K::Char('Y') => {
                let end = self.line_at(e.line).len();
                self.vim.mode = Mode::Normal;
                self.vim_apply(
                    id,
                    ctx,
                    Operator::Yank,
                    pos(s.line, 0),
                    pos(e.line, end),
                    true,
                    fx,
                );
            }
            K::Char('~') | K::Char('u') | K::Char('U') => {
                let case = match key {
                    K::Char('~') => Case::Toggle,
                    K::Char('u') => Case::Lower,
                    _ => Case::Upper,
                };
                self.vim.mode = Mode::Normal;
                self.vim_apply(id, ctx, Operator::Case(case), s, e, false, fx);
            }
            K::Char('J') => {
                self.vim.mode = Mode::Normal;
                self.set_cursor(Cursor {
                    position: pos(e.line.max(s.line + 1).min(self.content.line_count() - 1), 0),
                    selection: Some(pos(s.line, 0)),
                });
                let outcome = self.run(id, EditorAction::JoinLines, ctx);
                fx.scroll.push(outcome.scroll);
            }
            K::Char('p') | K::Char('P') => {
                self.vim.count = Some(count);
                self.vim_put(true, fx);
            }
            K::Char(':') => fx.request = Some("vim_command"),
            K::Char('*') | K::Char('#') => {}
            _ => {}
        }
    }

    /// `.`: the last change again, with the text typed after it.
    fn vim_repeat(&mut self, id: &str, ctx: &ActionContext, fx: &mut Effects) {
        let Some((keys, typed)) = self.vim.last_change.clone() else {
            return;
        };
        self.vim.replaying = true;
        for key in keys {
            self.vim_handle(id, key, ctx, fx);
        }
        if self.vim.mode == Mode::Insert {
            if !typed.is_empty() {
                self.perform_one(Action::Edit(Edit::Paste(Arc::new(typed))));
            }
            self.vim_leave_insert();
        }
        self.vim.replaying = false;
    }
}

fn toggled(text: &str) -> String {
    text.chars()
        .flat_map(|c| {
            if c.is_uppercase() {
                c.to_lowercase().collect::<Vec<_>>()
            } else {
                c.to_uppercase().collect::<Vec<_>>()
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ctx() -> ActionContext {
        ActionContext {
            indent: Some(crate::editor::Indent::spaces(4)),
            pairs: true,
            comment: Some("#".into()),
            ..Default::default()
        }
    }

    fn keys(s: &mut EditorState, typed: &str) {
        for c in typed.chars() {
            let key = match c {
                '\u{1b}' => VimKey::Escape,
                '\n' => VimKey::Enter,
                c => VimKey::Char(c),
            };
            // Insert mode types through the editor, as its keys do.
            if let (Mode::Insert, VimKey::Char(c)) = (s.vim.mode, &key) {
                let _ = s.perform("e", Action::Edit(Edit::Insert(*c)));
                continue;
            }
            let _ = s.vim_key("e", key, &ctx());
        }
    }

    fn at(s: &EditorState) -> (usize, usize) {
        let p = s.content.cursor().position;
        (p.line, p.column)
    }

    #[test]
    fn motions() {
        let mut s = EditorState::new("foo bar.baz\n  qux");
        keys(&mut s, "w");
        assert_eq!(at(&s), (0, 4));
        keys(&mut s, "w");
        assert_eq!(at(&s), (0, 7));
        keys(&mut s, "W");
        assert_eq!(at(&s), (1, 2));
        keys(&mut s, "0");
        assert_eq!(at(&s), (1, 0));
        keys(&mut s, "^");
        assert_eq!(at(&s), (1, 2));
        keys(&mut s, "gg$");
        assert_eq!(at(&s), (0, 10));
        keys(&mut s, "0fb");
        assert_eq!(at(&s), (0, 4));
        keys(&mut s, ";");
        assert_eq!(at(&s), (0, 8));
        keys(&mut s, "G");
        assert_eq!(at(&s), (1, 2));
    }

    #[test]
    fn operators_and_counts() {
        let mut s = EditorState::new("one two three\nfour\nfive");
        keys(&mut s, "dw");
        assert_eq!(s.text(), "two three\nfour\nfive");
        keys(&mut s, "2dd");
        assert_eq!(s.text(), "five");
        keys(&mut s, "u");
        assert_eq!(s.text(), "two three\nfour\nfive");
        keys(&mut s, "ggcwTWO\u{1b}");
        assert_eq!(s.text(), "TWO three\nfour\nfive");
        keys(&mut s, "w.");
        assert_eq!(s.text(), "TWO TWO\nfour\nfive");
        keys(&mut s, "jyyp");
        assert_eq!(s.text(), "TWO TWO\nfour\nfour\nfive");
        keys(&mut s, "x");
        assert_eq!(s.text(), "TWO TWO\nfour\nour\nfive");
    }

    #[test]
    fn text_objects_and_visual_mode() {
        let mut s = EditorState::new("f(a, \"b c\")");
        keys(&mut s, "fbdi\"");
        assert_eq!(s.text(), "f(a, \"\")");
        keys(&mut s, "0fadi(");
        assert_eq!(s.text(), "f()");
        let mut s = EditorState::new("abc def\nghi");
        keys(&mut s, "vey");
        assert_eq!(s.vim.register, Some(("abc".to_owned(), false)));
        keys(&mut s, "Vjd");
        assert_eq!(s.text(), "");
        let mut s = EditorState::new("a\nb\nc");
        keys(&mut s, ">>");
        assert_eq!(s.text(), "    a\nb\nc");
        keys(&mut s, "jgcc");
        assert_eq!(s.text(), "    a\n# b\nc");
    }

    #[test]
    fn modes_are_reported() {
        let mut s = EditorState::new("x");
        let out = s.vim_key("e", VimKey::Char('i'), &ctx());
        assert_eq!(out.action, Some("vim_insert"));
        let out = s.vim_key("e", VimKey::Escape, &ctx());
        assert_eq!(out.action, Some("vim_normal"));
        let out = s.vim_key("e", VimKey::Char('/'), &ctx());
        assert_eq!(out.action, Some("vim_search"));
    }
}
