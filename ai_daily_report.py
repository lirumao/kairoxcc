#!/usr/bin/env python3
"""
AI Daily Report Generator
Automatically fetches latest AI news from company blogs and Twitter/X creators,
generates an HTML report, and uploads to GitHub.
"""

import os
import sys
import json
import re
import subprocess
import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

# Try to import requests, install if not available
try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Installing required packages...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "-q"])
    import requests
    from bs4 import BeautifulSoup


# ============== Configuration ==============
REPO_OWNER = "lirumao"
REPO_NAME = "kairoxcc"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPORTS_DIR = "reports"

# Sources to monitor
SOURCES = {
    "anthropic": {
        "name": "Anthropic",
        "url": "https://www.anthropic.com/news",
        "type": "blog",
        "rss": "https://www.anthropic.com/rss.xml"
    },
    "openai": {
        "name": "OpenAI",
        "url": "https://openai.com/blog",
        "type": "blog",
        "rss": "https://openai.com/blog/rss.xml"
    },
    "deepmind": {
        "name": "Google DeepMind",
        "url": "https://deepmind.google/discover/blog/",
        "type": "blog",
        "rss": "https://deepmind.google/discover/blog/rss.xml"
    },
    "google_ai": {
        "name": "Google AI",
        "url": "https://ai.googleblog.com",
        "type": "blog",
        "rss": "https://ai.googleblog.com/feeds/posts/default"
    },
    "microsoft_research": {
        "name": "Microsoft Research",
        "url": "https://www.microsoft.com/en-us/research/research-area/artificial-intelligence/",
        "type": "blog",
        "rss": "https://www.microsoft.com/en-us/research/feed/"
    },
    "ai2": {
        "name": "Allen Institute for AI",
        "url": "https://allenai.org/blog",
        "type": "blog",
        "rss": "https://blog.allenai.org/feed"
    },
    "huggingface": {
        "name": "Hugging Face",
        "url": "https://huggingface.co/blog",
        "type": "blog",
        "rss": "https://huggingface.co/blog/feed.xml"
    },
    "papers_with_code": {
        "name": "Papers with Code",
        "url": "https://paperswithcode.com",
        "type": "blog",
        "rss": "https://paperswithcode.com/rss"
    }
}

# Twitter/X creators to monitor (using nitter or similar)
TWITTER_CREATORS = [
    "@ylecun",
    "@karpathy",
    "@goodfellow_ian",
    "@hardmaru",
    "@DrJimFan",
    "@_jasonwei",
    "@bindureddy",
    "@EMostaque",
    "@sama",
    "@gdb",
    "@mer__edith",
    "@lilianweng"
]


# ============== Content Fetchers ==============

def fetch_rss_feed(url, max_items=5):
    """Fetch and parse RSS feed."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse RSS XML
        soup = BeautifulSoup(response.content, "xml")
        items = []
        
        for item in soup.find_all("item")[:max_items]:
            title = item.find("title")
            link = item.find("link")
            pub_date = item.find("pubDate")
            description = item.find("description")
            
            items.append({
                "title": title.text.strip() if title else "No title",
                "url": link.text.strip() if link else "",
                "date": pub_date.text.strip() if pub_date else "",
                "summary": description.text.strip()[:300] + "..." if description and len(description.text) > 300 
                          else (description.text.strip() if description else "")
            })
        
        return items
    except Exception as e:
        print(f"Error fetching RSS from {url}: {e}")
        return []


def fetch_blog_page(url, selector, max_items=5):
    """Fetch blog page and extract articles."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        articles = []
        
        # Try to find article links
        article_links = soup.find_all("a", href=re.compile(r"(blog|news|article|post)"))[:max_items * 2]
        
        for link in article_links[:max_items]:
            href = link.get("href", "")
            if href.startswith("/"):
                href = urljoin(url, href)
            elif not href.startswith("http"):
                href = urljoin(url, href)
            
            title = link.get_text(strip=True)
            if title and len(title) > 10:
                articles.append({
                    "title": title,
                    "url": href,
                    "date": "",
                    "summary": ""
                })
        
        return articles
    except Exception as e:
        print(f"Error fetching blog page {url}: {e}")
        return []


