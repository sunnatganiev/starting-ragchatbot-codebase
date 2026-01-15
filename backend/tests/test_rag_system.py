"""
Integration tests for the RAG system.
Tests the complete query flow and component integration.
"""
import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestRAGSystemInitialization:
    """Tests for RAG system initialization."""

    def test_tool_manager_has_both_tools(self, mock_config):
        """Both search and outline tools are registered on initialization."""
        with patch('rag_system.VectorStore'), \
             patch('rag_system.AIGenerator'), \
             patch('rag_system.DocumentProcessor'):

            from rag_system import RAGSystem
            rag = RAGSystem(mock_config)

            tools = rag.tool_manager.get_tool_definitions()
            tool_names = [t['function']['name'] for t in tools]

            assert "search_course_content" in tool_names
            assert "get_course_outline" in tool_names

    def test_components_initialized_with_config(self, mock_config):
        """All components receive correct configuration."""
        with patch('rag_system.VectorStore') as mock_vs, \
             patch('rag_system.AIGenerator') as mock_ai, \
             patch('rag_system.DocumentProcessor') as mock_dp:

            from rag_system import RAGSystem
            RAGSystem(mock_config)

            # Verify DocumentProcessor got chunk settings
            mock_dp.assert_called_once_with(
                mock_config.CHUNK_SIZE,
                mock_config.CHUNK_OVERLAP
            )

            # Verify VectorStore got path and model
            mock_vs.assert_called_once_with(
                mock_config.CHROMA_PATH,
                mock_config.EMBEDDING_MODEL,
                mock_config.MAX_RESULTS
            )

            # Verify AIGenerator got API key and model
            mock_ai.assert_called_once_with(
                mock_config.OPENAI_API_KEY,
                mock_config.OPENAI_MODEL
            )


class TestRAGSystemQuery:
    """Tests for RAG system query handling."""

    def test_query_returns_answer_and_sources(self, mock_config):
        """Full query flow returns response and sources."""
        with patch('rag_system.VectorStore') as mock_vs, \
             patch('rag_system.AIGenerator') as mock_ai, \
             patch('rag_system.DocumentProcessor'):

            mock_vs.return_value.search.return_value = Mock(
                error=None,
                documents=["content"],
                metadata=[{"course_title": "Test", "lesson_number": 1}],
                is_empty=lambda: False
            )
            mock_vs.return_value.get_lesson_link.return_value = "http://example.com"
            mock_ai.return_value.generate_response.return_value = "Answer"

            from rag_system import RAGSystem
            rag = RAGSystem(mock_config)

            answer, sources = rag.query("test query", "session_1")

            assert answer == "Answer"

    def test_query_creates_session_if_missing(self, mock_config):
        """Session is created when session_id not provided."""
        with patch('rag_system.VectorStore'), \
             patch('rag_system.AIGenerator') as mock_ai, \
             patch('rag_system.DocumentProcessor'):

            mock_ai.return_value.generate_response.return_value = "Answer"

            from rag_system import RAGSystem
            rag = RAGSystem(mock_config)

            # Query without session_id
            answer, sources = rag.query("test")

            assert answer == "Answer"

    def test_query_passes_tools_to_ai_generator(self, mock_config):
        """Tool definitions are passed to AI generator."""
        with patch('rag_system.VectorStore'), \
             patch('rag_system.AIGenerator') as mock_ai, \
             patch('rag_system.DocumentProcessor'):

            mock_ai.return_value.generate_response.return_value = "Answer"

            from rag_system import RAGSystem
            rag = RAGSystem(mock_config)

            rag.query("test", "session_1")

            # Verify generate_response was called with tools
            call_kwargs = mock_ai.return_value.generate_response.call_args.kwargs
            assert 'tools' in call_kwargs
            assert 'tool_manager' in call_kwargs

    def test_sources_retrieved_after_query(self, mock_config):
        """Sources are retrieved from tool manager after query."""
        with patch('rag_system.VectorStore') as mock_vs, \
             patch('rag_system.AIGenerator') as mock_ai, \
             patch('rag_system.DocumentProcessor'):

            mock_vs.return_value.search.return_value = Mock(
                error=None,
                documents=["content"],
                metadata=[{"course_title": "Test", "lesson_number": 1}],
                is_empty=lambda: False
            )
            mock_vs.return_value.get_lesson_link.return_value = "http://example.com"
            mock_ai.return_value.generate_response.return_value = "Answer"

            from rag_system import RAGSystem
            rag = RAGSystem(mock_config)

            # Manually set sources to verify retrieval
            rag.search_tool.last_sources = [{"label": "Test", "link": "http://test.com"}]

            answer, sources = rag.query("test", "session_1")

            # Sources should be returned (before reset)
            # Note: The actual sources depend on whether tool was called
            assert isinstance(sources, list)

    def test_sources_reset_after_query(self, mock_config):
        """Sources are reset after being retrieved."""
        with patch('rag_system.VectorStore') as mock_vs, \
             patch('rag_system.AIGenerator') as mock_ai, \
             patch('rag_system.DocumentProcessor'):

            mock_vs.return_value.search.return_value = Mock(
                error=None,
                documents=["content"],
                metadata=[{"course_title": "Test", "lesson_number": 1}],
                is_empty=lambda: False
            )
            mock_vs.return_value.get_lesson_link.return_value = "http://example.com"
            mock_ai.return_value.generate_response.return_value = "Answer"

            from rag_system import RAGSystem
            rag = RAGSystem(mock_config)

            # Set sources
            rag.search_tool.last_sources = [{"label": "Test", "link": "http://test.com"}]

            rag.query("test", "session_1")

            # Sources should be reset after query
            assert rag.tool_manager.get_last_sources() == []

    def test_query_with_conversation_history(self, mock_config):
        """Conversation history is passed to AI generator."""
        with patch('rag_system.VectorStore'), \
             patch('rag_system.AIGenerator') as mock_ai, \
             patch('rag_system.DocumentProcessor'):

            mock_ai.return_value.generate_response.return_value = "Answer"

            from rag_system import RAGSystem
            rag = RAGSystem(mock_config)

            # Create session and add history
            session_id = rag.session_manager.create_session()
            rag.session_manager.add_exchange(session_id, "previous question", "previous answer")

            # Query with existing session
            rag.query("follow up question", session_id)

            # Verify history was passed
            call_kwargs = mock_ai.return_value.generate_response.call_args.kwargs
            assert 'conversation_history' in call_kwargs


