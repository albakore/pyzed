//! Syntax highlighting with user-defined scope colors (so themes can match Zed's palettes).
//!
//! Adapted from `iced_highlighter`, which only ships a handful of fixed syntect themes. A code
//! editor keeps its highlighting in a [`Document`]: every line with the parser state before it,
//! so an edit only parses again the lines it changed (until the parser is back in the state it
//! was in before), and the text, the sticky headers and the minimap share one parse. On top of
//! syntect's scopes, Python gets Zed's naming conventions (types, constants, properties and
//! variables).

use std::collections::HashMap;
use std::hash::{Hash, Hasher};
use std::ops::Range;
use std::str::FromStr;
use std::sync::{Arc, LazyLock, Mutex};
use std::time::{Duration, Instant};

use iced::advanced::text::highlighter::{self, Format};
use iced::{Color, Font};
use two_face::re_exports::syntect::highlighting::{
    self, FontStyle, ScopeSelectors, StyleModifier, ThemeItem, ThemeSettings,
};
use two_face::re_exports::syntect::parsing::{self, Scope, ScopeStack};

static SYNTAXES: LazyLock<parsing::SyntaxSet> = LazyLock::new(two_face::syntax::extra_no_newlines);

static THEMES: LazyLock<Mutex<HashMap<u64, &'static highlighting::Theme>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));

const LINES_PER_SNAPSHOT: usize = 50;

/// Registers (once) a syntect theme built from `(scope, color, italic, bold)` rules.
pub fn theme_id(rules: &[(String, Color, bool, bool)]) -> u64 {
    let mut hasher = std::hash::DefaultHasher::new();
    for (scope, color, italic, bold) in rules {
        scope.hash(&mut hasher);
        color.into_rgba8().hash(&mut hasher);
        italic.hash(&mut hasher);
        bold.hash(&mut hasher);
    }
    let id = hasher.finish();

    let mut themes = THEMES.lock().unwrap();
    themes.entry(id).or_insert_with(|| {
        let scopes = rules
            .iter()
            .filter_map(|(scope, color, italic, bold)| {
                let [r, g, b, a] = color.into_rgba8();
                let mut font_style = FontStyle::empty();
                if *italic {
                    font_style |= FontStyle::ITALIC;
                }
                if *bold {
                    font_style |= FontStyle::BOLD;
                }
                Some(ThemeItem {
                    scope: ScopeSelectors::from_str(scope).ok()?,
                    style: StyleModifier {
                        foreground: Some(highlighting::Color { r, g, b, a }),
                        background: None,
                        font_style: Some(font_style),
                    },
                })
            })
            .collect();
        Box::leak(Box::new(highlighting::Theme {
            name: None,
            author: None,
            settings: ThemeSettings::default(),
            scopes,
        }))
    });
    id
}

fn theme(id: u64) -> &'static highlighting::Theme {
    static EMPTY: LazyLock<highlighting::Theme> = LazyLock::new(highlighting::Theme::default);
    THEMES.lock().unwrap().get(&id).copied().unwrap_or(&EMPTY)
}

pub fn has_syntax(token: &str) -> bool {
    SYNTAXES.find_syntax_by_token(token).is_some()
}

/// What a [`Highlighter`] and a [`Document`] need to color text.
#[derive(Debug, Clone, PartialEq)]
pub struct Settings {
    pub token: String,
    pub theme: u64,
    pub font: Font,
    /// Color of text no rule matches (`None`: the iced theme's text color).
    pub default: Option<Color>,
    /// The editor's shared highlighting: lines are read from it instead of parsed again.
    pub document: Option<Shared>,
}

/// A [`Document`] shared by an editor's text, sticky headers and minimap.
#[derive(Clone, Default)]
pub struct Shared(Arc<Mutex<Document>>);

impl Shared {
    pub fn lock(&self) -> std::sync::MutexGuard<'_, Document> {
        self.0.lock().unwrap_or_else(|e| e.into_inner())
    }
}

impl PartialEq for Shared {
    fn eq(&self, other: &Self) -> bool {
        Arc::ptr_eq(&self.0, &other.0)
    }
}

impl std::fmt::Debug for Shared {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("Shared(..)")
    }
}

#[derive(Debug, Clone)]
pub struct Highlight {
    color: Option<Color>,
    font: Option<Font>,
}

impl Highlight {
    pub fn to_format(&self, theme: &iced::Theme) -> Format<Font> {
        Format {
            color: Some(self.color.unwrap_or_else(|| theme.palette().text)),
            font: self.font,
        }
    }
}

