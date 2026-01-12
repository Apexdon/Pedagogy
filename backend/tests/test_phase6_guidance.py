"""
Phase 6: AI Guidance Engine - Automated Test Script

Tests all components of the AI Guidance Engine:
1. Health checks (services, LLM, guidance)
2. Authentication flow
3. Guidance generation
4. Session management
5. Step navigation
6. Database persistence

Usage:
    cd backend
    ./venv/Scripts/python.exe tests/test_phase6_guidance.py
"""

import asyncio
import httpx
import json
import sys
import os
from datetime import datetime
from typing import Optional, Dict, Any

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Configuration
BASE_URL = "http://localhost:8000"
TEST_USER_EMAIL = "phase6tester@example.com"
TEST_USER_PASSWORD = "SecurePass123"
TEST_USER_NAME = "Phase6 Tester"
TEST_ORG_NAME = "Phase6 Test Org"

# Check if terminal supports colors
USE_COLORS = os.environ.get("TERM") or os.environ.get("WT_SESSION") or sys.platform != "win32"


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m" if USE_COLORS else ""
    RED = "\033[91m" if USE_COLORS else ""
    YELLOW = "\033[93m" if USE_COLORS else ""
    BLUE = "\033[94m" if USE_COLORS else ""
    CYAN = "\033[96m" if USE_COLORS else ""
    RESET = "\033[0m" if USE_COLORS else ""
    BOLD = "\033[1m" if USE_COLORS else ""


