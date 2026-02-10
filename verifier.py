import re

class Verifier:
    """
    Component responsible for technical accuracy and relevance checking.
    """
    def __init__(self, ai_client=None):
        self.ai_client = ai_client

    def verify(self, draft, original_post, thread_history=None):
        """
        Verifies the draft against the context.
        Returns (is_valid, reason, refined_draft)
        """
        if "[SKIP]" in draft.upper():
            return False, "Draft matches skip pattern", draft
        
        if len(draft) < 10:
            return False, "Draft too short", draft

        if self.contains_broken_code(draft):
            return False, "Draft contains potential code syntax errors", draft
        
        return True, "Passed basic verification", draft

    def is_thread_resolved(self, thread_history):
        """
        Returns True if the thread history suggests the issue is already resolved.
        """
        if not thread_history:
            return False
            
        history_text = "\n".join(thread_history).lower()
        
        # 1. Quick rule-based check
        resolved_keywords = ["thanks", "it worked", "solved", "fixed it", "resolved", "thank you", "perfect"]
        # Only check the last 2 messages for "thanks" to be sure
        last_messages = "\n".join(thread_history[-2:]).lower()
        
        for kw in resolved_keywords:
            if kw in last_messages:
                # We'll let the AI confirm this in the next stage
                return True
                
        return False

    def contains_broken_code(self, text):
        """
        Regex based check for obvious code syntax errors if code is detected.
        """
        if "```" in text:
            # Simple check for matching blocks
            if text.count("```") % 2 != 0:
                return True
        return False
