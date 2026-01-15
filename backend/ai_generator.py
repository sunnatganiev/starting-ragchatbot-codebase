from openai import OpenAI
import json
import logging
from typing import List, Optional, Dict, Any
from config import config

# Set up logging
logger = logging.getLogger(__name__)

class AIGenerator:
    """Handles interactions with OpenAI's GPT-4o-mini API for generating responses"""

    # Static system prompt - optimized for GPT-4o-mini with multi-round tool calling
    SYSTEM_PROMPT = """You are an AI assistant specialized in course materials and educational content with access to two specialized tools.

AVAILABLE TOOLS:
1. Course Content Search - For searching specific course content and detailed materials
2. Course Outline Tool - For retrieving complete course structure with all lessons

SEQUENTIAL TOOL CALLING CAPABILITY:
- You can make up to 2 sequential tool calling rounds per query
- Each round is a SEPARATE API request where you can reason about previous results
- After receiving tool results, you can request additional tools if needed
- Example workflow:
  * Round 1: Search for "prompt caching" → Get initial results
  * Round 2: If results mention "Lesson 3", search "Lesson 3 prompt caching" for more detail
- Use multiple rounds when initial results are incomplete or suggest deeper investigation

CRITICAL RULES FOR TOOL USAGE:
- Use the OUTLINE TOOL when users ask about course structure, outline, lesson list, or "what's in a course"
- Use the CONTENT SEARCH TOOL for questions about specific course content or detailed educational materials
- For general knowledge questions, answer directly without using tools
- Make additional tool calls if initial results are insufficient or incomplete
- Synthesize all tool results into accurate responses without meta-commentary

RESPONSE REQUIREMENTS FOR OUTLINES:
- When using the outline tool, present the complete information returned:
  - Course title
  - Course link (if available)
  - Full list of lessons with lesson numbers and titles
- Format the outline clearly and readably
- Do not add extra commentary beyond what the tool provides

GENERAL RESPONSE REQUIREMENTS:
- Provide direct, factual answers only
- Never mention tool processes or reasoning
- Never use phrases like "based on the search results" or "according to the tool"
- Keep responses brief and focused (under 200 words unless detail required)
- Include relevant examples when they enhance understanding
- Use clear, accessible language

For general questions about programming concepts, definitions, or common knowledge, answer immediately from your training. Only use tools when specific course details are needed."""

    def __init__(self, api_key: str, model: str):
        self.client = OpenAI(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0.0,
            "max_tokens": 800
        }

    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use (in OpenAI format)
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # OpenAI requires system message as first message in array
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query}
        ]

        # If tools are available, use the tool calling loop
        if tools and tool_manager:
            logger.debug("Tools available, using tool calling loop")
            return self._execute_tool_calling_loop(messages, tools, tool_manager)

        # No tools available - make simple API call
        response = self._make_api_call(messages, tools=None)
        return response.choices[0].message.content

    def _make_api_call(self, messages: List[Dict[str, Any]], tools: Optional[List] = None):
        """
        Make an OpenAI API call with given messages and optional tools.

        Args:
            messages: List of message dictionaries to send to the API
            tools: Optional list of tool definitions

        Returns:
            OpenAI API response object

        Raises:
            Exception: If API call fails
        """
        api_params = {
            **self.base_params,
            "messages": messages
        }

        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = "auto"
            logger.debug(f"Making API call with {len(tools)} tools available")
        else:
            logger.debug("Making API call without tools")

        try:
            response = self.client.chat.completions.create(**api_params)
            logger.debug(f"API call successful, finish_reason: {response.choices[0].finish_reason}")
            return response
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise

    def _make_final_api_call(self, messages: List[Dict[str, Any]]) -> str:
        """
        Make final API call without tools and return text response.

        Args:
            messages: List of message dictionaries to send to the API

        Returns:
            Generated text response

        Raises:
            Exception: If API call fails
        """
        logger.debug("Making final API call (no tools)")
        response = self._make_api_call(messages, tools=None)
        return response.choices[0].message.content

    def _execute_tool_calling_loop(self, messages: List[Dict[str, Any]], tools: List, tool_manager) -> str:
        """
        Execute tool calling loop supporting up to MAX_TOOL_ROUNDS sequential rounds.

        In each round:
        1. Make API call with tools available
        2. If Claude requests tools, execute them and add results to messages
        3. Repeat until Claude stops calling tools or max rounds reached
        4. Make final API call without tools to get synthesized response

        Args:
            messages: Initial message history (system + user query)
            tools: List of available tool definitions
            tool_manager: Manager to execute tools

        Returns:
            Final synthesized response text

        Raises:
            Exception: If any API call fails
        """
        max_rounds = config.MAX_TOOL_ROUNDS
        logger.info(f"Starting tool calling loop (max {max_rounds} rounds)")

        for round_num in range(max_rounds):
            logger.debug(f"Tool round {round_num + 1}/{max_rounds}: Making API call with tools")

            # Make API call with tools available
            response = self._make_api_call(messages, tools)

            # Check if Claude wants to use tools
            if response.choices[0].finish_reason != "tool_calls":
                logger.info(f"Claude responded without tools after {round_num} rounds")
                return response.choices[0].message.content

            # Execute tools and update message history
            logger.info(f"Tool calls detected in round {round_num + 1}")
            messages, _ = self._execute_single_tool_round(response, messages, tool_manager)

            logger.info(f"Completed tool round {round_num + 1}/{max_rounds}")

        # Max rounds reached - make final call without tools
        logger.info(f"Max tool rounds ({max_rounds}) reached, making final synthesis call")
        return self._make_final_api_call(messages)

    def _execute_single_tool_round(self, api_response, messages: List[Dict[str, Any]], tool_manager) -> tuple[List[Dict[str, Any]], bool]:
        """
        Execute tools from a single API response and update message history.

        Args:
            api_response: The API response containing tool calls
            messages: Current message history to append to
            tool_manager: Manager to execute tools

        Returns:
            Tuple of (updated_messages, should_continue)
            - updated_messages: Message list with assistant message and tool results
            - should_continue: True if API response indicates more tool calls possible
        """
        # Add AI's tool use response (entire message object)
        assistant_message = api_response.choices[0].message
        messages.append({
            "role": "assistant",
            "content": assistant_message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in assistant_message.tool_calls
            ]
        })

        # Execute all tool calls and collect results
        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
            logger.info(f"Executing tool: {tool_name}")

            # Parse JSON arguments
            try:
                arguments = json.loads(tool_call.function.arguments)
                logger.debug(f"Tool arguments parsed: {arguments}")
            except json.JSONDecodeError as e:
                error_msg = f"Failed to parse tool arguments for {tool_name}: {e}"
                logger.error(error_msg)
                logger.error(f"Raw arguments string: {tool_call.function.arguments}")
                # Return error as tool result instead of silently failing
                tool_result = f"Error: {error_msg}"
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": tool_result
                })
                continue

            # Execute tool
            try:
                tool_result = tool_manager.execute_tool(tool_name, **arguments)
                logger.info(f"Tool {tool_name} executed successfully")
            except Exception as e:
                logger.error(f"Tool {tool_name} execution failed: {e}")
                tool_result = f"Error executing tool: {str(e)}"

            # Add tool result message
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_call.function.name,
                "content": tool_result
            })

        # Return updated messages and signal to continue (more rounds possible)
        return messages, True

    def _handle_tool_execution(self, initial_response, base_messages: List[Dict[str, Any]], tool_manager):
        """
        Legacy method: Handle execution of tool calls and get follow-up response.
        This is kept for backward compatibility during refactoring.

        Args:
            initial_response: The response containing tool use requests
            base_messages: Base messages list (includes system + user message)
            tool_manager: Manager to execute tools

        Returns:
            Final response text after tool execution
        """
        # Execute single round
        messages, _ = self._execute_single_tool_round(initial_response, base_messages.copy(), tool_manager)

        # Get final response without tools using helper method
        # Deliberately omit tools to prevent recursive calling
        return self._make_final_api_call(messages)
