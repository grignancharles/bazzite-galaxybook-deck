// Wrap IBus.InputContext.prototype.process_key_event_async so a filter sees
// every key the GNOME input method sends to IBus and can swallow some of
// them. Kept free of Shell imports so the install/remove logic can be tested
// with plain gjs against a fake prototype.
//
// Several extensions may wrap the same method (Voice Hold does). Each one
// captures the method it found and calls it when it does not swallow the
// key, which chains the wrappers. Removing a wrapper restores the captured
// method only when the wrapper is still the one installed on the prototype;
// otherwise a later wrapper captured ours, so ours stays in the chain and is
// made inert (pass-through) instead. That keeps every extension working in
// whatever order they are enabled and disabled.

// Stand-in for the GAsyncResult of a swallowed key.
const CONSUMED = {};

// `filter(keyval, keycode, state)` returns true to swallow the key. Returns
// a handle with `remove()`.
export function installKeyFilter(proto, filter) {
    const origProcess = proto.process_key_event_async;
    const origFinish = proto.process_key_event_async_finish;
    let active = true;

    const wrapProcess = function (...args) {
        const callback = args[args.length - 1];
        if (active && typeof callback === 'function' && filter(args[0], args[1], args[2])) {
            // Answer right away: the shell only tells Clutter the key was
            // handled, so no main loop source is left behind.
            callback(this, CONSUMED);
            return undefined;
        }
        return origProcess.apply(this, args);
    };
    const wrapFinish = function (res) {
        if (res === CONSUMED)
            return true;
        return origFinish.call(this, res);
    };

    proto.process_key_event_async = wrapProcess;
    proto.process_key_event_async_finish = wrapFinish;

    return {
        remove() {
            active = false;
            if (proto.process_key_event_async === wrapProcess)
                proto.process_key_event_async = origProcess;
            if (proto.process_key_event_async_finish === wrapFinish)
                proto.process_key_event_async_finish = origFinish;
        },
    };
}
