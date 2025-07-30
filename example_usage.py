#!/usr/bin/env python3
"""
Example usage script for Technical Documentation Agent
This script demonstrates how to use the API endpoints
"""

import requests
import time
import json
from typing import Dict, Any

# API base URL
BASE_URL = "http://localhost:8000"


def print_response(title: str, response: requests.Response):
    """Print formatted response"""
    print(f"\n{'='*50}")
    print(f"{title}")
    print(f"{'='*50}")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def wait_for_processing(chat_id: str, max_wait: int = 60) -> bool:
    """Wait for documentation processing to complete"""
    print(f"\nWaiting for processing to complete (max {max_wait} seconds)...")
    
    start_time = time.time()
    while time.time() - start_time < max_wait:
        response = requests.get(f"{BASE_URL}/api/v1/processing-status/{chat_id}")
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            progress = data.get("progress", 0)
            
            print(f"Status: {status}, Progress: {progress}%")
            
            if status == "completed":
                print("Processing completed successfully!")
                return True
            elif status == "failed":
                print(f"Processing failed: {data.get('error_message', 'Unknown error')}")
                return False
        
        time.sleep(2)
    
    print("Processing timeout!")
    return False


def main():
    """Main example function"""
    print("Technical Documentation Agent - Example Usage")
    print("=" * 50)
    
    # Test 1: Health check
    print("\n1. Testing health check...")
    response = requests.get(f"{BASE_URL}/health")
    print_response("Health Check", response)
    
    # Test 2: Get graph info
    print("\n2. Getting graph information...")
    response = requests.get(f"{BASE_URL}/api/v1/graph-info")
    print_response("Graph Info", response)
    
    # Test 3: Process documentation
    print("\n3. Processing documentation...")
    chat_id = f"example_chat_{int(time.time())}"
    
    process_data = {
        "url": "https://docs.python.org/3/library/requests.html",
        "chat_id": chat_id
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/process-documentation", json=process_data)
    print_response("Process Documentation", response)
    
    # Test 4: Wait for processing
    if response.status_code == 200:
        success = wait_for_processing(chat_id)
        
        if success:
            # Test 5: Chat with agent
            print("\n4. Testing chat functionality...")
            
            questions = [
                "What is the requests library?",
                "How do I make a GET request?",
                "What are the main features of requests?",
                "Show me an example of POST request"
            ]
            
            for i, question in enumerate(questions, 1):
                print(f"\nQuestion {i}: {question}")
                
                chat_data = {"message": question}
                response = requests.post(f"{BASE_URL}/api/v1/chat/{chat_id}", json=chat_data)
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"Response: {data['response'][:200]}...")
                    if data.get('sources'):
                        print(f"Sources: {data['sources']}")
                else:
                    print(f"Error: {response.status_code} - {response.text}")
                
                time.sleep(1)  # Small delay between questions
            
            # Test 6: Get chat history
            print("\n5. Getting chat history...")
            response = requests.get(f"{BASE_URL}/api/v1/chat-history/{chat_id}")
            print_response("Chat History", response)
            
            # Test 7: Clean up (optional)
            print("\n6. Cleaning up...")
            response = requests.delete(f"{BASE_URL}/api/v1/chat/{chat_id}")
            print_response("Delete Chat", response)
    
    print("\nExample completed!")


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the API server.")
        print("Make sure the server is running with: uvicorn app.main:app --reload")
    except KeyboardInterrupt:
        print("\nExample interrupted by user.")
    except Exception as e:
        print(f"Error: {str(e)}") 