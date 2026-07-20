"""Image handling class for rendering graphics without external libraries."""

from __future__ import annotations

import pathlib

# Try to import cv2 and numpy, fall back to mocks if not available
try:
    import cv2
    import numpy as np
except ImportError:
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
    import mock_cv2 as cv2
    # Create mock numpy
    class MockNumpy:
        class uint8:
            pass
    np = MockNumpy()


class Img:
    """Image wrapper for OpenCV-based graphics rendering."""

    def __init__(self):
        self.img = None

    def read(self, path: str | pathlib.Path,
             size: tuple[int, int] | None = None,
             keep_aspect: bool = False,
             interpolation: int = cv2.INTER_AREA) -> "Img":
        """
        Load `path` into self.img and **optionally resize**.

        Parameters
        ----------
        path : str | Path
            Image file to load.
        size : (width, height) | None
            Target size in pixels.  If None, keep original.
        keep_aspect : bool
            • False  → resize exactly to `size`
            • True   → shrink so the *longer* side fits `size` while
                       preserving aspect ratio (no cropping).
        interpolation : OpenCV flag
            E.g.  `cv2.INTER_AREA` for shrink, `cv2.INTER_LINEAR` for enlarge.

        Returns
        -------
        Img
            `self`, so you can chain:  `sprite = Img().read("foo.png", (64,64))`
        """
        path = str(path)
        self.img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if self.img is None:
            raise FileNotFoundError(f"Cannot load image: {path}")

        if size is not None:
            target_w, target_h = size
            h, w = self.img.shape[:2]

            if keep_aspect:
                scale = min(target_w / w, target_h / h)
                new_w, new_h = int(w * scale), int(h * scale)
            else:
                new_w, new_h = target_w, target_h

            self.img = cv2.resize(self.img, (new_w, new_h), interpolation=interpolation)

        return self

    def draw_on(self, other_img: "Img", x: int, y: int) -> None:
        """Draw this image on another image at position (x, y)."""
        if self.img is None or other_img.img is None:
            raise ValueError("Both images must be loaded before drawing.")

        if self.img.shape[2] != other_img.img.shape[2]:
            if self.img.shape[2] == 3 and other_img.img.shape[2] == 4:
                self.img = cv2.cvtColor(self.img, cv2.COLOR_BGR2BGRA)
            elif self.img.shape[2] == 4 and other_img.img.shape[2] == 3:
                self.img = cv2.cvtColor(self.img, cv2.COLOR_BGRA2BGR)

        h, w = self.img.shape[:2]
        H, W = other_img.img.shape[:2]

        if y + h > H or x + w > W:
            raise ValueError(f"Image does not fit at position ({x}, {y}). "
                           f"Image size: {w}x{h}, Canvas size: {W}x{H}")

        # If using mock cv2 with list-backed images, use a simple pixel copy.
        if hasattr(other_img.img, 'data') and isinstance(other_img.img.data, list):
            for row_idx in range(h):
                for col_idx in range(w):
                    other_img.img[y + row_idx][x + col_idx] = self.img[row_idx][col_idx]
            return

        roi = other_img.img[y:y + h, x:x + w]

        if self.img.shape[2] == 4:
            b, g, r, a = cv2.split(self.img)
            mask = a / 255.0
            for c in range(3):
                roi[..., c] = (1 - mask) * roi[..., c] + mask * self.img[..., c]
        else:
            other_img.img[y:y + h, x:x + w] = self.img

    def put_text(self, txt: str, x: int, y: int, font_size: float,
                 color: tuple = (255, 255, 255, 255), thickness: int = 1) -> None:
        """Add text to the image."""
        if self.img is None:
            raise ValueError("Image not loaded.")
        cv2.putText(self.img, txt, (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX, font_size,
                    color, thickness, cv2.LINE_AA)

    def draw_rectangle(self, x: int, y: int, width: int, height: int,
                       color: tuple = (255, 255, 255, 255), thickness: int = 2) -> None:
        """Draw a rectangle outline on the image."""
        if self.img is None:
            raise ValueError("Image not loaded.")
        cv2.rectangle(self.img, (x, y), (x + width, y + height), color, thickness)

    def fill_rectangle(self, x: int, y: int, width: int, height: int,
                       color: tuple = (255, 255, 255, 255)) -> None:
        """Fill a rectangle on the image."""
        if self.img is None:
            raise ValueError("Image not loaded.")
        cv2.rectangle(self.img, (x, y), (x + width, y + height), color, -1)

    def draw_circle(self, x: int, y: int, radius: int,
                    color: tuple = (255, 255, 255, 255), thickness: int = 2) -> None:
        """Draw a circle on the image."""
        if self.img is None:
            raise ValueError("Image not loaded.")
        cv2.circle(self.img, (x, y), radius, color, thickness)

    def show(self, window_name: str = "Image") -> None:
        """Display the image in a window."""
        if self.img is None:
            raise ValueError("Image not loaded.")
        cv2.imshow(window_name, self.img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    def save(self, path: str | pathlib.Path) -> None:
        """Save the image to a file."""
        if self.img is None:
            raise ValueError("Image not loaded.")
        cv2.imwrite(str(path), self.img)

    def get_size(self) -> tuple[int, int]:
        """Get image dimensions as (width, height)."""
        if self.img is None:
            return (0, 0)
        h, w = self.img.shape[:2]
        return (w, h)

    def clone(self) -> "Img":
        """Create a deep copy of this image."""
        if self.img is None:
            raise ValueError("Image not loaded.")
        new_img = Img()
        new_img.img = self.img.copy()
        return new_img