def print_header(title: str):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}  {title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


def print_test(name: str, passed: bool, details: str = ""):
    """Print test result."""
    if passed:
        status = f"{Colors.GREEN}[PASS]{Colors.RESET}"
    else:
        status = f"{Colors.RED}[FAIL]{Colors.RESET}"
    print(f"  {status} {name}")
    if details and not passed:
        print(f"       {Colors.YELLOW}{details}{Colors.RESET}")


def print_info(message: str):
    """Print info message."""
    print(f"  {Colors.CYAN}ℹ {message}{Colors.RESET}")


def print_step(step: int, message: str):
    """Print step indicator."""
    print(f"\n{Colors.BOLD}[Step {step}]{Colors.RESET} {message}")


class Phase6Tester:
    """Automated tester for Phase 6 AI Guidance Engine."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.org_id: Optional[str] = None
        self.session_id: Optional[str] = None
        self.results: Dict[str, bool] = {}

    async def run_all_tests(self):
        """Run all Phase 6 tests."""
        print_header("Phase 6: AI Guidance Engine - Automated Tests")
        print(f"  Target: {self.base_url}")
        print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            self.client = client

            # Step 1: Health Checks
            print_step(1, "Health Checks")
            await self.test_health_checks()

            # Step 2: Authentication
            print_step(2, "Authentication")
            await self.test_authentication()

            if not self.access_token:
                print(f"\n{Colors.RED}Cannot proceed without authentication.{Colors.RESET}")
                return self.print_summary()

            # Step 3: Guidance Generation
            print_step(3, "Guidance Generation")
            await self.test_guidance_generation()

            if not self.session_id:
                print(f"\n{Colors.RED}Cannot proceed without a guidance session.{Colors.RESET}")
                return self.print_summary()

            # Step 4: Session Management
            print_step(4, "Session Management")
            await self.test_session_management()

            # Step 5: Step Navigation
            print_step(5, "Step Navigation")
            await self.test_step_navigation()

            # Step 6: Session Control
            print_step(6, "Session Control")
            await self.test_session_control()

            # Step 7: LLM Quality Tests
            print_step(7, "LLM Response Quality")
            await self.test_llm_quality()

            # Step 8: Database Persistence
            print_step(8, "Database Persistence")
            await self.test_database_persistence()

        return self.print_summary()

    async def test_health_checks(self):
        """Test all health endpoints."""
        # Basic health
        try:
            resp = await self.client.get(f"{self.base_url}/health")
            data = resp.json()
            passed = resp.status_code == 200 and data.get("status") == "healthy"
            self.results["health_basic"] = passed
            print_test("Basic health check", passed)
        except Exception as e:
            self.results["health_basic"] = False
            print_test("Basic health check", False, str(e))

        # Services health
        try:
            resp = await self.client.get(f"{self.base_url}/health/services")
            data = resp.json()
            passed = resp.status_code == 200
            self.results["health_services"] = passed
            print_test("Services health check", passed)
            if passed:
                for service, info in data.get("services", {}).items():
                    status = info.get("status", "unknown")
                    print_info(f"{service}: {status}")
        except Exception as e:
            self.results["health_services"] = False
            print_test("Services health check", False, str(e))

        # Guidance health
        try:
            resp = await self.client.get(f"{self.base_url}/guidance/health")
            data = resp.json()
            passed = resp.status_code == 200
            self.results["health_guidance"] = passed
            print_test("Guidance health check", passed)
            if passed:
                llm = data.get("llm", {})
                print_info(f"LLM Provider: {llm.get('provider', 'unknown')}")
                print_info(f"LLM Model: {llm.get('model', 'unknown')}")
                print_info(f"LLM Available: {llm.get('available', False)}")
        except Exception as e:
            self.results["health_guidance"] = False
            print_test("Guidance health check", False, str(e))

    async def test_authentication(self):
        """Test authentication flow."""
        # Try to register (might already exist)
        try:
            resp = await self.client.post(
                f"{self.base_url}/auth/register",
                json={
                    "email": TEST_USER_EMAIL,
                    "password": TEST_USER_PASSWORD,
                    "full_name": TEST_USER_NAME,
                }
            )
            if resp.status_code == 201:
                print_info("Created new test user")
            elif resp.status_code == 400:
                print_info("Test user already exists, will login")
        except Exception as e:
            print_info(f"Registration: {e}")

        # Login
        try:
            resp = await self.client.post(
                f"{self.base_url}/auth/login",
                json={
                    "email": TEST_USER_EMAIL,
                    "password": TEST_USER_PASSWORD,
                }
            )
            data = resp.json()

            if resp.status_code == 200:
                # Check for tokens - might be preliminary_token if no org
                tokens = data.get("tokens")
                if tokens:
                    self.access_token = tokens.get("access_token")
                    self.refresh_token = tokens.get("refresh_token")
                    # Get org_id from the login response (for org_admin users)
                    org_info = data.get("organisation")
                    if org_info:
                        self.org_id = org_info.get("org_id")
                else:
                    # User has no org, use preliminary token to set up org
                    preliminary_token = data.get("preliminary_token")
                    if preliminary_token:
                        print_info("User needs organisation setup")
                        await self._setup_organisation_with_token(preliminary_token)

                self.user_id = data.get("user", {}).get("user_id")
                passed = self.access_token is not None
                self.results["auth_login"] = passed
                print_test("Login", passed)
                if passed:
                    print_info(f"User ID: {self.user_id}")
                    if self.org_id:
                        print_info(f"Organisation ID: {self.org_id}")
            else:
                self.results["auth_login"] = False
                detail = data.get("detail", resp.text[:100])
                print_test("Login", False, f"Status {resp.status_code}: {detail}")
        except Exception as e:
            self.results["auth_login"] = False
            print_test("Login", False, str(e))

        # If we still don't have an org_id after login, something is wrong
        if self.access_token and not self.org_id:
            print_info("Warning: Logged in but no organisation ID obtained")

    async def _setup_organisation_with_token(self, preliminary_token: str):
        """Set up organisation for test user using preliminary token."""
        try:
            import uuid
            org_slug = f"phase6test{uuid.uuid4().hex[:6]}"
            resp = await self.client.post(
                f"{self.base_url}/org/onboard",
                headers={"Authorization": f"Bearer {preliminary_token}"},
                json={
                    "org_name": TEST_ORG_NAME,
                    "org_slug": org_slug,
                    "admin_email": TEST_USER_EMAIL,
                    "admin_password": TEST_USER_PASSWORD,
                    "admin_name": TEST_USER_NAME,
                }
            )
            if resp.status_code == 201:
                data = resp.json()
                self.org_id = data.get("org_id")
                print_info(f"Created organisation: {self.org_id}")

                # Re-login to get full access token
                resp = await self.client.post(
                    f"{self.base_url}/auth/login",
                    json={
                        "email": TEST_USER_EMAIL,
                        "password": TEST_USER_PASSWORD,
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    tokens = data.get("tokens")
                    if tokens:
                        self.access_token = tokens.get("access_token")
                        self.refresh_token = tokens.get("refresh_token")
                        print_info("Got access token after org setup")
            else:
                print_info(f"Org setup failed: {resp.status_code} - {resp.text[:100]}")
        except Exception as e:
            print_info(f"Failed to setup org: {e}")

    async def _setup_organisation(self):
        """Set up organisation for test user (legacy method)."""
        try:
            import uuid
            org_slug = f"phase6-test-{uuid.uuid4().hex[:8]}"
            resp = await self.client.post(
                f"{self.base_url}/org/onboard",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={
                    "org_name": TEST_ORG_NAME,
                    "org_slug": org_slug,
                    "org_type": "other",
                    "role": "admin",
                }
            )
            if resp.status_code == 201:
                data = resp.json()
                self.org_id = data.get("org_id")
                # Re-login to get updated token with org
                resp = await self.client.post(
                    f"{self.base_url}/auth/login",
                    json={
                        "email": TEST_USER_EMAIL,
                        "password": TEST_USER_PASSWORD,
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    tokens = data.get("tokens")
                    if tokens:
                        self.access_token = tokens.get("access_token")
                print_info(f"Created organisation: {self.org_id}")
        except Exception as e:
            print_info(f"Failed to setup org: {e}")

    async def test_guidance_generation(self):
        """Test guidance generation endpoint."""
        headers = {"Authorization": f"Bearer {self.access_token}"}

        # Simple query
        try:
            resp = await self.client.post(
                f"{self.base_url}/guidance/generate",
                headers=headers,
                json={
                    "query": "How do I save a file?",
                    "application_context": "Text Editor",
                },
                timeout=600.0  # LLM can be very slow on first request (5-10 minutes)
            )
            if resp.status_code == 200:
                data = resp.json()
                self.session_id = data.get("session_id")
                total_steps = data.get("total_steps", 0)
                passed = data.get("success", False) and total_steps > 0
                self.results["guidance_generate"] = passed
                print_test("Generate guidance", passed)
                if passed:
                    print_info(f"Session ID: {self.session_id}")
                    print_info(f"Total steps: {total_steps}")
                    print_info(f"Confidence: {data.get('overall_confidence', 0):.2f}")
                    # Show first step
                    steps = data.get("steps", [])
                    if steps:
                        print_info(f"Step 1: {steps[0].get('instruction', 'N/A')[:50]}...")
            else:
                self.results["guidance_generate"] = False
                error = resp.json().get("detail", resp.text[:100])
                print_test("Generate guidance", False, error)
        except Exception as e:
            self.results["guidance_generate"] = False
            print_test("Generate guidance", False, str(e))

    async def test_session_management(self):
        """Test session management endpoints."""
        headers = {"Authorization": f"Bearer {self.access_token}"}

        # List sessions
        try:
            resp = await self.client.get(
                f"{self.base_url}/guidance/sessions",
                headers=headers,
            )
            passed = resp.status_code == 200
            self.results["session_list"] = passed
            print_test("List sessions", passed)
            if passed:
                data = resp.json()
                print_info(f"Total sessions: {data.get('total', 0)}")
        except Exception as e:
            self.results["session_list"] = False
            print_test("List sessions", False, str(e))

        # Get session details
        try:
            resp = await self.client.get(
                f"{self.base_url}/guidance/sessions/{self.session_id}",
                headers=headers,
            )
            passed = resp.status_code == 200
            self.results["session_get"] = passed
            print_test("Get session details", passed)
        except Exception as e:
            self.results["session_get"] = False
            print_test("Get session details", False, str(e))

        # Get session state
        try:
            resp = await self.client.get(
                f"{self.base_url}/guidance/sessions/{self.session_id}/state",
                headers=headers,
            )
            passed = resp.status_code == 200
            self.results["session_state"] = passed
            print_test("Get session state", passed)
            if passed:
                data = resp.json()
                print_info(f"Current step: {data.get('current_step', 0)}/{data.get('total_steps', 0)}")
                print_info(f"Status: {data.get('status', 'unknown')}")
        except Exception as e:
            self.results["session_state"] = False
            print_test("Get session state", False, str(e))

    async def test_step_navigation(self):
        """Test step navigation endpoints."""
        headers = {"Authorization": f"Bearer {self.access_token}"}

        # Advance step
        try:
            resp = await self.client.post(
                f"{self.base_url}/guidance/sessions/{self.session_id}/advance",
                headers=headers,
            )
            passed = resp.status_code == 200
            self.results["step_advance"] = passed
            print_test("Advance step", passed)
            if passed:
                data = resp.json()
                print_info(f"Moved: step {data.get('previous_step')} → {data.get('current_step')}")
        except Exception as e:
            self.results["step_advance"] = False
            print_test("Advance step", False, str(e))

        # Go to specific step
        try:
            resp = await self.client.post(
                f"{self.base_url}/guidance/sessions/{self.session_id}/goto/1",
                headers=headers,
            )
            passed = resp.status_code == 200
            self.results["step_goto"] = passed
            print_test("Go to step", passed)
        except Exception as e:
            self.results["step_goto"] = False
            print_test("Go to step", False, str(e))

        # Skip step
        try:
            resp = await self.client.post(
                f"{self.base_url}/guidance/sessions/{self.session_id}/skip",
                headers=headers,
            )
            passed = resp.status_code == 200
            self.results["step_skip"] = passed
            print_test("Skip step", passed)
        except Exception as e:
            self.results["step_skip"] = False
            print_test("Skip step", False, str(e))

    async def test_session_control(self):
        """Test session control endpoints."""
        headers = {"Authorization": f"Bearer {self.access_token}"}

        # Pause session
        try:
            resp = await self.client.post(
                f"{self.base_url}/guidance/sessions/{self.session_id}/pause",
                headers=headers,
            )
            passed = resp.status_code == 200
            self.results["session_pause"] = passed
            print_test("Pause session", passed)
        except Exception as e:
            self.results["session_pause"] = False
            print_test("Pause session", False, str(e))

        # Resume session
        try:
            resp = await self.client.post(
                f"{self.base_url}/guidance/sessions/{self.session_id}/resume",
                headers=headers,
            )
            passed = resp.status_code == 200
            self.results["session_resume"] = passed
            print_test("Resume session", passed)
        except Exception as e:
            self.results["session_resume"] = False
            print_test("Resume session", False, str(e))

        # Create another session for abandon test
        try:
            resp = await self.client.post(
                f"{self.base_url}/guidance/generate",
                headers=headers,
                json={"query": "Test query for abandon"},
                timeout=600.0  # LLM can be slow
            )
            if resp.status_code == 200:
                abandon_session_id = resp.json().get("session_id")
                # Abandon it
                resp = await self.client.post(
                    f"{self.base_url}/guidance/sessions/{abandon_session_id}/abandon",
                    headers=headers,
                )
                passed = resp.status_code == 200
                self.results["session_abandon"] = passed
                print_test("Abandon session", passed)
            else:
                self.results["session_abandon"] = False
                print_test("Abandon session", False, "Failed to create test session")
        except Exception as e:
            self.results["session_abandon"] = False
            print_test("Abandon session", False, str(e))

    async def test_llm_quality(self):
        """Test LLM response quality with different queries."""
        headers = {"Authorization": f"Bearer {self.access_token}"}

        test_queries = [
            {
                "query": "How do I copy and paste text?",
                "context": "Windows",
                "expected_min_steps": 2,
            },
            {
                "query": "How to create a new folder?",
                "context": "File Explorer",
                "expected_min_steps": 2,
            },
        ]

        for i, test in enumerate(test_queries):
            try:
                resp = await self.client.post(
                    f"{self.base_url}/guidance/generate",
                    headers=headers,
                    json={
                        "query": test["query"],
                        "application_context": test["context"],
                    },
                    timeout=600.0  # LLM can be slow
                )
                if resp.status_code == 200:
                    data = resp.json()
                    steps = data.get("steps", [])
                    passed = (
                        len(steps) >= test["expected_min_steps"] and
                        all(s.get("instruction") for s in steps)
                    )
                    self.results[f"llm_quality_{i+1}"] = passed
                    print_test(f"Query: '{test['query'][:30]}...'", passed)
                    if passed:
                        print_info(f"Generated {len(steps)} steps")
                else:
                    self.results[f"llm_quality_{i+1}"] = False
                    print_test(f"Query: '{test['query'][:30]}...'", False)
            except Exception as e:
                self.results[f"llm_quality_{i+1}"] = False
                print_test(f"Query: '{test['query'][:30]}...'", False, str(e))

    async def test_database_persistence(self):
        """Test database persistence."""
        headers = {"Authorization": f"Bearer {self.access_token}"}

        # Verify session exists in list
        try:
            resp = await self.client.get(
                f"{self.base_url}/guidance/sessions",
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                sessions = data.get("sessions", [])
                found = any(s.get("session_id") == self.session_id for s in sessions)
                self.results["db_persistence"] = found
                print_test("Session persisted in database", found)
                if found:
                    print_info(f"Found session {self.session_id[:8]}... in database")
            else:
                self.results["db_persistence"] = False
                print_test("Session persisted in database", False)
        except Exception as e:
            self.results["db_persistence"] = False
            print_test("Session persisted in database", False, str(e))

    def print_summary(self) -> bool:
        """Print test summary and return overall success."""
        print_header("Test Summary")

        total = len(self.results)
        passed = sum(1 for v in self.results.values() if v)
        failed = total - passed

        print(f"  Total Tests: {total}")
        print(f"  {Colors.GREEN}Passed: {passed}{Colors.RESET}")
        print(f"  {Colors.RED}Failed: {failed}{Colors.RESET}")

        if failed > 0:
            print(f"\n  {Colors.YELLOW}Failed Tests:{Colors.RESET}")
            for name, result in self.results.items():
                if not result:
                    print(f"    - {name}")

        success_rate = (passed / total * 100) if total > 0 else 0
        print(f"\n  Success Rate: {success_rate:.1f}%")

        if success_rate == 100:
            print(f"\n  {Colors.GREEN}{Colors.BOLD}*** All tests passed! ***{Colors.RESET}")
        elif success_rate >= 80:
            print(f"\n  {Colors.YELLOW}[!] Most tests passed, some issues to fix.{Colors.RESET}")
        else:
            print(f"\n  {Colors.RED}[X] Multiple failures detected.{Colors.RESET}")

        return failed == 0


async def main():
    """Main entry point."""
    print(f"\n{Colors.BOLD}Phase 6: AI Guidance Engine - Test Suite{Colors.RESET}")
    print(f"{'='*50}\n")

    # Check if server is running
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BASE_URL}/health")
            if resp.status_code != 200:
                print(f"{Colors.RED}Error: Backend server not responding properly{Colors.RESET}")
                print(f"Make sure the server is running: ./venv/Scripts/python.exe -m uvicorn app.main:app")
                sys.exit(1)
    except Exception as e:
        print(f"{Colors.RED}Error: Cannot connect to backend at {BASE_URL}{Colors.RESET}")
        print(f"Make sure the server is running: ./venv/Scripts/python.exe -m uvicorn app.main:app")
        print(f"Error: {e}")
        sys.exit(1)

    tester = Phase6Tester()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
