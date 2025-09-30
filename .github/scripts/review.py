import os
import requests
from github import Github

# Setup OpenRouter
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Setup GitHub
g = Github(os.environ["GITHUB_TOKEN"])
repo = g.get_repo(os.environ["GITHUB_REPOSITORY"])
pr_number = int(os.environ["GITHUB_REF"].split("/")[-1])
pr = repo.get_pull(pr_number)

# Collect changed files
diff_text = ""
for file in pr.get_files():
    if file.patch:
        diff_text += f"\n--- {file.filename} ---\n{file.patch}\n"

# Prepare prompt
prompt = f"""
You are a senior software engineer performing a pull request (PR) review.  
Do not write conversational text.  
Always return your feedback in the following structured format:

---
Summary: ✅ Looks good overall / ⚠️ Issues found

Findings:
- [category] Short, clear, actionable point
- [category] Short, clear, actionable point

Commit Suggestion:
Provide a short commit-style message that summarizes the main fixes needed.
---

Categories can be: security, bug, readability, performance, maintainability.

Code diff:
{diff_text}
"""

# Call OpenRouter API
payload = {
    "model": "openai/gpt-5-chat",
    "messages": [
        {"role": "system", "content": "You are a senior software engineer reviewing GitHub PRs."},
        {"role": "user", "content": prompt},
    ],
    "max_tokens": 500,
}

headers = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
}

response = requests.post(OPENROUTER_URL, headers=headers, json=payload)
response.raise_for_status()
review_text = response.json()["choices"][0]["message"]["content"]

# Post comment to PR
pr.create_issue_comment(f"🤖 GPT-5 Review:\n\n{review_text}")
