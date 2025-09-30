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
You are a senior code reviewer.
Review the following PR changes and:
- Suggest improvements
- Point out code smells
- Recommend better practices
- Suggest removal of redundant code
- Keep response short and clear

Code diff:
{diff_text}
"""

# Call OpenRouter API with GPT-5-mini
payload = {
    "model": "openai/gpt-5-nano",
    "messages": [
        {"role": "system", "content": "You are an expert software engineer reviewing GitHub PRs."},
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
pr.create_issue_comment(f"🤖 GPT-5-nano Review:\n\n{review_text}")