/// A colored piece of a line.
#[derive(Debug, Clone, PartialEq)]
pub struct Span {
    pub range: Range<usize>,
    pub color: Option<Color>,
    pub font: Option<Font>,
    /// A name that may lead to a definition (Ctrl+click): not a keyword, string, comment,
    /// number, punctuation or `self`.
    pub link: bool,
}

impl Span {
    fn highlight(&self) -> Highlight {
        Highlight {
            color: self.color,
            font: self.font,
        }
    }
}

type State = (parsing::ParseState, ScopeStack);

fn syntax(token: &str) -> &'static parsing::SyntaxReference {
    SYNTAXES
        .find_syntax_by_token(token)
        .unwrap_or_else(|| SYNTAXES.find_syntax_plain_text())
}

fn initial(token: &str) -> State {
    (parsing::ParseState::new(syntax(token)), ScopeStack::new())
}

fn scope(name: &str) -> Scope {
    Scope::new(name).expect("a valid scope")
}

/// The scopes the Python conventions look at and add.
struct Scopes {
    generic: Scope,
    qualified: Scope,
    annotation: [Scope; 2],
    constant: Scope,
    class: Scope,
    member: Scope,
    variable: Scope,
    mapping: Scope,
    mapping_key: Scope,
    key_value: Scope,
    string: Scope,
    not_links: [Scope; 8],
}

static SCOPES: LazyLock<Scopes> = LazyLock::new(|| Scopes {
    generic: scope("meta.generic-name"),
    qualified: scope("meta.qualified-name"),
    annotation: [
        scope("meta.function.parameters.annotation"),
        scope("meta.function.annotation.return"),
    ],
    constant: scope("variable.other.constant.python"),
    class: scope("support.class.python"),
    member: scope("variable.other.member.python"),
    variable: scope("variable.other.readwrite.python"),
    mapping: scope("meta.mapping-or-set"),
    mapping_key: scope("meta.mapping.key.python"),
    key_value: scope("punctuation.separator.mapping.key-value"),
    string: scope("meta.string"),
    not_links: [
        scope("comment"),
        scope("string"),
        scope("keyword"),
        scope("storage"),
        scope("constant.numeric"),
        scope("constant.language"),
        scope("punctuation"),
        scope("variable.language"),
    ],
});

fn has(stack: &[Scope], wanted: Scope) -> bool {
    stack.iter().any(|s| wanted.is_prefix_of(*s))
}

/// Zed's naming conventions for the Python names syntect leaves generic (`meta.generic-name`
/// right under `meta.qualified-name`): `ALL_CAPS` is a constant, `CamelCase` and names in
/// annotations are types, a name after a dot is a property and anything else a variable.
fn python_name(stack: &[Scope], line: &str, range: &Range<usize>) -> Option<Scope> {
    let s = &*SCOPES;
    let [.., outer, inner] = stack else {
        return None;
    };
    if !s.generic.is_prefix_of(*inner) || !s.qualified.is_prefix_of(*outer) {
        return None;
    }
    let bare = line.get(range.clone())?.trim_start_matches('_');
    let first = bare.chars().next()?;
    if first.is_ascii_uppercase() {
        let caps = bare
            .chars()
            .all(|c| c.is_ascii_uppercase() || c.is_ascii_digit() || c == '_');
        return Some(if caps { s.constant } else { s.class });
    }
    if s.annotation.iter().any(|a| has(stack, *a)) {
        return Some(s.class);
    }
    let after_dot = line[..range.start].trim_end().ends_with('.');
    Some(if after_dot { s.member } else { s.variable })
}

fn is_name(text: &str) -> bool {
    let mut chars = text.chars();
    chars.next().is_some_and(|c| c.is_alphabetic() || c == '_')
        && chars.all(|c| c.is_alphanumeric() || c == '_')
}

/// How lines are colored: the theme, the language and the fallbacks.
struct Painter {
    theme: highlighting::Highlighter<'static>,
    python: bool,
    font: Font,
    default: Option<Color>,
}

impl Painter {
    fn new(token: &str, theme_id: u64, font: Font, default: Option<Color>) -> Self {
        Self {
            theme: highlighting::Highlighter::new(theme(theme_id)),
            python: syntax(token).name == "Python",
            font,
            default,
        }
    }

