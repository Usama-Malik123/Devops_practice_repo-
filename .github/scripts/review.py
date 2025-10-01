import os
import requests
from github import Github

# Setup OpenAI
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

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

# Professional prompt (frontend, backend, monorepo)
prompt = f"""
You are a senior software engineer reviewing a GitHub Pull Request (PR).
Write the review as a single GitHub comment that is professional, clear, and actionable.

Your review must:
- Identify any bugs, logical errors, or potential edge cases, explaining why they may be problematic.
- Point out security, performance, or scalability risks, with suggestions for improvement.
- Recommend changes that improve readability, maintainability, and consistency across the codebase.
- Highlight areas where redundant, unused, or overly complex code should be removed or simplified.
- For frontend code, check for issues in UI/UX, accessibility, responsiveness, and best practices in state management.
- For backend code, check for API design flaws, inefficient database queries, poor error handling, and missing validations.
- For monorepos, ensure consistency in coding style, dependencies, and shared modules across different packages.
- If the code is generally well-written, acknowledge that positively while still providing constructive suggestions.

Style guidelines:
- Write in a professional but approachable tone.
- Use bullet points for clarity, with short explanations if needed.
- Keep it focused and relevant — avoid unnecessary detail, but don’t be overly brief.
- Do not start a back-and-forth conversation — this is a one-time review comment.

Code diff:
{diff_text}
"""

# Call OpenAI API with safer model
payload = {
    "model": "gpt-5-mini",   # <-- more reliable than gpt-5-mini
    "messages": [
        {"role": "system", "content": "You are an expert software engineer reviewing GitHub PRs."},
        {"role": "user", "content": prompt},
    ],
    "max_completion_tokens": 200,
}

headers = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
}

response = requests.post(OPENAI_URL, headers=headers, json=payload)
response.raise_for_status()
data = response.json()

# Debugging (optional, can be removed later)
print("DEBUG OpenAI response:", data)

# Safely extract review text
review_text = (
    data["choices"][0].get("message", {}).get("content")
    or data["choices"][0].get("messages", {}).get("content")
    or ""
)

# Fallback if still empty
if not review_text:
    review_text = "⚠️ Could not generate a review. Please check the diff size or API response."

# Post comment to PR
pr.create_issue_comment(f"🤖 GPT Review:\n\n{review_text}")
