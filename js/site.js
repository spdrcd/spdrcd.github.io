/*!
 * site.js — lightbox for the "Through the Lens" gallery.
 * No dependencies. Progressive enhancement: without JS the gallery still renders,
 * it just isn't expandable.
 */
(function () {
    "use strict";

    var grid = document.querySelector("#gallery .photo-grid");
    if (!grid) return;

    var figures = Array.prototype.slice.call(grid.querySelectorAll("figure"));
    if (!figures.length) return;

    var items = figures.map(function (fig) {
        var img = fig.querySelector("img");
        var cap = fig.querySelector("figcaption");
        return {
            src: img ? img.getAttribute("src") : "",
            alt: img ? img.getAttribute("alt") : "",
            caption: cap ? cap.textContent.trim() : ""
        };
    });

    var current = 0;
    var lastFocused = null;

    var box = document.createElement("div");
    box.className = "lightbox";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    box.setAttribute("aria-label", "Photo viewer");
    box.hidden = true;
    box.innerHTML =
        '<button class="lb-close" type="button" aria-label="Close">&times;</button>' +
        '<button class="lb-nav lb-prev" type="button" aria-label="Previous photo">&#8249;</button>' +
        '<button class="lb-nav lb-next" type="button" aria-label="Next photo">&#8250;</button>' +
        '<figure class="lb-stage">' +
        '<img class="lb-img" src="" alt="" />' +
        '<figcaption class="lb-caption"></figcaption>' +
        "</figure>";
    document.body.appendChild(box);

    var imgEl = box.querySelector(".lb-img");
    var capEl = box.querySelector(".lb-caption");
    var closeBtn = box.querySelector(".lb-close");
    var prevBtn = box.querySelector(".lb-prev");
    var nextBtn = box.querySelector(".lb-next");

    function render(i) {
        current = (i + items.length) % items.length;
        var it = items[current];
        imgEl.setAttribute("src", it.src);
        imgEl.setAttribute("alt", it.alt);
        capEl.textContent = it.caption + "  (" + (current + 1) + " / " + items.length + ")";
    }

    function open(i) {
        lastFocused = document.activeElement;
        render(i);
        box.hidden = false;
        document.body.classList.add("lb-open");
        closeBtn.focus();
    }

    function close() {
        box.hidden = true;
        document.body.classList.remove("lb-open");
        imgEl.setAttribute("src", "");
        if (lastFocused && lastFocused.focus) lastFocused.focus();
    }

    figures.forEach(function (fig, i) {
        fig.setAttribute("tabindex", "0");
        fig.setAttribute("role", "button");
        fig.setAttribute("aria-label", "Expand photo: " + items[i].caption);
        fig.addEventListener("click", function () { open(i); });
        fig.addEventListener("keydown", function (e) {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                open(i);
            }
        });
    });

    closeBtn.addEventListener("click", close);
    prevBtn.addEventListener("click", function () { render(current - 1); });
    nextBtn.addEventListener("click", function () { render(current + 1); });

    box.addEventListener("click", function (e) {
        if (e.target === box || e.target.classList.contains("lb-stage")) close();
    });

    document.addEventListener("keydown", function (e) {
        if (box.hidden) return;
        if (e.key === "Escape") close();
        else if (e.key === "ArrowLeft") render(current - 1);
        else if (e.key === "ArrowRight") render(current + 1);
        else if (e.key === "Tab") {
            var focusables = [closeBtn, prevBtn, nextBtn];
            var idx = focusables.indexOf(document.activeElement);
            e.preventDefault();
            var next = e.shiftKey ? idx - 1 : idx + 1;
            focusables[(next + focusables.length) % focusables.length].focus();
        }
    });

    var touchX = null;
    box.addEventListener("touchstart", function (e) {
        touchX = e.changedTouches[0].clientX;
    }, { passive: true });
    box.addEventListener("touchend", function (e) {
        if (touchX === null) return;
        var dx = e.changedTouches[0].clientX - touchX;
        if (Math.abs(dx) > 50) render(dx > 0 ? current - 1 : current + 1);
        touchX = null;
    }, { passive: true });
})();
