import os
import json
import requests
from github import Github
import time

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
last_comment_id = None

def call_openai(prompt, max_tokens=600, retries=3):  # Reduced tokens
    for attempt in range(retries):
        try:
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are an expert code reviewer. Review ONLY this one file. Return ONLY a valid JSON array of issues. Be precise on lines from patch context."},
                    {"role": "user", "content": prompt},
                ],
                "max_completion_tokens": max_tokens,
            }
            headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
            response = requests.post(OPENAI_URL, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise e

# Collect files
files_data = [{"filename": f.filename, "patch": f.patch} for f in pr.get_files() if f.patch]
print(f"Processing {len(files_data)} files separately...")

for idx, file_data in enumerate(files_data):
    filename = file_data["filename"]
    patch = file_data["patch"]
    
    file_prompt = f"""File: {filename}

Patch:
{patch}

Review ONLY this file for bugs/security/performance/quality. Use @@ lines for context (e.g., @@ -10 +10 @@ = line 10).

Return ONLY JSON array:
[
  {{"line": 45, "severity": "HIGH", "category": "BUG", "body": "Issue desc (2-3 sentences)"}}
]

- line: Original file line from patch.
- severity: CRITICAL/HIGH/MEDIUM/LOW
- category: SECURITY/BUG/PERFORMANCE/MAINTAINABILITY/STYLE
- No issues? Empty [].
- NO other text/JSON."""

    try:
        response = call_openai(file_prompt)
        content = response["choices"][0]["message"]["content"].strip()
        
        # Robust JSON extract
        content = content.replace("```json", "").replace("```", "").strip()
        if not content.startswith("["):
            start = content.find("[")
            end = content.rfind("]") + 1
            if start != -1 and end > start:
                content = content[start:end]
            else:
                content = "[]"  # Fallback to empty
        
        comments = json.loads(content)
        print(f"File {filename}: {len(comments)} issues parsed")
        
        # Inlines & counts
        file_comments = []
        file_severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        
        for comment in comments:
            if not isinstance(comment, dict) or not comment.get("body") or not comment.get("line"):
                continue
            
            line = int(comment["line"])
            severity = comment.get("severity", "LOW").upper()
            category = comment.get("category", "GENERAL").upper()
            body = comment["body"]
            
            emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵"}.get(severity, "💡")
            comment_body = f"{emoji} **{severity}** | {category}\n\n{body}"
            
            try:
                review_comment = pr.create_review_comment(
                    body=comment_body, commit=repo.get_commit(commit_sha), path=filename, line=line
                )
                all_inline_comments.append({"file": filename, "severity": severity, "category": category})
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
                file_severity_counts[severity] += 1
                file_comments.append(f"{emoji} {severity} ({category}) on line {line}")
                print(f"  ✓ Inline posted: {filename}:{line}")
            except Exception as e:
                print(f"  ✗ Inline failed: {e}")
        
        # ALWAYS post per-file summary (even if no issues)
        if file_comments:
            file_status = "🚨 CRITICAL" if file_severity_counts["CRITICAL"] > 0 else "⚠️ CHANGES NEEDED" if (file_severity_counts["HIGH"] + file_severity_counts["MEDIUM"]) > 0 else "ℹ️ MINOR"
            issues_list = ', '.join(file_comments[:5]) + ('...' if len(file_comments) > 5 else '')
            summary_body = f"""## 📁 {filename} | {file_status}

**Quick Issues:** {len(file_comments)} total
- {issues_list}

**Breakdown:**
- 🔴 Critical: {file_severity_counts['CRITICAL']}
- 🟠 High: {file_severity_counts['HIGH']}
- 🟡 Medium: {file_severity_counts['MEDIUM']}
- 🔵 Low: {file_severity_counts['LOW']}

See inline comments in the diff for fixes."""
        else:
            summary_body = f"""## ✅ {filename} | Looks Good!

No issues found in this file. Solid changes! 🚀"""
        
        try:
            issue_comment = pr.create_issue_comment(summary_body + (f"\n> {last_comment_id}" if last_comment_id else ""))
            last_comment_id = issue_comment.id
            print(f"  ✓ Posted file summary for {filename}")
        except Exception as e:
            print(f"  ✗ File summary failed for {filename}: {e}")
        
        time.sleep(1)
        
    except json.JSONDecodeError as e:
        print(f"JSON error {filename}: {e}")
        error_body = f"""## ⚠️ {filename} Review Failed

JSON parse issue—check patch size. Raw GPT output: {content[:200]}..."""
        try:
            issue_comment = pr.create_issue_comment(error_body)
            last_comment_id = issue_comment.id
            print(f"  ✓ Posted error summary for {filename}")
        except Exception as e2:
            print(f"  ✗ Error summary failed: {e2}")
    except Exception as e:
        print(f"Error {filename}: {e}")

# ALWAYS post overall summary (enhanced with suggestions)
total_issues = len(all_inline_comments)
print(f"\nTotal inlines posted: {total_issues}")

# Quick final GPT call for holistic suggestions (if issues exist)
suggestions = []
if total_issues > 0:
    agg_prompt = f"""Summarize top 3-5 improvements for this PR based on {total_issues} issues across {len(files_data)} files. Focus on security/bugs/performance. Return ONLY a numbered list (1-5 lines max), e.g.:
1. Use env vars for hard-coded secrets.
2. Parameterize SQL queries.
Be concise and actionable."""
    
    try:
        response = call_openai(agg_prompt, max_tokens=200)
        content = response["choices"][0]["message"]["content"].strip()
        suggestions = [line.strip() for line in content.split('\n') if line.strip() and line[0].isdigit()]
        print(f"  ✓ Got {len(suggestions)} suggestions from GPT")
    except Exception as e:
        print(f"  ✗ Suggestions failed: {e} (using fallback)")
        suggestions = ["1. Review all inline comments for fixes.", "2. Add unit tests for new features.", "3. Run security scans (e.g., Snyk)."]  # Fallback

if total_issues == 0:
    overall_body = f"""## 🎉 PR Fully Reviewed

**APPROVED** - No issues across {len(files_data)} files! Great work. Merge confidently. 🚀

**Quick Tips:** Test edge cases and add docs for future-proofing."""
else:
    critical_high = severity_counts.get("CRITICAL", 0) + severity_counts.get("HIGH", 0)
    status = "🚨 BLOCKING CRITICALS" if severity_counts.get("CRITICAL", 0) > 0 else "⚠️ PRIORITY FIXES" if critical_high > 0 else "💡 IMPROVEMENTS"
    
    suggestions_str = '\n'.join(suggestions[:5]) if suggestions else "Review per-file summaries for details."
    
    overall_body = f"""## 📊 Full PR Summary | {status}

**Totals ({total_issues} issues in {len(files_data)} files):**
- 🔴 Critical: {severity_counts.get('CRITICAL', 0)} | 🟠 High: {severity_counts.get('HIGH', 0)}
- 🟡 Medium: {severity_counts.get('MEDIUM', 0)} | 🔵 Low: {severity_counts.get('LOW', 0)}

**Top Suggestions:**
{suggestions_str}

Prioritize criticals before merge. Check inlines above!"""

try:
    pr.create_issue_comment(overall_body + (f"\n> {last_comment_id}" if last_comment_id else ""))
    print("  ✓ Posted enhanced overall summary")
except Exception as e:
    print(f"  ✗ Overall summary failed: {e} - {overall_body[:100]}...")  # Log body for debug

print(f"✅ Complete! Enhanced summary with {len(suggestions)} suggestions added.")