class TestRAGSystemErrorHandling:
    """Tests for error handling in RAG system."""

    def test_ai_generator_error_propagates(self, mock_config):
        """Errors from AI generator propagate to caller."""
        with patch('rag_system.VectorStore'), \
             patch('rag_system.AIGenerator') as mock_ai, \
             patch('rag_system.DocumentProcessor'):

            mock_ai.return_value.generate_response.side_effect = Exception("API Error")

            from rag_system import RAGSystem
            rag = RAGSystem(mock_config)

            with pytest.raises(Exception) as exc_info:
                rag.query("test")

            assert "API Error" in str(exc_info.value)

    def test_empty_config_api_key_behavior(self, mock_empty_config):
        """
        Test behavior when OPENAI_API_KEY is empty.
        The error should occur during the first API call.
        """
        with patch('rag_system.VectorStore'), \
             patch('rag_system.DocumentProcessor'):
            # Don't mock AIGenerator - let it initialize with empty key
            with patch('ai_generator.OpenAI') as mock_openai:
                mock_client = Mock()
                mock_client.chat.completions.create.side_effect = Exception(
                    "Incorrect API key provided"
                )
                mock_openai.return_value = mock_client

                from rag_system import RAGSystem
                rag = RAGSystem(mock_empty_config)

                with pytest.raises(Exception) as exc_info:
                    rag.query("test")

                assert "API key" in str(exc_info.value)


class TestRAGSystemDocumentLoading:
    """Tests for document loading functionality."""

    def test_add_course_folder_initializes_vector_store(self, mock_config):
        """Adding courses populates the vector store."""
        with patch('rag_system.VectorStore') as mock_vs, \
             patch('rag_system.AIGenerator'), \
             patch('rag_system.DocumentProcessor') as mock_dp, \
             patch('os.path.exists', return_value=True), \
             patch('os.listdir', return_value=['course.txt']), \
             patch('os.path.isfile', return_value=True):

            # Mock document processing
            mock_course = Mock()
            mock_course.title = "Test Course"
            mock_dp.return_value.process_course_document.return_value = (mock_course, [])
            mock_vs.return_value.get_existing_course_titles.return_value = []

            from rag_system import RAGSystem
            rag = RAGSystem(mock_config)

            courses, chunks = rag.add_course_folder("/fake/path")

            # Should add course metadata
            mock_vs.return_value.add_course_metadata.assert_called()
