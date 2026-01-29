"""
Browser URL Extractor using pywinauto.

This module provides reliable URL extraction from browser windows
using Windows UI Automation via pywinauto library.
"""

import logging
from typing import Optional, List, Dict, Any
import re

logger = logging.getLogger(__name__)

# Browser process names (lowercase)
BROWSER_PROCESSES = {
    "chrome.exe", "msedge.exe", "firefox.exe",
    "brave.exe", "opera.exe", "vivaldi.exe", "chromium.exe"
}


def is_browser_process(process_name: str) -> bool:
    """Check if a process name is a known browser."""
    return process_name.lower() in BROWSER_PROCESSES


def looks_like_url(s: str) -> bool:
    """Check if a string looks like a URL."""
    if not s:
        return False

    s_lower = s.lower().strip()

    # Check for protocols
    if any(s_lower.startswith(proto) for proto in [
        "http://", "https://", "file://", "about:", "chrome://", "edge://"
    ]):
        return True

    # Check for domain-like patterns (no spaces, has dots)
    if '.' in s and ' ' not in s and not s.startswith(' '):
        parts = s.split('.')
        if len(parts) >= 2:
            tlds = ["com", "org", "net", "co", "uk", "io", "dev", "app", "edu", "gov"]
            last_part = parts[-1].lower().split('/')[0]  # Handle paths
            for tld in tlds:
                if last_part == tld or last_part.startswith(tld + ':'):
                    return True

    return False


def extract_domain(url: str) -> Optional[str]:
    """Extract domain from URL."""
    if not url:
        return None
    try:
        url = url.lower()
        # Remove protocol
        for proto in ["https://", "http://", "file://"]:
            if url.startswith(proto):
                url = url[len(proto):]
                break

        # Get domain part (before first /)
        domain = url.split('/')[0]
        # Remove port
        domain = domain.split(':')[0]
        # Remove www
        if domain.startswith("www."):
            domain = domain[4:]

        return domain if domain else None
    except:
        return None


def url_matches_pattern(url: str, pattern: str) -> bool:
    """Check if URL matches a pattern."""
    if not url or not pattern:
        return False

    domain = extract_domain(url)
    if not domain:
        return False

    pattern_lower = pattern.lower()

    # Remove protocol from pattern
    for proto in ["https://", "http://"]:
        if pattern_lower.startswith(proto):
            pattern_lower = pattern_lower[len(proto):]

    # Handle wildcard patterns like *.rs-online.com
    if pattern_lower.startswith("*."):
        suffix = pattern_lower[2:]
        return domain.endswith(suffix) or domain == suffix

    # Direct match or subdomain match
    return domain == pattern_lower or domain.endswith("." + pattern_lower)


def get_browser_url_pywinauto(hwnd: int) -> Optional[str]:
    """
    Extract URL from a browser window using pywinauto.

    Args:
        hwnd: Window handle of the browser window

    Returns:
        URL string if found, None otherwise
    """
    try:
        from pywinauto import Desktop
        from pywinauto.controls.uiawrapper import UIAWrapper

        logger.info(f"Extracting URL from hwnd: {hwnd}")

        # Connect to the window
        desktop = Desktop(backend="uia")

        # Find the window by handle
        window = None
        for win in desktop.windows():
            if win.handle == hwnd:
                window = win
                break

        if not window:
            logger.warning(f"Could not find window with hwnd {hwnd}")
            return None

        logger.info(f"Found window: {window.window_text()[:50]}...")

        # Search for address bar - try multiple strategies

        # Strategy 1: Look for Edit controls with address-related names
        address_indicators = [
            "address and search bar",
            "address bar",
            "address",
            "omnibox",
            "search or type url",
            "search or enter web address",
        ]

        try:
            # Get all Edit controls
            edits = window.descendants(control_type="Edit")
            logger.info(f"Found {len(edits)} Edit controls")

            for edit in edits:
                try:
                    name = edit.element_info.name or ""
                    auto_id = edit.element_info.automation_id or ""

                    logger.debug(f"Edit: name='{name}', autoId='{auto_id}'")

                    # Check if this looks like an address bar
                    name_lower = name.lower()
                    auto_id_lower = auto_id.lower()

                    is_address = any(
                        ind in name_lower or ind in auto_id_lower
                        for ind in address_indicators
                    )

                    if is_address:
                        logger.info(f"Found potential address bar: name='{name}'")

                        # Try to get the value
                        try:
                            # Get text from the edit control
                            value = edit.get_value()
                            if value and looks_like_url(value):
                                logger.info(f"Found URL: {value}")
                                return value
                        except Exception as e:
                            logger.debug(f"Could not get value: {e}")

                        # Try legacy text retrieval
                        try:
                            text = edit.window_text()
                            if text and looks_like_url(text):
                                logger.info(f"Found URL via window_text: {text}")
                                return text
                        except Exception as e:
                            logger.debug(f"Could not get window_text: {e}")

                except Exception as e:
                    logger.debug(f"Error checking edit control: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Error searching Edit controls: {e}")

        # Strategy 2: Look for any control with URL-like value
        try:
            for ctrl in window.descendants():
                try:
                    if hasattr(ctrl, 'get_value'):
                        value = ctrl.get_value()
                        if value and looks_like_url(value):
                            logger.info(f"Found URL in control: {value}")
                            return value
                except:
                    pass
        except Exception as e:
            logger.debug(f"Error in value search: {e}")

        logger.warning("Could not find URL in browser window")
        return None

    except ImportError as e:
        logger.error(f"pywinauto not available: {e}")
        return None
    except Exception as e:
        logger.error(f"Error extracting browser URL: {e}", exc_info=True)
        return None


