import os
import json
import requests
from github import Github
import time  # For retries

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

def call_openai(prompt, max_tokens=1000, retries=3):
    """Helper with retries for rate limits"""
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
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
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
    
    # File-specific prompt
    file_prompt = f"""
Review this file: {filename}

Patch:
{patch}

INSTRUCTIONS:
1. Review carefully for bugs, security, performance, code quality.
2. Be specific: exact problem + solution.
3. Use patch @@ headers for line context (e.g., @@ -10,5 +10,6 @@ means changes around original line 10).
4. Return ONLY valid JSON array:
[
  {{
    "line": 45,  // Original file line number
    "severity": "HIGH",
    "category": "BUG",
    "body": "Specific issue (2-3 sentences max)"
  }}
]

RULES:
- "line": Original file line (from patch context).
- "severity": CRITICAL / HIGH / MEDIUM / LOW
- "category": SECURITY / BUG / PERFORMANCE / MAINTAINABILITY / STYLE
- If no issues: return []
- NO text outside JSON.
"""
    
    try:
        response = call_openai(file_prompt, max_tokens=800)  # Smaller for single file
        content = response["choices"][0]["message"]["content"].strip()
        
        # Clean & parse JSON (robust)
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
        
        # Post inline comments
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
                    all_inline_comments.append({"file": filename, "severity": severity, "category": category})
                    severity_counts[severity] += 1
                    file_severity_counts[severity] += 1
                    file_comments.append(f"{emoji} {severity} ({category})")
                    print(f"  ✓ Inline: {filename}:{line}")
                except Exception as e:
                    print(f"  ✗ Inline failed {filename}:{line} - {e}")
        
        # Post file-specific summary comment (grouped)
        if file_comments:
            file_summary = f"""## 📁 {filename} Review

**Issues Found:** {', '.join(file_comments)}

**Breakdown:**
- 🔴 Critical: {file_severity_counts['CRITICAL']}
- 🟠 High: {file_severity_counts['HIGH']}
- 🟡 Medium: {file_severity_counts['MEDIUM']}
- 🔵 Low: {file_severity_counts['LOW']}

Review inline comments above for details."""
            
            pr.create_issue_comment(file_summary)
        else:
            # Optional: Post "looks good" per file
            pr.create_issue_comment(f"## ✅ {filename}\n\nNo issues found. Looks solid!")
            
        time.sleep(1)  # Rate limit buffer
        
    except json.JSONDecodeError as e:
        print(f"JSON parse error for {filename}: {e}. Skipping.")
        pr.create_issue_comment(f"## ⚠️ {filename}\n\nReview failed—check logs. Patch too complex?")
    except Exception as e:
        print(f"Error for {filename}: {e}")
        pr.create_issue_comment(f"## ❌ {filename}\n\nReview error: {str(e)}")

# Overall summary
print(f"\nTotal inline comments: {len(all_inline_comments)}")

if len(all_inline_comments) == 0:
    pr.create_issue_comment("## 🎉 Full PR Review\n\n**APPROVED** - No issues across all files!")
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

print("✅ File-by-file review complete!")
