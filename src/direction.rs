//! Right-to-left layouts (Arabic, Hebrew, Persian, Urdu...).
//!
//! `pz.direction(content, "rtl")` lays its content out as usual and then mirrors it: every
//! box moves to the other side of its parent (`Mirror`), so rows run from right to left,
//! `"left"` alignment and padding become the start side and the menus and tooltips open on the
//! side the text starts from. Glyphs, images and drawings are not flipped: the text inside keeps
//! its own order (the bidirectional algorithm of the text engine) and lines up on the right.
//!
//! Mirroring is a switch: a `"ltr"` part inside a right-to-left window mirrors again, which puts
//! its boxes back where they were (code editors, media controls, phone numbers, charts).
//! Widgets that place things from their own numbers instead of their children's boxes (sliders,
//! progress bars, splits, scrollables, pins) are handled one by one in `render.rs`.

use std::collections::HashMap;
use std::sync::RwLock;

use iced::advanced::layout::{self, Layout};
use iced::advanced::widget::{self, Tree, Widget, tree};
use iced::advanced::{Clipboard, Shell, mouse, overlay, renderer};
use iced::{Element, Event, Length, Rectangle, Size, Vector};
use pyo3::prelude::*;

use crate::app::Message;

/// Moves every box in `node` to the other side of its parent, all the way down.
pub fn mirror(node: &mut layout::Node) {
    let width = node.size().width;
    for child in node.children_mut() {
        let bounds = child.bounds();
        child.move_to_mut((width - bounds.x - bounds.width, bounds.y));
        mirror(child);
    }
}

/// Lays its content out, then mirrors it (see the module docs). Its own box stays where its
/// parent puts it.
pub struct Mirror<'a> {
    content: Element<'a, Message>,
}

impl<'a> Mirror<'a> {
    pub fn new(content: impl Into<Element<'a, Message>>) -> Self {
        Self {
            content: content.into(),
        }
    }
}

impl Widget<Message, iced::Theme, iced::Renderer> for Mirror<'_> {
    fn tag(&self) -> tree::Tag {
        self.content.as_widget().tag()
    }

    fn state(&self) -> tree::State {
        self.content.as_widget().state()
    }

    fn children(&self) -> Vec<Tree> {
        self.content.as_widget().children()
    }

    fn diff(&self, tree: &mut Tree) {
        self.content.as_widget().diff(tree);
    }

    fn size(&self) -> Size<Length> {
        self.content.as_widget().size()
    }

    fn size_hint(&self) -> Size<Length> {
        self.content.as_widget().size_hint()
    }

    fn layout(
        &mut self,
        tree: &mut Tree,
        renderer: &iced::Renderer,
        limits: &layout::Limits,
    ) -> layout::Node {
        let mut node = self.content.as_widget_mut().layout(tree, renderer, limits);
        mirror(&mut node);
        node
    }

    fn operate(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &iced::Renderer,
        operation: &mut dyn widget::Operation,
    ) {
        self.content
            .as_widget_mut()
            .operate(tree, layout, renderer, operation);
    }

    fn update(
        &mut self,
        tree: &mut Tree,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        renderer: &iced::Renderer,
        clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        viewport: &Rectangle,
    ) {
        self.content.as_widget_mut().update(
            tree, event, layout, cursor, renderer, clipboard, shell, viewport,
        );
    }

    fn mouse_interaction(
        &self,
        tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
        renderer: &iced::Renderer,
    ) -> mouse::Interaction {
        self.content
            .as_widget()
            .mouse_interaction(tree, layout, cursor, viewport, renderer)
    }

    fn draw(
        &self,
        tree: &Tree,
        renderer: &mut iced::Renderer,
        theme: &iced::Theme,
        style: &renderer::Style,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        self.content
            .as_widget()
            .draw(tree, renderer, theme, style, layout, cursor, viewport);
    }

    fn overlay<'b>(
        &'b mut self,
        tree: &'b mut Tree,
        layout: Layout<'b>,
        renderer: &iced::Renderer,
        viewport: &Rectangle,
        translation: Vector,
    ) -> Option<overlay::Element<'b, Message, iced::Theme, iced::Renderer>> {
        self.content
            .as_widget_mut()
            .overlay(tree, layout, renderer, viewport, translation)
            .map(|inner| overlay::Element::new(Box::new(MirrorOverlay { inner })))
    }
}

