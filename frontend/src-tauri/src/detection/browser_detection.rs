//! Browser URL Detection Module
//!
//! Provides functions to detect browser windows and extract the current URL
//! from the address bar using Windows UI Automation API.
//!
//! Supports major browsers: Chrome, Firefox, Edge, Brave, Opera

use serde::{Deserialize, Serialize};

/// Known browser process names
pub const BROWSER_PROCESSES: &[&str] = &[
    "chrome.exe",
    "firefox.exe",
    "msedge.exe",
    "brave.exe",
    "opera.exe",
    "vivaldi.exe",
    "chromium.exe",
];

/// Browser type enumeration
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum BrowserType {
    Chrome,
    Firefox,
    Edge,
    Brave,
    Opera,
    Vivaldi,
    Chromium,
    Unknown,
}

impl BrowserType {
    /// Detect browser type from process name
    pub fn from_process_name(process_name: &str) -> Self {
        match process_name.to_lowercase().as_str() {
            "chrome.exe" => BrowserType::Chrome,
            "firefox.exe" => BrowserType::Firefox,
            "msedge.exe" => BrowserType::Edge,
            "brave.exe" => BrowserType::Brave,
            "opera.exe" => BrowserType::Opera,
            "vivaldi.exe" => BrowserType::Vivaldi,
            "chromium.exe" => BrowserType::Chromium,
            _ => BrowserType::Unknown,
        }
    }
}

/// Extended window information including URL for browsers
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtendedWindowInfo {
    pub title: String,
    pub process_name: String,
    pub process_id: u32,
    pub hwnd: isize,
    pub is_browser: bool,
    pub browser_type: Option<BrowserType>,
    pub url: Option<String>,
    pub url_domain: Option<String>,
    /// Full origin (scheme + domain + port) - stays same across page navigations
    pub url_origin: Option<String>,
}

impl ExtendedWindowInfo {
    /// Extract domain from URL
    pub fn extract_domain(url: &str) -> Option<String> {
        // Handle common URL formats
        let url = url.trim();

        // Remove protocol
        let without_protocol = url
            .strip_prefix("https://")
            .or_else(|| url.strip_prefix("http://"))
            .or_else(|| url.strip_prefix("file://"))
            .unwrap_or(url);

        // Get domain part (before first /)
        let domain = without_protocol
            .split('/')
            .next()
            .unwrap_or(without_protocol);

        // Remove port if present
        let domain = domain.split(':').next().unwrap_or(domain);

        // Remove www. prefix for consistency
        let domain = domain.strip_prefix("www.").unwrap_or(domain);

        if domain.is_empty() || !domain.contains('.') {
            None
        } else {
            Some(domain.to_lowercase())
        }
    }

    /// Check if URL matches a pattern
    pub fn url_matches_pattern(&self, pattern: &str) -> bool {
        let pattern = pattern.to_lowercase();

        // Check URL directly
        if let Some(ref url) = self.url {
            let url_lower = url.to_lowercase();
            if url_lower.contains(&pattern) {
                log::debug!("URL matches pattern directly: {} contains {}", url_lower, pattern);
                return true;
            }
        }

        // Check domain
        if let Some(ref domain) = self.url_domain {
            let domain_lower = domain.to_lowercase();

            // Handle wildcard patterns
            if pattern.starts_with("*.") {
                let suffix = &pattern[2..];
                if domain_lower.ends_with(suffix) || domain_lower == suffix.strip_prefix('.').unwrap_or(suffix) {
                    log::debug!("Domain matches wildcard pattern: {} matches {}", domain_lower, pattern);
                    return true;
                }
            }

            // Handle patterns ending with wildcard
            if pattern.ends_with(".*") {
                let prefix = &pattern[..pattern.len() - 2];
                if domain_lower.starts_with(prefix) {
                    log::debug!("Domain matches prefix pattern: {} matches {}", domain_lower, pattern);
                    return true;
                }
            }

            // Direct match or contains
            if domain_lower == pattern || domain_lower.contains(&pattern) {
                log::debug!("Domain matches pattern: {} contains {}", domain_lower, pattern);
                return true;
            }
        }

        // Fallback: Check if window title contains the domain pattern (for browsers)
        // This helps when UI Automation fails to get the URL
        if self.is_browser {
            let title_lower = self.title.to_lowercase();

            // Extract the main domain name from the pattern (e.g., "rs-online" from "uk.rs-online.com")
            let domain_parts: Vec<&str> = pattern.split('.').collect();

            // Check each significant part of the domain
            for part in &domain_parts {
                // Skip common TLDs and country codes
                if part.len() > 2 && *part != "com" && *part != "org" && *part != "net" && *part != "www" {
                    if title_lower.contains(*part) {
                        log::info!("Window title contains domain part '{}': {}", part, self.title);
                        return true;
                    }
                }
            }

            // Also check the full domain without TLD
            // e.g., for "uk.rs-online.com", check if title contains "rs-online"
            if domain_parts.len() >= 2 {
                // Try second-to-last part (usually the main domain)
                let main_domain = domain_parts.get(domain_parts.len().saturating_sub(2)).unwrap_or(&"");
                if main_domain.len() > 2 && title_lower.contains(*main_domain) {
                    log::info!("Window title contains main domain '{}': {}", main_domain, self.title);
                    return true;
                }
            }
        }

        log::debug!("No match found for pattern '{}' in URL: {:?}, domain: {:?}, title: {}",
            pattern, self.url, self.url_domain, self.title);
        false
    }
}

