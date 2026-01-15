"""
Unit tests for AIGenerator class.
Tests tool calling flow and error handling.
"""
import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestAIGeneratorInitialization:
    """Tests for AIGenerator initialization."""

    def test_initialization_with_valid_key(self):
        """Verify AIGenerator initializes with valid API key."""
        with patch('ai_generator.OpenAI') as mock_openai:
            from ai_generator import AIGenerator

            ai_gen = AIGenerator("test-api-key", "gpt-4o-mini")

            mock_openai.assert_called_once_with(api_key="test-api-key")
            assert ai_gen.model == "gpt-4o-mini"

    def test_initialization_with_empty_key_still_creates_client(self):
        """
        Empty API key creates client (OpenAI SDK behavior).
        Failure happens on first API call, not initialization.
        """
        with patch('ai_generator.OpenAI') as mock_openai:
            from ai_generator import AIGenerator

            ai_gen = AIGenerator("", "gpt-4o-mini")

            # OpenAI client is created even with empty key
            mock_openai.assert_called_once_with(api_key="")


class TestGenerateResponse:
    """Tests for AIGenerator.generate_response() method."""

    def test_simple_query_without_tools(self, mock_openai_client):
        """Test direct response without tool usage."""
        with patch('ai_generator.OpenAI', return_value=mock_openai_client):
            from ai_generator import AIGenerator

            ai_gen = AIGenerator("test-key", "gpt-4o-mini")
            response = ai_gen.generate_response("What is Python?")

            assert response == "Test response"
            assert mock_openai_client.chat.completions.create.called

    def test_query_with_tool_call_flow(self, mock_openai_client_with_tool_call, mock_vector_store):
        """Test complete two-stage tool call flow."""
        with patch('ai_generator.OpenAI', return_value=mock_openai_client_with_tool_call):
            from ai_generator import AIGenerator
            from search_tools import ToolManager, CourseSearchTool

            ai_gen = AIGenerator("test-key", "gpt-4o-mini")

            tool_manager = ToolManager()
            search_tool = CourseSearchTool(mock_vector_store)
            tool_manager.register_tool(search_tool)

            response = ai_gen.generate_response(
                "What is prompt caching?",
                tools=tool_manager.get_tool_definitions(),
                tool_manager=tool_manager
            )

            assert response == "Prompt caching is a technique..."
            # Should make 2 API calls: first for tool decision, second for final response
            assert mock_openai_client_with_tool_call.chat.completions.create.call_count == 2

    def test_api_error_propagates(self, mock_openai_client_error):
        """Test that OpenAI API errors propagate and are not swallowed."""
        with patch('ai_generator.OpenAI', return_value=mock_openai_client_error):
            from ai_generator import AIGenerator

            ai_gen = AIGenerator("test-key", "gpt-4o-mini")

            with pytest.raises(Exception) as exc_info:
                ai_gen.generate_response("Test query")

            assert "API Error" in str(exc_info.value)

    def test_conversation_history_appended_to_system_prompt(self, mock_openai_client):
        """Verify conversation history is included in system prompt."""
        with patch('ai_generator.OpenAI', return_value=mock_openai_client):
            from ai_generator import AIGenerator

            ai_gen = AIGenerator("test-key", "gpt-4o-mini")
            history = "User: Hello\nAssistant: Hi there!"

            ai_gen.generate_response("Follow up question", conversation_history=history)

            call_args = mock_openai_client.chat.completions.create.call_args
            messages = call_args.kwargs['messages']
            system_content = messages[0]['content']

            assert history in system_content


