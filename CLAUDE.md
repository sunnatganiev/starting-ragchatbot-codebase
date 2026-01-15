# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
# Quick start (recommended)
./run.sh

# Manual start
cd backend
uv run uvicorn app:app --reload --port 8000
```

The server runs on `http://localhost:8000` with:
- Frontend served at root `/`
- API at `/api/query` and `/api/courses`
- Auto-docs at `/docs`

### Dependency Management

**IMPORTANT:** Always use `uv` for package management and running Python. Do NOT use `pip` or `python` directly.

```bash
# Install/sync dependencies
uv sync

# Add new dependency
uv add <package-name>

# Run Python files or commands
uv run python script.py
uv run <command>
```

### Environment Setup
Required: Create `.env` file with:
```
OPENAI_API_KEY=your_key_here
```

### Code Quality Tools

The project uses several tools to maintain code quality and consistency:

**Tools Installed:**
- `black`: Code formatter (line length: 88)
- `isort`: Import organizer (configured to work with black)
- `flake8`: Linter for style and error checking
- `mypy`: Static type checker
- `pytest`: Testing framework with coverage reporting

**Quick Commands:**
```bash
# Format code automatically
./format.sh

# Run all quality checks
./quality.sh

# Auto-fix formatting issues
./fix.sh

# Individual tools
uv run black backend/              # Format code
uv run isort backend/               # Organize imports
uv run flake8 backend/              # Lint code
uv run mypy backend/                # Type check
uv run pytest                       # Run tests with coverage
```

**Configuration Files:**
- `pyproject.toml`: Contains configuration for black, isort, mypy, and pytest
- `.flake8`: Flake8-specific configuration (max line length, ignored rules)

**Development Workflow:**
1. Before committing: Run `./fix.sh` to auto-format code
2. Before pushing: Run `./quality.sh` to ensure all checks pass
3. CI/CD should run `./quality.sh` to enforce quality standards

**Common Flake8 Ignore Rules:**
- `E203`: Whitespace before ':' (conflicts with black)
- `E501`: Line too long (handled by black)
- `W503`: Line break before binary operator (PEP 8 updated)

## Architecture Overview

### Two-Stage Tool-Based RAG Pattern

This system implements a **sophisticated tool-calling architecture** rather than traditional retrieve-then-generate RAG:

1. **First OpenAI API Call** (ai_generator.py:80)
   - User query sent with tools available
   - GPT-4o-mini autonomously decides whether to search course content
   - Returns `finish_reason="tool_calls"` if search needed

2. **Tool Execution** (ai_generator.py:89-155)
   - `CourseSearchTool` executes vector search
   - Results formatted with course/lesson metadata
   - Sources tracked separately for UI display

3. **Second OpenAI API Call** (ai_generator.py:145-154)
   - Original query + tool results sent to GPT-4o-mini
   - GPT-4o-mini synthesizes answer **without meta-commentary**
   - System prompt enforces: no "based on search results" language

**Why This Matters:** GPT-4o-mini intelligently skips search for general questions, reducing latency and cost. The two-call pattern enables context-aware synthesis without cluttering responses.

### Dual ChromaDB Collection Strategy

**course_catalog** (vector_store.py:51)
- One document per course (course title as embedding)
- Metadata: title, instructor, links, lesson_count, lessons_json
- Purpose: Semantic course name resolution
- Example: "MCP" query → finds "MCP: Build Rich-Context AI Apps with Anthropic"

**course_content** (vector_store.py:52)
- Many documents (800-char chunks with 100-char overlap)
- Metadata: course_title, lesson_number, chunk_index
- Chunks prefixed with context: "Course {title} Lesson {N} content: ..."
- Enables filtered search by course AND/OR lesson

**Search Flow** (vector_store.py:61-100):
```python
query="prompt caching", course_name="Building Towards"
  ↓
1. _resolve_course_name() → semantic match → exact title
2. _build_filter() → {"course_title": "Building Towards Computer Use..."}
3. course_content.query() → top 5 semantically similar chunks
```

### Document Processing Pipeline

**Expected Format** (document_processor.py:97-104):
```
Course Title: [title]
Course Link: [url]
Course Instructor: [instructor]

Lesson 0: [lesson title]
Lesson Link: [url]
[lesson content...]
```

**Chunking Strategy** (document_processor.py:25-91):
- Sentence-based splitting with smart boundary detection
- Handles abbreviations (Dr., Mr., etc.)
- Builds chunks up to 800 chars, overlaps 100 chars
- Ensures complete sentences (never mid-sentence breaks)

### Session Management

**In-memory storage** (session_manager.py):
- Auto-generated session IDs: `session_1`, `session_2`, etc.
- Stores last 4 messages (2 user/assistant exchanges)
- History formatted and appended to system prompt
- **Caveat:** Sessions lost on server restart

### Configuration Rationale

**Key Settings** (config.py):
- `CHUNK_SIZE=800`: Balances context vs. precision
- `CHUNK_OVERLAP=100`: Ensures continuity across boundaries
- `MAX_RESULTS=5`: Prevents context overload for GPT-4o-mini
- `MAX_HISTORY=2`: Recent context without token bloat
- `OPENAI_MODEL=gpt-4o-mini`: Fast, cost-efficient with strong tool use

## Code Organization Principles

### Component Responsibilities