def fetch_all_sources():
    """Fetch content from all configured sources."""
    all_content = {}
    
    for source_id, source_info in SOURCES.items():
        print(f"Fetching from {source_info['name']}...")
        
        # Try RSS first
        if "rss" in source_info:
            items = fetch_rss_feed(source_info["rss"], max_items=5)
            if items:
                all_content[source_id] = {
                    "name": source_info["name"],
                    "items": items
                }
                continue
        
        # Fallback to blog page scraping
        items = fetch_blog_page(source_info["url"], "article", max_items=5)
        if items:
            all_content[source_id] = {
                "name": source_info["name"],
                "items": items
            }
    
    return all_content


# ============== HTML Report Generator ==============

def generate_html_report(content_data, date_str):
    """Generate a beautiful HTML report from the fetched content."""
    
    html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Daily Report - {date_str}</title>
    <style>
        :root {{
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text: #1e293b;
            --text-secondary: #64748b;
            --border: #e2e8f0;
            --shadow: 0 1px 3px rgba(0,0,0,0.1);
            --shadow-lg: 0 10px 25px rgba(0,0,0,0.1);
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }}
        
        header {{
            text-align: center;
            padding: 3rem 0;
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
            margin-bottom: 2rem;
            border-radius: 16px;
            box-shadow: var(--shadow-lg);
        }}
        
        header h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            font-weight: 700;
        }}
        
        header .date {{
            font-size: 1.1rem;
            opacity: 0.9;
        }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        
        .stat-card {{
            background: var(--card-bg);
            padding: 1.5rem;
            border-radius: 12px;
            box-shadow: var(--shadow);
            text-align: center;
        }}
        
        .stat-card .number {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary);
        }}
        
        .stat-card .label {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}
        
        .source-section {{
            background: var(--card-bg);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: var(--shadow);
        }}
        
        .source-header {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 1rem;
            padding-bottom: 0.75rem;
            border-bottom: 2px solid var(--border);
        }}
        
        .source-icon {{
            width: 40px;
            height: 40px;
            background: var(--primary);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 700;
            font-size: 1.2rem;
        }}
        
        .source-title {{
            font-size: 1.25rem;
            font-weight: 600;
        }}
        
        .article-list {{
            list-style: none;
        }}
        
        .article-item {{
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 0.75rem;
            transition: all 0.2s;
            border: 1px solid transparent;
        }}
        
        .article-item:hover {{
            background: #f1f5f9;
            border-color: var(--border);
        }}
        
        .article-title {{
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--primary);
            text-decoration: none;
            display: block;
            margin-bottom: 0.25rem;
        }}
        
        .article-title:hover {{
            text-decoration: underline;
        }}
        
        .article-meta {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }}
        
        .article-summary {{
            font-size: 0.9rem;
            color: var(--text-secondary);
            line-height: 1.5;
        }}
        
        .empty-state {{
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
        }}
        
        footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}
        
        .tag {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            background: #dbeafe;
            color: var(--primary);
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 500;
            margin-right: 0.5rem;
        }}
        
        @media (max-width: 768px) {{
            .container {{
                padding: 1rem;
            }}
            
            header h1 {{
                font-size: 1.75rem;
            }}
            
            .stats {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>AI Daily Report</h1>
            <div class="date">{date_str}</div>
        </header>
        
        <div class="stats">
            <div class="stat-card">
                <div class="number">{len(content_data)}</div>
                <div class="label">Sources</div>
            </div>
            <div class="stat-card">
                <div class="number">{sum(len(v['items']) for v in content_data.values())}</div>
                <div class="label">Articles</div>
            </div>
        </div>
"""
    
    # Add content sections
    for source_id, source_data in content_data.items():
        items = source_data.get("items", [])
        name = source_data.get("name", source_id)
        
        html_template += f"""
        <section class="source-section">
            <div class="source-header">
                <div class="source-icon">{name[0]}</div>
                <h2 class="source-title">{name}</h2>
            </div>
            <ul class="article-list">
"""
        
        if items:
            for item in items:
                title = item.get("title", "Untitled")
                url = item.get("url", "#")
                date = item.get("date", "")
                summary = item.get("summary", "")
                
                html_template += f"""
                <li class="article-item">
                    <a href="{url}" class="article-title" target="_blank" rel="noopener">{title}</a>
                    {f'<div class="article-meta">{date}</div>' if date else ''}
                    {f'<div class="article-summary">{summary}</div>' if summary else ''}
                </li>
"""
        else:
            html_template += """
                <li class="empty-state">
                    No new articles found
                </li>
"""
        
        html_template += """
            </ul>
        </section>
"""
    
    # Close HTML
    html_template += f"""
        <footer>
            <p>Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | AI Daily Report</p>
        </footer>
    </div>
</body>
</html>"""
    
    return html_template


# ============== GitHub Upload ==============

def upload_to_github(file_path, repo_owner, repo_name, github_token, branch="main"):
    """Upload file to GitHub repository."""
    try:
        # Read file content
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # GitHub API endpoint
        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{file_path}"
        
        # Check if file already exists
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        import base64
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        
        # Get existing file SHA if it exists
        response = requests.get(api_url, headers=headers)
        sha = None
        if response.status_code == 200:
            sha = response.json().get("sha")
        
        # Prepare data
        data = {
            "message": f"Update AI Daily Report - {datetime.datetime.now().strftime('%Y-%m-%d')}",
            "content": content_b64,
            "branch": branch
        }
        
        if sha:
            data["sha"] = sha
        
        # Upload file
        response = requests.put(api_url, headers=headers, json=data)
        response.raise_for_status()
        
        print(f"Successfully uploaded {file_path} to GitHub")
        return True
        
    except Exception as e:
        print(f"Error uploading to GitHub: {e}")
        return False


def push_via_git(file_path, repo_url, branch="main"):
    """Push file to GitHub using git commands."""
    try:
        # Configure git
        subprocess.run(["git", "config", "user.email", "ai-reporter@example.com"], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "AI Reporter"], check=True, capture_output=True)
        
        # Add and commit
        subprocess.run(["git", "add", file_path], check=True, capture_output=True)
        
        # Check if there are changes to commit
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
        if result.returncode == 0:
            print("No changes to commit")
            return True
        
        subprocess.run(
            ["git", "commit", "-m", f"AI Daily Report - {datetime.datetime.now().strftime('%Y-%m-%d')}"],
            check=True,
            capture_output=True
        )
        
        # Push
        subprocess.run(["git", "push", "origin", branch], check=True, capture_output=True)
        
        print(f"Successfully pushed {file_path} to GitHub via git")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error pushing via git: {e}")
        print(f"stderr: {e.stderr.decode() if e.stderr else 'N/A'}")
        return False
    except Exception as e:
        print(f"Error pushing via git: {e}")
        return False


# ============== Main ==============

def main():
    """Main function to generate and upload daily report."""
    print("=" * 60)
    print("AI Daily Report Generator")
    print("=" * 60)
    
    # Get current date
    today = datetime.datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    date_display = today.strftime("%Y年%m月%d日")
    
    print(f"\nDate: {date_display}")
    print("Fetching content from sources...\n")
    
    # Fetch content
    content_data = fetch_all_sources()
    
    if not content_data:
        print("Warning: No content fetched from any source")
    
    # Generate HTML report
    print("\nGenerating HTML report...")
    html_content = generate_html_report(content_data, date_display)
    
    # Save report
    report_filename = f"{REPORTS_DIR}/report_{date_str}.html"
    os.makedirs(REPORTS_DIR, exist_ok=True)
    
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"Report saved to: {report_filename}")
    
    # Also save as index.html for easy viewing
    index_path = f"{REPORTS_DIR}/index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    # Upload to GitHub
    print("\nUploading to GitHub...")
    
    # Try git push first (more reliable)
    success = push_via_git(report_filename, f"https://github.com/{REPO_OWNER}/{REPO_NAME}.git")
    
    if not success and GITHUB_TOKEN:
        # Fallback to API upload
        success = upload_to_github(report_filename, REPO_OWNER, REPO_NAME, GITHUB_TOKEN)
    
    if success:
        print(f"\nReport uploaded successfully!")
        print(f"View at: https://{REPO_OWNER}.github.io/{REPO_NAME}/{report_filename}")
    else:
        print("\nFailed to upload report. Please check your credentials.")
        return 1
    
    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