    fn span(&self, stack: &ScopeStack, line: &str, range: Range<usize>) -> Span {
        let style = self.theme.style_mod_for_stack(&stack.scopes);
        let color = style
            .foreground
            .map(|c| Color::from_rgba8(c.r, c.g, c.b, f32::from(c.a) / 255.0))
            .or(self.default);
        let font = style.font_style.and_then(|fs| {
            if fs.is_empty() {
                return None;
            }
            let mut f = self.font;
            if fs.contains(FontStyle::ITALIC) {
                f.style = iced::font::Style::Italic;
            }
            if fs.contains(FontStyle::BOLD) {
                f.weight = iced::font::Weight::Bold;
            }
            Some(f)
        });
        let not_links = &SCOPES.not_links;
        let link = is_name(&line[range.clone()])
            && !stack
                .scopes
                .iter()
                .any(|scope| not_links.iter().any(|n| n.is_prefix_of(*scope)));
        Span {
            range,
            color,
            font,
            link,
        }
    }

    /// Colors one line from `state`, leaving `state` at the start of the next line.
    fn line(&self, state: &mut State, line: &str) -> Vec<Span> {
        let s = &*SCOPES;
        let (parser, stack) = state;
        let ops = parser.parse_line(line, &SYNTAXES).unwrap_or_default();
        let mut spans: Vec<Span> = Vec::new();
        // Strings right inside a `{` that is not known to be a dict or a set yet: the `:` after
        // one makes it a key (syntect only marks the keys after the first one).
        let mut keys: Vec<(usize, ScopeStack)> = Vec::new();
        let ranges = ScopeRangeIterator {
            ops,
            line_length: line.len(),
            index: 0,
            last_str_index: 0,
        };
        for (range, op) in ranges {
            let _ = stack.apply(&op);
            if range.is_empty() {
                continue;
            }
            let name = if self.python {
                python_name(&stack.scopes, line, &range)
            } else {
                None
            };
            let span = match name {
                Some(extra) => {
                    stack.push(extra);
                    let span = self.span(stack, line, range);
                    stack.pop();
                    span
                }
                None => self.span(stack, line, range),
            };
            if self.python {
                let scopes = &stack.scopes;
                if has(scopes, s.key_value) {
                    for (index, mut key) in keys.drain(..) {
                        if let Some(at) =
                            key.scopes.iter().rposition(|x| s.mapping.is_prefix_of(*x))
                        {
                            key.scopes.insert(at + 1, s.mapping_key);
                            let range = spans[index].range.clone();
                            spans[index] = self.span(&key, line, range);
                        }
                    }
                } else if has(scopes, s.mapping) && has(scopes, s.string) {
                    keys.push((spans.len(), stack.clone()));
                } else if !line[span.range.clone()].trim().is_empty() {
                    keys.clear();
                }
            }
            spans.push(span);
        }
        spans
    }
}

/// The highlighting of one line of a [`Document`].
struct Line {
    text: String,
    /// The parser state at the start of the line: exact down to the first line not parsed yet;
    /// below it, what it was before the last edit (to tell when parsing again can stop).
    before: Option<State>,
    spans: Option<Arc<[Span]>>,
}

/// The highlighting of a whole text, kept between edits (see the module docs).
#[derive(Default)]
pub struct Document {
    key: Option<(String, u64, Font, Option<Color>)>,
    lines: Vec<Line>,
    /// The lines above this one are highlighted.
    parsed: usize,
    /// The lines from `tail` up to `reusable` kept their highlighting from before the last edit:
    /// it is right again if the parser reaches one of them in the state it had there.
    tail: usize,
    reusable: usize,
    /// The parser state after the last line, once everything is parsed.
    end: Option<State>,
    /// `end` before the last edit, for when the parser catches up with the old parse.
    reusable_end: Option<State>,
}

impl Document {
    fn token(&self) -> &str {
        self.key.as_ref().map_or("txt", |k| k.0.as_str())
    }

    fn painter(&self) -> Painter {
        let (token, theme, font, default) = self
            .key
            .clone()
            .unwrap_or_else(|| ("txt".into(), 0, Font::MONOSPACE, None));
        Painter::new(&token, theme, font, default)
    }

