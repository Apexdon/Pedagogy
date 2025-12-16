"""
Quick test script for Phase 3 RAG System

Run with: python test_rag.py
"""

import httpx
import asyncio
from pathlib import Path

BASE_URL = "http://localhost:8000"


async def test_rag_system():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=180.0) as client:

        # ============================================
        # Step 1: Register or Login
        # ============================================
        print("\n=== Step 1: Authentication ===")

        # Try to register (will fail if user exists, that's ok)
        register_response = await client.post("/auth/register", json={
            "email": "ragtest@example.com",
            "password": "testpass123",
            "full_name": "RAG Tester"
        })
        print(f"Register: {register_response.status_code}")

        # Create organisation (will fail if exists, that's ok)
        org_response = await client.post("/org/onboard", json={
            "org_name": "RAG Test Org",
            "org_slug": "rag-test-org",
            "admin_email": "ragtest@example.com",
            "admin_password": "testpass123",
            "admin_name": "RAG Tester"
        })
        print(f"Create Org: {org_response.status_code}")

        # Login
        login_response = await client.post("/auth/login", json={
            "email": "ragtest@example.com",
            "password": "testpass123"
        })
        print(f"Login: {login_response.status_code}")

        if login_response.status_code != 200:
            print(f"Login failed: {login_response.text}")
            return

        login_data = login_response.json()
        preliminary_token = login_data.get("preliminary_token")
        organisations = login_data.get("organisations", [])

        if not organisations:
            print("No organisations found for user")
            return

        org_id = organisations[0]["org_id"]
        print(f"Organisation ID: {org_id}")

        # Select organisation
        select_response = await client.post(
            "/auth/select-organisation",
            json={"org_id": org_id},
            headers={"Authorization": f"Bearer {preliminary_token}"}
        )
        print(f"Select Org: {select_response.status_code}")

        if select_response.status_code != 200:
            print(f"Select org failed: {select_response.text}")
            return

        tokens = select_response.json().get("tokens", {})
        access_token = tokens.get("access_token")

        if not access_token:
            print("No access token received")
            return

        auth_headers = {"Authorization": f"Bearer {access_token}"}
        print("Authentication successful!")

        # ============================================
        # Step 2: Create Knowledge Base
        # ============================================
        print("\n=== Step 2: Create Knowledge Base ===")

        kb_response = await client.post(
            "/org/knowledge-bases",
            json={
                "kb_name": "Test Knowledge Base",
                "description": "A test KB for RAG system"
            },
            headers=auth_headers
        )
        print(f"Create KB: {kb_response.status_code}")

        if kb_response.status_code not in [200, 201]:
            print(f"Create KB failed: {kb_response.text}")
            return

        kb_data = kb_response.json()
        kb_id = kb_data.get("kb_id")
        print(f"Knowledge Base ID: {kb_id}")

        # ============================================
        # Step 3: Upload a Test Document
        # ============================================
        print("\n=== Step 3: Upload Document ===")

        # Create a test markdown document
        test_doc_content = """# Invoice Submission Guide

## Step 1: Access the Invoice Portal
Navigate to the Finance section in the main menu and click on "Submit Invoice".

## Step 2: Fill in Invoice Details
1. Enter the invoice number in the "Invoice #" field
2. Select the vendor from the dropdown menu
3. Enter the invoice date and due date
4. Add line items with descriptions and amounts

## Step 3: Attach Supporting Documents
Click the "Attach Files" button to upload:
- Original invoice PDF
- Purchase order (if applicable)
- Delivery receipt

## Step 4: Review and Submit
1. Review all entered information
2. Click "Calculate Totals" to verify amounts
3. Click "Submit for Approval" button
4. You will receive a confirmation email

## Common Issues
- If the vendor is not in the list, contact Procurement
- For invoices over $10,000, additional approval is required
- Late invoices may incur penalties
"""

        test_doc_path = Path("test_document.md")
        test_doc_path.write_text(test_doc_content)

        # Upload the document
        with open(test_doc_path, "rb") as f:
            files = {"files": ("test_document.md", f, "text/markdown")}
            data = {
                "kb_id": kb_id,
                "chunk_size": "300",
                "chunk_overlap": "50"
            }
            upload_response = await client.post(
                "/org/upload-knowledge",
                files=files,
                data=data,
                headers=auth_headers
            )

        print(f"Upload: {upload_response.status_code}")

        if upload_response.status_code != 200:
            print(f"Upload failed: {upload_response.text}")
        else:
            upload_data = upload_response.json()
            print(f"Documents processed: {len(upload_data.get('documents_processed', []))}")
            print(f"Total chunks: {upload_data.get('total_chunks', 0)}")
            print(f"Processing time: {upload_data.get('processing_time_sec', 0)}s")

        # Clean up test file
        test_doc_path.unlink()

        # ============================================
        # Step 4: Query the Knowledge Base
        # ============================================
        print("\n=== Step 4: RAG Query ===")

        queries = [
            "How do I submit an invoice?",
            "What documents do I need to attach?",
            "What happens for invoices over $10,000?"
        ]

        for query in queries:
            print(f"\nQuery: '{query}'")

            query_response = await client.post(
                "/org/query/rag",
                json={
                    "query": query,
                    "kb_id": kb_id,
                    "top_k": 3,
                    "min_similarity": 0.3
                },
                headers=auth_headers
            )

            if query_response.status_code == 200:
                result = query_response.json()
                print(f"  Results: {result.get('total_results', 0)}")
                print(f"  Search time: {result.get('search_time_ms', 0)}ms")

                for i, chunk in enumerate(result.get("results", [])[:2]):
                    print(f"  [{i+1}] Similarity: {chunk.get('similarity', 0):.3f}")
                    text_preview = chunk.get("chunk_text", "")[:100].replace("\n", " ")
                    print(f"      Text: {text_preview}...")
            else:
                print(f"  Query failed: {query_response.text}")

        # ============================================
        # Step 5: List Knowledge Bases
        # ============================================
        print("\n=== Step 5: List Knowledge Bases ===")

        list_response = await client.get(
            "/org/knowledge-bases",
            headers=auth_headers
        )

        if list_response.status_code == 200:
            kbs = list_response.json()
            print(f"Total KBs: {kbs.get('total_count', 0)}")
            for kb in kbs.get("knowledge_bases", []):
                print(f"  - {kb.get('kb_name')}: {kb.get('document_count', 0)} docs, {kb.get('total_chunks', 0)} chunks")

        print("\n=== Test Complete ===")


if __name__ == "__main__":
    print("RAG System Test Script")
    print("=" * 50)
    print("Make sure the server is running: uvicorn app.main:app --reload")
    print("=" * 50)

    asyncio.run(test_rag_system())