**rag_system.py** - Orchestrator only
- Initializes all components
- Coordinates query flow
- No business logic (delegates to components)

**ai_generator.py** - OpenAI API abstraction
- Handles two-stage API calls
- Manages tool execution loop
- System prompt defined as static class constant (performance optimization)

**search_tools.py** - Extensible tool framework
- Abstract `Tool` base class
- `ToolManager` for registration/execution
- Tools store sources in `self.last_sources` for UI retrieval

**vector_store.py** - ChromaDB wrapper
- Encapsulates all vector operations
- Returns `SearchResults` dataclass (not raw ChromaDB format)
- Semantic course resolution built-in

**document_processor.py** - Stateless processor
- Pure functions for text manipulation
- Regex-based metadata extraction
- Sentence-aware chunking algorithm

### Important Implementation Details

**Source Tracking Flow:**
1. Tool executes search → stores sources in `self.last_sources`
2. RAG system calls `tool_manager.get_last_sources()` after generation
3. Sources included in API response for frontend display
4. `tool_manager.reset_sources()` clears for next query

**Why Separate:** Keeps GPT-4o-mini's response clean (no citations in text) while providing UI with rich source data.

**System Prompt Strategy:**
- Defined once as class constant `AIGenerator.SYSTEM_PROMPT`
- Prevents rebuilding on every API call
- Conversation history appended dynamically

**Error Handling Philosophy:**
- Vector search errors return `SearchResults.empty(error_msg)`
- No exceptions raised to Claude (graceful degradation)
- Frontend displays errors as assistant messages

## Modifying the System

### Adding a New Tool

1. Create tool class in `search_tools.py`:
```python
class NewTool(Tool):
    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "name": "tool_name",
            "description": "What it does",
            "input_schema": {...}
        }

    def execute(self, **kwargs) -> str:
        # Implementation
        return "result"
```

2. Register in `rag_system.py:__init__`:
```python
new_tool = NewTool(dependencies)
self.tool_manager.register_tool(new_tool)
```

Claude will automatically see it in tool definitions.

### Adding Document Types

**Current Support:** .txt, .pdf, .docx (document_processor.py:81)

To add new types:
1. Update file extension check in `rag_system.py:81`
2. Add parsing logic to `DocumentProcessor.read_file()` if special handling needed
3. Ensure output matches expected format (title/link/instructor + lessons)

### Changing Chunking Strategy

**Location:** `document_processor.py:25-91`

Current algorithm:
- Sentence boundaries via regex (line 34)
- Build chunks by adding complete sentences until size limit
- Calculate overlap by counting backwards from chunk end

**Modifying:** Change `CHUNK_SIZE` and `CHUNK_OVERLAP` in `config.py`, or override `chunk_text()` method for different strategy (e.g., paragraph-based, token-based).

### Adjusting Search Behavior

**Filter Combinations** (vector_store.py:118-133):
```python
# Current logic
if course_title and lesson_number:
    return {"$and": [...]}  # Both filters
elif course_title:
    return {"course_title": course_title}
elif lesson_number:
    return {"lesson_number": lesson_number}
```

ChromaDB supports `$or`, `$in`, `$ne` operators. Extend `_build_filter()` for complex queries.

## Startup Behavior

**Automatic Document Loading** (app.py:88-98):
- On server start, loads all docs from `../docs/` folder
- Checks existing course titles to avoid duplicates
- Skips re-processing if course already in vector store
- Prints summary: "Added {N} courses with {M} chunks"

**To Force Rebuild:**
```python
# In rag_system.add_course_folder()
rag_system.add_course_folder(docs_path, clear_existing=True)
```

## Frontend Integration

**API Contract:**

```typescript
// Query endpoint
POST /api/query
Request: {query: string, session_id?: string | null}
Response: {answer: string, sources: string[], session_id: string}

// Analytics endpoint
GET /api/courses
Response: {total_courses: number, course_titles: string[]}
```

**Session Flow:**
1. First query: `session_id` is `null`
2. Backend creates session, returns ID
3. Frontend stores ID, includes in subsequent queries
4. Backend retrieves history via session ID

**Sources Display:**
- Backend returns list like `["Course Name - Lesson 1", "Course Name - Lesson 3"]`
- Frontend renders in collapsible `<details>` element
- Sources tracked during tool execution (not by Claude)

## Common Gotchas

### ChromaDB Persistence
- Database stored at `./chroma_db/` (relative to backend/)
- Persists across restarts
- Duplicate adds prevented by checking `get_existing_course_titles()`
- Delete `chroma_db/` folder to reset completely

### Conversation History Limits
- Only last 2 exchanges (4 messages) included in context
- Older messages automatically pruned
- History lost on server restart (in-memory only)
- Increase via `config.MAX_HISTORY`

### Tool Execution Context
- Tools execute in `_handle_tool_execution()` (ai_generator.py:89)
- Tool results sent back as `role="user"` message
- Second API call has **no tools** available (prevents loops)
- Claude must synthesize from provided tool results

### Embedding Model Loading
- First run downloads `all-MiniLM-L6-v2` from HuggingFace
- Cached in `~/.cache/torch/sentence_transformers/`
- Approx 80MB download
- Subsequent runs use cached model

### Frontend Static Files
- Served via custom `DevStaticFiles` class (app.py:107)
- No-cache headers prevent stale JS/CSS during development
- Production: remove no-cache headers for performance