    /// Takes the text's current lines, keeping the highlighting of the lines that did not change.
    pub fn update<S: AsRef<str>>(&mut self, settings: &Settings, lines: &[S]) {
        let key = (
            settings.token.clone(),
            settings.theme,
            settings.font,
            settings.default,
        );
        if self.key.as_ref() != Some(&key) {
            *self = Document {
                key: Some(key),
                ..Document::default()
            };
        }
        let old_len = self.lines.len();
        let mut prefix = 0;
        while prefix < old_len.min(lines.len()) && self.lines[prefix].text == lines[prefix].as_ref()
        {
            prefix += 1;
        }
        if prefix == old_len && prefix == lines.len() {
            return;
        }
        let mut suffix = 0;
        while suffix < (old_len - prefix).min(lines.len() - prefix)
            && self.lines[old_len - 1 - suffix].text == lines[lines.len() - 1 - suffix].as_ref()
        {
            suffix += 1;
        }
        let old_parsed = self.parsed;
        let old_end = self.end.take();
        // The state at the first changed line, if the old parse got there.
        let first = if prefix > old_parsed {
            None
        } else if prefix < old_len {
            self.lines[prefix].before.clone()
        } else if old_len == 0 {
            Some(initial(self.token()))
        } else {
            old_end.clone()
        };
        let tail_start = old_len - suffix;
        let mut tail = self.lines.split_off(tail_start);
        self.lines.truncate(prefix);
        // Below the old frontier nothing was right.
        for (i, line) in tail.iter_mut().enumerate() {
            if tail_start + i > old_parsed {
                line.before = None;
            }
            if tail_start + i >= old_parsed {
                line.spans = None;
            }
        }
        self.lines
            .extend(lines[prefix..lines.len() - suffix].iter().map(|text| Line {
                text: text.as_ref().to_owned(),
                before: None,
                spans: None,
            }));
        self.tail = self.lines.len();
        self.lines.extend(tail);
        self.reusable = if old_parsed > tail_start {
            old_parsed + self.tail - tail_start
        } else {
            self.tail
        };
        self.reusable_end = if old_parsed == old_len { old_end } else { None };
        self.parsed = prefix.min(old_parsed);
        if self.parsed == prefix
            && let Some(state) = first
        {
            self.arrive(state);
        }
    }

    /// The parser reached line `parsed` in `state`.
    fn arrive(&mut self, state: State) {
        let i = self.parsed;
        if i == self.lines.len() {
            self.end = Some(state);
            return;
        }
        let line = &mut self.lines[i];
        if i >= self.tail
            && i < self.reusable
            && line.spans.is_some()
            && line.before.as_ref() == Some(&state)
        {
            // Back in step with the old parse: the rest is still right.
            self.parsed = self.reusable;
            self.tail = self.reusable;
            if self.parsed == self.lines.len() {
                self.end = self.reusable_end.take();
            }
            return;
        }
        line.before = Some(state);
        if i >= self.tail {
            line.spans = None;
        }
    }

    /// Highlights the lines down to `last` (at least), and then for at most `budget`.
    fn parse(&mut self, last: usize, budget: Option<Duration>) {
        if self.parsed >= self.lines.len() {
            return;
        }
        let painter = self.painter();
        let started = Instant::now();
        while self.parsed < self.lines.len() {
            if self.parsed > last && budget.is_none_or(|b| started.elapsed() >= b) {
                break;
            }
            let i = self.parsed;
            let mut state = match self.lines[i].before.take() {
                Some(state) => state,
                None => initial(self.token()),
            };
            let before = state.clone();
            let spans = painter.line(&mut state, &self.lines[i].text);
            let line = &mut self.lines[i];
            line.before = Some(before);
            line.spans = Some(spans.into());
            self.parsed += 1;
            self.arrive(state);
        }
    }

    /// Highlights the lines down to `last`.
    pub fn ensure(&mut self, last: usize) {
        self.parse(last, None);
    }

    /// Highlights more lines for at most `budget`; `true` once every line is.
    pub fn advance(&mut self, budget: Duration) -> bool {
        self.parse(0, Some(budget));
        self.done()
    }

    pub fn done(&self) -> bool {
        self.parsed >= self.lines.len()
    }

    /// The colors of line `i`, if it is highlighted.
    pub fn spans(&self, i: usize) -> Option<&Arc<[Span]>> {
        if i < self.parsed {
            self.lines.get(i)?.spans.as_ref()
        } else {
            None
        }
    }

    /// The colors of line `i` holding `text`, highlighting down to it if needed.
    fn spans_of(&mut self, i: usize, text: &str) -> Option<Arc<[Span]>> {
        if self.lines.get(i)?.text != text {
            return None;
        }
        self.ensure(i);
        self.spans(i).cloned()
    }

