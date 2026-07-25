(function () {
    const lightbox = document.getElementById("fanz-lightbox");

    if (!lightbox) {
        return;
    }

    const image = lightbox.querySelector(
        "[data-fanz-lightbox-image]"
    );

    const video = lightbox.querySelector(
        "[data-fanz-lightbox-video]"
    );

    const audio = lightbox.querySelector(
        "[data-fanz-lightbox-audio]"
    );

    const audioWrap = lightbox.querySelector(
        "[data-fanz-lightbox-audio-wrap]"
    );

    const pdf = lightbox.querySelector(
        "[data-fanz-lightbox-pdf]"
    );

    const caption = lightbox.querySelector(
        "[data-fanz-lightbox-caption]"
    );

    const counter = lightbox.querySelector(
        "[data-fanz-lightbox-counter]"
    );

    const previousButton = lightbox.querySelector(
        "[data-fanz-lightbox-prev]"
    );

    const nextButton = lightbox.querySelector(
        "[data-fanz-lightbox-next]"
    );

    const lightboxItems = Array.from(
        document.querySelectorAll("[data-fanz-lightbox]")
    );

    let activeGallery = [];
    let currentIndex = 0;
    let touchStartX = 0;
    let touchStartY = 0;

    function resetMedia() {
        if (image) {
            image.src = "";
            image.alt = "";
            image.hidden = true;
        }

        if (video) {
            video.pause();
            video.removeAttribute("src");
            video.load();
            video.hidden = true;
        }

        if (audio) {
            audio.pause();
            audio.removeAttribute("src");
            audio.load();
        }

        if (audioWrap) {
            audioWrap.hidden = true;
        }

        if (pdf) {
            pdf.src = "about:blank";
            pdf.hidden = true;
        }
    }

    function getMediaType(item) {
        return item.dataset.fanzLightboxType || "image";
    }

    function getMediaSource(item) {
        return (
            item.dataset.fanzLightboxSrc ||
            item.getAttribute("href") ||
            ""
        );
    }

    function getMediaCaption(item) {
        const thumbnail = item.querySelector("img");

        return (
            item.dataset.fanzLightboxCaption ||
            thumbnail?.dataset.caption ||
            thumbnail?.alt ||
            ""
        );
    }

    function showMedia(index) {
        if (!activeGallery.length) {
            return;
        }

        currentIndex =
            (index + activeGallery.length) % activeGallery.length;

        const item = activeGallery[currentIndex];
        const mediaType = getMediaType(item);
        const mediaSource = getMediaSource(item);
        const thumbnail = item.querySelector("img");

        resetMedia();

        if (mediaType === "video" && video) {
            video.src = mediaSource;
            video.hidden = false;
            video.load();
        } else if (
            mediaType === "audio" &&
            audio &&
            audioWrap
        ) {
            audio.src = mediaSource;
            audioWrap.hidden = false;
            audio.load();
        } else if (mediaType === "pdf" && pdf) {
            pdf.src = mediaSource;
            pdf.hidden = false;
        } else if (image) {
            image.src = mediaSource;
            image.alt = thumbnail?.alt || "";
            image.hidden = false;
        }

        const text = getMediaCaption(item);

        if (caption) {
            if (text) {
                caption.textContent = text;
                caption.hidden = false;
            } else {
                caption.textContent = "";
                caption.hidden = true;
            }
        }

        const hasMultipleItems = activeGallery.length > 1;

        if (counter) {
            if (hasMultipleItems) {
                counter.textContent =
                    `${currentIndex + 1} / ${activeGallery.length}`;

                counter.hidden = false;
            } else {
                counter.textContent = "";
                counter.hidden = true;
            }
        }

        if (previousButton) {
            previousButton.hidden = !hasMultipleItems;
        }

        if (nextButton) {
            nextButton.hidden = !hasMultipleItems;
        }

        lightbox.classList.add("is-open");
        lightbox.setAttribute("aria-hidden", "false");

        document.body.classList.add(
            "fanz-lightbox-open"
        );
    }

    function closeLightbox() {
        lightbox.classList.remove("is-open");
        lightbox.setAttribute("aria-hidden", "true");

        document.body.classList.remove(
            "fanz-lightbox-open"
        );

        resetMedia();

        if (caption) {
            caption.textContent = "";
            caption.hidden = true;
        }

        if (counter) {
            counter.textContent = "";
            counter.hidden = true;
        }
    }

    function showPreviousMedia(event) {
        event?.stopPropagation();
        showMedia(currentIndex - 1);
    }

    function showNextMedia(event) {
        event?.stopPropagation();
        showMedia(currentIndex + 1);
    }

    function handleTouchStart(event) {
        const touch = event.changedTouches[0];

        touchStartX = touch.clientX;
        touchStartY = touch.clientY;
    }

    function handleTouchEnd(event) {
        if (!lightbox.classList.contains("is-open")) {
            return;
        }

        const touch = event.changedTouches[0];

        const deltaX = touch.clientX - touchStartX;
        const deltaY = touch.clientY - touchStartY;

        const minimumSwipeDistance = 50;

        const isHorizontalSwipe =
            Math.abs(deltaX) > Math.abs(deltaY);

        if (
            !isHorizontalSwipe ||
            Math.abs(deltaX) < minimumSwipeDistance
        ) {
            return;
        }

        if (deltaX < 0) {
            showNextMedia();
        } else {
            showPreviousMedia();
        }
    }

    lightboxItems.forEach(function (item) {
        item.addEventListener("click", function (event) {
            event.preventDefault();

            const groupName =
                item.dataset.fanzLightboxGroup || "__default__";

            activeGallery = lightboxItems.filter(
                function (candidate) {
                    const candidateGroup =
                        candidate.dataset.fanzLightboxGroup ||
                        "__default__";

                    return candidateGroup === groupName;
                }
            );

            const clickedIndex = activeGallery.indexOf(item);

            showMedia(clickedIndex >= 0 ? clickedIndex : 0);
        });
    });

    previousButton?.addEventListener(
        "click",
        showPreviousMedia
    );

    nextButton?.addEventListener(
        "click",
        showNextMedia
    );

    lightbox
        .querySelectorAll("[data-fanz-lightbox-close]")
        .forEach(function (control) {
            control.addEventListener(
                "click",
                closeLightbox
            );
        });

    lightbox.addEventListener(
        "touchstart",
        handleTouchStart,
        { passive: true }
    );

    lightbox.addEventListener(
        "touchend",
        handleTouchEnd,
        { passive: true }
    );

    document.addEventListener("keydown", function (event) {
        if (!lightbox.classList.contains("is-open")) {
            return;
        }

        if (event.key === "Escape") {
            closeLightbox();
        } else if (event.key === "ArrowLeft") {
            showPreviousMedia();
        } else if (event.key === "ArrowRight") {
            showNextMedia();
        }
    });
})();
