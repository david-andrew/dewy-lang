// Wait for an observable state change; the timer only bounds a hung process.
module.exports = function waitFor(events, predicate, timeout, describe) {
    return new Promise((resolve, reject) => {
        const finish = (error) => {
            clearTimeout(timer);
            events.off('state', check);
            error ? reject(error) : resolve();
        };
        const check = () => {
            try { if (predicate()) finish(); }
            catch (error) { finish(error); }
        };
        const timer = setTimeout(() => finish(new Error(describe())), timeout);
        events.on('state', check);
        check();
    });
};