    /// The piece of line `i` with byte `at`.
    pub fn span_at(&self, i: usize, at: usize) -> Option<&Span> {
        self.spans(i)?
            .iter()
            .find(|span| span.range.start <= at && at < span.range.end)
    }
}

pub struct Highlighter {
    token: String,
    painter: Painter,
    document: Option<Shared>,
    caches: Vec<State>,
    current_line: usize,
}

impl highlighter::Highlighter for Highlighter {
    type Settings = Settings;
    type Highlight = Highlight;
    type Iterator<'a> = Box<dyn Iterator<Item = (Range<usize>, Self::Highlight)> + 'a>;

    fn new(settings: &Self::Settings) -> Self {
        Highlighter {
            token: settings.token.clone(),
            painter: Painter::new(
                &settings.token,
                settings.theme,
                settings.font,
                settings.default,
            ),
            document: settings.document.clone(),
            caches: vec![initial(&settings.token)],
            current_line: 0,
        }
    }

    fn update(&mut self, new_settings: &Self::Settings) {
        *self = Self::new(new_settings);
    }

    fn change_line(&mut self, line: usize) {
        if self.document.is_some() {
            self.current_line = line;
            return;
        }
        let snapshot = line / LINES_PER_SNAPSHOT;

        if snapshot <= self.caches.len() {
            self.caches.truncate(snapshot);
            self.current_line = snapshot * LINES_PER_SNAPSHOT;
        } else {
            self.caches.truncate(1);
            self.current_line = 0;
        }

        let state = self
            .caches
            .last()
            .cloned()
            .unwrap_or_else(|| initial(&self.token));

        self.caches.push(state);
    }

    fn highlight_line(&mut self, line: &str) -> Self::Iterator<'_> {
        let index = self.current_line;
        self.current_line += 1;
        if let Some(document) = &self.document
            && let Some(spans) = document.lock().spans_of(index, line)
        {
            return Box::new((0..spans.len()).map(move |i| {
                let span = &spans[i];
                (span.range.clone(), span.highlight())
            }));
        }

        if index / LINES_PER_SNAPSHOT >= self.caches.len() {
            let state = self
                .caches
                .last()
                .expect("caches must not be empty")
                .clone();
            self.caches.push(state);
        }
        let state = self.caches.last_mut().expect("caches must not be empty");
        let spans = self.painter.line(state, line);
        Box::new(
            spans
                .into_iter()
                .map(|span| (span.range.clone(), span.highlight())),
        )
    }

    fn current_line(&self) -> usize {
        self.current_line
    }
}

struct ScopeRangeIterator {
    ops: Vec<(usize, parsing::ScopeStackOp)>,
    line_length: usize,
    index: usize,
    last_str_index: usize,
}

impl Iterator for ScopeRangeIterator {
    type Item = (Range<usize>, parsing::ScopeStackOp);

