let solverIframe;
let solveId = 0;
let solveCallbacks = {};
let solveQueue = [];
let solverReady = false;
let solverErrored = false;
let sentData = false;
let solverGeneration = 0;
let initGeneration = -1;
let recoverPromise = null;

let sandboxUrl = fetch(chrome.runtime.getURL(`sandbox.html`))
    .then((resp) => resp.blob())
    .then((blob) => URL.createObjectURL(blob))
    .catch(console.error);

function requeuePendingSolves() {
    let queued = new Set(solveQueue.map((t) => t.id));
    for (let id of Object.keys(solveCallbacks)) {
        let numId = +id;
        let cb = solveCallbacks[id];
        if (!cb || queued.has(numId)) continue;
        solveQueue.push({ id: numId, path: cb.path, method: cb.method });
        queued.add(numId);
    }
}

function createSolverFrame() {
    if (solverIframe) solverIframe.remove();
    solverReady = false;
    requeuePendingSolves();
    solverGeneration++;
    let generation = solverGeneration;
    solverIframe = document.createElement("iframe");
    solverIframe.style.position = "fixed";
    solverIframe.style.left = "-9999px";
    solverIframe.style.top = "0";
    solverIframe.width = "10";
    solverIframe.height = "10";
    solverIframe.style.border = "none";
    solverIframe.style.opacity = "0";
    solverIframe.style.pointerEvents = "none";
    solverIframe.tabIndex = -1;
    let resolveLoaded;
    solverIframe._loaded = new Promise((resolve) => {
        resolveLoaded = resolve;
    });
    solverIframe.addEventListener("load", () => {
        if (!solverIframe.src) return;
        resolveLoaded();
    });
    sandboxUrl.then((url) => {
        if (generation !== solverGeneration) return;
        solverIframe.src = url;
    });
    let injectedBody = document.getElementById("injected-body");
    if (injectedBody) {
        injectedBody.appendChild(solverIframe);
    } else {
        let int = setInterval(() => {
            if (generation !== solverGeneration) {
                clearInterval(int);
                return;
            }
            let injectedBody = document.getElementById("injected-body");
            if (injectedBody) {
                injectedBody.appendChild(solverIframe);
                clearInterval(int);
            }
        }, 10);
    }
}
createSolverFrame();

function solveChallenge(path, method) {
    return new Promise((resolve, reject) => {
        if (solverErrored) {
            reject("Solver errored during initialization");
            return;
        }
        let id = solveId++;
        let settled = false;
        let timeout = setTimeout(() => {
            if (settled || !solveCallbacks[id]) return;
            settled = true;
            delete solveCallbacks[id];
            solveQueue = solveQueue.filter((t) => t.id !== id);
            reject("Solver timed out");
        }, 30000);
        solveCallbacks[id] = {
            resolve: (v) => {
                if (settled) return;
                settled = true;
                clearTimeout(timeout);
                resolve(v);
            },
            reject: (e) => {
                if (settled) return;
                settled = true;
                clearTimeout(timeout);
                reject(e);
            },
            time: Date.now(),
            path,
            method,
        };
        if (!solverReady || !solverIframe || !solverIframe.contentWindow) {
            solveQueue.push({ id, path, method });
        } else {
            try {
                solverIframe.contentWindow.postMessage(
                    { action: "solve", id, path, method },
                    "*"
                );
            } catch (e) {
                console.error(`Error sending challenge to solver:`, e);
                delete solveCallbacks[id];
                clearTimeout(timeout);
                settled = true;
                reject(e);
            }
        }
    });
}

function recoverSolver(reason) {
    if (solverErrored) return Promise.resolve();
    if (recoverPromise) return recoverPromise;
    console.warn("Recovering challenge solver:", reason);
    recoverPromise = (async () => {
        try {
            createSolverFrame();
            await initChallenge();
            let start = Date.now();
            while (
                !solverReady &&
                !solverErrored &&
                Date.now() - start < 10000
            ) {
                await new Promise((r) => setTimeout(r, 50));
            }
        } finally {
            recoverPromise = null;
        }
    })();
    return recoverPromise;
}

setInterval(() => {
    if (!sentData || recoverPromise || solverErrored) return;
    let loadingBox = document.getElementById("loading-box");
    let loadingVisible = loadingBox && !loadingBox.hidden;
    if (!solverReady && solveQueue.length) {
        let oldest = Math.min(...solveQueue.map((t) => {
            let cb = solveCallbacks[t.id];
            return cb ? cb.time : Date.now();
        }));
        if (loadingVisible || Date.now() - oldest > 6000) {
            console.log(
                "Something's wrong with the challenge solver, reloading",
                solveQueue
            );
            recoverSolver("watchdog");
        }
    }
}, 2000);

