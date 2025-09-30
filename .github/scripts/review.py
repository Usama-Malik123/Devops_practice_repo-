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
You are an experienced senior software engineer performing a professional pull request (PR) review.

Your task:
- Analyze the provided code changes carefully.
- Identify potential bugs, logical errors, or edge cases.
- Highlight security vulnerabilities or unsafe coding practices.
- Point out performance issues or inefficient patterns.
- Suggest improvements for readability, maintainability, and scalability.
- Recommend the removal of redundant or dead code.
- If everything looks good, explicitly confirm with a brief positive note.

Guidelines:
- Be objective, constructive, and concise.
- Focus only on the provided diff (do not invent missing context).
- Organize feedback with clear bullet points.
- Use a professional and respectful tone.

Code diff:
{diff_text}
"""

# Call OpenRouter API with GPT-4.1
payload = {
    "model": "openai/gpt-4.1",
    "messages": [
        {"role": "system", "content": "You are an expert software engineer reviewing GitHub PRs."},
        {"role": "user", "content": prompt},
    ],
    "max_tokens": 600,
}

headers = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
}

response = requests.post(OPENROUTER_URL, headers=headers, json=payload)
response.raise_for_status()
review_text = response.json()["choices"][0]["message"]["content"]

# Post comment to PR
pr.create_issue_comment(f"🤖 GPT-4.1 Review:\n\n{review_text}")