impl<'a> From<Mirror<'a>> for Element<'a, Message> {
    fn from(widget: Mirror<'a>) -> Self {
        Element::new(widget)
    }
}

/// The menus, tooltips and pop-ups of a mirrored part: placed by their owner (beside a box
/// that is already mirrored), with their own content mirrored inside.
struct MirrorOverlay<'a> {
    inner: overlay::Element<'a, Message, iced::Theme, iced::Renderer>,
}

impl overlay::Overlay<Message, iced::Theme, iced::Renderer> for MirrorOverlay<'_> {
    fn layout(&mut self, renderer: &iced::Renderer, bounds: Size) -> layout::Node {
        let mut node = self.inner.as_overlay_mut().layout(renderer, bounds);
        mirror(&mut node);
        node
    }

    fn draw(
        &self,
        renderer: &mut iced::Renderer,
        theme: &iced::Theme,
        style: &renderer::Style,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
    ) {
        self.inner
            .as_overlay()
            .draw(renderer, theme, style, layout, cursor);
    }

    fn operate(
        &mut self,
        layout: Layout<'_>,
        renderer: &iced::Renderer,
        operation: &mut dyn widget::Operation,
    ) {
        self.inner
            .as_overlay_mut()
            .operate(layout, renderer, operation);
    }

    fn update(
        &mut self,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        renderer: &iced::Renderer,
        clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
    ) {
        self.inner
            .as_overlay_mut()
            .update(event, layout, cursor, renderer, clipboard, shell);
    }

    fn mouse_interaction(
        &self,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        renderer: &iced::Renderer,
    ) -> mouse::Interaction {
        self.inner
            .as_overlay()
            .mouse_interaction(layout, cursor, renderer)
    }

    fn overlay<'b>(
        &'b mut self,
        layout: Layout<'b>,
        renderer: &iced::Renderer,
    ) -> Option<overlay::Element<'b, Message, iced::Theme, iced::Renderer>> {
        self.inner
            .as_overlay_mut()
            .overlay(layout, renderer)
            .map(|inner| overlay::Element::new(Box::new(MirrorOverlay { inner })))
    }

    fn index(&self) -> f32 {
        self.inner.as_overlay().index()
    }
}

/// Whether `c` is a letter of a right-to-left script (strong R or AL in the bidirectional
/// algorithm), by block: Hebrew, Arabic, Syriac, Thaana, N'Ko, Samaritan, Mandaic and their
/// presentation forms.
pub fn is_rtl_char(c: char) -> bool {
    matches!(
        c as u32,
        0x0590..=0x08FF | 0xFB1D..=0xFDFF | 0xFE70..=0xFEFF | 0x10800..=0x10FFF | 0x1E800..=0x1EFFF
    )
}

/// Whether the text has letters of a right-to-left script.
pub fn has_rtl(text: &str) -> bool {
    text.chars().any(is_rtl_char)
}

/// Put before a line to make it read from the right: U+200F RIGHT-TO-LEFT MARK, a strong
/// right-to-left character, then U+200B ZERO WIDTH SPACE so the text engine shapes the mark as a
/// word of its own (in the same word, the first letter could come out in another font).
const RTL_START: &str = "\u{200F}\u{200B}";

/// Whether the first letter of `line` that has a direction is a left-to-right one (Latin,
/// Cyrillic, Greek...): such a line reads from the left unless it is told otherwise.
fn starts_left_to_right(line: &str) -> bool {
    line.chars()
        .find(|&c| is_rtl_char(c) || c.is_alphabetic())
        .is_some_and(|c| !is_rtl_char(c))
}

