import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
from openai import OpenAI
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")
import google.generativeai as genai
import config
from verifier import Verifier
from humanizer import Humanizer

class AIReplier:
    def __init__(self, api_key=None):
        # Initialize Cerebras (as fallback) - only if key exists
        cerebras_key = api_key or getattr(config, 'CEREBRAS_API_KEY', None)
        if cerebras_key:
            self.cerebras_client = OpenAI(
                base_url="https://api.cerebras.ai/v1",
                api_key=cerebras_key
            )
        else:
            self.cerebras_client = None
        
        # Initialize Gemini Keys List
        self.gemini_keys = getattr(config, 'GEMINI_API_KEYS', [])
        legacy_key = getattr(config, 'GEMINI_API_KEY', None)
        if legacy_key and legacy_key not in self.gemini_keys:
            self.gemini_keys.insert(0, legacy_key)

        # Initialize sub-components
        self.verifier = Verifier()
        self.humanizer = Humanizer()

        if self.gemini_keys:
            print(f" AI Engine: Gemini Primary ({len(self.gemini_keys)} keys configured)")
        elif self.cerebras_client:
            print(" AI Engine: Cerebras enabled")
        else:
            print(" WARNING: No AI Engine configured!")

    def clean_reply(self, text):
        import re
        contractions = {
            r"\bi'm\b": "I am", r"\bi've\b": "I have", r"\bi'll\b": "I will",
            r"\bi'd\b": "I would", r"\bit's\b": "it is", r"\bcan't\b": "cannot",
            r"\bdon't\b": "do not", r"\bdoesn't\b": "does not", r"\bisn't\b": "is not",
            r"\baren't\b": "are not", r"\bwon't\b": "will not", r"\bshouldn't\b": "should not",
            r"\bwouldn't\b": "would not", r"\bthere's\b": "there is", r"\bhere's\b": "here is",
            r"\bthat's\b": "that is", r"\bwhat's\b": "what is", r"\bwho's\b": "who is",
            r"\bhow's\b": "how is", r"\bwe're\b": "we are", r"\byou're\b": "you are",
            r"\bthey're\b": "they are", r"\bsomething's\b": "something is",
            r"\beverything's\b": "everything is", r"\banyone's\b": "anyone is",
            r"\banybody's\b": "anybody is", r"\bwasn't\b": "was not", r"\bower't\b": "were not",
        }
        cleaned = text
        for pattern, replacement in contractions.items():
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'#\w+', '', cleaned)
        return cleaned.strip()

    def generate_reply(self, original_post, thread_history=None, platform_name="generic", last_speaker=None, my_name="unknown"):
        """
        Multi-stage generation pipeline: Expert Draft -> Verifier -> Humanizer.
        """
        # --- STAGE 0: RESOLUTION CHECK ---
        if self.verifier.is_thread_resolved(thread_history):
            print(" [Verifier] Thread seems resolved. Skipping.")
            return "[SKIP]"

        # --- STAGE 1: EXPERT DRAFTING ---
        draft = self._generate_draft(original_post, thread_history, platform_name, last_speaker, my_name)
        
        if not draft or "[SKIP]" in draft.upper():
            return "[SKIP]"

        # --- STAGE 2: VERIFICATION ---
        is_valid, reason, refined_draft = self.verifier.verify(draft, original_post, thread_history)
        if not is_valid:
            print(f" [Verifier] Rejecting draft: {reason}")
            return "[SKIP]"
        
        # --- STAGE 3: HUMANIZATION ---
        # First, semantic humanization via AI if possible
        humanized = self._ai_humanize(refined_draft, last_speaker)
        # Second, rule-based cleanup
        final_reply = self.humanizer.humanize(humanized)
        
        return final_reply

    def _generate_draft(self, original_post, thread_history, platform_name, last_speaker, my_name):
        # Platform Specific Context Rules
        # ... (rules same as before)
        platform_rules = {
            "glideapps.com": "Glide no-code expert. Talk about 'Relations', 'Rollups'.",
            "webflow.com": "Webflow designer. Focus on CSS, CMS, interactions.",
            "cursor.com": "Developer using Cursor IDE. Knowledge of AI code gen.",
            "ansible.com": "DevOps engineer. Use YAML snippets.",
            "arduino.cc": "Embedded systems engineer. C++ focus.",
            "freecodecamp.org": "Expert coder. Solve issues and explain 'why'.",
            "modular.com": "Mojo/AI developer. Performance focus.",
            "zoom.us": "Zoom API developer. JWT/OAuth/SDK focus.",
            "unity.com": "Unity Game Developer. C# and objects/scripts.",
            "bubble.io": "Bubble.io developer. Workflows, Data Types focus."
        }
        
        context_instruction = "You are a helpful forum member."
        for domain, rule in platform_rules.items():
            if domain in platform_name:
                context_instruction = rule
                break

        context_info = f"THREAD CONTEXT:\n{original_post}\n\n"
        if thread_history:
            context_info += "RECENT CONVERSATION:\n"
            for msg in thread_history[-5:]:
                context_info += f"- {msg}\n"
        
        target_speaker = last_speaker if last_speaker else "the user"
        
        prompt = f"""
        ACT AS: {context_instruction}
        GOAL: Provide a technically perfect solution to '{target_speaker}'.
        CONTEXT: {context_info}
        
        RULES:
        - NEVER CLAIM CREDIT: Do NOT use "We" or "I fixed it" unless you are reporting your OWN code action (unlikely). Use "The team fixed it", "It looks like a fix was merged", or "The official solution is...".
        - IMPROVE, DON'T REPEAT: Look at previous replies. Do NOT repeat what has already been suggested. Only add extra value, a new perspective, or a simplified practical summary.
        - If unsure, return [SKIP].
        - No fluff, no robotic intros. 
        - Max 2-3 sentences of pure value.
        - Name MUST match '{target_speaker}'.
        
        Draft Jawab (Technical focus):
        """
        return self._call_ai(prompt)

    def _ai_humanize(self, draft, target_speaker):
        """
        Uses AI to rephrase the technical draft into a natural conversational tone.
        """
        prompt = f"""
        REPHRASE this technical forum reply to sound like a normal human developer talking to a friend.
        
        Original Draft: "{draft}"
        Target User: "{target_speaker}"
        
        HUMANIZATION RULES:
        - Vary sentence length.
        - Use simple, direct language.
        - Add a short natural greeting if appropriate (e.g. "Good catch [Name]!" or "That makes sense..."). 
        - DO NOT use "Oh, I see what you mean" or "I understand your point" - these sound like a bot.
        - REMOVE any "As an AI", "In conclusion", or "I hope this helps".
        - Do NOT use long hyphens/em-dashes (—) or double hyphens (--). Use commas or periods instead.
        - Do NOT change the technical meaning or code.
        
        Humanized Reply:
        """
        return self._call_ai(prompt)

    def _call_ai(self, prompt):
        # Utility to call Gemini/Cerebras with rotation and error handling
        if getattr(config, 'USE_GEMINI', False) and self.gemini_keys:
            for i, key in enumerate(self.gemini_keys):
                try:
                    genai.configure(api_key=key)
                    model = genai.GenerativeModel('models/gemini-flash-latest')
                    response = model.generate_content(prompt)
                    return response.text.strip()
                except Exception as e:
                    if "429" in str(e): continue
                    print(f" [AI Error] Key {i+1}: {e}")
        
        if getattr(config, 'USE_CEREBRAS', False) and self.cerebras_client:
            try:
                response = self.cerebras_client.chat.completions.create(
                    model="llama3.1-8b",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300
                )
                return response.choices[0].message.content.strip()
            except: pass
            
        return "[SKIP]"
