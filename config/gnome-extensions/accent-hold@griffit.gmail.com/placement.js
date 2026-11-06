// Where to put a popup so that it is visible. Pure functions (no Shell
// imports) so they can be tested with plain gjs. Monitors and frames are
// {x, y, width, height} in stage coordinates.

// Margin kept between the popup and the monitor edges.
const EDGE_MARGIN = 4;

// The monitor containing the point, else `primary`. Written out rather than
// using LayoutManager.findMonitorForPoint(), which does not exist on GNOME 45.
export function monitorAt(monitors, primary, x, y) {
    for (const m of monitors) {
        if (x >= m.x && x < m.x + m.width && y >= m.y && y < m.y + m.height)
            return m;
    }
    return primary;
}

// Move a `width` x `height` box at (x, y) so it lies inside the monitor.
// With no monitor the position is returned unchanged.
export function clampToMonitor(x, y, width, height, monitor) {
    if (!monitor)
        return [x, y];
    const maxX = monitor.x + monitor.width - width - EDGE_MARGIN;
    const maxY = monitor.y + monitor.height - height - EDGE_MARGIN;
    return [
        Math.max(monitor.x + EDGE_MARGIN, Math.min(x, maxX)),
        Math.max(monitor.y + EDGE_MARGIN, Math.min(y, maxY)),
    ];
}

// Whether the cursor rectangle reported by the application can be used. The
// shell keeps the last rectangle forever, including after the application
// that reported it lost the focus, so a rectangle is only trusted when it
// lies inside the frame of the focused window (when there is one). A
// rectangle at the origin means the application reported nothing.
export function cursorRectUsable(rect, frame) {
    if (!rect || typeof rect.x !== 'number' || typeof rect.y !== 'number')
        return false;
    if (!rect.x && !rect.y)
        return false;
    if (!frame)
        return true;
    return rect.x >= frame.x && rect.x < frame.x + frame.width &&
        rect.y >= frame.y && rect.y < frame.y + frame.height;
}

// Point below the text cursor when the rectangle is usable, else below the
// pointer.
export function anchorPoint(rect, frame, pointer) {
    if (cursorRectUsable(rect, frame))
        return [rect.x, rect.y + (rect.height || 0) + 6];
    const [px, py] = pointer;
    return [px, py + 24];
}
