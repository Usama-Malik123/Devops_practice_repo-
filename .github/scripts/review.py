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

# Prepare prompt (your saved version)
prompt = f"""
You are a senior software engineer providing a pull request (PR) review.  
Write the review as if it is a single GitHub comment on the commit — concise, clear, and professional.

Your review must:
- Be consistent in tone and format across all PRs.
- Point out bugs, logical errors, or edge cases.
- Highlight security or performance concerns.
- Suggest improvements in readability and maintainability.
- Recommend removal of redundant or unnecessary code.
- If the code is good overall, state that briefly and positively.

Style guidelines:
- Keep it short and to the point.
- Do not start a conversation — this is a one-time review comment.
- Use bullet points for findings.
- Avoid over-explaining or adding unnecessary complexity.

Code diff:
{diff_text}
"""

# Call OpenRouter API with GPT-5-nano
payload = {
    "model": "openai/gpt-5-nano",
    "messages": [
        {"role": "system", "content": "You are an expert software engineer reviewing GitHub PRs."},
        {"role": "user", "content": prompt},
    ],
    "max_tokens": 800,
}

headers = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
}

response = requests.post(OPENROUTER_URL, headers=headers, json=payload)
response.raise_for_status()
review_text = response.json()["choices"][0]["message"]["content"]

# Post comment to PR
pr.create_issue_comment(f"🤖 GPT-5-nano Review:\n\n{review_text}")