def find_all_browser_windows() -> List[Dict[str, Any]]:
    """
    Find all open browser windows.

    Returns:
        List of dicts with 'hwnd', 'title', 'process_name' for each browser window
    """
    try:
        from pywinauto import Desktop
        import psutil

        browsers = []
        desktop = Desktop(backend="uia")

        for win in desktop.windows():
            try:
                hwnd = win.handle
                title = win.window_text()

                if not title:
                    continue

                # Get process name
                pid = win.process_id()
                try:
                    proc = psutil.Process(pid)
                    process_name = proc.name()
                except:
                    continue

                if is_browser_process(process_name):
                    browsers.append({
                        "hwnd": hwnd,
                        "title": title,
                        "process_name": process_name
                    })
                    logger.info(f"Found browser: {process_name} - '{title[:50]}...'")

            except Exception as e:
                logger.debug(f"Error checking window: {e}")
                continue

        return browsers

    except Exception as e:
        logger.error(f"Error finding browser windows: {e}")
        return []


def find_browser_with_url_pattern(url_patterns: List[str]) -> Optional[Dict[str, Any]]:
    """
    Find a browser window with a URL matching the given patterns.

    Args:
        url_patterns: List of URL patterns (e.g., ["rs-online.com", "uk.rs-online.com"])

    Returns:
        Dict with 'hwnd', 'title', 'process_name', 'url', 'domain' if found, None otherwise
    """
    logger.info(f"Searching for browser matching URL patterns: {url_patterns}")

    browsers = find_all_browser_windows()
    logger.info(f"Found {len(browsers)} browser windows")

    for browser in browsers:
        hwnd = browser["hwnd"]
        title = browser["title"]

        logger.info(f"Checking browser: {title[:50]}...")

        url = get_browser_url_pywinauto(hwnd)

        if url:
            browser["url"] = url
            browser["domain"] = extract_domain(url)

            for pattern in url_patterns:
                if url_matches_pattern(url, pattern):
                    logger.info(f"Match found! URL '{url}' matches pattern '{pattern}'")
                    return browser

            logger.info(f"URL '{url}' does not match patterns")
        else:
            logger.info(f"Could not extract URL from this browser")

    logger.info("No browser found matching URL patterns")
    return None


def get_foreground_browser_url() -> Optional[Dict[str, Any]]:
    """
    Get URL from the currently active browser window (if foreground window is a browser).

    Returns:
        Dict with 'hwnd', 'title', 'process_name', 'url', 'domain' if found, None otherwise
    """
    try:
        from pywinauto import Desktop
        import psutil
        from ctypes import windll

        # Get foreground window handle
        hwnd = windll.user32.GetForegroundWindow()
        if not hwnd:
            return None

        desktop = Desktop(backend="uia")

        # Find window by handle
        for win in desktop.windows():
            if win.handle == hwnd:
                title = win.window_text()
                pid = win.process_id()

                try:
                    proc = psutil.Process(pid)
                    process_name = proc.name()
                except:
                    return None

                if not is_browser_process(process_name):
                    logger.info(f"Foreground window is not a browser: {process_name}")
                    return None

                url = get_browser_url_pywinauto(hwnd)

                if url:
                    return {
                        "hwnd": hwnd,
                        "title": title,
                        "process_name": process_name,
                        "url": url,
                        "domain": extract_domain(url)
                    }

                return {
                    "hwnd": hwnd,
                    "title": title,
                    "process_name": process_name,
                    "url": None,
                    "domain": None
                }

        return None

    except Exception as e:
        logger.error(f"Error getting foreground browser URL: {e}")
        return None


# Test function
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("Browser URL Extractor Test")
    print("=" * 60)

    print("\n1. Finding all browser windows...")
    browsers = find_all_browser_windows()
    print(f"   Found {len(browsers)} browser windows:")
    for b in browsers:
        print(f"   - {b['process_name']}: {b['title'][:50]}...")

    print("\n2. Testing foreground browser URL extraction...")
    result = get_foreground_browser_url()
    if result:
        print(f"   Foreground browser: {result['process_name']}")
        print(f"   Title: {result['title'][:50]}...")
        print(f"   URL: {result.get('url', 'NOT FOUND')}")
        print(f"   Domain: {result.get('domain', 'N/A')}")
    else:
        print("   No browser in foreground or URL extraction failed")

    print("\n3. Searching for browser with RS Components URL...")
    result = find_browser_with_url_pattern(["uk.rs-online.com", "rs-online.com"])
    if result:
        print(f"   Found match!")
        print(f"   Browser: {result['process_name']}")
        print(f"   Title: {result['title'][:50]}...")
        print(f"   URL: {result.get('url')}")
        print(f"   Domain: {result.get('domain')}")
    else:
        print("   No matching browser found")

    print("\n" + "=" * 60)
