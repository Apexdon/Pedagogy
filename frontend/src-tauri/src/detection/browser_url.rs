//! Browser URL extraction using uiautomation crate
//!
//! Provides reliable URL/origin extraction from browser address bars
//! using Windows UI Automation with the uiautomation crate.
//!
//! This module improves upon the raw Windows COM API approach by using
//! the higher-level uiautomation crate which handles COM initialization
//! and provides cleaner element searching.

use uiautomation::types::Handle;

/// Extract URL from a browser window using UI Automation
///
/// This function uses the uiautomation crate to find and read the browser's
/// address bar. It tries multiple strategies to locate the address bar:
/// 1. Search for Edit controls with names containing address bar indicators
/// 2. Look for controls with specific automation IDs
///
/// Returns the full URL if found, None otherwise.
pub fn get_browser_url_uia(hwnd: isize) -> Option<String> {
    use uiautomation::UIAutomation;
    use uiautomation::controls::ControlType;
    use uiautomation::patterns::UIValuePattern;
    use uiautomation::patterns::UILegacyIAccessiblePattern;

    log::debug!("Attempting URL extraction via uiautomation crate for hwnd: {}", hwnd);

    // Initialize UI Automation
    let automation = match UIAutomation::new() {
        Ok(auto) => auto,
        Err(e) => {
            log::warn!("Failed to create UIAutomation instance: {:?}", e);
            return None;
        }
    };

    // Get element from window handle - use uiautomation's Handle type
    let hwnd_handle = Handle::from(hwnd);
    let window_element = match automation.element_from_handle(hwnd_handle) {
        Ok(elem) => elem,
        Err(e) => {
            log::warn!("Failed to get element from handle: {:?}", e);
            return None;
        }
    };

    log::debug!("Got window element, searching for address bar...");

    // Address bar name indicators for various browsers
    let indicators = [
        "address and search bar",  // Chrome/Edge
        "address bar",
        "address",
        "omnibox",
        "search or type",
        "url",
        "location bar",            // Firefox
        "web address",
        "navigate to",
        "urlbar",
    ];

    // Strategy 1: Use matcher to find Edit controls
    let matcher = automation.create_matcher()
        .from(window_element.clone())
        .timeout(1000)
        .control_type(ControlType::Edit);

    if let Ok(elements) = matcher.find_all() {
        log::debug!("Found {} Edit controls", elements.len());

        for element in elements {
            // Check element name
            if let Ok(name) = element.get_name() {
                let name_lower = name.to_lowercase();

                for indicator in &indicators {
                    if name_lower.contains(indicator) {
                        log::debug!("Found element with name containing '{}': {}", indicator, name);

                        // Try to get value
                        if let Ok(value_pattern) = element.get_pattern::<UIValuePattern>() {
                            if let Ok(value) = value_pattern.get_value() {
                                if !value.is_empty() && looks_like_url(&value) {
                                    log::info!("Got URL via ValuePattern: {}", value);
                                    return Some(value);
                                }
                            }
                        }

                        // Try legacy pattern
                        if let Ok(legacy_pattern) = element.get_pattern::<UILegacyIAccessiblePattern>() {
                            if let Ok(value) = legacy_pattern.get_value() {
                                if !value.is_empty() && looks_like_url(&value) {
                                    log::info!("Got URL via LegacyPattern: {}", value);
                                    return Some(value);
                                }
                            }
                        }
                    }
                }
            }

            // Also check AutomationId for browser-specific patterns
            if let Ok(auto_id) = element.get_automation_id() {
                let auto_id_lower = auto_id.to_lowercase();
                if auto_id_lower.contains("address") ||
                   auto_id_lower.contains("url") ||
                   auto_id_lower.contains("omnibox") ||
                   auto_id_lower.contains("urlbar") {
                    log::debug!("Found element with AutomationId: {}", auto_id);

                    if let Ok(value_pattern) = element.get_pattern::<UIValuePattern>() {
                        if let Ok(value) = value_pattern.get_value() {
                            if !value.is_empty() && looks_like_url(&value) {
                                log::info!("Got URL via AutomationId match: {}", value);
                                return Some(value);
                            }
                        }
                    }
                }
            }
        }
    }

    // Strategy 2: Try to get any Edit control's value that looks like a URL
    let matcher2 = automation.create_matcher()
        .from(window_element)
        .timeout(500)
        .control_type(ControlType::Edit);

    if let Ok(elements) = matcher2.find_all() {
        for element in elements {
            if let Ok(value_pattern) = element.get_pattern::<UIValuePattern>() {
                if let Ok(value) = value_pattern.get_value() {
                    if !value.is_empty() && looks_like_url(&value) {
                        log::info!("Got URL from Edit control: {}", value);
                        return Some(value);
                    }
                }
            }
        }
    }

    log::debug!("Could not find URL via uiautomation");
    None
}

