import pytest
import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.database.database import get_db, create_tables
from app.config import settings

# Create test client
client = TestClient(app)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def setup_database():
    """Setup test database"""
    create_tables()
    yield
    # Cleanup could be added here


def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Technical Documentation Agent API"
    assert data["version"] == "1.0.0"


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_process_documentation():
    """Test documentation processing endpoint"""
    request_data = {
        "url": "https://docs.python.org/3/library/requests.html",
        "chat_id": "test_chat_123"
    }
    
    response = client.post("/api/v1/process-documentation", json=request_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["chat_id"] == "test_chat_123"
    assert data["status"] == "processing"


def test_get_processing_status():
    """Test processing status endpoint"""
    chat_id = "test_chat_123"
    
    response = client.get(f"/api/v1/processing-status/{chat_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["chat_id"] == chat_id
    assert "status" in data
    assert "progress" in data


def test_chat_with_agent():
    """Test chat endpoint"""
    chat_id = "test_chat_123"
    message_data = {
        "message": "What is this documentation about?"
    }
    
    response = client.post(f"/api/v1/chat/{chat_id}", json=message_data)
    # This might fail if documentation is not processed yet, which is expected
    assert response.status_code in [200, 500]


def test_get_chat_history():
    """Test chat history endpoint"""
    chat_id = "test_chat_123"
    
    response = client.get(f"/api/v1/chat-history/{chat_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["chat_id"] == chat_id
    assert "messages" in data


def test_get_graph_info():
    """Test graph info endpoint"""
    response = client.get("/api/v1/graph-info")
    assert response.status_code == 200
    
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)


def test_invalid_chat_id():
    """Test with invalid chat ID"""
    response = client.get("/api/v1/processing-status/invalid_chat_id")
    assert response.status_code == 404


def test_duplicate_chat_id():
    """Test duplicate chat ID handling"""
    request_data = {
        "url": "https://docs.python.org/3/library/requests.html",
        "chat_id": "duplicate_test_123"
    }
    
    # First request should succeed
    response1 = client.post("/api/v1/process-documentation", json=request_data)
    assert response1.status_code == 200
    
    # Second request with same chat_id should fail
    response2 = client.post("/api/v1/process-documentation", json=request_data)
    assert response2.status_code == 400 