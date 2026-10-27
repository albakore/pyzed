//! The user's key bindings, written like Zed's keymap: `"ctrl-shift-k"`, `"alt-up"`, `"f2"` or a
//! chord of two keys such as `"ctrl-k ctrl-c"` or Emacs's `"ctrl-x u"`. They are checked before
//! the default keys, and a key bound to nothing (`None`) loses its default action. The first key
//! of a chord only waits for the second one (a chord bound to nothing leaves the second key to
//! the app, so the app's own chords work while the editor has the keyboard).

use iced::keyboard;
use iced::widget::text_editor;

use super::{EditorAction, FoldOp};

/// What a key runs: an editor action or a fold command.
#[derive(Debug, Clone, Copy)]
pub enum Target {
    Action(EditorAction),
    Fold(FoldOp),
}

/// The fold commands, by Zed's action names.
pub const FOLDS: [(&str, FoldOp); 5] = [
    ("fold", FoldOp::AtCursor),
    ("unfold_lines", FoldOp::UnfoldAtCursor),
    ("toggle_fold", FoldOp::ToggleAtCursor),
    ("fold_all", FoldOp::FoldAll),
    ("unfold_all", FoldOp::UnfoldAll),
];

impl Target {
    pub fn parse(name: &str) -> Option<Self> {
        if let Some(action) = EditorAction::parse(name) {
            return Some(Self::Action(action));
        }
        let name = name.trim().trim_start_matches("editor::");
        let name = name.to_lowercase().replace('_', "");
        FOLDS
            .iter()
            .find(|(n, _)| n.replace('_', "") == name)
            .map(|(_, op)| Self::Fold(*op))
    }
}

/// One key with its modifiers. `command` is Ctrl (Cmd on macOS).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Keystroke {
    command: bool,
    alt: bool,
    shift: bool,
    key: String,
}

const NAMED: [&str; 27] = [
    "up",
    "down",
    "left",
    "right",
    "enter",
    "tab",
    "escape",
    "pageup",
    "pagedown",
    "home",
    "end",
    "backspace",
    "delete",
    "space",
    "insert",
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "f9",
    "f10",
    "f11",
    "f12",
];

impl Keystroke {
    pub fn parse(text: &str) -> Option<Self> {
        let mut rest = text.trim().to_lowercase();
        let mut stroke = Self {
            command: false,
            alt: false,
            shift: false,
            key: String::new(),
        };
        while let Some((modifier, after)) = rest.split_once(['-', '+'])
            && !after.is_empty()
        {
            match modifier {
                "ctrl" | "control" | "cmd" | "super" | "win" | "secondary" => stroke.command = true,
                "alt" | "option" | "opt" => stroke.alt = true,
                "shift" => stroke.shift = true,
                _ => return None,
            }
            rest = after.to_owned();
        }
        stroke.key = match rest.as_str() {
            "esc" => "escape".to_owned(),
            "return" => "enter".to_owned(),
            "del" => "delete".to_owned(),
            "pgup" => "pageup".to_owned(),
            "pgdown" => "pagedown".to_owned(),
            " " => "space".to_owned(),
            key if key.chars().count() == 1 || NAMED.contains(&key) => key.to_owned(),
            _ => return None,
        };
        Some(stroke)
    }

    pub fn matches(&self, press: &text_editor::KeyPress) -> bool {
        self.matches_key(&press.key, press.modifiers)
    }

    pub fn matches_key(&self, key: &keyboard::Key, m: keyboard::Modifiers) -> bool {
        if (m.command(), m.alt(), m.shift()) != (self.command, self.alt, self.shift) {
            // Shifted punctuation (`alt-<` is Alt+Shift+,) is written without the Shift.
            let shifted = m.shift()
                && !self.shift
                && (m.command(), m.alt()) == (self.command, self.alt)
                && self.key.chars().count() == 1
                && !self.key.chars().all(char::is_alphanumeric);
            if !shifted {
                return false;
            }
        }
        key_name(key).is_some_and(|key| key == self.key)
    }
}

