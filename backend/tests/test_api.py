"""
API endpoint tests for the RAG system.
Tests FastAPI endpoints using TestClient.
"""
import pytest
from unittest.mock import Mock


@pytest.mark.api
class TestQueryEndpoint:
    """Tests for POST /api/query endpoint."""

    def test_query_endpoint_success(self, test_client):
        """Valid query returns 200 with answer, sources, and session_id."""
        response = test_client.post("/api/query", json={
            "query": "What is prompt caching?",
            "session_id": None
        })

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data

        # Verify data types
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["session_id"], str)

    def test_query_endpoint_creates_session(self, test_client, mock_rag_system_for_api):
        """Query without session_id creates new session."""
        response = test_client.post("/api/query", json={
            "query": "test query"
        })

        assert response.status_code == 200
        data = response.json()

        # Verify session was created
        assert data["session_id"] is not None
        mock_rag_system_for_api.session_manager.create_session.assert_called_once()

    def test_query_endpoint_uses_existing_session(self, test_client, mock_rag_system_for_api):
        """Query with session_id reuses existing session."""
        existing_session = "existing_session_123"

        response = test_client.post("/api/query", json={
            "query": "follow up question",
            "session_id": existing_session
        })

        assert response.status_code == 200
        data = response.json()

        # Verify query was called with existing session
        mock_rag_system_for_api.query.assert_called_once_with(
            "follow up question",
            existing_session
        )

        # Verify create_session was NOT called (session already exists)
        mock_rag_system_for_api.session_manager.create_session.assert_not_called()

    def test_query_endpoint_handles_rag_error(self, test_client, mock_rag_system_for_api):
        """RAG system errors return 500 with error message."""
        # Configure mock to raise exception
        mock_rag_system_for_api.query.side_effect = Exception("OpenAI API error")

        response = test_client.post("/api/query", json={
            "query": "test query"
        })

        assert response.status_code == 500
        data = response.json()

        # Verify error details are included
        assert "detail" in data
        assert "OpenAI API error" in data["detail"]

    def test_query_endpoint_returns_proper_source_format(self, test_client):
        """Sources follow Source model schema with label and optional link."""
        response = test_client.post("/api/query", json={
            "query": "What is prompt caching?"
        })

        assert response.status_code == 200
        data = response.json()

        # Verify sources structure
        assert isinstance(data["sources"], list)
        if len(data["sources"]) > 0:
            source = data["sources"][0]
            assert "label" in source
            # link is optional, so just check if present it's a string
            if "link" in source:
                assert source["link"] is None or isinstance(source["link"], str)


@pytest.mark.api
class TestCoursesEndpoint:
    """Tests for GET /api/courses endpoint."""

    def test_courses_endpoint_success(self, test_client):
        """Returns course statistics with 200 status."""
        response = test_client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "total_courses" in data
        assert "course_titles" in data

        # Verify data types
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)

        # Verify expected values from mock
        assert data["total_courses"] == 2
        assert len(data["course_titles"]) == 2
        assert "Course 1" in data["course_titles"]
        assert "Course 2" in data["course_titles"]

    def test_courses_endpoint_empty_state(self, test_client, mock_rag_system_for_api):
        """Returns empty list when no courses loaded."""
        # Configure mock to return empty state
        mock_rag_system_for_api.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }

        response = test_client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_courses_endpoint_handles_error(self, test_client, mock_rag_system_for_api):
        """Analytics errors return 500."""
        # Configure mock to raise exception
        mock_rag_system_for_api.get_course_analytics.side_effect = Exception(
            "Vector store connection error"
        )

        response = test_client.get("/api/courses")

        assert response.status_code == 500
        data = response.json()

        # Verify error details are included
        assert "detail" in data
        assert "Vector store connection error" in data["detail"]


@pytest.mark.api
class TestRequestValidation:
    """Tests for request validation using Pydantic models."""

    def test_query_request_missing_query_field(self, test_client):
        """Missing required 'query' field returns 422 validation error."""
        response = test_client.post("/api/query", json={
            "session_id": "test_session"
            # Missing "query" field
        })

        assert response.status_code == 422
        data = response.json()

        # FastAPI returns validation error details
        assert "detail" in data

    def test_query_request_optional_session_id(self, test_client):
        """session_id=null is valid (optional field)."""
        response = test_client.post("/api/query", json={
            "query": "test query",
            "session_id": None
        })

        assert response.status_code == 200

    def test_query_request_omitted_session_id(self, test_client):
        """Omitted session_id is valid (optional field)."""
        response = test_client.post("/api/query", json={
            "query": "test query"
            # session_id omitted entirely
        })

        assert response.status_code == 200

    def test_response_models_match_schema(self, test_client):
        """Response data matches Pydantic model structure."""
        # Test QueryResponse schema
        response = test_client.post("/api/query", json={
            "query": "test"
        })
        assert response.status_code == 200
        query_data = response.json()

        # Verify all required fields are present
        required_fields = ["answer", "sources", "session_id"]
        for field in required_fields:
            assert field in query_data, f"Missing required field: {field}"

        # Test CourseStats schema
        response = test_client.get("/api/courses")
        assert response.status_code == 200
        courses_data = response.json()

        # Verify all required fields are present
        required_fields = ["total_courses", "course_titles"]
        for field in required_fields:
            assert field in courses_data, f"Missing required field: {field}"

    def test_invalid_json_body(self, test_client):
        """Invalid JSON in request body returns 422."""
        response = test_client.post(
            "/api/query",
            data="invalid json {{{",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422
