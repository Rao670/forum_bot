
import sys
import os
sys.path.append(os.getcwd())
from ai_replier import AIReplier

def test_ai():
    import os
    from openai import OpenAI
    client = OpenAI() # Uses pre-configured Manus environment
    
    replier = AIReplier()
    # Mock _call_ai to use Manus OpenAI
    def mock_call_ai(prompt):
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    
    replier._call_ai = mock_call_ai
    # Ensure USE_GEMINI or something is set to enter the call_ai logic if it wasn't mocked
    # But since we mocked it, it should work.
    
    # Simulate a GitLab thread
    original_post = "How do I enable AI features in GitLab self-managed?"
    thread_history = [
        "arueda: I'm looking for the external agent option but it's missing.",
        "dnsmichi: You need to enable the ai_agent_external_models flag in the Rails console first."
    ]
    
    print("--- Testing GitLab Response ---")
    reply = replier.generate_reply(
        original_post=original_post,
        thread_history=thread_history,
        platform_name="gitlab.com",
        last_speaker="dnsmichi",
        my_name="KernelCoder"
    )
    print(f"Bot Reply: {reply}")
    
    # Test a resolved thread
    print("\n--- Testing Resolved Thread ---")
    thread_history_resolved = thread_history + ["arueda: Thanks, that worked!"]
    reply_resolved = replier.generate_reply(
        original_post=original_post,
        thread_history=thread_history_resolved,
        platform_name="gitlab.com",
        last_speaker="arueda",
        my_name="KernelCoder"
    )
    print(f"Bot Reply (should be [SKIP]): {reply_resolved}")

if __name__ == "__main__":
    test_ai()
