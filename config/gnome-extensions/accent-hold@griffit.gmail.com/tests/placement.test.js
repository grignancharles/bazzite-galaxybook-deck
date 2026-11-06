// Run: gjs -m extension/tests/placement.test.js
import System from 'system';
import {monitorAt, clampToMonitor, cursorRectUsable, anchorPoint} from '../placement.js';

let failures = 0;
function test(name, fn) {
    try {
        fn();
        print(`PASS ${name}`);
    } catch (e) {
        failures++;
        print(`FAIL ${name}: ${e.message}`);
    }
}
function check(cond, msg) {
    if (!cond)
        throw new Error(msg);
}
function same(a, b, msg) {
    check(JSON.stringify(a) === JSON.stringify(b), `${msg}: got ${JSON.stringify(a)}`);
}

const left = {x: 0, y: 0, width: 1920, height: 1080};
const right = {x: 1920, y: 0, width: 1280, height: 1024};
const monitors = [left, right];

test('monitorAt finds the monitor containing the point', () => {
    check(monitorAt(monitors, left, 100, 100) === left, 'left');
    check(monitorAt(monitors, left, 1920, 10) === right, 'right edge is inclusive on the right monitor');
    check(monitorAt(monitors, left, 1919, 10) === left, 'last column of the left monitor');
});

test('monitorAt falls back to the primary monitor off-screen', () => {
    check(monitorAt(monitors, right, 5000, 5000) === right, 'primary');
    check(monitorAt([], left, 10, 10) === left, 'no monitors at all');
    check(monitorAt([], null, 10, 10) === null, 'nothing known');
});

test('clampToMonitor keeps the box inside, with a margin', () => {
    same(clampToMonitor(100, 100, 200, 50, left), [100, 100], 'already inside');
    same(clampToMonitor(1900, 100, 200, 50, left), [1716, 100], 'pushed left');
    same(clampToMonitor(100, 1070, 200, 50, left), [100, 1026], 'pushed up (last line of a maximized editor)');
    same(clampToMonitor(-50, -50, 200, 50, left), [4, 4], 'pushed to the top-left corner');
    same(clampToMonitor(3000, 1000, 200, 50, right), [2996, 970], 'secondary monitor offset');
});

test('clampToMonitor without a monitor leaves the point alone', () => {
    same(clampToMonitor(7, 8, 200, 50, null), [7, 8], 'unchanged');
});

test('cursorRectUsable rejects missing, empty and stale rectangles', () => {
    const frame = {x: 500, y: 300, width: 800, height: 600};
    check(!cursorRectUsable(undefined, frame), 'no rect');
    check(!cursorRectUsable({x: 0, y: 0, width: 0, height: 0}, frame), 'origin = nothing reported');
    check(cursorRectUsable({x: 600, y: 400, width: 1, height: 20}, frame), 'inside the focused window');
    check(!cursorRectUsable({x: 100, y: 100, width: 1, height: 20}, frame), 'outside: left by a previous app');
    check(!cursorRectUsable({x: 2500, y: 400, width: 1, height: 20}, frame), 'on another monitor');
    check(cursorRectUsable({x: 600, y: 400, width: 1, height: 20}, null), 'no focused window: trusted');
});

test('anchorPoint uses the cursor when usable, else the pointer', () => {
    const frame = {x: 0, y: 0, width: 1920, height: 1080};
    same(anchorPoint({x: 600, y: 400, width: 1, height: 20}, frame, [10, 10]), [600, 426], 'below the cursor');
    same(anchorPoint(null, frame, [10, 10]), [10, 34], 'below the pointer');
    same(anchorPoint({x: 5000, y: 400, width: 1, height: 20}, frame, [10, 10]), [10, 34], 'stale rect ignored');
});

if (failures)
    System.exit(1);