class TestToolExecution:
    """Tests for tool execution handling in AIGenerator."""

    def test_malformed_json_arguments_handling(self, mock_vector_store):
        """
        CRITICAL TEST: Malformed JSON in tool arguments is handled gracefully.

        New behavior (fixed): JSON parse error is logged and returns error message
        as tool result, allowing the AI to handle the error gracefully.
        """
        with patch('ai_generator.OpenAI') as mock_openai:
            # Setup response with malformed JSON in tool arguments
            mock_tool_call = Mock()
            mock_tool_call.id = "call_123"
            mock_tool_call.type = "function"
            mock_tool_call.function.name = "search_course_content"
            mock_tool_call.function.arguments = "{ invalid json }"  # Malformed!

            mock_msg1 = Mock()
            mock_msg1.content = None
            mock_msg1.tool_calls = [mock_tool_call]
            mock_resp1 = Mock()
            mock_resp1.choices = [Mock(message=mock_msg1, finish_reason="tool_calls")]

            # Second call: AI should get error message and handle it
            mock_msg2 = Mock()
            mock_msg2.content = "I encountered an error processing that request."
            mock_msg2.tool_calls = None
            mock_resp2 = Mock()
            mock_resp2.choices = [Mock(message=mock_msg2, finish_reason="stop")]

            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = [mock_resp1, mock_resp2]
            mock_openai.return_value = mock_client

            from ai_generator import AIGenerator
            from search_tools import ToolManager, CourseSearchTool

            ai_gen = AIGenerator("test-key", "gpt-4o-mini")
            tm = ToolManager()
            tm.register_tool(CourseSearchTool(mock_vector_store))

            # Should now handle gracefully and return response
            response = ai_gen.generate_response(
                "test",
                tools=tm.get_tool_definitions(),
                tool_manager=tm
            )

            # Verify it returned a response (error was handled gracefully)
            assert response == "I encountered an error processing that request."

    def test_tool_manager_called_with_correct_args(self, mock_vector_store):
        """Verify tool manager receives correct arguments from parsed JSON."""
        with patch('ai_generator.OpenAI') as mock_openai:
            # Setup valid tool call
            mock_tool_call = Mock()
            mock_tool_call.id = "call_456"
            mock_tool_call.type = "function"
            mock_tool_call.function.name = "search_course_content"
            mock_tool_call.function.arguments = '{"query": "test query", "course_name": "MCP"}'

            mock_msg1 = Mock()
            mock_msg1.content = None
            mock_msg1.tool_calls = [mock_tool_call]
            mock_resp1 = Mock()
            mock_resp1.choices = [Mock(message=mock_msg1, finish_reason="tool_calls")]

            mock_msg2 = Mock()
            mock_msg2.content = "Final response"
            mock_msg2.tool_calls = None
            mock_resp2 = Mock()
            mock_resp2.choices = [Mock(message=mock_msg2, finish_reason="stop")]

            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = [mock_resp1, mock_resp2]
            mock_openai.return_value = mock_client

            from ai_generator import AIGenerator
            from search_tools import ToolManager, CourseSearchTool

            ai_gen = AIGenerator("test-key", "gpt-4o-mini")
            tm = ToolManager()
            tm.register_tool(CourseSearchTool(mock_vector_store))

            ai_gen.generate_response(
                "test",
                tools=tm.get_tool_definitions(),
                tool_manager=tm
            )

            # Verify search was called with correct args
            mock_vector_store.search.assert_called_with(
                query="test query",
                course_name="MCP",
                lesson_number=None
            )

    def test_tools_available_in_all_rounds(self, mock_openai_client_with_tool_call, mock_vector_store):
        """Verify tools are available in all rounds for sequential tool calling."""
        with patch('ai_generator.OpenAI', return_value=mock_openai_client_with_tool_call):
            from ai_generator import AIGenerator
            from search_tools import ToolManager, CourseSearchTool

            ai_gen = AIGenerator("test-key", "gpt-4o-mini")

            tool_manager = ToolManager()
            search_tool = CourseSearchTool(mock_vector_store)
            tool_manager.register_tool(search_tool)

            ai_gen.generate_response(
                "query",
                tools=tool_manager.get_tool_definitions(),
                tool_manager=tool_manager
            )

            # Get all API calls
            calls = mock_openai_client_with_tool_call.chat.completions.create.call_args_list

            # First call should have tools (round 1)
            first_call_kwargs = calls[0].kwargs
            assert 'tools' in first_call_kwargs

            # Second call should ALSO have tools (round 2, for sequential calling)
            second_call_kwargs = calls[1].kwargs
            assert 'tools' in second_call_kwargs


class TestAPIKeyValidation:
    """Tests for API key validation behavior."""

    def test_empty_api_key_causes_failure_on_api_call(self):
        """Empty API key causes authentication failure on first API call."""
        with patch('ai_generator.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = Exception(
                "Incorrect API key provided"
            )
            mock_openai.return_value = mock_client

            from ai_generator import AIGenerator

            ai_gen = AIGenerator("", "gpt-4o-mini")  # Empty key

            with pytest.raises(Exception) as exc_info:
                ai_gen.generate_response("test")

            assert "API key" in str(exc_info.value)

    def test_invalid_api_key_format_causes_failure(self):
        """Invalid API key format causes authentication failure."""
        with patch('ai_generator.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = Exception(
                "Invalid API key format"
            )
            mock_openai.return_value = mock_client

            from ai_generator import AIGenerator

            ai_gen = AIGenerator("not-a-valid-key", "gpt-4o-mini")

            with pytest.raises(Exception) as exc_info:
                ai_gen.generate_response("test")

            assert "Invalid" in str(exc_info.value) or "API key" in str(exc_info.value)


