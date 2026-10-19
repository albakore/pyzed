"""The spacing every panel of Pyzed Design shares, so docks, lists and the property grid line up.

Each panel's content sits ``GUTTER`` pixels from both of its sides: section headings, list rows, property
labels and the right end of the fields. Rows of a list are ``ROW_GAP`` apart, and blocks inside a panel
(a header, a group of properties) are ``BLOCK`` apart.
"""

#: Margin between a panel's sides and its content, left and right alike.
GUTTER = 12.0
#: Space between blocks inside a panel (a header and what follows, two groups).
BLOCK = 8.0
#: Space between the rows of a list or a property group.
ROW_GAP = 2.0
#: Height of a property's field, and padding above and below it.
ROW_HEIGHT = 26.0
ROW_PAD = 2.0
#: Width of the property names column, and space between it and the fields.
LABEL_WIDTH = 92.0
LABEL_GAP = 8.0
#: Width of a scroll bar: scrolling panels keep it clear of their content, so the gutter shows on both sides.
SCROLLBAR = 8.0
#: Height of a row of a list (the toolbox, the outline).
ITEM_HEIGHT = 26.0
#: Padding of a group's content in the property grid (top, sides, bottom).
GROUP_PADDING = (4.0, GUTTER, BLOCK, GUTTER)
#: Padding of a panel's heading block (a control's name and description).
HEADER_PADDING = (10.0, GUTTER, BLOCK, GUTTER)
