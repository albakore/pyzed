//! A column that only builds, lays out and draws the rows inside the visible area, so a
//! list or table with hundreds of thousands of rows costs the same as one with fifty.
//!
//! Every row has the same height, so the column knows its total height and where each
//! row goes without building them. Rows are built on demand by a callback (which calls
//! Python) when they scroll into view, and dropped when they leave it. Their widget state
//! (hover, focus...) lives in this widget's tree state, keyed by row index.

use std::collections::{BTreeMap, HashMap};
use std::ops::Range;

use iced::advanced::layout::{self, Layout};
use iced::advanced::renderer;
use iced::advanced::widget::{self, Tree, Widget, tree};
use iced::advanced::{Clipboard, Shell, mouse, overlay};
use iced::{Element, Event, Length, Rectangle, Size, Vector};

/// Rows built before the first redraw tells us which ones are visible.
const INITIAL_ROWS: usize = 48;

type Builder<'a, Message, Theme, Renderer> =
    Box<dyn Fn(usize) -> Element<'a, Message, Theme, Renderer> + 'a>;

pub struct VirtualColumn<'a, Message, Theme, Renderer> {
    count: usize,
    item_height: f32,
    spacing: f32,
    overscan: usize,
    width: Length,
    builder: Builder<'a, Message, Theme, Renderer>,
    /// Rows built during this view, with their layouts (relative to the row's slot).
    items: BTreeMap<usize, Item<'a, Message, Theme, Renderer>>,
    /// The width rows were laid out with.
    row_width: f32,
}

struct Item<'a, Message, Theme, Renderer> {
    element: Element<'a, Message, Theme, Renderer>,
    node: layout::Node,
}

struct State {
    trees: HashMap<usize, Tree>,
    /// The rows shown last time; a new view builds these first.
    range: Range<usize>,
}

impl<'a, Message, Theme, Renderer> VirtualColumn<'a, Message, Theme, Renderer>
where
    Renderer: iced::advanced::Renderer,
{
    pub fn new(
        count: usize,
        item_height: f32,
        spacing: f32,
        overscan: usize,
        width: Length,
        builder: impl Fn(usize) -> Element<'a, Message, Theme, Renderer> + 'a,
    ) -> Self {
        Self {
            count,
            item_height: item_height.max(1.0),
            spacing: spacing.max(0.0),
            overscan,
            width,
            builder: Box::new(builder),
            items: BTreeMap::new(),
            row_width: 0.0,
        }
    }

    fn stride(&self) -> f32 {
        self.item_height + self.spacing
    }

    fn total_height(&self) -> f32 {
        if self.count == 0 {
            0.0
        } else {
            self.count as f32 * self.stride() - self.spacing
        }
    }

    /// The rows intersecting `viewport`, widened by `overscan` on each side.
    fn visible(&self, bounds: Rectangle, viewport: &Rectangle) -> Range<usize> {
        let top = (viewport.y - bounds.y).max(0.0);
        let bottom = (viewport.y + viewport.height - bounds.y).min(self.total_height());
        if bottom <= top || self.count == 0 {
            return 0..0;
        }
        let stride = self.stride();
        let first = (top / stride).floor() as usize;
        let last = ((bottom / stride).ceil() as usize).min(self.count);
        first.saturating_sub(self.overscan)..(last + self.overscan).min(self.count)
    }

    fn limits(&self) -> layout::Limits {
        layout::Limits::new(Size::ZERO, Size::new(self.row_width, self.item_height))
    }

    /// Builds and lays out the rows in `range` that aren't built yet, drops the others and
    /// forgets the widget state of rows far away from it.
    fn show(&mut self, state: &mut State, renderer: &Renderer, range: Range<usize>) {
        self.items.retain(|i, _| range.contains(i));
        let limits = self.limits();
        for i in range.clone() {
            if self.items.contains_key(&i) {
                continue;
            }
            let mut element = (self.builder)(i);
            let tree = match state.trees.get_mut(&i) {
                Some(tree) => {
                    tree.diff(&element);
                    tree
                }
                None => state.trees.entry(i).or_insert_with(|| Tree::new(&element)),
            };
            let node = element.as_widget_mut().layout(tree, renderer, &limits);
            self.items.insert(i, Item { element, node });
        }
        let keep = range.len().max(self.overscan);
        let (lo, hi) = (range.start.saturating_sub(keep), range.end + keep);
        state
            .trees
            .retain(|i, _| (lo..hi).contains(i) && *i < self.count);
        state.range = range;
    }

    fn offset(&self, bounds: Rectangle, index: usize) -> Vector {
        Vector::new(bounds.x, bounds.y + index as f32 * self.stride())
    }
}

impl<Message, Theme, Renderer> Widget<Message, Theme, Renderer>
    for VirtualColumn<'_, Message, Theme, Renderer>
