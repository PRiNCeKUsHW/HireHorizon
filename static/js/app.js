/* HireHorizon — small progressive-enhancement layer.
 * Every control here also works as a plain form POST; this only removes the
 * page reload. No framework, no build step. */
(function () {
  "use strict";

  function csrfToken() {
    var input = document.querySelector("[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  /* These toggles change a count and a pressed state in place, with no page
   * reload to announce. Without a live region a screen reader user presses
   * Like and hears nothing at all, so every handler routes its result here. */
  var announcer = document.createElement("div");
  announcer.className = "sr-only";
  announcer.setAttribute("aria-live", "polite");
  announcer.setAttribute("role", "status");
  // The tag is deferred, so the body is already parsed by the time this runs.
  document.body.appendChild(announcer);

  function announce(message) {
    announcer.textContent = message;
  }

  function setBusy(button, busy) {
    button.classList.toggle("is-busy", busy);
    if (busy) {
      button.setAttribute("aria-busy", "true");
    } else {
      button.removeAttribute("aria-busy");
    }
  }

  function post(url) {
    return fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
    }).then(function (response) {
      if (response.status === 403 || response.status === 401) {
        window.location.href = "/login/?next=" + encodeURIComponent(location.pathname);
        return null;
      }
      if (!response.ok) throw new Error("Request failed: " + response.status);
      return response.json();
    });
  }

  /* Toggle buttons: like, repost, bookmark. */
  function wireToggle(selector, apply) {
    document.addEventListener("click", function (event) {
      var button = event.target.closest(selector);
      if (!button) return;

      // Signed-out visitors go to the login page instead of a failed POST.
      if (button.dataset.auth === "0") {
        window.location.href =
          "/login/?next=" + encodeURIComponent(location.pathname);
        return;
      }

      event.preventDefault();
      if (button.classList.contains("is-busy")) return;
      setBusy(button, true);

      post(button.dataset.url)
        .then(function (data) {
          if (data) announce(apply(button, data));
        })
        .catch(function () {
          // Fall back to a normal navigation if the request failed.
          window.location.reload();
        })
        .finally(function () {
          setBusy(button, false);
        });
    });
  }

  function setCount(button, selector, value) {
    var el = button.querySelector(selector);
    if (el && typeof value === "number") {
      el.textContent = value < 1000 ? String(value) : (value / 1000).toFixed(1) + "K";
    }
  }

  /* Each handler returns the sentence the live region should read out. */
  wireToggle(".js-like", function (button, data) {
    button.classList.toggle("is-on", data.liked);
    button.setAttribute("aria-pressed", data.liked ? "true" : "false");
    setCount(button, ".js-like-count", data.count);
    return data.liked ? "Liked" : "Like removed";
  });

  wireToggle(".js-repost", function (button, data) {
    button.classList.toggle("is-on", data.reposted);
    button.setAttribute("aria-pressed", data.reposted ? "true" : "false");
    setCount(button, ".js-repost-count", data.count);
    return data.reposted ? "Reposted" : "Repost removed";
  });

  wireToggle(".js-bookmark", function (button, data) {
    button.classList.toggle("is-on", data.bookmarked);
    button.setAttribute("aria-pressed", data.bookmarked ? "true" : "false");
    return data.bookmarked ? "Bookmarked" : "Bookmark removed";
  });

  /* Follow / unfollow on the profile page. */
  document.addEventListener("click", function (event) {
    var button = event.target.closest(".js-follow-btn");
    if (!button) return;
    event.preventDefault();
    if (button.classList.contains("is-busy")) return;
    setBusy(button, true);

    post(button.dataset.url)
      .then(function (data) {
        if (!data) return;
        button.textContent = data.following ? "Following" : "Follow";
        button.classList.toggle("btn--ghost", data.following);
        button.classList.toggle("btn--primary", !data.following);
        button.setAttribute("aria-pressed", data.following ? "true" : "false");
        announce(data.following ? "Following" : "No longer following");
      })
      .catch(function () {
        window.location.reload();
      })
      .finally(function () {
        setBusy(button, false);
      });
  });

  /* Threaded replies: point the comment form at a parent comment. */
  var parentInput = document.getElementById("reply-parent");
  var banner = document.getElementById("replying-to");
  var bannerName = document.getElementById("replying-to-name");

  document.addEventListener("click", function (event) {
    var replyButton = event.target.closest(".js-reply");
    if (replyButton && parentInput) {
      parentInput.value = replyButton.dataset.parent;
      if (banner && bannerName) {
        bannerName.textContent = "@" + replyButton.dataset.name;
        banner.hidden = false;
      }
      var box = document.querySelector(".form--inline textarea");
      if (box) box.focus();
      return;
    }

    if (event.target.closest(".js-cancel-reply") && parentInput) {
      parentInput.value = "";
      if (banner) banner.hidden = true;
    }
  });

  /* Keep the newest message in view when opening a conversation. */
  var chat = document.querySelector(".chat");
  if (chat) chat.scrollTop = chat.scrollHeight;
})();
