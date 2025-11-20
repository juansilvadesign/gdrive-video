document.addEventListener("DOMContentLoaded", () => {
    const header = document.querySelector(".header");
    const notDriveMessage = document.getElementById("only-in-drive-message");
    const downloadContainer = document.getElementById("download-container");
    const statusMessage = document.getElementById("status-message");
    const btnOn = document.getElementById("button-on");
    const btnOff = document.getElementById("button-off");
    const reloadBtn = document.querySelector(".reload-button");

    function updateUI(isEnabled) {
        btnOn.disabled = isEnabled;
        btnOff.disabled = !isEnabled;
        reloadBtn.classList.toggle("active", isEnabled);
    }

    function handleStateChange(newState) {
        chrome.storage.local.set({ extensionEnabled: newState }, () => {
            updateUI(newState);

            if (!newState) {
                downloadContainer.innerHTML = "";
                statusMessage.textContent = "Extension stopped.";
                setTimeout(() => {
                    statusMessage.textContent = "Click ON to start extension.";
                }, 2000);
            }

            chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
                const tab = tabs[0];
                if (!tab) return;

                chrome.runtime.sendMessage(
                    {
                        type: "setEnabled",
                        enabled: newState,
                        tabId: tab.id,
                        url: tab.url,
                    },
                    (response) => {
                        if (newState && response?.success) {
                            chrome.tabs.reload(tab.id);
                        }
                    }
                );
            });
        });
    }

    INVALID_FILENAME_CHARACTERS_REGEX = /([<>:"\/\\|?*])+/g;
    FILENAME_EXTENSION_REGEX = /^.*\.[a-zA-Z0-9]+$/;

    function filenameCleanAndNormalize(filename) {
        const cleaned = filename.replaceAll(INVALID_FILENAME_CHARACTERS_REGEX, "-");
        return cleaned.match(FILENAME_EXTENSION_REGEX) ? cleaned : cleaned + ".mp4";
    }

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        const tab = tabs[0];
        if (!tab || !tab.url.startsWith("https://drive.google.com/")) {
            header.classList.add("hidden");
            downloadContainer.classList.add("hidden");
            statusMessage.classList.add("hidden");
            notDriveMessage.classList.remove("hidden");
            return;
        }

        header.classList.remove("hidden");
        downloadContainer.classList.remove("hidden");
        statusMessage.classList.remove("hidden");
        notDriveMessage.classList.add("hidden");

        chrome.storage.local.get(["extensionEnabled"], (result) => {
            const isEnabled = result.extensionEnabled !== undefined ? result.extensionEnabled : false;
            updateUI(isEnabled);
        });

        btnOn.addEventListener("click", () => handleStateChange(true));
        btnOff.addEventListener("click", () => handleStateChange(false));

        reloadBtn.addEventListener("click", () => {
            chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
                if (tabs[0]?.id) {
                    chrome.tabs.reload(tabs[0].id);
                }
            });
        });

        const activeTabId = tab.id;

        function checkRequests() {
            chrome.runtime.sendMessage({ type: "getRequests" }, (response) => {
                if (response && response.requests) {
                    const matchingRequests = [];
                    for (const requestId in response.requests) {
                        const req = response.requests[requestId];
                        if (req.tabId === activeTabId && req.lastItagUrl && req.videoTitle) {
                            matchingRequests.push(req);
                        }
                    }
                    if (matchingRequests.length > 0) {
                        statusMessage.textContent = "";
                        downloadContainer.innerHTML = "";
                        matchingRequests.forEach((req) => {
                            const item = document.createElement("div");
                            item.classList.add("video-item");

                            const titleSpan = document.createElement("span");
                            titleSpan.classList.add("video-title");
                            titleSpan.title = req.videoTitle;
                            titleSpan.textContent = req.videoTitle;

                            const button = document.createElement("button");
                            button.classList.add("download-button");
                            button.innerHTML =
                                '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-download-icon lucide-download"><path d="M12 15V3"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/></svg>';
                            button.addEventListener("click", () => {
                                chrome.downloads.download(
                                    {
                                        url: req.lastItagUrl,
                                        filename: filenameCleanAndNormalize(req.videoTitle),
                                        conflictAction: "uniquify",
                                    },
                                    () => {
                                        if (chrome.runtime.lastError) {
                                            statusMessage.textContent = `Error: ${chrome.runtime.lastError.message}`;
                                            statusMessage.classList.add("error");
                                        }
                                    }
                                );
                            });

                            item.appendChild(titleSpan);
                            item.appendChild(button);
                            downloadContainer.appendChild(item);
                        });
                    } else {
                        chrome.storage.local.get(["extensionEnabled"], (result) => {
                            if (result.extensionEnabled) {
                                statusMessage.textContent =
                                    "Waiting for new video source. If not working reload the page.";
                            }
                        });
                    }
                }
            });
        }

        setInterval(() => checkRequests(), 1500);
    });
});
