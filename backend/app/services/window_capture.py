"""
Window Capture Service

Provides window detection and capture functionality for targeted screen capture.
Supports pattern matching to find specific application windows.
"""

import base64
import fnmatch
import io
import logging
import platform
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class WindowInfo:
    """Information about a detected window."""
    window_handle: int
    title: str
    process_name: str
    process_id: int
    is_visible: bool
    is_minimized: bool
    rect: dict  # {left, top, right, bottom}


class WindowCaptureService:
    """
    Service for window detection and capture.

    Provides cross-platform window management with focus on Windows support.
    """

    def __init__(self):
        """Initialize the window capture service."""
        self.platform = platform.system()
        self._init_platform_support()

    def _init_platform_support(self):
        """Initialize platform-specific modules."""
        if self.platform == "Windows":
            try:
                import win32gui
                import win32process
                import win32con
                import win32ui
                import ctypes
                from PIL import Image
                self._win32_available = True
                logger.info("Windows capture support initialized")
            except ImportError as e:
                logger.warning(f"Windows capture modules not available: {e}")
                self._win32_available = False
        else:
            self._win32_available = False
            logger.info(f"Running on {self.platform} - limited capture support")

    def list_windows(self, visible_only: bool = True) -> List[WindowInfo]:
        """
        List all windows on the system.

        Args:
            visible_only: Only return visible windows

        Returns:
            List of WindowInfo objects
        """
        if self.platform == "Windows" and self._win32_available:
            return self._list_windows_win32(visible_only)
        else:
            logger.warning(f"Window listing not supported on {self.platform}")
            return []

    def _list_windows_win32(self, visible_only: bool = True) -> List[WindowInfo]:
        """List windows using Win32 API."""
        import win32gui
        import win32process
        import psutil

        windows = []

        def enum_callback(hwnd, results):
            if visible_only and not win32gui.IsWindowVisible(hwnd):
                return True

            try:
                title = win32gui.GetWindowText(hwnd)
                if not title:  # Skip windows without titles
                    return True

                # Get process info
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    process = psutil.Process(pid)
                    process_name = process.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    process_name = "Unknown"

                # Get window rect
                try:
                    rect = win32gui.GetWindowRect(hwnd)
                    rect_dict = {
                        "left": rect[0],
                        "top": rect[1],
                        "right": rect[2],
                        "bottom": rect[3]
                    }
                except Exception:
                    rect_dict = {"left": 0, "top": 0, "right": 0, "bottom": 0}

                # Check if minimized
                is_minimized = win32gui.IsIconic(hwnd)

                windows.append(WindowInfo(
                    window_handle=hwnd,
                    title=title,
                    process_name=process_name,
                    process_id=pid,
                    is_visible=win32gui.IsWindowVisible(hwnd),
                    is_minimized=is_minimized,
                    rect=rect_dict
                ))
            except Exception as e:
                logger.debug(f"Error getting window info for {hwnd}: {e}")

            return True

        win32gui.EnumWindows(enum_callback, windows)
        return windows

    def find_window_by_pattern(
        self,
        pattern: str,
        process_name: Optional[str] = None
    ) -> Optional[WindowInfo]:
        """
        Find a window matching the given pattern.

        Args:
            pattern: Window title pattern (supports wildcards: *text*)
            process_name: Optional process name filter

        Returns:
            Matching WindowInfo or None
        """
        windows = self.list_windows(visible_only=True)
        logger.info(f"Looking for window with pattern: '{pattern}', found {len(windows)} visible windows")

        for window in windows:
            # Check title pattern match
            matches = self._matches_pattern(window.title, pattern)
            logger.debug(f"  Window: '{window.title}' matches '{pattern}': {matches}")
            if matches:
                # If process filter specified, check it too
                if process_name:
                    if self._matches_pattern(window.process_name, process_name):
                        logger.info(f"Found matching window: {window.title}")
                        return window
                else:
                    logger.info(f"Found matching window: {window.title}")
                    return window

        logger.warning(f"No window found matching pattern: '{pattern}'")
        return None

    def find_windows_by_pattern(
        self,
        pattern: str,
        process_name: Optional[str] = None
    ) -> List[WindowInfo]:
        """
        Find all windows matching the given pattern.

        Args:
            pattern: Window title pattern (supports wildcards)
            process_name: Optional process name filter

        Returns:
            List of matching WindowInfo objects
        """
        windows = self.list_windows(visible_only=True)
        matches = []

        for window in windows:
            if self._matches_pattern(window.title, pattern):
                if process_name:
                    if self._matches_pattern(window.process_name, process_name):
                        matches.append(window)
                else:
                    matches.append(window)

        return matches

    def _matches_pattern(self, text: str, pattern: str) -> bool:
        """
        Check if text matches the pattern.

        Supports:
        - Wildcards: *text*, text*, *text
        - Case-insensitive matching

        Args:
            text: Text to match
            pattern: Pattern to match against

        Returns:
            True if text matches pattern
        """
        if not pattern:
            return True

        # Case-insensitive matching
        text_lower = text.lower()
        pattern_lower = pattern.lower()

        # Use fnmatch for wildcard support
        return fnmatch.fnmatch(text_lower, pattern_lower)

    def capture_window(
        self,
        window: WindowInfo,
        include_border: bool = False
    ) -> Optional[str]:
        """
        Capture a screenshot of a specific window.

        Args:
            window: WindowInfo of window to capture
            include_border: Include window border/chrome

        Returns:
            Base64 encoded PNG image or None on failure
        """
        if self.platform == "Windows" and self._win32_available:
            return self._capture_window_win32(window, include_border)
        else:
            logger.warning(f"Window capture not supported on {self.platform}")
            return None

    def _capture_window_win32(
        self,
        window: WindowInfo,
        include_border: bool = False
    ) -> Optional[str]:
        """Capture window using Win32 API."""
        import win32gui
        import win32ui
        import win32con
        from PIL import Image

        hwnd = window.window_handle

        try:
            # Get window dimensions
            if include_border:
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            else:
                # Get client area (without border)
                left, top, right, bottom = win32gui.GetClientRect(hwnd)
                # Convert to screen coordinates
                pt = win32gui.ClientToScreen(hwnd, (left, top))
                left, top = pt
                pt = win32gui.ClientToScreen(hwnd, (right, bottom))
                right, bottom = pt

            width = right - left
            height = bottom - top

            if width <= 0 or height <= 0:
                logger.error(f"Invalid window dimensions: {width}x{height}")
                return None

            # Create device contexts
            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()

            # Create bitmap
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)

            # Copy screen to bitmap
            result = saveDC.BitBlt(
                (0, 0), (width, height),
                mfcDC, (0, 0) if include_border else (left - window.rect["left"], top - window.rect["top"]),
                win32con.SRCCOPY
            )

            # Convert to PIL Image
            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)

            img = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1
            )

            # Cleanup
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwndDC)

            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            return base64.b64encode(buffer.read()).decode('utf-8')

        except Exception as e:
            logger.error(f"Failed to capture window: {e}")
            return None

    def capture_window_by_pattern(
        self,
        pattern: str,
        process_name: Optional[str] = None,
        include_border: bool = False
    ) -> Tuple[Optional[str], Optional[WindowInfo]]:
        """
        Find and capture a window matching the pattern.

        Args:
            pattern: Window title pattern
            process_name: Optional process name filter
            include_border: Include window border

        Returns:
            Tuple of (base64_image, window_info) or (None, None) if not found
        """
        window = self.find_window_by_pattern(pattern, process_name)
        if not window:
            logger.warning(f"No window found matching pattern: {pattern}")
            return None, None

        if window.is_minimized:
            logger.warning(f"Window is minimized: {window.title}")
            # Optionally restore the window here

        image = self.capture_window(window, include_border)
        return image, window

    def validate_pattern(self, pattern: str) -> Tuple[bool, List[WindowInfo], Optional[str]]:
        """
        Validate a window pattern by checking if any windows match.

        Args:
            pattern: Window title pattern to validate

        Returns:
            Tuple of (is_valid, matching_windows, error_message)
        """
        if not pattern:
            return False, [], "Pattern cannot be empty"

        try:
            # Try to compile as regex to check validity
            # (Even though we use fnmatch, this catches obvious errors)
            if not any(c in pattern for c in ['*', '?', '[', ']']):
                # No wildcards, treat as substring match
                pattern = f"*{pattern}*"

            matching = self.find_windows_by_pattern(pattern)
            return len(matching) > 0, matching, None

        except Exception as e:
            return False, [], str(e)

    def bring_window_to_front(self, window: WindowInfo) -> bool:
        """
        Bring a window to the foreground.

        Args:
            window: Window to bring to front

        Returns:
            True if successful
        """
        if self.platform == "Windows" and self._win32_available:
            import win32gui
            import win32con

            try:
                hwnd = window.window_handle

                # Restore if minimized
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

                # Bring to foreground
                win32gui.SetForegroundWindow(hwnd)
                return True
            except Exception as e:
                logger.error(f"Failed to bring window to front: {e}")
                return False

        return False


# Global service instance
_window_capture_service: Optional[WindowCaptureService] = None


def get_window_capture_service() -> WindowCaptureService:
    """Get or create window capture service instance."""
    global _window_capture_service
    # Re-create if the existing instance doesn't have win32 support but we're on Windows
    if _window_capture_service is not None:
        if _window_capture_service.platform == "Windows" and not _window_capture_service._win32_available:
            logger.info("Recreating WindowCaptureService to check for win32 support")
            _window_capture_service = None
    if _window_capture_service is None:
        _window_capture_service = WindowCaptureService()
    return _window_capture_service