    fn next(&mut self) -> Option<Self::Item> {
        if self.index > self.ops.len() {
            return None;
        }

        let next_str_i = if self.index == self.ops.len() {
            self.line_length
        } else {
            self.ops[self.index].0
        };

        let range = self.last_str_index..next_str_i;
        self.last_str_index = next_str_i;

        let op = if self.index == 0 {
            parsing::ScopeStackOp::Noop
        } else {
            self.ops[self.index - 1].1.clone()
        };

        self.index += 1;
        Some((range, op))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const KEY: Color = Color::from_rgb(1.0, 0.0, 0.0);
    const STRING: Color = Color::from_rgb(0.0, 1.0, 0.0);
    const MEMBER: Color = Color::from_rgb(0.0, 0.0, 1.0);
    const CLASS: Color = Color::from_rgb(1.0, 1.0, 0.0);
    const CONSTANT: Color = Color::from_rgb(0.0, 1.0, 1.0);
    const VARIABLE: Color = Color::from_rgb(1.0, 0.0, 1.0);

    fn settings() -> Settings {
        let rules = [
            ("string", STRING),
            ("meta.mapping.key string", KEY),
            ("variable.other.readwrite", VARIABLE),
            ("variable.other.member", MEMBER),
            ("support.class", CLASS),
            ("variable.other.constant", CONSTANT),
        ]
        .map(|(scope, color)| (scope.to_string(), color, false, false));
        Settings {
            token: "py".into(),
            theme: theme_id(&rules),
            font: Font::MONOSPACE,
            default: None,
            document: None,
        }
    }

    fn color_of(document: &mut Document, line: usize, text: &str, word: &str) -> Option<Color> {
        let at = text.find(word).expect("the word is on the line");
        document.ensure(line);
        document.span_at(line, at).and_then(|span| span.color)
    }

    fn fresh(lines: &[&str]) -> Vec<Vec<Span>> {
        let mut document = Document::default();
        document.update(&settings(), lines);
        document.ensure(lines.len());
        (0..lines.len())
            .map(|i| document.spans(i).unwrap().to_vec())
            .collect()
    }

    #[test]
    fn colors_names_the_way_zed_does() {
        let lines = ["CHANNELS = make(Chat, self.channel, count)"];
        let mut document = Document::default();
        document.update(&settings(), &lines);
        assert_eq!(
            color_of(&mut document, 0, lines[0], "CHANNELS"),
            Some(CONSTANT)
        );
        assert_eq!(color_of(&mut document, 0, lines[0], "Chat"), Some(CLASS));
        assert_eq!(
            color_of(&mut document, 0, lines[0], "channel"),
            Some(MEMBER)
        );
        assert_eq!(
            color_of(&mut document, 0, lines[0], "count"),
            Some(VARIABLE)
        );
    }

    #[test]
    fn the_first_key_of_a_dict_is_a_key_too() {
        let lines = [
            "SIZES = {",
            "    \"xs\": 1,",
            "    \"sm\": 2,",
            "}",
            "pair = {\"a\": 1, \"b\": 2}",
        ];
        let mut document = Document::default();
        document.update(&settings(), &lines);
        assert_eq!(color_of(&mut document, 1, lines[1], "xs"), Some(KEY));
        assert_eq!(color_of(&mut document, 2, lines[2], "sm"), Some(KEY));
        assert_eq!(color_of(&mut document, 4, lines[4], "a\""), Some(KEY));
        assert_eq!(color_of(&mut document, 4, lines[4], "b\""), Some(KEY));
        let set = ["names = {\"a\", \"b\"}"];
        document.update(&settings(), &set);
        assert_eq!(color_of(&mut document, 0, set[0], "a\""), Some(STRING));
    }

    #[test]
    fn only_names_are_links() {
        let line = "def f(a): return run(self.size, \"text\", 3)  # note";
        let mut document = Document::default();
        document.update(&settings(), &[line]);
        document.ensure(0);
        let link = |word: &str| document.span_at(0, line.find(word).unwrap()).unwrap().link;
        assert!(link("run"));
        assert!(link("f("));
        assert!(link("size"));
        for word in ["def", "self", "return", "text", "3", "note"] {
            assert!(!link(word), "{word} is not a link");
        }
    }

    #[test]
    fn an_edit_parses_again_only_until_the_parser_is_back_in_step() {
        let mut lines: Vec<String> = (0..2000).map(|i| format!("value_{i} = {i}")).collect();
        let mut document = Document::default();
        document.update(&settings(), &lines);
        assert!(document.advance(Duration::from_secs(60)));
        lines[1000] = "value_1000 = 1000 + 1".into();
        document.update(&settings(), &lines);
        assert_eq!(document.parsed, 1000);
        document.ensure(1000);
        assert!(
            document.done(),
            "the lines after the edit kept their colors"
        );
    }

    #[test]
    fn edits_end_with_the_colors_of_a_fresh_parse() {
        let mut lines = vec![
            "x = 1",
            "def f():",
            "    return \"a\"",
            "y = {\"k\": 2}",
            "z = f()",
        ];
        let mut document = Document::default();
        document.update(&settings(), &lines);
        document.ensure(lines.len());
        // Opening a string changes every line below; closing it brings back the old colors.
        for edit in [
            (1, "s = \"\"\"open"),
            (3, "close\"\"\""),
            (1, "def f():"),
            (3, "y = {\"k\": 2}"),
        ] {
            lines[edit.0] = edit.1;
            document.update(&settings(), &lines);
            document.ensure(lines.len());
            let got: Vec<Vec<Span>> = (0..lines.len())
                .map(|i| document.spans(i).unwrap().to_vec())
                .collect();
            assert_eq!(
                got,
                fresh(&lines),
                "after setting line {} to {:?}",
                edit.0,
                edit.1
            );
        }
        lines.insert(2, "    pass");
        lines.remove(0);
        document.update(&settings(), &lines);
        document.ensure(lines.len());
        let got: Vec<Vec<Span>> = (0..lines.len())
            .map(|i| document.spans(i).unwrap().to_vec())
            .collect();
        assert_eq!(got, fresh(&lines));
    }
}