/// Check if a string looks like a URL
fn looks_like_url(s: &str) -> bool {
    let s_lower = s.to_lowercase();

    // Must start with protocol or look like a domain
    if s_lower.starts_with("http://") ||
       s_lower.starts_with("https://") ||
       s_lower.starts_with("file://") ||
       s_lower.starts_with("about:") ||
       s_lower.starts_with("chrome://") ||
       s_lower.starts_with("edge://") {
        return true;
    }

    // Check for domain-like patterns (contains dot, no spaces at start)
    if !s.starts_with(' ') && s.contains('.') && !s.contains(' ') {
        let parts: Vec<&str> = s.split('.').collect();
        if parts.len() >= 2 {
            // Check for common TLDs
            let last_part = parts.last().unwrap().to_lowercase();
            let tlds = ["com", "org", "net", "co", "uk", "io", "dev", "app", "edu", "gov"];
            for tld in &tlds {
                if last_part.starts_with(tld) {
                    return true;
                }
            }
        }
    }

    false
}

/// Extract the origin from a full URL
///
/// The origin consists of the scheme, host, and port (if non-standard).
/// Example: "https://uk.rs-online.com/web/products" -> "https://uk.rs-online.com"
///
/// This is useful for matching because the origin stays the same
/// regardless of which page the user is on.
pub fn extract_origin(url: &str) -> Option<String> {
    // Handle protocol-relative URLs
    let url_with_protocol = if url.starts_with("//") {
        format!("https:{}", url)
    } else if !url.contains("://") {
        // No protocol, assume https
        format!("https://{}", url)
    } else {
        url.to_string()
    };

    // Parse the URL
    let parts: Vec<&str> = url_with_protocol.splitn(2, "://").collect();
    if parts.len() != 2 {
        return None;
    }

    let scheme = parts[0];
    let rest = parts[1];

    // Extract host (and port if present)
    let host_end = rest.find('/').unwrap_or(rest.len());
    let host_port = &rest[..host_end];

    // Remove any userinfo (user:pass@)
    let host_port = if let Some(at_pos) = host_port.rfind('@') {
        &host_port[at_pos + 1..]
    } else {
        host_port
    };

    if host_port.is_empty() {
        return None;
    }

    Some(format!("{}://{}", scheme, host_port))
}

/// Extract just the domain (host without port) from a URL
pub fn extract_domain_from_url(url: &str) -> Option<String> {
    if let Some(origin) = extract_origin(url) {
        // Remove protocol
        let without_proto = origin
            .trim_start_matches("https://")
            .trim_start_matches("http://")
            .trim_start_matches("file://");

        // Remove port
        let domain = if let Some(colon_pos) = without_proto.find(':') {
            &without_proto[..colon_pos]
        } else {
            without_proto
        };

        // Remove www. prefix for consistency
        let domain = domain.trim_start_matches("www.");

        if !domain.is_empty() {
            return Some(domain.to_lowercase());
        }
    }

    None
}

/// Check if a URL matches a target origin pattern
///
/// Supports:
/// - Exact domain match: "uk.rs-online.com"
/// - Wildcard subdomain: "*.rs-online.com" matches "uk.rs-online.com", "www.rs-online.com"
/// - Full origin match: "https://uk.rs-online.com"
pub fn url_matches_origin_pattern(url: &str, pattern: &str) -> bool {
    let url_domain = match extract_domain_from_url(url) {
        Some(d) => d,
        None => return false,
    };

    let pattern_lower = pattern.to_lowercase();

    // Remove protocol from pattern if present
    let pattern_domain = pattern_lower
        .trim_start_matches("https://")
        .trim_start_matches("http://")
        .trim_start_matches("www.");

    // Handle wildcard patterns
    if pattern_domain.starts_with("*.") {
        let suffix = &pattern_domain[2..]; // Remove "*."
        return url_domain.ends_with(suffix) || url_domain == suffix.trim_start_matches(".");
    }

    // Direct match
    url_domain == pattern_domain || url_domain.ends_with(&format!(".{}", pattern_domain))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_origin() {
        assert_eq!(
            extract_origin("https://uk.rs-online.com/web/products"),
            Some("https://uk.rs-online.com".to_string())
        );
        assert_eq!(
            extract_origin("http://localhost:3000/api"),
            Some("http://localhost:3000".to_string())
        );
        assert_eq!(
            extract_origin("https://example.com"),
            Some("https://example.com".to_string())
        );
    }

    #[test]
    fn test_extract_domain() {
        assert_eq!(
            extract_domain_from_url("https://uk.rs-online.com/web/"),
            Some("uk.rs-online.com".to_string())
        );
        assert_eq!(
            extract_domain_from_url("https://www.google.com"),
            Some("google.com".to_string())
        );
    }

    #[test]
    fn test_url_matches_pattern() {
        // Exact match
        assert!(url_matches_origin_pattern(
            "https://uk.rs-online.com/web/",
            "uk.rs-online.com"
        ));

        // Wildcard match
        assert!(url_matches_origin_pattern(
            "https://uk.rs-online.com/",
            "*.rs-online.com"
        ));
        assert!(url_matches_origin_pattern(
            "https://www.rs-online.com/",
            "*.rs-online.com"
        ));

        // No match
        assert!(!url_matches_origin_pattern(
            "https://google.com/",
            "rs-online.com"
        ));
    }

    #[test]
    fn test_looks_like_url() {
        assert!(looks_like_url("https://example.com"));
        assert!(looks_like_url("http://localhost:3000"));
        assert!(looks_like_url("example.com"));
        assert!(looks_like_url("uk.rs-online.com"));
        assert!(!looks_like_url("just some text"));
        assert!(!looks_like_url("Search or type URL"));
    }
}
