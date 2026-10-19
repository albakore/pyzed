//! Custom window frames: the invisible borders that resize a window without system decorations.
//!
//! A window opened with `decorations=False` has no border for the system to grab, so
//! `window_edges` wraps the whole view and turns presses near its edges into a native
//! resize (`window::drag_resize`). The rest of the frame (title bar, buttons, menu) is
//! drawn in Python (`ui.window_frame`).

use iced::advanced::layout::{self, Layout};
use iced::advanced::renderer;
use iced::advanced::widget::{self, Tree, Widget};
use iced::advanced::{Clipboard, Shell, mouse, overlay};
use iced::window::Direction;
use iced::{Element, Event, Length, Point, Rectangle, Size, Vector};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use crate::app::Message;
use crate::widget::{Kind, child, new};

/// Wraps `content` (the whole window) so that pressing within `border` pixels of an edge
/// resizes the window: the way to resize windows opened with `decorations=False`. The
/// corners take twice as much room. `enabled=False` turns it off (for a maximized window).
#[pyfunction]
#[pyo3(signature = (content, *, border=6.0, enabled=true))]
pub fn window_edges(
    py: Python<'_>,
    content: &Bound<'_, PyAny>,
    border: f32,
    enabled: bool,
) -> PyResult<Py<crate::widget::Widget>> {
    if !border.is_finite() || border < 0.0 {
        return Err(PyValueError::new_err(
            "border must be a positive number of pixels",
        ));
    }
    new(
        py,
        Kind::WindowEdges {
            child: child(content)?,
            border: if enabled { border } else { 0.0 },
        },
    )
}

/// The resize direction for a point of `bounds`, or `None` away from its edges.
pub fn edge_at(bounds: Rectangle, point: Point, border: f32) -> Option<Direction> {
    if border <= 0.0 || !bounds.contains(point) {
        return None;
    }
    let corner = border * 2.0;
    let left = point.x - bounds.x;
    let top = point.y - bounds.y;
    let right = bounds.x + bounds.width - point.x;
    let bottom = bounds.y + bounds.height - point.y;
    let (near_left, near_right) = (left < border, right < border);
    let (near_top, near_bottom) = (top < border, bottom < border);
    // A corner grabs a little further along both edges, so it is easy to hit.
    let (corner_left, corner_right) = (left < corner, right < corner);
    let (corner_top, corner_bottom) = (top < corner, bottom < corner);
    Some(match () {
        _ if (near_top && corner_left) || (near_left && corner_top) => Direction::NorthWest,
        _ if (near_top && corner_right) || (near_right && corner_top) => Direction::NorthEast,
        _ if (near_bottom && corner_left) || (near_left && corner_bottom) => Direction::SouthWest,
        _ if (near_bottom && corner_right) || (near_right && corner_bottom) => Direction::SouthEast,
        _ if near_top => Direction::North,
        _ if near_bottom => Direction::South,
        _ if near_left => Direction::West,
        _ if near_right => Direction::East,
        _ => return None,
    })
}

fn cursor_for(direction: Direction) -> mouse::Interaction {
    match direction {
        Direction::North | Direction::South => mouse::Interaction::ResizingVertically,
        Direction::East | Direction::West => mouse::Interaction::ResizingHorizontally,
        Direction::NorthEast | Direction::SouthWest => mouse::Interaction::ResizingDiagonallyUp,
        Direction::NorthWest | Direction::SouthEast => mouse::Interaction::ResizingDiagonallyDown,
    }
}

pub struct WindowEdges<'a, Theme, Renderer> {
    content: Element<'a, Message, Theme, Renderer>,
    border: f32,
}

impl<'a, Theme, Renderer> WindowEdges<'a, Theme, Renderer> {
    pub fn new(content: impl Into<Element<'a, Message, Theme, Renderer>>, border: f32) -> Self {
        Self {
            content: content.into(),
            border,
        }
    }
}