where
    Renderer: iced::advanced::Renderer,
{
    fn tag(&self) -> tree::Tag {
        tree::Tag::of::<State>()
    }

    fn state(&self) -> tree::State {
        tree::State::new(State {
            trees: HashMap::new(),
            range: 0..self.count.min(INITIAL_ROWS),
        })
    }

    fn size(&self) -> Size<Length> {
        Size::new(self.width, Length::Shrink)
    }

    fn layout(
        &mut self,
        tree: &mut Tree,
        renderer: &Renderer,
        limits: &layout::Limits,
    ) -> layout::Node {
        let size = limits.resolve(
            self.width,
            Length::Shrink,
            Size::new(0.0, self.total_height()),
        );
        let size = Size::new(size.width, self.total_height());
        let state = tree.state.downcast_mut::<State>();
        if (size.width - self.row_width).abs() > f32::EPSILON {
            // A new width: lay every row out again.
            self.row_width = size.width;
            self.items.clear();
        }
        let range = state.range.start.min(self.count)..state.range.end.min(self.count);
        self.show(state, renderer, range);
        layout::Node::new(size)
    }

    fn operate(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &Renderer,
        operation: &mut dyn widget::Operation,
    ) {
        let bounds = layout.bounds();
        let stride = self.stride();
        let state = tree.state.downcast_mut::<State>();
        for (i, item) in self.items.iter_mut() {
            let Some(tree) = state.trees.get_mut(i) else {
                continue;
            };
            let row = Layout::with_offset(
                Vector::new(bounds.x, bounds.y + *i as f32 * stride),
                &item.node,
            );
            item.element
                .as_widget_mut()
                .operate(tree, row, renderer, operation);
        }
    }

    fn update(
        &mut self,
        tree: &mut Tree,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        renderer: &Renderer,
        clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        viewport: &Rectangle,
    ) {
        let bounds = layout.bounds();
        let state = tree.state.downcast_mut::<State>();
        let range = self.visible(bounds, viewport);
        if range != state.range || range.clone().any(|i| !self.items.contains_key(&i)) {
            self.show(state, renderer, range);
            shell.request_redraw();
        }
        let stride = self.stride();
        for (i, item) in self.items.iter_mut() {
            let Some(tree) = state.trees.get_mut(i) else {
                continue;
            };
            let row = Layout::with_offset(
                Vector::new(bounds.x, bounds.y + *i as f32 * stride),
                &item.node,
            );
            item.element.as_widget_mut().update(
                tree, event, row, cursor, renderer, clipboard, shell, viewport,
            );
        }
    }

    fn mouse_interaction(
        &self,
        tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
        renderer: &Renderer,
    ) -> mouse::Interaction {
        let bounds = layout.bounds();
        let state = tree.state.downcast_ref::<State>();
        self.items
            .iter()
            .filter_map(|(i, item)| {
                let tree = state.trees.get(i)?;
                let row = Layout::with_offset(self.offset(bounds, *i), &item.node);
                Some(
                    item.element
                        .as_widget()
                        .mouse_interaction(tree, row, cursor, viewport, renderer),
                )
            })
            .max()
            .unwrap_or_default()
    }

    fn draw(
        &self,
        tree: &Tree,
        renderer: &mut Renderer,
        theme: &Theme,
        style: &renderer::Style,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        let bounds = layout.bounds();
        let state = tree.state.downcast_ref::<State>();
        for (i, item) in &self.items {
            let Some(tree) = state.trees.get(i) else {
                continue;
            };
            let row = Layout::with_offset(self.offset(bounds, *i), &item.node);
            if row.bounds().intersects(viewport) {
                item.element
                    .as_widget()
                    .draw(tree, renderer, theme, style, row, cursor, viewport);
            }
        }
    }

    fn overlay<'b>(
        &'b mut self,
        tree: &'b mut Tree,
        layout: Layout<'b>,
        renderer: &Renderer,
        viewport: &Rectangle,
        translation: Vector,
    ) -> Option<overlay::Element<'b, Message, Theme, Renderer>> {
        let bounds = layout.bounds();
        let stride = self.stride();
        let state = tree.state.downcast_mut::<State>();
        let mut trees: HashMap<usize, &'b mut Tree> =
            state.trees.iter_mut().map(|(i, t)| (*i, t)).collect();
        let overlays: Vec<_> = self
            .items
            .iter_mut()
            .filter_map(|(i, item)| {
                let tree = trees.remove(i)?;
                let row = Layout::with_offset(
                    Vector::new(bounds.x, bounds.y + *i as f32 * stride),
                    &item.node,
                );
                item.element
                    .as_widget_mut()
                    .overlay(tree, row, renderer, viewport, translation)
            })
            .collect();
        (!overlays.is_empty()).then(|| overlay::Group::with_children(overlays).overlay())
    }
}

impl<'a, Message, Theme, Renderer> From<VirtualColumn<'a, Message, Theme, Renderer>>
    for Element<'a, Message, Theme, Renderer>
where
    Message: 'a,
    Theme: 'a,
    Renderer: iced::advanced::Renderer + 'a,
{
    fn from(column: VirtualColumn<'a, Message, Theme, Renderer>) -> Self {
        Element::new(column)
    }
}
