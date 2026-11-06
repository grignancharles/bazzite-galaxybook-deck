// Run: gjs -m extension/tests/imPatch.test.js
// Two extensions wrapping the same prototype method (Accent Hold and Voice
// Hold) must keep working whatever the enable/disable order.
import System from 'system';
import {installKeyFilter} from '../imPatch.js';

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

// A fake IBus.InputContext prototype: the original async method answers
// through the callback with its own result object, like the real one.
function fakeProto() {
    const log = [];
    const ORIG = {orig: true};
    const proto = {
        process_key_event_async(keyval, keycode, state, time, cancellable, callback) {
            log.push(`orig ${keyval}`);
            // The shell promisifies the method: without a callback it
            // returns a promise instead.
            if (typeof callback !== 'function')
                return Promise.resolve(false);
            callback(this, ORIG);
            return undefined;
        },
        process_key_event_async_finish(res) {
            if (res !== ORIG)
                throw new Error('unknown result');
            return false;
        },
    };
    proto.ORIG_PROCESS = proto.process_key_event_async;
    proto.ORIG_FINISH = proto.process_key_event_async_finish;
    return {proto, log};
}

// Send a key through the (possibly wrapped) method, the way inputMethod.js
// does, and return what the finish wrapper answers.
function send(proto, keyval) {
    let handled = null;
    proto.process_key_event_async(keyval, 0, 0, -1, null, (ctx, res) => {
        handled = proto.process_key_event_async_finish.call(ctx, res);
    });
    return handled;
}

function restored(proto) {
    return proto.process_key_event_async === proto.ORIG_PROCESS &&
        proto.process_key_event_async_finish === proto.ORIG_FINISH;
}

test('a swallowed key never reaches the original and is reported handled', () => {
    const {proto, log} = fakeProto();
    const h = installKeyFilter(proto, keyval => keyval === 1);
    check(send(proto, 1) === true, 'swallowed');
    check(send(proto, 2) === false, 'passed');
    check(log.join() === 'orig 2', 'original saw only key 2');
    h.remove();
    check(restored(proto), 'restored');
});

test('without a callback (promise form) the call goes straight through', () => {
    const {proto, log} = fakeProto();
    const h = installKeyFilter(proto, () => true);
    proto.process_key_event_async(1, 0, 0, -1, null);
    check(log.join() === 'orig 1', 'original called');
    h.remove();
});

test('AH enable, VH enable, AH disable, VH disable', () => {
    const {proto, log} = fakeProto();
    const ah = installKeyFilter(proto, keyval => keyval === 1);
    const vh = installKeyFilter(proto, keyval => keyval === 2);
    check(send(proto, 1) === true && send(proto, 2) === true, 'both filters active');
    ah.remove();
    // VH captured AH's wrapper: it must stay in the chain, inert.
    check(!restored(proto), 'AH did not yank the prototype under VH');
    check(send(proto, 1) === false, 'AH filter now inert');
    check(send(proto, 2) === true, 'VH filter still active');
    vh.remove();
    check(send(proto, 1) === false && send(proto, 2) === false, 'everything passes');
    check(log.join() === 'orig 1,orig 1,orig 2', 'original saw the passed keys');
});

test('AH enable, VH enable, VH disable, AH disable (LIFO) restores fully', () => {
    const {proto} = fakeProto();
    const ah = installKeyFilter(proto, keyval => keyval === 1);
    const vh = installKeyFilter(proto, keyval => keyval === 2);
    vh.remove();
    check(send(proto, 2) === false && send(proto, 1) === true, 'only AH left');
    ah.remove();
    check(restored(proto), 'prototype back to the original');
});

test('re-enabling after an out-of-order disable still works', () => {
    const {proto} = fakeProto();
    const ah1 = installKeyFilter(proto, keyval => keyval === 1);
    const vh = installKeyFilter(proto, keyval => keyval === 2);
    ah1.remove();
    const ah2 = installKeyFilter(proto, keyval => keyval === 1);
    check(send(proto, 1) === true && send(proto, 2) === true, 'both active again');
    ah2.remove();
    vh.remove();
    check(send(proto, 1) === false && send(proto, 2) === false, 'all inert or removed');
});

test('removing twice is harmless', () => {
    const {proto} = fakeProto();
    const h = installKeyFilter(proto, () => true);
    h.remove();
    h.remove();
    check(restored(proto), 'restored once');
});

if (failures)
    System.exit(1);
