(function () {
    const lightbox = document.getElementById("fanz-lightbox");

    if (!lightbox) {
        return;
    }

    const image = lightbox.querySelector(
        "[data-fanz-lightbox-image]"
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

    function showImage(index) {
        if (!activeGallery.length) {
            return;
        }

        currentIndex =
            (index + activeGallery.length) % activeGallery.length;

        const link = activeGallery[currentIndex];
        const thumbnail = link.querySelector("img");

        image.src = link.href;
        image.alt = thumbnail?.alt || "";

        const text =
            link.dataset.fanzLightboxCaption ||
            thumbnail?.dataset.caption ||
            thumbnail?.alt ||
            "";

        if (text) {
            caption.textContent = text;
            caption.hidden = false;
        } else {
            caption.textContent = "";
            caption.hidden = true;
        }

        const hasMultipleImages = activeGallery.length > 1;

        if (counter) {
            if (hasMultipleImages) {
                counter.textContent =
                    `${currentIndex + 1} / ${activeGallery.length}`;
                counter.hidden = false;
            } else {
                counter.textContent = "";
                counter.hidden = true;
            }
        }

        if (previousButton) {
            previousButton.hidden = !hasMultipleImages;
        }

        if (nextButton) {
            nextButton.hidden = !hasMultipleImages;
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

        image.src = "";
        image.alt = "";

        caption.textContent = "";
        caption.hidden = true;

        if (counter) {
            counter.textContent = "";
            counter.hidden = true;
        }
    }

        function showPreviousImage(event) {
        event?.stopPropagation();
        showImage(currentIndex - 1);
    }

    function showNextImage(event) {
        event?.stopPropagation();
        showImage(currentIndex + 1);
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
            showNextImage();
        } else {
            showPreviousImage();
        }
    }

lightboxItems.forEach(function (item) {
    item.addEventListener("click", function (event) {
        event.preventDefault();

        const groupName =
            item.dataset.fanzLightboxGroup || "__default__";

        activeGallery = lightboxItems.filter(function (candidate) {
            const candidateGroup =
                candidate.dataset.fanzLightboxGroup || "__default__";

            return candidateGroup === groupName;
        });

        const clickedIndex = activeGallery.indexOf(item);

        showImage(clickedIndex >= 0 ? clickedIndex : 0);
    });
});

    previousButton?.addEventListener(
        "click",
        showPreviousImage
    );

    nextButton?.addEventListener(
        "click",
        showNextImage
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
            showPreviousImage();
        } else if (event.key === "ArrowRight") {
            showNextImage();
        }
    });
})();