class TestSequentialToolCalling:
    """Tests for multi-round sequential tool calling capability."""

    def test_two_sequential_tool_rounds(self, mock_openai_client_two_tool_rounds, mock_vector_store):
        """Test that AI can make 2 sequential tool calls across separate API rounds."""
        with patch('ai_generator.OpenAI', return_value=mock_openai_client_two_tool_rounds):
            from ai_generator import AIGenerator
            from search_tools import ToolManager, CourseSearchTool

            ai_gen = AIGenerator("test-key", "gpt-4o-mini")
            tm = ToolManager()
            tm.register_tool(CourseSearchTool(mock_vector_store))

            response = ai_gen.generate_response(
                "Tell me about prompt caching",
                tools=tm.get_tool_definitions(),
                tool_manager=tm
            )

            # Verify final response
            assert response == "Based on both searches, prompt caching allows..."

            # Verify 3 API calls were made (round 1, round 2, final synthesis)
            assert mock_openai_client_two_tool_rounds.chat.completions.create.call_count == 3

            # Verify both tool searches were executed
            assert mock_vector_store.search.call_count == 2

    def test_max_tool_rounds_enforced(self, mock_openai_client_max_rounds_reached, mock_vector_store):
        """Test that MAX_TOOL_ROUNDS limit is enforced."""
        with patch('ai_generator.OpenAI', return_value=mock_openai_client_max_rounds_reached):
            from ai_generator import AIGenerator
            from search_tools import ToolManager, CourseSearchTool

            ai_gen = AIGenerator("test-key", "gpt-4o-mini")
            tm = ToolManager()
            tm.register_tool(CourseSearchTool(mock_vector_store))

            response = ai_gen.generate_response(
                "Complex query requiring multiple searches",
                tools=tm.get_tool_definitions(),
                tool_manager=tm
            )

            # Verify final response after hitting limit
            assert response == "Synthesized answer from all tool results"

            # Verify exactly 3 API calls (2 tool rounds + 1 final synthesis)
            assert mock_openai_client_max_rounds_reached.chat.completions.create.call_count == 3

            # Verify both tool searches were executed
            assert mock_vector_store.search.call_count == 2

    def test_early_stop_when_no_more_tools_needed(self, mock_openai_client_with_tool_call, mock_vector_store):
        """Test that loop stops early if AI doesn't request more tools."""
        with patch('ai_generator.OpenAI', return_value=mock_openai_client_with_tool_call):
            from ai_generator import AIGenerator
            from search_tools import ToolManager, CourseSearchTool

            ai_gen = AIGenerator("test-key", "gpt-4o-mini")
            tm = ToolManager()
            tm.register_tool(CourseSearchTool(mock_vector_store))

            response = ai_gen.generate_response(
                "Simple query",
                tools=tm.get_tool_definitions(),
                tool_manager=tm
            )

            # Verify response
            assert response == "Prompt caching is a technique..."

            # Should only make 2 API calls (tool round + stop response)
            assert mock_openai_client_with_tool_call.chat.completions.create.call_count == 2

            # Only one search executed
            assert mock_vector_store.search.call_count == 1

    def test_tools_available_in_second_round(self, mock_openai_client_two_tool_rounds):
        """Verify tools are provided in the second API round."""
        with patch('ai_generator.OpenAI', return_value=mock_openai_client_two_tool_rounds):
            from ai_generator import AIGenerator
            from search_tools import ToolManager, CourseSearchTool
            from unittest.mock import Mock

            ai_gen = AIGenerator("test-key", "gpt-4o-mini")
            tm = ToolManager()
            tm.register_tool(CourseSearchTool(Mock()))

            ai_gen.generate_response(
                "query",
                tools=tm.get_tool_definitions(),
                tool_manager=tm
            )

            # Get all API call kwargs
            calls = mock_openai_client_two_tool_rounds.chat.completions.create.call_args_list

            # Both round 1 and round 2 should have tools
            assert 'tools' in calls[0].kwargs  # Round 1
            assert 'tools' in calls[1].kwargs  # Round 2
