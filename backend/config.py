import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

@dataclass
class Config:
    """Configuration settings for the RAG system"""
    # OpenAI API settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = "gpt-4o-mini"

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.OPENAI_API_KEY or self.OPENAI_API_KEY.strip() == "":
            raise ValueError(
                "OPENAI_API_KEY environment variable is required. "
                "Please create a .env file with your OpenAI API key."
            )
    
    # Embedding model settings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    
    # Document processing settings
    CHUNK_SIZE: int = 800       # Size of text chunks for vector storage
    CHUNK_OVERLAP: int = 100     # Characters to overlap between chunks
    MAX_RESULTS: int = 5         # Maximum search results to return
    MAX_HISTORY: int = 2         # Number of conversation messages to remember

    # Tool calling settings
    MAX_TOOL_ROUNDS: int = 2     # Maximum sequential tool calling rounds per query
    
    # Database paths
    CHROMA_PATH: str = "./chroma_db"  # ChromaDB storage location

config = Config()