/// A text shown in a right-to-left part: a line that mixes right-to-left letters with a Latin
/// word or a number at its start ("Pyzed 2.0 مرحبا") reads from the right, as the rest of the
/// part. Lines that start with a right-to-left letter already do, and lines without such letters
/// keep their own direction.
pub fn rtl_text(text: &str) -> std::borrow::Cow<'_, str> {
    // A text that is just a pointing mark (a breadcrumb's separator) points the other way.
    let mut chars = text.trim().chars();
    if let (Some(c), None) = (chars.next(), chars.next())
        && let Some(other) = mirrored_mark(c)
    {
        return std::borrow::Cow::Owned(text.replace(c, other.encode_utf8(&mut [0; 4])));
    }
    let marked = |line: &str| has_rtl(line) && starts_left_to_right(line);
    if !text.split('\n').any(marked) {
        return std::borrow::Cow::Borrowed(text);
    }
    let mut out = String::with_capacity(text.len() + 16);
    for (i, line) in text.split('\n').enumerate() {
        if i > 0 {
            out.push('\n');
        }
        if marked(line) {
            out.push_str(RTL_START);
        }
        out.push_str(line);
    }
    std::borrow::Cow::Owned(out)
}

/// Marks that point along the line, and their mirror image.
fn mirrored_mark(c: char) -> Option<char> {
    Some(match c {
        '›' => '‹',
        '‹' => '›',
        '»' => '«',
        '«' => '»',
        '>' => '<',
        '<' => '>',
        '→' => '←',
        '←' => '→',
        '▸' => '◂',
        '◂' => '▸',
        _ => return None,
    })
}

/// Icons that point along the line (arrows, chevrons, side panels, undo and redo), each with its
/// mirror image: a right-to-left part shows `chevron-left` for `chevron-right`.
static MIRRORED_ICONS: RwLock<Option<HashMap<char, char>>> = RwLock::new(None);

/// The icon to show in a right-to-left part.
pub fn mirrored_icon(c: char) -> char {
    MIRRORED_ICONS
        .read()
        .ok()
        .and_then(|map| map.as_ref().and_then(|map| map.get(&c).copied()))
        .unwrap_or(c)
}

/// The Lucide icons swapped in right-to-left parts, as pairs of characters (set by
/// `pyzed.bidi` from the icon names).
#[pyfunction]
pub fn _set_mirrored_icons(pairs: Vec<(char, char)>) {
    let mut map = HashMap::with_capacity(pairs.len() * 2);
    for (a, b) in pairs {
        map.insert(a, b);
        map.insert(b, a);
    }
    if let Ok(mut slot) = MIRRORED_ICONS.write() {
        *slot = Some(map);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mirror_moves_children_to_the_other_side() {
        let leaf = |x: f32, w: f32| layout::Node::new(Size::new(w, 10.0)).move_to((x, 0.0));
        let inner = layout::Node::with_children(Size::new(40.0, 10.0), vec![leaf(5.0, 10.0)])
            .move_to((10.0, 0.0));
        let mut root = layout::Node::with_children(Size::new(100.0, 10.0), vec![inner]);
        mirror(&mut root);
        let inner = &root.children()[0];
        assert_eq!(inner.bounds().x, 50.0);
        assert_eq!(inner.children()[0].bounds().x, 25.0);
        // Mirroring twice puts everything back.
        mirror(&mut root);
        assert_eq!(root.children()[0].bounds().x, 10.0);
        assert_eq!(root.children()[0].children()[0].bounds().x, 5.0);
    }

    #[test]
    fn rtl_text_marks_lines_that_start_left_to_right() {
        assert_eq!(rtl_text("Hello"), "Hello");
        assert_eq!(rtl_text("שלום Pyzed"), "שלום Pyzed");
        assert_eq!(rtl_text("Pyzed مرحبا"), "\u{200F}\u{200B}Pyzed مرحبا");
        assert_eq!(
            rtl_text("2.0 Pyzed מהיר\nשלום"),
            "\u{200F}\u{200B}2.0 Pyzed מהיר\nשלום"
        );
        assert_eq!(rtl_text("Hello\nשלום"), "Hello\nשלום");
        assert_eq!(rtl_text(" › "), " ‹ ");
    }

    #[test]
    fn rtl_letters() {
        assert!(has_rtl("abc ש"));
        assert!(has_rtl("سلام"));
        assert!(!has_rtl("Hello 123 — ñ"));
    }
}
