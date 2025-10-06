import os
import json
import requests
import time
from github import Github

# Setup
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
g = Github(os.environ["GITHUB_TOKEN"])
repo = g.get_repo(os.environ["GITHUB_REPOSITORY"])
pr_number = int(os.environ["PR_NUMBER"])
commit_sha = os.environ.get("COMMIT_SHA", repo.get_pull(pr_number).head.sha)
pr = repo.get_pull(pr_number)

all_inline_comments = []
severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
file_errors = []  # track files that failed review


def call_openai(prompt, max_tokens=1000, retries=5):
    """Helper with retries for rate limits (429)"""
    for attempt in range(retries):
        try:
            payload = {
                "model": "gpt-4.1-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert code reviewer. Review this SINGLE file thoroughly. Return ONLY valid JSON array of inline comments. Be specific and focused.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "max_completion_tokens": max_tokens,
            }
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            }
            response = requests.post(OPENAI_URL, headers=headers, json=payload)

            if response.status_code == 429:
                wait = 2 ** attempt
                print(f"Rate limited (429). Sleeping {wait}s...")
                time.sleep(wait)
                continue

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"Request failed ({e}). Retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise e


# Collect files
files_data = []
for file in pr.get_files():
    if file.patch:
        files_data.append({"filename": file.filename, "patch": file.patch})

print(f"Processing {len(files_data)} files...")

for file_data in files_data:
    filename = file_data["filename"]
    patch = file_data["patch"]

    file_prompt = f"""
Review this file: {filename}

Patch:
{patch}

INSTRUCTIONS:
1. Review carefully for bugs, security, performance, code quality.
2. Be specific: exact problem + solution.
3. Use patch @@ headers for line context.
4. Return ONLY valid JSON array:
[
  {{
    "line": 45,
    "severity": "HIGH",
    "category": "BUG",
    "body": "Specific issue (2-3 sentences max)"
  }}
]
"""

    try:
        response = call_openai(file_prompt, max_tokens=800)
        content = response["choices"][0]["message"]["content"].strip()

        # Clean JSON
        if "```" in content:
            parts = content.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    content = part[4:].strip()
                    break
                elif part.startswith("["):
                    content = part
                    break

        start = content.find("[")
        end = content.rfind("]") + 1
        if start != -1 and end != 0:
            content = content[start:end]

        comments = json.loads(content)
        print(f"File {filename}: {len(comments)} issues found")

        # Track per file
        file_comments = []
        file_severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}

        for comment in comments:
            if not isinstance(comment, dict):
                continue

            line = comment.get("line")
            severity = comment.get("severity", "LOW")
            category = comment.get("category", "GENERAL")
            body = comment.get("body", "")

            if line and body:
                emoji = {
                    "CRITICAL": "🔴",
                    "HIGH": "🟠",
                    "MEDIUM": "🟡",
                    "LOW": "🔵",
                }.get(severity, "💡")
                comment_body = f"{emoji} **{severity}** | {category}\n\n{body}"

                try:
                    pr.create_review_comment(
                        body=comment_body,
                        commit=repo.get_commit(commit_sha),
                        path=filename,
                        line=int(line),
                    )
                    all_inline_comments.append(
                        {"file": filename, "severity": severity, "category": category}
                    )
                    severity_counts[severity] += 1
                    file_severity_counts[severity] += 1
                    file_comments.append(f"{emoji} {severity} ({category})")
                    print(f"  ✓ Inline: {filename}:{line}")
                except Exception as e:
                    print(f"  ✗ Inline failed {filename}:{line} - {e}")

        # File summary
        if file_comments:
            file_summary = f"""## 📁 {filename} Review

**Issues Found:** {", ".join(file_comments)}

**Breakdown:**
- 🔴 Critical: {file_severity_counts["CRITICAL"]}
- 🟠 High: {file_severity_counts["HIGH"]}
- 🟡 Medium: {file_severity_counts["MEDIUM"]}
- 🔵 Low: {file_severity_counts["LOW"]}

Review inline comments above for details."""
            pr.create_issue_comment(file_summary)
        else:
            pr.create_issue_comment(f"## ✅ {filename}\n\nNo issues found. Looks solid!")

        time.sleep(1)

    except Exception as e:
        print(f"Error for {filename}: {e}")
        pr.create_issue_comment(f"## ❌ {filename}\n\nReview error: {str(e)}")
        file_errors.append(filename)

# ==== PR-wide summary ====
print(f"\nTotal inline comments: {len(all_inline_comments)}")

if len(all_inline_comments) == 0 and len(file_errors) == 0:
    pr.create_issue_comment(
        "## 🎉 Full PR Review\n\n**APPROVED** - No issues across all files!"
    )
elif len(file_errors) > 0:
    pr.create_issue_comment(
        f"## ⚠️ Full PR Review Incomplete\n\n"
        f"Some files could not be reviewed due to API errors or rate limits.\n\n"
        f"**Unreviewed files:** {', '.join(file_errors)}"
    )
else:
    critical_high = severity_counts["CRITICAL"] + severity_counts["HIGH"]
    if severity_counts["CRITICAL"] > 0:
        status = "🚨 CRITICAL ISSUES"
        message = "Fix criticals before merge."
    elif critical_high > 0:
        status = "⚠️ NEEDS CHANGES"
        message = "Address high-priority inline comments."
    else:
        status = "ℹ️ SUGGESTIONS"
        message = "Minor tweaks recommended."

    overall_summary = f"""## 📊 PR-Wide Summary: {status}

{message}

**Totals:**
- 🔴 Critical: {severity_counts["CRITICAL"]}
- 🟠 High: {severity_counts["HIGH"]}
- 🟡 Medium: {severity_counts["MEDIUM"]}
- 🔵 Low: {severity_counts["LOW"]}

{len(all_inline_comments)} inline comments posted. See file-specific sections above."""
    pr.create_issue_comment(overall_summary)

print("✅ File-by-file review complete + PR summary posted!")
