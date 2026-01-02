from openai import OpenAI

class AIReplier:
    def __init__(self, api_key="csk-fthmtp5jrkfkjhfmvdtyjvkwx5jc95vnn8d5eenk42kkyxcw"):
        # Cerebras uses an OpenAI-compatible API
        self.client = OpenAI(
            base_url="https://api.cerebras.ai/v1",
            api_key=api_key
        )

    def generate_reply(self, post_content):
        """
        Generates a helpful, summarized, and well-toned reply using Cerebras API.
        """
        prompt = f"""
        You are a helpful community assistant. Read the following forum post and provide a helpful, 
        summarized, and polite response that solves the user's query. 
        Keep the tone professional yet friendly. 
        Limit the response to 2-3 concise sentences.

        Post Content:
        {post_content}

        Helpful Reply:
        """
        
        try:
            response = self.client.chat.completions.create(
                model="llama3.1-8b", # Common model on Cerebras
                messages=[
                    {"role": "system", "content": "You are a helpful and concise forum assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating AI reply with Cerebras: {e}")
            return "I'm sorry, I couldn't generate a response at this time. Please check back later or contact support."
