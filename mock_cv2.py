"""Mock cv2 module for testing without OpenCV installation."""

from typing import Tuple


class MockImage:
    """Mock image array that behaves like numpy array."""
    def __init__(self, height, width, channels=4):
        self.shape = (height, width, channels)
        self.dtype = 'uint8'
        self.data = [[[(0, 0, 0, 255) if channels == 4 else (0, 0, 0) for _ in range(channels)] for _ in range(width)] for _ in range(height)]
    
    def __getitem__(self, key):
        if isinstance(key, tuple):
            if len(key) == 2:
                row_key, col_key = key
                if isinstance(row_key, slice) or isinstance(col_key, slice):
                    rows = self.data[row_key]
                    return [row[col_key] for row in rows]
                return self.data[row_key][col_key]
        return self.data[key]
    
    def __setitem__(self, key, value):
        if isinstance(key, tuple) and len(key) == 2:
            row_key, col_key = key
            if isinstance(row_key, slice) or isinstance(col_key, slice):
                rows = self.data[row_key]
                for i, row in enumerate(rows):
                    if isinstance(col_key, slice):
                        row[col_key] = value[i]
                    else:
                        row[col_key] = value[i]
                return
            self.data[row_key][col_key] = value
            return
        self.data[key] = value
    
    def copy(self):
        new_img = MockImage(self.shape[0], self.shape[1], self.shape[2])
        new_img.data = [row[:] for row in self.data]
        return new_img
    
    def astype(self, dtype):
        return self


# Mock constants
IMREAD_UNCHANGED = 1
INTER_AREA = 1
INTER_LINEAR = 2
FONT_HERSHEY_SIMPLEX = 0
LINE_AA = 16
EVENT_LBUTTONDOWN = 1
EVENT_RBUTTONDOWN = 2
EVENT_MOUSEMOVE = 0


def imread(path, flags=0):
    """Mock imread - returns a test image."""
    # Return a dummy image with appropriate channels based on flags
    if flags == IMREAD_UNCHANGED:
        return MockImage(100, 100, 4)
    return MockImage(100, 100, 3)


def imwrite(path, img):
    """Mock imwrite."""
    return True


def imshow(window_name, img):
    """Mock imshow."""
    pass


def waitKey(delay=0):
    """Mock waitKey."""
    return -1


def destroyAllWindows():
    """Mock destroyAllWindows."""
    pass


def namedWindow(window_name):
    """Mock namedWindow."""
    pass


def setMouseCallback(window_name, callback):
    """Mock setMouseCallback."""
    pass


def resize(img, size, interpolation=INTER_AREA):
    """Mock resize."""
    if isinstance(size, tuple):
        return MockImage(size[1], size[0], img.shape[2] if len(img.shape) > 2 else 1)
    return img


def cvtColor(img, code):
    """Mock cvtColor."""
    return img


def split(img):
    """Mock split."""
    if len(img.shape) == 3 and img.shape[2] == 4:
        return [img[:, :, 0], img[:, :, 1], img[:, :, 2], img[:, :, 3]]
    elif len(img.shape) == 3 and img.shape[2] == 3:
        return [img[:, :, 0], img[:, :, 1], img[:, :, 2]]
    return [img]


def putText(img, text, org, fontFace, fontScale, color, thickness=1, lineType=LINE_AA):
    """Mock putText."""
    pass


def rectangle(img, pt1, pt2, color, thickness=1):
    """Mock rectangle."""
    pass


def circle(img, center, radius, color, thickness=1):
    """Mock circle."""
    pass