impl<Theme, Renderer> Widget<Message, Theme, Renderer> for WindowEdges<'_, Theme, Renderer>
where
    Renderer: iced::advanced::Renderer,
{
    fn children(&self) -> Vec<Tree> {
        vec![Tree::new(&self.content)]
    }

    fn diff(&self, tree: &mut Tree) {
        tree.diff_children(std::slice::from_ref(&self.content));
    }

    fn size(&self) -> Size<Length> {
        self.content.as_widget().size()
    }

    fn layout(
        &mut self,
        tree: &mut Tree,
        renderer: &Renderer,
        limits: &layout::Limits,
    ) -> layout::Node {
        let child = self
            .content
            .as_widget_mut()
            .layout(&mut tree.children[0], renderer, limits);
        layout::Node::with_children(child.size(), vec![child])
    }

    fn operate(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &Renderer,
        operation: &mut dyn widget::Operation,
    ) {
        self.content.as_widget_mut().operate(
            &mut tree.children[0],
            layout.children().next().unwrap(),
            renderer,
            operation,
        );
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
        if let Event::Mouse(mouse::Event::ButtonPressed(mouse::Button::Left)) = event
            && let Some(position) = cursor.position()
            && let Some(direction) = edge_at(layout.bounds(), position, self.border)
        {
            shell.publish(Message::DragResize(direction));
            shell.capture_event();
            return;
        }
        self.content.as_widget_mut().update(
            &mut tree.children[0],
            event,
            layout.children().next().unwrap(),
            cursor,
            renderer,
            clipboard,
            shell,
            viewport,
        );
    }

    fn mouse_interaction(
        &self,
        tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
        renderer: &Renderer,
    ) -> mouse::Interaction {
        if let Some(position) = cursor.position()
            && let Some(direction) = edge_at(layout.bounds(), position, self.border)
        {
            return cursor_for(direction);
        }
        self.content.as_widget().mouse_interaction(
            &tree.children[0],
            layout.children().next().unwrap(),
            cursor,
            viewport,
            renderer,
        )
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
        self.content.as_widget().draw(
            &tree.children[0],
            renderer,
            theme,
            style,
            layout.children().next().unwrap(),
            cursor,
            viewport,
        );
    }

    fn overlay<'b>(
        &'b mut self,
        tree: &'b mut Tree,
        layout: Layout<'b>,
        renderer: &Renderer,
        viewport: &Rectangle,
        translation: Vector,
    ) -> Option<overlay::Element<'b, Message, Theme, Renderer>> {
        self.content.as_widget_mut().overlay(
            &mut tree.children[0],
            layout.children().next().unwrap(),
            renderer,
            viewport,
            translation,
        )
    }
}

impl<'a, Theme, Renderer> From<WindowEdges<'a, Theme, Renderer>>
    for Element<'a, Message, Theme, Renderer>
where
    Theme: 'a,
    Renderer: iced::advanced::Renderer + 'a,
{
    fn from(edges: WindowEdges<'a, Theme, Renderer>) -> Self {
        Element::new(edges)
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(window_edges, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    const WINDOW: Rectangle = Rectangle {
        x: 0.0,
        y: 0.0,
        width: 800.0,
        height: 600.0,
    };

    fn at(x: f32, y: f32) -> Option<Direction> {
        edge_at(WINDOW, Point::new(x, y), 6.0)
    }

    fn name(direction: Option<Direction>) -> &'static str {
        match direction {
            None => "-",
            Some(Direction::North) => "n",
            Some(Direction::South) => "s",
            Some(Direction::East) => "e",
            Some(Direction::West) => "w",
            Some(Direction::NorthEast) => "ne",
            Some(Direction::NorthWest) => "nw",
            Some(Direction::SouthEast) => "se",
            Some(Direction::SouthWest) => "sw",
        }
    }

    #[test]
    fn edges_and_corners() {
        assert_eq!(name(at(400.0, 300.0)), "-");
        assert_eq!(name(at(400.0, 2.0)), "n");
        assert_eq!(name(at(400.0, 598.0)), "s");
        assert_eq!(name(at(1.0, 300.0)), "w");
        assert_eq!(name(at(799.0, 300.0)), "e");
        assert_eq!(name(at(2.0, 2.0)), "nw");
        // a corner reaches twice as far along each edge
        assert_eq!(name(at(10.0, 2.0)), "nw");
        assert_eq!(name(at(798.0, 10.0)), "ne");
        assert_eq!(name(at(10.0, 598.0)), "sw");
        assert_eq!(name(at(795.0, 595.0)), "se");
        assert_eq!(name(at(900.0, 2.0)), "-");
    }

    #[test]
    fn disabled_border_never_resizes() {
        assert_eq!(name(edge_at(WINDOW, Point::new(0.0, 0.0), 0.0)), "-");
    }
}
