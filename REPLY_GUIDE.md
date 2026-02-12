# Forum Bot: Reply Handling & Prioritization Guide

This guide explains how the bot decides **who** to reply to, **when** to reply, and **how** to handle situations with multiple active posts.

## 1. Priority Logic (Who to reply to first?)

The bot follows a specific priority order to ensure the most important interactions are handled first:

| Priority | Interaction Type | Action |
| :--- | :--- | :--- |
| **1 (Highest)** | **Direct Mentions / Replies** | Checked via the notification bell (`check_notifications`). These are people specifically waiting for *you*. |
| **2** | **Recent Active Threads** | Threads with new activity since the last visit, especially where the bot was previously involved. |
| **3** | **New Topics (Discovery)** | Searching categories for new questions that haven't been answered yet. |

## 2. Decision Framework (Should I reply?)

Before generating a reply, the bot runs through these "Antigravity" filters:

### A. Identity Protection (Self-Reply Prevention)
- **Username Match:** Checks if the `last_speaker` matches your username or known aliases.
- **Ownership Detection:** Looks for "Edit" or "Delete" buttons on the last post. If visible, it means *you* wrote that post.
- **CSS Indicators:** Checks for classes like `.post--by-current-user`.
- **Result:** If the last post is yours, the bot **skips** to avoid talking to itself.

### B. Resolution Check
- The `Verifier` scans the last 2-3 messages for keywords like "thanks", "solved", or "it worked".
- **Result:** If the issue is resolved, the bot **skips** to save credits and avoid being annoying.

### C. Staff/Moderator Interference
- The bot scans the entire thread for staff badges or moderator icons.
- **Result:** If a staff member has already replied, the bot **skips** to let the official support handle it.

## 3. Handling Multiple Posts (The "Crowd" Problem)

When many people are talking, the bot uses these strategies:

1.  **Targeted Context:** The AI is instructed to reply specifically to the `last_speaker`, not just the thread in general.
2.  **Value Check:** The AI compares its proposed answer with `thread_history`. If the answer has already been given, it returns `[SKIP]`.
3.  **Pacing:** The bot uses `global_last_reply_time` to ensure it doesn't spam multiple replies in a short window.
4.  **Main Button Focus:** It always looks for the **Main Reply Button** at the bottom of the page, avoiding individual "Reply" buttons on every post which can lead to nested confusion.

## 4. How to Improve Reply Accuracy

If you notice the bot is replying to the wrong person:
1.  Check `huggingface_bot.py` -> `bot_aliases`. Ensure all your forum usernames are listed there.
2.  Review `ai_replier.py` -> `_generate_draft`. The prompt ensures the name in the reply matches the `target_speaker`.
3.  Ensure `MANUAL_REVIEW` is set to `True` in `config.py` if you want to double-check replies before they go live.