/// The name of a key as written in a keystroke (`"up"`, `"f2"`, `"k"`).
fn key_name(key: &keyboard::Key) -> Option<String> {
    use keyboard::key::Named;
    Some(match key.as_ref() {
        keyboard::Key::Character(" ") => "space".to_owned(),
        keyboard::Key::Character(c) => c.to_lowercase(),
        keyboard::Key::Named(named) => match named {
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
            Named::Backspace => "backspace",
            Named::Delete => "delete",
            Named::Space => "space",
            Named::Insert => "insert",
            Named::F1 => "f1",
            Named::F2 => "f2",
            Named::F3 => "f3",
            Named::F4 => "f4",
            Named::F5 => "f5",
            Named::F6 => "f6",
            Named::F7 => "f7",
            Named::F8 => "f8",
            Named::F9 => "f9",
            Named::F10 => "f10",
            Named::F11 => "f11",
            Named::F12 => "f12",
            _ => return None,
        }
        .to_owned(),
        _ => return None,
    })
}

/// A user binding: a key, or the second key of a chord after its first one (`prefix`), and
/// what it runs.
#[derive(Debug, Clone)]
pub struct KeyBinding {
    prefix: Option<Keystroke>,
    stroke: Keystroke,
    target: Option<Target>,
}

impl KeyBinding {
    /// Parses `keys` (`"ctrl-d"`, `"ctrl-k ctrl-c"`, `"ctrl-x u"`) bound to the action `name`, or
    /// to nothing.
    pub fn parse(keys: &str, name: Option<&str>) -> Result<Self, String> {
        let target = match name.map(str::trim).filter(|n| !n.is_empty()) {
            Some(name) => {
                Some(Target::parse(name).ok_or_else(|| format!("unknown editor action {name:?}"))?)
            }
            None => None,
        };
        let strokes: Vec<&str> = keys.split_whitespace().collect();
        let bad = || format!("invalid keystroke {keys:?}");
        let (prefix, stroke) = match strokes.as_slice() {
            [one] => (None, Keystroke::parse(one).ok_or_else(bad)?),
            [first, second] => (
                Some(Keystroke::parse(first).ok_or_else(bad)?),
                Keystroke::parse(second).ok_or_else(bad)?,
            ),
            _ => return Err(bad()),
        };
        Ok(Self {
            prefix,
            stroke,
            target,
        })
    }
}

/// The user's binding for `press`: `Some(None)` when the key is bound to nothing, `None` when
/// the user did not bind it. `pending` is the first key of a chord, when one was pressed.
pub fn lookup(
    keymap: &[KeyBinding],
    press: &text_editor::KeyPress,
    pending: Option<&Keystroke>,
) -> Option<Option<Target>> {
    keymap
        .iter()
        .rev()
        .find(|b| b.prefix.as_ref() == pending && b.stroke.matches(press))
        .map(|b| b.target)
}

/// The first key of a chord of `keymap` that `press` is, if any.
pub fn prefix(keymap: &[KeyBinding], press: &text_editor::KeyPress) -> Option<Keystroke> {
    keymap
        .iter()
        .filter_map(|b| b.prefix.as_ref())
        .find(|p| p.matches(press))
        .cloned()
}

/// Ctrl+K, the first key of the editor's own chords.
pub fn ctrl_k() -> Keystroke {
    Keystroke::parse("ctrl-k").expect("a keystroke")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_keystrokes() {
        let k = Keystroke::parse("Ctrl-Shift-K").unwrap();
        assert!(k.command && k.shift && !k.alt);
        assert_eq!(k.key, "k");
        assert_eq!(Keystroke::parse("alt+up").unwrap().key, "up");
        assert_eq!(Keystroke::parse("ctrl--").unwrap().key, "-");
        assert_eq!(Keystroke::parse("esc").unwrap().key, "escape");
        assert!(Keystroke::parse("hyper-k").is_none());
        assert!(Keystroke::parse("ctrl-nope").is_none());
    }

    #[test]
    fn parses_bindings() {
        let b = KeyBinding::parse("ctrl-k ctrl-c", Some("editor::ToggleComments")).unwrap();
        assert_eq!(b.prefix, Some(ctrl_k()));
        assert!(matches!(
            b.target,
            Some(Target::Action(EditorAction::ToggleComments))
        ));
        assert!(matches!(
            KeyBinding::parse("ctrl-alt-f", Some("fold_all"))
                .unwrap()
                .target,
            Some(Target::Fold(FoldOp::FoldAll))
        ));
        assert!(KeyBinding::parse("ctrl-d", None).unwrap().target.is_none());
        assert!(KeyBinding::parse("ctrl-d", Some("nope")).is_err());
        let emacs = KeyBinding::parse("ctrl-x u", Some("undo")).unwrap();
        assert_eq!(emacs.prefix, Keystroke::parse("ctrl-x"));
        assert!(KeyBinding::parse("ctrl-a ctrl-b ctrl-c", Some("undo")).is_err());
    }
}
