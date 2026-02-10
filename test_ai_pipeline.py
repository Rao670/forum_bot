from ai_replier import AIReplier
from unittest import mock

def test_pipeline():
    replier = AIReplier()
    
    # Test case: Valid technical question
    original_post = "How do I fix Error 1000 in Zoom RTMS?"
    thread_history = ["User1: I keep getting Error 1000 when connecting to WebSocket."]
    last_speaker = "User1"
    
    print("--- Running Pipeline Test ---")
    reply = replier.generate_reply(original_post, thread_history, "zoom.us", last_speaker, "Abdullah")
    print(f"Final Reply:\n{reply}")
    print("-----------------------------")

if __name__ == "__main__":
    test_pipeline()
