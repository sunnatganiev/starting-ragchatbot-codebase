"""
Shared pytest fixtures for RAG chatbot tests.
"""

from dataclasses import dataclass
from unittest.mock import Mock

import pytest


@dataclass
class MockConfig:
    """Test configuration matching the real Config structure."""

    OPENAI_API_KEY: str = "test-api-key"
    OPENAI_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    MAX_RESULTS: int = 5
    MAX_HISTORY: int = 2
    CHROMA_PATH: str = "./test_chroma_db"


@pytest.fixture
def mock_config():
    """Standard test configuration with valid values."""
    return MockConfig()


@pytest.fixture
def mock_empty_config():
    """Configuration with empty API key (simulates missing .env)."""
    return MockConfig(OPENAI_API_KEY="")


@pytest.fixture
def mock_vector_store():
    """Mock VectorStore with successful search results."""
    store = Mock()

    # Configure search to return valid results
    mock_results = Mock()
    mock_results.error = None
    mock_results.documents = ["Content about prompt caching..."]
    mock_results.metadata = [{"course_title": "Test Course", "lesson_number": 1}]
    mock_results.is_empty.return_value = False

    store.search.return_value = mock_results
    store.get_lesson_link.return_value = "https://example.com/lesson1"
    store._resolve_course_name.return_value = "Test Course"

    return store


@pytest.fixture
def mock_vector_store_empty():
    """Mock VectorStore that returns empty results."""
    store = Mock()

    mock_results = Mock()
    mock_results.error = None
    mock_results.documents = []
    mock_results.metadata = []
    mock_results.is_empty.return_value = True

    store.search.return_value = mock_results

    return store


