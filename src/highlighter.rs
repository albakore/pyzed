//! Syntax highlighting with user-defined scope colors (so themes can match Zed's palettes).
//!
//! Adapted from `iced_highlighter`, which only ships a handful of fixed syntect themes.

use std::collections::HashMap;
use std::hash::{Hash, Hasher};
use std::ops::Range;
use std::str::FromStr;
use std::sync::{LazyLock, Mutex};

use iced::advanced::text::highlighter::{self, Format};
use iced::{Color, Font};
use two_face::re_exports::syntect::highlighting::{
    self, FontStyle, ScopeSelectors, StyleModifier, ThemeItem, ThemeSettings,
};
use two_face::re_exports::syntect::parsing;

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

#[derive(Debug, Clone, PartialEq)]
pub struct Settings {
    pub token: String,
    pub theme: u64,
    pub font: Font,
    /// Color of text no rule matches (`None`: the iced theme's text color).
    pub default: Option<Color>,
}

#[derive(Debug)]
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

    pub fn color(&self) -> Option<Color> {
        self.color
    }
}

pub struct Highlighter {
    syntax: &'static parsing::SyntaxReference,
    default: Option<Color>,
    highlighter: highlighting::Highlighter<'static>,
    font: Font,
    caches: Vec<(parsing::ParseState, parsing::ScopeStack)>,
    current_line: usize,
}

fn syntax(token: &str) -> &'static parsing::SyntaxReference {
    SYNTAXES
        .find_syntax_by_token(token)
        .unwrap_or_else(|| SYNTAXES.find_syntax_plain_text())
}

impl highlighter::Highlighter for Highlighter {
    type Settings = Settings;
    type Highlight = Highlight;
    type Iterator<'a> = Box<dyn Iterator<Item = (Range<usize>, Self::Highlight)> + 'a>;

    fn new(settings: &Self::Settings) -> Self {
        let syntax = syntax(&settings.token);
        Highlighter {
            syntax,
            default: settings.default,
            highlighter: highlighting::Highlighter::new(theme(settings.theme)),
            font: settings.font,
            caches: vec![(parsing::ParseState::new(syntax), parsing::ScopeStack::new())],
            current_line: 0,
        }
    }

    fn update(&mut self, new_settings: &Self::Settings) {
        self.syntax = syntax(&new_settings.token);
        self.highlighter = highlighting::Highlighter::new(theme(new_settings.theme));
        self.font = new_settings.font;
        self.default = new_settings.default;
        self.change_line(0);
    }

    fn change_line(&mut self, line: usize) {
        let snapshot = line / LINES_PER_SNAPSHOT;

        if snapshot <= self.caches.len() {
            self.caches.truncate(snapshot);
            self.current_line = snapshot * LINES_PER_SNAPSHOT;
        } else {
            self.caches.truncate(1);
            self.current_line = 0;
        }

        let (parser, stack) = self.caches.last().cloned().unwrap_or_else(|| {
            (
                parsing::ParseState::new(self.syntax),
                parsing::ScopeStack::new(),
            )
        });

        self.caches.push((parser, stack));
    }

    fn highlight_line(&mut self, line: &str) -> Self::Iterator<'_> {
        if self.current_line / LINES_PER_SNAPSHOT >= self.caches.len() {
            let (parser, stack) = self.caches.last().expect("caches must not be empty");
            self.caches.push((parser.clone(), stack.clone()));
        }

        self.current_line += 1;

        let (parser, stack) = self.caches.last_mut().expect("caches must not be empty");
        let ops = parser.parse_line(line, &SYNTAXES).unwrap_or_default();
        let highlighter = &self.highlighter;
        let font = self.font;
        let default = self.default;

        Box::new(
            ScopeRangeIterator {
                ops,
                line_length: line.len(),
                index: 0,
                last_str_index: 0,
            }
            .filter_map(move |(range, scope)| {
                let _ = stack.apply(&scope);
                if range.is_empty() {
                    return None;
                }
                let style = highlighter.style_mod_for_stack(&stack.scopes);
                let color = style
                    .foreground
                    .map(|c| Color::from_rgba8(c.r, c.g, c.b, f32::from(c.a) / 255.0))
                    .or(default);
                let font = style.font_style.and_then(|fs| {
                    if fs.is_empty() {
                        return None;
                    }
                    let mut f = font;
                    if fs.contains(FontStyle::ITALIC) {
                        f.style = iced::font::Style::Italic;
                    }
                    if fs.contains(FontStyle::BOLD) {
                        f.weight = iced::font::Weight::Bold;
                    }
                    Some(f)
                });
                Some((range, Highlight { color, font }))
            }),
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