/// Check if a process name is a known browser
pub fn is_browser_process(process_name: &str) -> bool {
    let name_lower = process_name.to_lowercase();
    BROWSER_PROCESSES.iter().any(|&browser| name_lower == browser)
}

#[cfg(target_os = "windows")]
mod windows_impl {
    use super::*;
    use windows::Win32::Foundation::HWND;
    use windows::Win32::UI::WindowsAndMessaging::{
        GetForegroundWindow, GetWindowTextW, GetWindowThreadProcessId,
    };
    use windows::Win32::System::Threading::{
        OpenProcess, PROCESS_QUERY_LIMITED_INFORMATION,
    };
    use windows::Win32::System::ProcessStatus::GetModuleBaseNameW;

    /// Get the process name from a window handle
    pub fn get_process_name_from_hwnd(hwnd: HWND) -> Option<String> {
        use windows::Win32::System::Threading::QueryFullProcessImageNameW;
        use windows::Win32::System::Threading::PROCESS_NAME_WIN32;

        unsafe {
            let mut process_id: u32 = 0;
            GetWindowThreadProcessId(hwnd, Some(&mut process_id));

            if process_id == 0 {
                return None;
            }

            let handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, process_id).ok()?;

            // First try QueryFullProcessImageNameW (works better with limited permissions)
            let mut path_buf: [u16; 260] = [0; 260];
            let mut path_len: u32 = 260;

            if QueryFullProcessImageNameW(handle, PROCESS_NAME_WIN32, windows::core::PWSTR(path_buf.as_mut_ptr()), &mut path_len).is_ok() && path_len > 0 {
                let full_path = String::from_utf16_lossy(&path_buf[..path_len as usize]);
                // Extract just the executable name from the full path
                if let Some(exe_name) = full_path.rsplit('\\').next() {
                    return Some(exe_name.to_string());
                }
            }

            // Fallback to GetModuleBaseNameW
            let mut name_buf: [u16; 260] = [0; 260];
            let len = GetModuleBaseNameW(handle, None, &mut name_buf);

            if len > 0 {
                let name = String::from_utf16_lossy(&name_buf[..len as usize]);
                Some(name)
            } else {
                None
            }
        }
    }

    /// Get the process ID from a window handle
    pub fn get_process_id_from_hwnd(hwnd: HWND) -> u32 {
        unsafe {
            let mut process_id: u32 = 0;
            GetWindowThreadProcessId(hwnd, Some(&mut process_id));
            process_id
        }
    }

    /// Get extended window information for the foreground window
    pub fn get_extended_window_info() -> Option<ExtendedWindowInfo> {
        unsafe {
            let hwnd = GetForegroundWindow();
            if hwnd.0 == std::ptr::null_mut() {
                return None;
            }

            get_extended_window_info_from_hwnd(hwnd)
        }
    }

    /// Get extended window information from a specific window handle
    pub fn get_extended_window_info_from_hwnd(hwnd: HWND) -> Option<ExtendedWindowInfo> {
        unsafe {
            // Get window title
            let mut title_buf: [u16; 512] = [0; 512];
            let len = GetWindowTextW(hwnd, &mut title_buf);
            let title = if len > 0 {
                String::from_utf16_lossy(&title_buf[..len as usize])
            } else {
                String::new()
            };

            // Get process info
            let process_name = get_process_name_from_hwnd(hwnd).unwrap_or_default();
            let process_id = get_process_id_from_hwnd(hwnd);

            // Check if it's a browser
            let is_browser = is_browser_process(&process_name);
            let browser_type = if is_browser {
                Some(BrowserType::from_process_name(&process_name))
            } else {
                None
            };

            // Try to get URL if it's a browser
            let (url, url_domain, url_origin) = if is_browser {
                let url = get_browser_url(hwnd, browser_type.as_ref());
                let domain = url.as_ref().and_then(|u| ExtendedWindowInfo::extract_domain(u));
                let origin = url.as_ref().and_then(|u| crate::detection::browser_url::extract_origin(u));
                (url, domain, origin)
            } else {
                (None, None, None)
            };

            Some(ExtendedWindowInfo {
                title,
                process_name,
                process_id,
                hwnd: hwnd.0 as isize,
                is_browser,
                browser_type,
                url,
                url_domain,
                url_origin,
            })
        }
    }

    /// Find a browser window matching the given URL patterns
    /// This searches all open windows, not just the foreground window
    pub fn find_browser_window_by_url(url_patterns: &[String]) -> Option<ExtendedWindowInfo> {
        use windows::Win32::UI::WindowsAndMessaging::{
            EnumWindows, IsWindowVisible, GetWindowTextLengthW,
        };
        use windows::Win32::Foundation::BOOL;
        use std::sync::Mutex;

        // Collect matching windows
        let results: Mutex<Vec<ExtendedWindowInfo>> = Mutex::new(Vec::new());
        let patterns = url_patterns.to_vec();

        unsafe extern "system" fn enum_callback(
            hwnd: HWND,
            lparam: windows::Win32::Foundation::LPARAM,
        ) -> BOOL {
            // Get the patterns from lparam
            let data = lparam.0 as *mut (&[String], &Mutex<Vec<ExtendedWindowInfo>>);
            let (patterns, results) = &*data;

            // Skip invisible windows
            if IsWindowVisible(hwnd).as_bool() == false {
                return BOOL(1); // Continue enumeration
            }

            // Skip windows without titles
            if GetWindowTextLengthW(hwnd) == 0 {
                return BOOL(1);
            }

            // Get process name
            if let Some(process_name) = get_process_name_from_hwnd(hwnd) {
                // Only check browser processes
                if is_browser_process(&process_name) {
                    if let Some(info) = get_extended_window_info_from_hwnd(hwnd) {
                        // Check if URL matches any pattern
                        for pattern in *patterns {
                            if info.url_matches_pattern(pattern) {
                                log::info!("Found matching browser window: {} (URL: {:?})",
                                    info.title, info.url_domain);
                                if let Ok(mut results) = results.lock() {
                                    results.push(info);
                                }
                                return BOOL(0); // Stop enumeration, we found a match
                            }
                        }
                    }
                }
            }

            BOOL(1) // Continue enumeration
        }

        unsafe {
            let data: (&[String], &Mutex<Vec<ExtendedWindowInfo>>) = (&patterns, &results);
            let lparam = windows::Win32::Foundation::LPARAM(&data as *const _ as isize);

            let _ = EnumWindows(Some(enum_callback), lparam);
        }

        // Return the first matching window
        results.into_inner().ok()?.into_iter().next()
    }

    /// Try to get the browser URL using UI Automation
    ///
    /// This uses Windows UI Automation API to find the address bar element
    /// and extract its value. Different browsers have different UI structures.
    ///
    /// Tries multiple strategies in order:
    /// 1. New uiautomation crate (most reliable)
    /// 2. Legacy raw COM API
    /// 3. Window title parsing (fallback)
    pub fn get_browser_url(hwnd: HWND, browser_type: Option<&BrowserType>) -> Option<String> {
        // First try new uiautomation crate (most reliable)
        if let Some(url) = crate::detection::browser_url::get_browser_url_uia(hwnd.0 as isize) {
            log::info!("Got URL via uiautomation crate: {}", url);
            return Some(url);
        }

        // Second try legacy UI Automation via raw COM
        if let Some(url) = get_url_via_ui_automation(hwnd) {
            log::info!("Got URL via legacy UI Automation: {}", url);
            return Some(url);
        }

        // Fallback: Try to extract URL/domain from window title
        // Many browsers show the domain or full URL in the title
        if let Some(url) = get_url_from_window_title(hwnd, browser_type) {
            log::info!("Got URL from window title: {}", url);
            return Some(url);
        }

        log::warn!("Could not extract URL from browser window");
        None
    }

    /// Try to extract URL from window title
    /// Browser titles often contain the domain: "Page Title - Site Name" or "Site Name - Browser"
    fn get_url_from_window_title(hwnd: HWND, _browser_type: Option<&BrowserType>) -> Option<String> {
        use windows::Win32::UI::WindowsAndMessaging::GetWindowTextW;

        unsafe {
            let mut title_buf: [u16; 512] = [0; 512];
            let len = GetWindowTextW(hwnd, &mut title_buf);
            if len == 0 {
                return None;
            }

            let title = String::from_utf16_lossy(&title_buf[..len as usize]);
            log::debug!("Window title for URL extraction: {}", title);

            // Look for URL patterns in the title
            // Pattern 1: Full URL in title (some browsers show this)
            if title.contains("http://") || title.contains("https://") {
                if let Some(start) = title.find("http") {
                    let url_part = &title[start..];
                    let end = url_part.find(|c: char| c.is_whitespace() || c == ')' || c == ']')
                        .unwrap_or(url_part.len());
                    return Some(url_part[..end].to_string());
                }
            }

            // Pattern 2: Common browser title patterns
            // Chrome/Edge: "Page Title - Site.com"
            // Firefox: "Page Title — Site.com"
            let separators = [" - ", " — ", " | ", " – "];
            for sep in separators {
                if let Some(parts) = title.split(sep).last() {
                    let potential_domain = parts.trim();
                    // Check if it looks like a domain (contains . and doesn't look like browser name)
                    if potential_domain.contains('.')
                        && !potential_domain.to_lowercase().contains("chrome")
                        && !potential_domain.to_lowercase().contains("edge")
                        && !potential_domain.to_lowercase().contains("firefox")
                        && !potential_domain.to_lowercase().contains("browser")
                        && !potential_domain.to_lowercase().contains("microsoft")
                        && !potential_domain.to_lowercase().contains("mozilla")
                    {
                        // Extract just the domain part
                        let domain = potential_domain.split_whitespace().next().unwrap_or(potential_domain);
                        if domain.contains('.') && domain.len() < 100 {
                            log::debug!("Extracted domain from title: {}", domain);
                            return Some(format!("https://{}", domain.to_lowercase()));
                        }
                    }
                }
            }

            None
        }
    }

    /// Get URL via Windows UI Automation API
    ///
    /// This is a simplified implementation that searches for edit controls
    /// with address-related names and extracts their value.
    fn get_url_via_ui_automation(hwnd: HWND) -> Option<String> {
        use windows::Win32::UI::Accessibility::{
            CUIAutomation, IUIAutomation, IUIAutomationElement,
            IUIAutomationValuePattern,
            UIA_ControlTypePropertyId, UIA_EditControlTypeId, UIA_ValuePatternId,
            UIA_NamePropertyId, UIA_AutomationIdPropertyId, TreeScope_Descendants,
        };
        use windows::Win32::System::Com::{CoCreateInstance, CLSCTX_INPROC_SERVER, CoInitializeEx, COINIT_MULTITHREADED};
        use windows::core::Interface;

        unsafe {
            // Initialize COM
            let _ = CoInitializeEx(None, COINIT_MULTITHREADED);

            // Create UI Automation instance
            let automation: IUIAutomation = match CoCreateInstance(&CUIAutomation, None, CLSCTX_INPROC_SERVER) {
                Ok(a) => a,
                Err(e) => {
                    log::warn!("Failed to create UI Automation: {:?}", e);
                    return None;
                }
            };

            // Get the element from HWND
            let root_element: IUIAutomationElement = match automation.ElementFromHandle(hwnd) {
                Ok(e) => e,
                Err(e) => {
                    log::warn!("Failed to get element from HWND: {:?}", e);
                    return None;
                }
            };

            // Create condition to find Edit controls
            // UIA_EditControlTypeId is 50004
            let condition = match automation.CreatePropertyCondition(
                UIA_ControlTypePropertyId,
                &windows::core::VARIANT::from(UIA_EditControlTypeId.0 as i32),
            ) {
                Ok(c) => c,
                Err(e) => {
                    log::warn!("Failed to create property condition: {:?}", e);
                    return None;
                }
            };

            // Find all edit controls
            let elements = match root_element.FindAll(TreeScope_Descendants, &condition) {
                Ok(e) => e,
                Err(e) => {
                    log::warn!("Failed to find edit controls: {:?}", e);
                    return None;
                }
            };

            let count = elements.Length().unwrap_or(0);
            log::debug!("Found {} edit controls in browser window", count);

            // Address bar indicators for different browsers
            let address_bar_indicators = [
                // Chrome/Edge
                "address and search bar",
                "address",
                "omnibox",
                "search or type",
                "search or enter",
                // Firefox
                "urlbar",
                "navigation toolbar",
                "search or enter address",
                "search with",
                // Generic
                "url",
                "location bar",
                "web address",
            ];

            for i in 0..count {
                if let Ok(element) = elements.GetElement(i) {
                    // Check the name property
                    let name_str = element.GetCurrentPropertyValue(UIA_NamePropertyId)
                        .ok()
                        .map(|v| variant_to_string(&v))
                        .unwrap_or_default();

                    // Check automation ID as well
                    let auto_id_str = element.GetCurrentPropertyValue(UIA_AutomationIdPropertyId)
                        .ok()
                        .map(|v| variant_to_string(&v))
                        .unwrap_or_default();

                    let name_lower = name_str.to_lowercase();
                    let auto_id_lower = auto_id_str.to_lowercase();

                    // Look for address bar indicators in name or automation ID
                    let is_address_bar = address_bar_indicators.iter().any(|indicator| {
                        name_lower.contains(indicator) || auto_id_lower.contains(indicator)
                    });

                    if is_address_bar {
                        log::debug!("Found potential address bar: name='{}', autoId='{}'", name_str, auto_id_str);

                        // Try to get the value using Value pattern
                        if let Ok(pattern) = element.GetCurrentPattern(UIA_ValuePatternId) {
                            if let Ok(value_pattern) = pattern.cast::<IUIAutomationValuePattern>() {
                                if let Ok(value) = value_pattern.CurrentValue() {
                                    let url = value.to_string();
                                    log::debug!("Address bar value: {}", url);
                                    if !url.is_empty() && (url.starts_with("http") || url.contains(".")) {
                                        return Some(url);
                                    }
                                }
                            }
                        }
                    }
                }
            }

            log::debug!("UI Automation did not find address bar URL");
            None
        }
    }

    /// Helper to convert VARIANT to String
    fn variant_to_string(variant: &windows::core::VARIANT) -> String {
        // Try to extract string from VARIANT
        // The VARIANT type in windows crate 0.58 uses a different structure
        match variant.to_string() {
            s if !s.is_empty() => s,
            _ => String::new(),
        }
    }
}