@pytest.fixture
def mock_vector_store_error():
    """Mock VectorStore that returns an error."""
    store = Mock()

    mock_results = Mock()
    mock_results.error = "Search error: Connection failed"
    mock_results.documents = []
    mock_results.metadata = []

    store.search.return_value = mock_results

    return store


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client with successful responses (no tool calls)."""
    client = Mock()

    # Successful completion response
    mock_message = Mock()
    mock_message.content = "Test response"
    mock_message.tool_calls = None

    mock_choice = Mock()
    mock_choice.message = mock_message
    mock_choice.finish_reason = "stop"

    mock_response = Mock()
    mock_response.choices = [mock_choice]

    client.chat.completions.create.return_value = mock_response

    return client


@pytest.fixture
def mock_openai_client_with_tool_call():
    """Mock OpenAI client that returns a tool call then final response."""
    client = Mock()

    # First call: returns tool call request
    mock_tool_call = Mock()
    mock_tool_call.id = "call_abc123"
    mock_tool_call.type = "function"
    mock_tool_call.function.name = "search_course_content"
    mock_tool_call.function.arguments = '{"query": "prompt caching"}'

    mock_message_with_tool = Mock()
    mock_message_with_tool.content = None
    mock_message_with_tool.tool_calls = [mock_tool_call]

    mock_choice_tool = Mock()
    mock_choice_tool.message = mock_message_with_tool
    mock_choice_tool.finish_reason = "tool_calls"

    mock_response_tool = Mock()
    mock_response_tool.choices = [mock_choice_tool]

    # Second call: returns final response after tool execution
    mock_message_final = Mock()
    mock_message_final.content = "Prompt caching is a technique..."
    mock_message_final.tool_calls = None

    mock_choice_final = Mock()
    mock_choice_final.message = mock_message_final
    mock_choice_final.finish_reason = "stop"

    mock_response_final = Mock()
    mock_response_final.choices = [mock_choice_final]

    # Return different responses on consecutive calls
    client.chat.completions.create.side_effect = [
        mock_response_tool,
        mock_response_final,
    ]

    return client


@pytest.fixture
def mock_openai_client_error():
    """Mock OpenAI client that raises an error."""
    client = Mock()
    client.chat.completions.create.side_effect = Exception("API Error: Invalid request")
    return client


@pytest.fixture
def mock_openai_client_two_tool_rounds():
    """Mock OpenAI client simulating 2 sequential tool calling rounds."""
    client = Mock()

    # Round 1: First tool call
    mock_tool_call_1 = Mock()
    mock_tool_call_1.id = "call_round1"
    mock_tool_call_1.type = "function"
    mock_tool_call_1.function.name = "search_course_content"
    mock_tool_call_1.function.arguments = '{"query": "prompt caching"}'

    mock_msg1 = Mock()
    mock_msg1.content = None
    mock_msg1.tool_calls = [mock_tool_call_1]
    mock_resp1 = Mock()
    mock_resp1.choices = [Mock(message=mock_msg1, finish_reason="tool_calls")]

    # Round 2: Second tool call after seeing round 1 results
    mock_tool_call_2 = Mock()
    mock_tool_call_2.id = "call_round2"
    mock_tool_call_2.type = "function"
    mock_tool_call_2.function.name = "search_course_content"
    mock_tool_call_2.function.arguments = (
        '{"query": "lesson 3 prompt caching", "lesson_number": 3}'
    )

    mock_msg2 = Mock()
    mock_msg2.content = None
    mock_msg2.tool_calls = [mock_tool_call_2]
    mock_resp2 = Mock()
    mock_resp2.choices = [Mock(message=mock_msg2, finish_reason="tool_calls")]

    # Final response after 2 rounds
    mock_msg3 = Mock()
    mock_msg3.content = "Based on both searches, prompt caching allows..."
    mock_msg3.tool_calls = None
    mock_resp3 = Mock()
    mock_resp3.choices = [Mock(message=mock_msg3, finish_reason="stop")]

    client.chat.completions.create.side_effect = [mock_resp1, mock_resp2, mock_resp3]
    return client


@pytest.fixture
def mock_openai_client_max_rounds_reached():
    """Mock OpenAI client that hits MAX_TOOL_ROUNDS limit."""
    client = Mock()

    # Round 1: Tool call
    mock_tool_call_1 = Mock()
    mock_tool_call_1.id = "call_round1"
    mock_tool_call_1.type = "function"
    mock_tool_call_1.function.name = "search_course_content"
    mock_tool_call_1.function.arguments = '{"query": "search 1"}'

    mock_msg1 = Mock()
    mock_msg1.content = None
    mock_msg1.tool_calls = [mock_tool_call_1]
    mock_resp1 = Mock()
    mock_resp1.choices = [Mock(message=mock_msg1, finish_reason="tool_calls")]

    # Round 2: Another tool call
    mock_tool_call_2 = Mock()
    mock_tool_call_2.id = "call_round2"
    mock_tool_call_2.type = "function"
    mock_tool_call_2.function.name = "search_course_content"
    mock_tool_call_2.function.arguments = '{"query": "search 2"}'

    mock_msg2 = Mock()
    mock_msg2.content = None
    mock_msg2.tool_calls = [mock_tool_call_2]
    mock_resp2 = Mock()
    mock_resp2.choices = [Mock(message=mock_msg2, finish_reason="tool_calls")]

    # Final call made without tools (max rounds reached)
    mock_msg3 = Mock()
    mock_msg3.content = "Synthesized answer from all tool results"
    mock_msg3.tool_calls = None
    mock_resp3 = Mock()
    mock_resp3.choices = [Mock(message=mock_msg3, finish_reason="stop")]

    client.chat.completions.create.side_effect = [mock_resp1, mock_resp2, mock_resp3]
    return client


# API Testing Fixtures

@pytest.fixture
def mock_rag_system_for_api():
    """Mock RAG system specifically for API tests."""
    rag = Mock()

    # Mock query method to return answer and sources
    rag.query.return_value = (
        "Test answer about prompt caching",
        [{"label": "Test Course - Lesson 1", "link": "https://example.com/lesson1"}]
    )

    # Mock get_course_analytics method
    rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Course 1", "Course 2"]
    }

    # Mock session manager
    rag.session_manager = Mock()
    rag.session_manager.create_session.return_value = "session_123"

    return rag


@pytest.fixture
def test_app(mock_rag_system_for_api):
    """Create a test FastAPI app without static files mounting."""
    from fastapi import FastAPI, HTTPException

    # Import Pydantic models from app.py
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from app import QueryRequest, QueryResponse, CourseStats, Source

    app = FastAPI()
    test_rag = mock_rag_system_for_api

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        """Test endpoint for query processing."""
        try:
            session_id = request.session_id
            if not session_id:
                session_id = test_rag.session_manager.create_session()

            answer, sources = test_rag.query(request.query, session_id)

            # Convert sources to Source objects if they're dicts
            if sources and isinstance(sources[0], dict):
                sources = [Source(**source) for source in sources]

            return QueryResponse(
                answer=answer,
                sources=sources,
                session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        """Test endpoint for course statistics."""
        try:
            analytics = test_rag.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


@pytest.fixture
def test_client(test_app):
    """Create FastAPI test client from test app."""
    from fastapi.testclient import TestClient
    return TestClient(test_app)
