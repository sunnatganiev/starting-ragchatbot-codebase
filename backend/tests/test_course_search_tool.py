"""
Unit tests for CourseSearchTool.execute() method.
Tests the search tool's ability to handle various scenarios.
"""
import pytest
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from search_tools import CourseSearchTool


class TestCourseSearchToolExecute:
    """Tests for CourseSearchTool.execute() method."""

    def test_execute_with_valid_query(self, mock_vector_store):
        """Search returns results successfully with valid query."""
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="prompt caching")

        mock_vector_store.search.assert_called_once_with(
            query="prompt caching",
            course_name=None,
            lesson_number=None
        )
        assert "[Test Course - Lesson 1]" in result
        assert "Content about prompt caching" in result

    def test_execute_with_course_filter(self, mock_vector_store):
        """Filter by course name works correctly."""
        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="test", course_name="MCP")

        mock_vector_store.search.assert_called_with(
            query="test",
            course_name="MCP",
            lesson_number=None
        )

    def test_execute_with_lesson_filter(self, mock_vector_store):
        """Filter by lesson number works correctly."""
        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="test", lesson_number=3)

        mock_vector_store.search.assert_called_with(
            query="test",
            course_name=None,
            lesson_number=3
        )

    def test_execute_with_all_filters(self, mock_vector_store):
        """Filter by both course name and lesson number works."""
        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="caching", course_name="MCP Course", lesson_number=5)

        mock_vector_store.search.assert_called_with(
            query="caching",
            course_name="MCP Course",
            lesson_number=5
        )

    def test_execute_with_empty_results(self, mock_vector_store_empty):
        """Returns proper message when no results found."""
        tool = CourseSearchTool(mock_vector_store_empty)
        result = tool.execute(query="nonexistent topic")

        assert "No relevant content found" in result

    def test_execute_with_search_error(self, mock_vector_store_error):
        """Handles search errors gracefully by returning error message."""
        tool = CourseSearchTool(mock_vector_store_error)
        result = tool.execute(query="test")

        assert "Search error:" in result
        assert "Connection failed" in result

    def test_execute_missing_query_raises_error(self, mock_vector_store):
        """
        CRITICAL TEST: Missing query parameter raises TypeError.
        This simulates what happens when JSON parsing fails in ai_generator
        and the tool is called with empty kwargs {}.
        """
        tool = CourseSearchTool(mock_vector_store)

        with pytest.raises(TypeError) as exc_info:
            tool.execute()  # No query - simulates JSON parse failure fallback

        assert "query" in str(exc_info.value).lower()

    def test_sources_tracked_after_search(self, mock_vector_store):
        """Sources are stored in last_sources for UI retrieval."""
        tool = CourseSearchTool(mock_vector_store)
        tool.last_sources = []  # Reset

        tool.execute(query="test")

        assert len(tool.last_sources) == 1
        assert tool.last_sources[0]["label"] == "Test Course - Lesson 1"
        assert tool.last_sources[0]["link"] == "https://example.com/lesson1"

    def test_sources_include_link_from_vector_store(self, mock_vector_store):
        """Lesson links are retrieved from vector store."""
        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="test")

        # Verify get_lesson_link was called
        mock_vector_store.get_lesson_link.assert_called_with("Test Course", 1)

    def test_format_results_header_format(self, mock_vector_store):
        """Verify the formatted result contains proper headers."""
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="test")

        # Should contain header in format [Course Title - Lesson N]
        assert "[Test Course - Lesson 1]" in result

    def test_tool_definition_format(self, mock_vector_store):
        """Verify tool definition matches OpenAI function calling format."""
        tool = CourseSearchTool(mock_vector_store)
        definition = tool.get_tool_definition()

        assert definition["type"] == "function"
        assert definition["function"]["name"] == "search_course_content"
        assert "parameters" in definition["function"]
        assert "query" in definition["function"]["parameters"]["properties"]
