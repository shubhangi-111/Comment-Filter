// Creator Safety Shield AI - Content Script for YouTube & Instagram

const DEFAULT_API_SERVER = "http://localhost:5000/v1/moderate/batch";

async function getApiServer() {
  return new Promise((resolve) => {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      chrome.storage.local.get(['apiServer'], (result) => {
        resolve(result.apiServer || DEFAULT_API_SERVER);
      });
    } else {
      resolve(DEFAULT_API_SERVER);
    }
  });
}

async function getUserId() {
  return new Promise((resolve) => {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      chrome.storage.local.get(['userId'], (result) => {
        resolve(result.userId || "");
      });
    } else {
      resolve("");
    }
  });
}

async function moderatePlatformComments() {
  const currentHost = window.location.hostname;
  const platform = currentHost.includes("youtube") ? "YouTube" : "Instagram";
  
  let commentNodes = [];

  if (platform === "YouTube") {
    // Select YouTube Comment Renderers
    const renderers = document.querySelectorAll("ytd-comment-renderer:not([data-shield-checked])");
    renderers.forEach(el => {
      el.dataset.shieldChecked = "true";
      const textEl = el.querySelector("#content-text");
      const authorEl = el.querySelector("#author-text");
      if (textEl) {
        commentNodes.push({
          domElement: el,
          commentText: textEl.innerText.trim(),
          authorUsername: authorEl ? authorEl.innerText.trim() : "@yt_user",
          authorName: authorEl ? authorEl.innerText.trim() : "YouTube User",
          platform: "YouTube"
        });
      }
    });
  } else if (platform === "Instagram") {
    // Select Instagram Comments
    const commentEls = document.querySelectorAll("div._a9zc:not([data-shield-checked])");
    commentEls.forEach(el => {
      el.dataset.shieldChecked = "true";
      const textSpan = el.querySelector("span");
      const authorAnchor = el.querySelector("a");
      if (textSpan) {
        commentNodes.push({
          domElement: el,
          commentText: textSpan.innerText.trim(),
          authorUsername: authorAnchor ? "@" + authorAnchor.innerText.trim() : "@ig_user",
          authorName: authorAnchor ? authorAnchor.innerText.trim() : "Instagram User",
          platform: "Instagram"
        });
      }
    });
  }

  if (commentNodes.length === 0) return;

  // Prepare batch payload
  const payload = {
    platform: platform,
    comments: commentNodes.map(c => ({
      comment: c.commentText,
      author_username: c.authorUsername,
      author_name: c.authorName
    }))
  };

  const userId = await getUserId();
  const apiServer = await getApiServer();

  try {
    const response = await fetch(apiServer, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "X-User-Id": userId
      },
      body: JSON.stringify(payload)
    });

    const res = await response.json();
    if (res.status === "success" && Array.isArray(res.data)) {
      res.data.forEach((pred, index) => {
        const item = commentNodes[index];
        if (item && pred.is_toxic) {
          // Blur & Hide Toxic Harassment Comment
          item.domElement.style.transition = "filter 0.3s ease";
          item.domElement.style.filter = "blur(6px)";
          item.domElement.style.opacity = "0.45";

          // Inject Creator Shield Alert Badge
          const alertBadge = document.createElement("div");
          alertBadge.style.background = "#ef4444";
          alertBadge.style.color = "#ffffff";
          alertBadge.style.padding = "4px 8px";
          alertBadge.style.borderRadius = "4px";
          alertBadge.style.fontSize = "12px";
          alertBadge.style.fontWeight = "bold";
          alertBadge.style.display = "inline-block";
          alertBadge.style.marginBottom = "4px";
          alertBadge.innerText = `🛡️ Flagged by Creator Shield [${pred.category || "Harassment"}]`;

          item.domElement.prepend(alertBadge);
        }
      });
    }
  } catch (err) {
    console.log("Creator Safety Shield API Notice:", err.message);
  }
}

// Run moderation cycle using MutationObserver for better performance
let timeoutId = null;
const observer = new MutationObserver(() => {
  if (timeoutId) clearTimeout(timeoutId);
  timeoutId = setTimeout(() => {
    moderatePlatformComments();
  }, 500); // debounce 500ms
});

observer.observe(document.body, { childList: true, subtree: true });

// Initial run
moderatePlatformComments();
console.log("🛡️ Creator Safety Shield Extension Active!");