#[cfg(target_os = "windows")]
pub use windows_impl::*;

#[cfg(not(target_os = "windows"))]
mod stub_impl {
    use super::*;

    pub fn get_extended_window_info() -> Option<ExtendedWindowInfo> {
        None
    }

    pub fn get_browser_url(_hwnd: isize, _browser_type: Option<&BrowserType>) -> Option<String> {
        None
    }
}

#[cfg(not(target_os = "windows"))]
pub use stub_impl::*;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_browser_process() {
        assert!(is_browser_process("chrome.exe"));
        assert!(is_browser_process("Chrome.exe"));
        assert!(is_browser_process("firefox.exe"));
        assert!(is_browser_process("msedge.exe"));
        assert!(!is_browser_process("notepad.exe"));
        assert!(!is_browser_process("code.exe"));
    }

    #[test]
    fn test_browser_type_from_process() {
        assert_eq!(BrowserType::from_process_name("chrome.exe"), BrowserType::Chrome);
        assert_eq!(BrowserType::from_process_name("CHROME.EXE"), BrowserType::Chrome);
        assert_eq!(BrowserType::from_process_name("firefox.exe"), BrowserType::Firefox);
        assert_eq!(BrowserType::from_process_name("msedge.exe"), BrowserType::Edge);
        assert_eq!(BrowserType::from_process_name("notepad.exe"), BrowserType::Unknown);
    }

    #[test]
    fn test_extract_domain() {
        assert_eq!(
            ExtendedWindowInfo::extract_domain("https://www.example.com/page"),
            Some("example.com".to_string())
        );
        assert_eq!(
            ExtendedWindowInfo::extract_domain("http://uk.rs-online.com/web/"),
            Some("uk.rs-online.com".to_string())
        );
        assert_eq!(
            ExtendedWindowInfo::extract_domain("https://accounts.google.com:443/login"),
            Some("accounts.google.com".to_string())
        );
        assert_eq!(
            ExtendedWindowInfo::extract_domain("not-a-url"),
            None
        );
    }

    #[test]
    fn test_url_pattern_matching() {
        let info = ExtendedWindowInfo {
            title: "Test".to_string(),
            process_name: "chrome.exe".to_string(),
            process_id: 1234,
            hwnd: 0,
            is_browser: true,
            browser_type: Some(BrowserType::Chrome),
            url: Some("https://uk.rs-online.com/web/products".to_string()),
            url_domain: Some("uk.rs-online.com".to_string()),
            url_origin: Some("https://uk.rs-online.com".to_string()),
        };

        // Direct domain match
        assert!(info.url_matches_pattern("rs-online.com"));
        assert!(info.url_matches_pattern("uk.rs-online.com"));

        // Wildcard patterns
        assert!(info.url_matches_pattern("*.rs-online.com"));

        // No match
        assert!(!info.url_matches_pattern("amazon.com"));
    }
}
