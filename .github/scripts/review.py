import os
import google.generativeai as genai
from github import Github

# Setup Gemini
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")

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

# Ask Gemini for review
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

response = model.generate_content(prompt)

# Post comment to PR
pr.create_issue_comment(f"🤖 Gemini Review:\n\n{response.text}")