window.addEventListener("message", (e) => {
    if (!solverIframe || e.source !== solverIframe.contentWindow) return;
    let data = e.data;
    if (data.action === "solved" && typeof data.id === "number") {
        let { id, result } = data;
        if (solveCallbacks[id]) {
            solveCallbacks[id].resolve(result);
            delete solveCallbacks[id];
        }
    } else if (data.action === "error" && typeof data.id === "number") {
        let { id, error } = data;
        if (solveCallbacks[id]) {
            solveCallbacks[id].reject(error);
            delete solveCallbacks[id];
        }
    } else if (data.action === "initError") {
        solverErrored = true;
        for (let id in solveCallbacks) {
            solveCallbacks[id].reject("Solver errored during initialization");
            delete solveCallbacks[id];
        }
        alert(
            `There was an error in initializing security header generator:\n${data.error}\nUser Agent: ${navigator.userAgent}\nOldTwitter doesn't allow unsigned requests anymore for your account security.`
        );
        console.error("Error initializing solver:");
        console.error(data.error);
        location.href = `${location.pathname}?newtwitter=true`;
    } else if (data.action === "ready") {
        solverReady = true;
        let queue = solveQueue;
        solveQueue = [];
        for (let task of queue) {
            if (!solveCallbacks[task.id]) continue;
            solverIframe.contentWindow.postMessage(
                {
                    action: "solve",
                    id: task.id,
                    path: task.path,
                    method: task.method,
                },
                "*"
            );
        }
    }
});

window._fetch = window.fetch;
fetch = async function (url, options) {
    if (
        !url.startsWith("/i/api") &&
        !url.startsWith("https://api.twitter.com") &&
        !url.startsWith("https://api.x.com")
    )
        return _fetch(url, options);
    if (!options) options = {};
    if (!options.headers) options.headers = {};
    if (!options.headers["x-twitter-auth-type"]) {
        options.headers["x-twitter-auth-type"] = "OAuth2Session";
    }
    if (!options.headers["x-twitter-active-user"]) {
        options.headers["x-twitter-active-user"] = "yes";
    }
    if (!url.startsWith("http:") && !url.startsWith("https:")) {
        let host = location.hostname;
        if (!["x.com", "twitter.com"].includes(host)) host = "x.com";
        if (!url.startsWith("/")) url = "/" + url;
        url = `https://${host}${url}`;
    }
    let parsedUrl = new URL(url);
    let method = options.method ? options.method.toUpperCase() : "GET";
    let solved;
    try {
        solved = await solveChallenge(parsedUrl.pathname, method);
    } catch (e) {
        if (
            !solverErrored &&
            (String(e).includes("Solver timed out") ||
                String(e).includes("not initialized"))
        ) {
            await recoverSolver(e);
            solved = await solveChallenge(parsedUrl.pathname, method);
        } else {
            throw e;
        }
    }
    options.headers["x-client-transaction-id"] = solved;
    if (
        options.method &&
        options.method.toUpperCase() === "POST" &&
        typeof options.body === "string"
    ) {
        options.headers["Content-Length"] = options.body.length;
    }

    return _fetch(url, options);
};

async function initChallenge() {
    let generation = solverGeneration;
    if (initGeneration === generation) return false;
    initGeneration = generation;
    try {
        let homepageData;
        let sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
        let host = location.hostname;
        if (!["x.com", "twitter.com"].includes(host)) host = "x.com";
        try {
            homepageData = await _fetch(`https://${host}/`).then((res) =>
                res.text()
            );
        } catch (e) {
            await sleep(500);
            try {
                homepageData = await _fetch(`https://${host}/`).then((res) =>
                    res.text()
                );
            } catch (e) {
                throw new Error("Failed to fetch homepage: " + e);
            }
        }
        if (generation !== solverGeneration) return false;

        let dom = new DOMParser().parseFromString(homepageData, "text/html");
        let verificationKey = dom.querySelector(
            'meta[name="twitter-site-verification"]'
        ).content;
        let anims = Array.from(
            dom.querySelectorAll('svg[id^="loading-x"]')
        ).map((svg) => svg.outerHTML);

        let vendorCode = homepageData.match(/vendor.(\w+).js"/)[1];
        let challengePos = homepageData.match(/(\d+):"ondemand.s"/)[1];
        let challengeCode = homepageData.match(
            new RegExp(`${challengePos}:"(\\w+)"`)
        )[1];

        OLDTWITTER_CONFIG.verificationKey = verificationKey;

        async function sendInit() {
            if (generation !== solverGeneration) return;
            sentData = true;
            if (!solverIframe) return setTimeout(sendInit, 50);
            try {
                await Promise.race([solverIframe._loaded, sleep(5000)]);
            } catch (e) {}
            if (generation !== solverGeneration) return;
            if (!solverIframe || !solverIframe.contentWindow)
                return setTimeout(sendInit, 50);
            solverIframe.contentWindow.postMessage(
                {
                    action: "init",
                    challengeCode,
                    vendorCode,
                    anims,
                    verificationCode: OLDTWITTER_CONFIG.verificationKey,
                },
                "*"
            );
        }
        await sendInit();
        return true;
    } catch (e) {
        console.error(`Error during challenge init:`);
        console.error(e);
        if (location.hostname === "twitter.com") {
            alert(
                `There was an error in initializing security header generator: ${e}\nUser Agent: ${navigator.userAgent}\nOldTwitter doesn't allow unsigned requests anymore for your account security. Currently the main reason for this happening is social network tracker protection blocking the script. Try disabling such settings in your browser and extensions that do that and refresh the page. This also might be because you're either not logged in or using twitter.com instead of x.com.`
            );
        } else {
            alert(
                `There was an error in initializing security header generator: ${e}\nUser Agent: ${navigator.userAgent}\nOldTwitter doesn't allow unsigned requests anymore for your account security. Currently the main reason for this happening is social network tracker protection blocking the script. Try disabling such settings in your browser and extensions that do that and refresh the page. This can also happen if you're not logged in.`
            );
        }
        return false;
    }
}

initChallenge();
