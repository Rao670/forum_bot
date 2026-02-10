import re

class Humanizer:
    """
    Component responsible for making AI text sound like a natural forum participant.
    """
    def __init__(self, ai_client=None):
        self.ai_client = ai_client

    def humanize(self, text):
        """
        Cleans up common AI-isms and robotic phrasing.
        """
        # 1. Remove robotic intros/outros
        robotic_patterns = [
            r"i hope this helps",
            r"let me know if you have",
            r"in conclusion",
            r"overall",
            r"to summarize",
            r"thank you for your question",
            r"as an ai",
            r"certainly!",
            r"i understand",
            r"here is the solution",
            r"oh, i see what you mean",
            r"i understand your point",
            r"i see what you're saying"
        ]
        
        cleaned = text
        for pattern in robotic_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
            
        # 2. Remove AI-style hyphens/dashes (— or --)
        # These look too "bookish" for a forum. Replace with comma or space.
        cleaned = re.sub(r'\s*[—–]\s*', ', ', cleaned) # Em/En dashes
        cleaned = re.sub(r'\s*--\s*', ', ', cleaned)   # Double hyphens
        
        return cleaned.strip()

    def inject_natural_flow(self, text):
        """
        Adds subtle human conversational elements.
        """
        # Placeholder for AI rephrasing
        return text
