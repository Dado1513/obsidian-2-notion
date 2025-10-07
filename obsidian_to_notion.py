#!/usr/bin/env python3
"""
Migrate Obsidian folder to Notion - Fixed for single folder migration
"""

import os
import argparse
import re
from pathlib import Path
from notion_client import Client
from notion_client.errors import APIResponseError
import mistune
import time
import mimetypes
import hashlib
import urllib.parse


def upload_to_github(file_path, config, unique_path):
    """Upload to GitHub repository with unique path."""
    try:
        import base64
        import requests
        
        path_obj = Path(file_path)
        if not path_obj.exists():
            print(f"  File not found: {file_path}")
            return None
        
        if not path_obj.is_file():
            print(f"  Not a file (is directory): {file_path}")
            return None
        
        file_name = path_obj.name
        file_size = os.path.getsize(file_path)
        
        if file_size > 100 * 1024 * 1024:
            print(f"  File too large for GitHub (>100MB): {file_size / 1024 / 1024:.1f}MB")
            return None
        
        with open(file_path, 'rb') as f:
            content = base64.b64encode(f.read()).decode('utf-8')
        
        # Sanitize paths for GitHub - KEEP URL ENCODING
        safe_unique_path = unique_path.replace('\\', '/').strip('./')
        if safe_unique_path == '' or safe_unique_path == '.':
            safe_unique_path = 'root'
        
        # URL encode each part of the path separately
        path_parts = safe_unique_path.split('/')
        encoded_path_parts = [urllib.parse.quote(part, safe='') for part in path_parts]
        safe_unique_path = '/'.join(encoded_path_parts)
        
        # URL encode the filename
        safe_file_name = urllib.parse.quote(file_name, safe='')
        
        # Build the path for GitHub API
        github_api_path = f"{config.get('folder', 'uploads')}/{safe_unique_path}/{safe_file_name}".replace('//', '/')
        
        url = f"https://api.github.com/repos/{config['repo_owner']}/{config['repo_name']}/contents/{github_api_path}"
        
        headers = {
            'Authorization': f"token {config['github_token']}",
            'Accept': 'application/vnd.github.v3+json'
        }
        
        data = {
            'message': f'Upload {file_name}',
            'content': content,
            'branch': config.get('branch', 'main')
        }
        
        response = requests.put(url, headers=headers, json=data, timeout=60)
        
        if response.status_code in [200, 201]:
            # Return raw URL with proper encoding - use just 'main', not 'refs/heads/main'
            raw_url = f"https://raw.githubusercontent.com/{config['repo_owner']}/{config['repo_name']}/{config.get('branch', 'main')}/{github_api_path}"
            print(f"  Uploaded to: {raw_url}")
            return raw_url
        elif response.status_code == 422:
            print(f"  File already exists")
            raw_url = f"https://raw.githubusercontent.com/{config['repo_owner']}/{config['repo_name']}/{config.get('branch', 'main')}/{github_api_path}"
            return raw_url
        else:
            print(f"  GitHub error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"  GitHub error: {e}")
        import traceback
        traceback.print_exc()
        return None

# def upload_to_github(file_path, config, unique_path):
#     """Upload to GitHub repository with unique path."""
#     try:
#         import base64
#         import requests
        
#         path_obj = Path(file_path)
#         if not path_obj.exists():
#             print(f"  File not found: {file_path}")
#             return None
        
#         if not path_obj.is_file():
#             print(f"  Not a file (is directory): {file_path}")
#             return None
        
#         file_name = path_obj.name
#         file_size = os.path.getsize(file_path)
        
#         if file_size > 100 * 1024 * 1024:
#             print(f"  File too large for GitHub (>100MB): {file_size / 1024 / 1024:.1f}MB")
#             return None
        
#         with open(file_path, 'rb') as f:
#             content = base64.b64encode(f.read()).decode('utf-8')
        
#         # Sanitize paths for GitHub
#         safe_unique_path = unique_path.replace('\\', '/').strip('./')
#         if safe_unique_path == '' or safe_unique_path == '.':
#             safe_unique_path = 'root'
        
#         safe_file_name = urllib.parse.quote(file_name)
#         path = f"{config.get('folder', 'uploads')}/{safe_unique_path}/{safe_file_name}".replace('//', '/')
        
#         url = f"https://api.github.com/repos/{config['repo_owner']}/{config['repo_name']}/contents/{path}"
        
#         headers = {
#             'Authorization': f"token {config['github_token']}",
#             'Accept': 'application/vnd.github.v3+json'
#         }
        
#         data = {
#             'message': f'Upload {file_name}',
#             'content': content,
#             'branch': config.get('branch', 'main')
#         }
        
#         response = requests.put(url, headers=headers, json=data, timeout=60)
        
#         if response.status_code in [200, 201]:
#             raw_url = f"https://raw.githubusercontent.com/{config['repo_owner']}/{config['repo_name']}/{config.get('branch', 'main')}/{path}"
#             return raw_url
#         elif response.status_code == 422:
#             print(f"  File already exists")
#             raw_url = f"https://raw.githubusercontent.com/{config['repo_owner']}/{config['repo_name']}/{config.get('branch', 'main')}/{path}"
#             return raw_url
#         else:
#             print(f"  GitHub error: {response.status_code}")
#             return None
            
#     except Exception as e:
#         print(f"  GitHub error: {e}")
#         return None


class FileUploader:
    """Unified file uploader supporting multiple providers."""
    
    def __init__(self, provider, config):
        self.provider = provider
        self.config = config
        self.cache = {}
        self.stats = {
            'images': 0,
            'pdfs': 0,
            'other': 0,
            'failed': 0,
            'skipped_dirs': 0
        }
        
        self.uploaders = {
            'github': upload_to_github,
        }
        
        if provider not in self.uploaders:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def upload(self, file_path, unique_path):
        """Upload file and return URL."""
        path_obj = Path(file_path)
        
        if not path_obj.exists():
            print(f"  File does not exist: {file_path}")
            self.stats['failed'] += 1
            return None
        
        if not path_obj.is_file():
            print(f"  Skipping directory: {file_path}")
            self.stats['skipped_dirs'] += 1
            return None
        
        cache_key = self._get_cache_key(file_path)
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        url = self.uploaders[self.provider](file_path, self.config, unique_path)
        
        if url:
            self.cache[cache_key] = url
            
            file_ext = Path(file_path).suffix.lower()
            if file_ext == '.pdf':
                self.stats['pdfs'] += 1
            elif file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp']:
                self.stats['images'] += 1
            else:
                self.stats['other'] += 1
        else:
            self.stats['failed'] += 1
        
        return url
    
    def _get_cache_key(self, file_path):
        """Generate unique cache key based on file content."""
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            return f"{file_path}_{file_hash}"
        except:
            return file_path
    
    def print_stats(self):
        """Print upload statistics."""
        total = self.stats['images'] + self.stats['pdfs'] + self.stats['other']
        print(f"\nUpload Statistics:")
        print(f"   Images:         {self.stats['images']}")
        print(f"   PDFs:           {self.stats['pdfs']}")
        print(f"   Other:          {self.stats['other']}")
        print(f"   Failed:         {self.stats['failed']}")
        print(f"   Skipped (dirs): {self.stats['skipped_dirs']}")
        print(f"   Total:          {total}")


def is_url(path):
    """Check if path is a URL."""
    from urllib.parse import urlparse
    try:
        result = urlparse(path)
        return all([result.scheme, result.netloc])
    except:
        return False


def decode_url_path(path):
    """Decode URL-encoded path (e.g., %20 -> space)."""
    return urllib.parse.unquote(path)


def resolve_relative_path(file_path, markdown_file_path, vault_dir, debug=False):
    """
    Resolve relative file path based on markdown file location.
    Fixed for single-folder migration.
    """
    if is_url(file_path):
        return file_path
    
    file_path = decode_url_path(file_path).strip()
    
    if not file_path:
        return None
    
    if debug:
        print(f"    Resolving: {file_path}")
        print(f"    From MD file: {markdown_file_path}")
        print(f"    Vault dir: {vault_dir}")
    
    md_dir = Path(markdown_file_path).parent
    vault_path = Path(vault_dir).resolve()
    
    # Check if we're in single-folder mode (vault_dir == markdown directory)
    is_single_folder = md_dir.resolve() == vault_path
    
    if debug:
        print(f"    Single folder mode: {is_single_folder}")
    
    # Strategy 1: Relative to markdown file (works for both modes)
    relative_path = md_dir / file_path
    if debug:
        print(f"    Try 1 (relative to MD): {relative_path}")
    if relative_path.exists() and relative_path.is_file():
        if debug:
            print(f"    ✓ Found!")
        return str(relative_path.resolve())
    
    # If single folder mode, only search within this folder
    if is_single_folder:
        # Try common attachment folders in same directory
        attachment_folders = [
            'attachments', 'Attachments',
            'assets', 'Assets',
            'files', 'Files',
            'images', 'Images',
            'pdfs', 'PDFs'
        ]
        
        file_name = Path(file_path).name
        for folder in attachment_folders:
            folder_path = md_dir / folder / file_name
            if debug:
                print(f"    Try (single folder - {folder}): {folder_path}")
            if folder_path.exists() and folder_path.is_file():
                if debug:
                    print(f"    ✓ Found!")
                return str(folder_path.resolve())
        
        # Search recursively in this folder only
        if debug:
            print(f"    Try (recursive in folder): searching for {file_name}")
        try:
            for item in md_dir.rglob(file_name):
                if item.is_file():
                    if debug:
                        print(f"    ✓ Found: {item}")
                    return str(item.resolve())
        except:
            pass
    else:
        # Normal vault mode - search from vault root
        vault_relative = vault_path / file_path
        if debug:
            print(f"    Try 2 (relative to vault): {vault_relative}")
        if vault_relative.exists() and vault_relative.is_file():
            if debug:
                print(f"    ✓ Found!")
            return str(vault_relative.resolve())
        
        # Continue with other strategies...
    
    if debug:
        print(f"    ✗ Not found")
    
    return None


def get_unique_path_for_file(file_path, vault_dir):
    """Generate unique path for file based on its location in vault."""
    try:
        file_path = Path(file_path).resolve()
        vault_dir = Path(vault_dir).resolve()
        
        # Get relative path from vault root
        try:
            rel_path = file_path.relative_to(vault_dir)
            parent_path = str(rel_path.parent).replace('\\', '/')
            
            if parent_path == '.' or parent_path == '':
                return 'root'
            
            return parent_path
        except ValueError:
            # File is outside vault, use hash
            return hashlib.md5(str(file_path).encode()).hexdigest()[:8]
    except:
        return 'root'


def convert_obsidian_links(content, vault_dir, page_map):
    """Convert Obsidian syntax to standard markdown."""
    
    # Convert Obsidian embeds ![[file]] to ![](file)
    content = re.sub(
        r'!\[\[([^\]]+)\]\]',
        r'![](\1)',
        content
    )
    
    # Convert wiki-links [[Page]] or [[Page|Text]]
    def replace_wiki_link(match):
        link_content = match.group(1)
        if '|' in link_content:
            page_name, display_text = link_content.split('|', 1)
        else:
            page_name = display_text = link_content
        
        if page_name in page_map:
            return f'[{display_text}]({page_map[page_name]})'
        else:
            return f'{display_text}'
    
    # Only convert [[...]] (Obsidian wiki-links), not regular [text](url) links
    content = re.sub(r'\[\[([^\]]+)\]\]', replace_wiki_link, content)
    
    return content


class ObsidianToNotionConverter(mistune.HTMLRenderer):
    """Convert Obsidian markdown to Notion blocks."""
    
    def __init__(self, vault_dir, markdown_file_path, uploader=None, debug=False):
        super().__init__()
        self.blocks = []
        self.vault_dir = vault_dir
        self.markdown_file_path = markdown_file_path
        self.uploader = uploader
        self.current_list_type = None
        self.debug = debug
        
    def heading(self, text, level, **kwargs):
        heading_types = {1: "heading_1", 2: "heading_2", 3: "heading_3"}
        if level > 3:
            level = 3
        
        block = {
            "object": "block",
            "type": heading_types[level],
            heading_types[level]: {
                "rich_text": [{"type": "text", "text": {"content": text[:2000]}}]
            }
        }
        self.blocks.append(block)
        return ""
    
    def paragraph(self, text, **kwargs):
        if not text.strip():
            return ""
        
        block = {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": self._parse_rich_text(text)}
        }
        self.blocks.append(block)
        return ""
    
    def block_code(self, code, info=None, **kwargs):
        language = info.strip() if info else "plain text"
        chunks = [code[i:i+2000] for i in range(0, len(code), 2000)]
        
        for chunk in chunks:
            block = {
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}],
                    "language": self._map_language(language)
                }
            }
            self.blocks.append(block)
        return ""
    
    def block_quote(self, text, **kwargs):
        block = {
            "object": "block",
            "type": "quote",
            "quote": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}
        }
        self.blocks.append(block)
        return ""
    
    def list(self, text, ordered, depth, **kwargs):
        self.current_list_type = "numbered_list_item" if ordered else "bulleted_list_item"
        return ""
    
    def list_item(self, text, **kwargs):
        list_type = self.current_list_type or "bulleted_list_item"
        block = {
            "object": "block",
            "type": list_type,
            list_type: {"rich_text": self._parse_rich_text(text)}
        }
        self.blocks.append(block)
        return ""

    def image(self, text, url="", title=None, **kwargs):
        """Handle image embeds - src should now be a GitHub URL."""
        # print(url)
        if self.debug:
            print(f"\n=== IMAGE DEBUG ===")
            print(f"  URL: {url}")
            print(f"  URL length: {len(url)}")
            print(f"  URL type: {type(url)}")
            print(f"==================")
        if not url or not url.strip():
            return ""

        # src should now be a GitHub URL
        block = {
            "object": "block",
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": url}
            }
        }
        if text:
            block["image"]["caption"] = [
                {"type": "text", "text": {"content": text[:2000]}}
            ]
        self.blocks.append(block)
        return ""
    
    #def _handle_file(self, src, file_type="file"):
    #    """Handle file upload with relative path resolution."""
    #    if not src or not src.strip():
        #     return None
        
        # if is_url(src):
        #     return src
        
        # decoded_src = decode_url_path(src)
        
        # if self.debug:
        #     print(f"\n  Handling {file_type}: {src}")
        #     if src != decoded_src:
        #         print(f"  Decoded to: {decoded_src}")
        
        # # Resolve relative path
        # file_path = resolve_relative_path(decoded_src, self.markdown_file_path, self.vault_dir, self.debug)
        
        # if file_path and Path(file_path).is_file() and self.uploader:
        #     unique_path = get_unique_path_for_file(file_path, self.vault_dir)
            
        #     file_ext = Path(file_path).suffix.lower()
        #     file_name = Path(file_path).name
            
        #     print(f"  Uploading {file_type} ({file_ext}): {file_name} (from {unique_path})...", end=" ")
            
        #     file_url = self.uploader.upload(file_path, unique_path)
        #     if file_url:
        #         print(f"✓")
        #         return file_url
        #     else:
        #         print("✗")
        # elif not file_path:
        #     if src and src.strip():
        #         print(f"  Warning: File not found: {decoded_src}")
        
        # return None
    
    def _add_missing_file_note(self, src, file_type):
        """Add a note about missing file."""
        block = {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": f"[{file_type} not available: {src}]"},
                        "annotations": {"italic": True, "color": "red"}
                    }
                ]
            }
        }
        self.blocks.append(block)
    
    def link(self, text, link=None, title=None, url=None, **kwargs):
        """Handle links - note mistune v3 has text FIRST, then link."""
        if self.debug:
            print(f"=== LINK DEBUG ===")
            print(f"  text: {repr(text)}")
            print(f"  link: {repr(link)}")
            print(f"  title: {repr(title)}")
            print(f"  url: {repr(url)}")    
            print(f"  kwargs: {kwargs}")
            print(f"==================")
        
        if not url or not url.strip():
            return text or ""
        
        url_lower = url.lower()
        
        if url_lower.endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt')):
            return f"[{text or Path(url).name}]({url})"
        
        return f"[{text or url}]({url})"
    
    def codespan(self, text, **kwargs):
        return f"`{text}`"
    
    def emphasis(self, text, **kwargs):
        return f"*{text}*"
    
    def strong(self, text, **kwargs):
        return f"**{text}**"
    
    def strikethrough(self, text, **kwargs):
        return f"~~{text}~~"
    
    def linebreak(self, **kwargs):
        return "\n"
    
    def newline(self, **kwargs):
        return ""
    
    def thematic_break(self, **kwargs):
        block = {"object": "block", "type": "divider", "divider": {}}
        self.blocks.append(block)
        return ""
    
    def _parse_rich_text(self, text):
        """Parse inline formatting."""
        rich_text = []
        
        # First, extract and replace links with placeholders to avoid interference
        link_map = {}
        link_counter = 0
        
        def save_link(match):
            nonlocal link_counter
            link_text = match.group(1)
            link_url = match.group(2)
            placeholder = f"__LINK_{link_counter}__"
            link_map[placeholder] = (link_text, link_url)
            link_counter += 1
            return placeholder
        
        # Extract links first (not including images which start with !)
        # text = re.sub(r'(?<!\!)\[([^\]]+)\]\(([^)]+)\)', save_link, text)
        # text = re.sub(r'(?<!\!)\[([^\]]+)\]\((.+?)\)(?!\()', save_link, text)
        text = re.sub(r'(?<!\!)\[([^\]]+)\]\(([^)]+\)[^)]*|[^)]+)\)', save_link, text)

        
        # Now process other formatting
        parts = re.split(r'(`[^`]+`)', text)
        
        for part in parts:
            if not part:
                continue
            
            if part.startswith('`') and part.endswith('`'):
                code_text = part[1:-1]
                if code_text:
                    rich_text.append({
                        "type": "text",
                        "text": {"content": code_text[:2000]},
                        "annotations": {"code": True}
                    })
            else:
                current_pos = 0
                # Simplified pattern without links
                pattern = r'(~~[^~]+~~|\*\*[^*]+\*\*|\*[^*]+\*|__LINK_\d+__)'
                
                for match in re.finditer(pattern, part):
                    if match.start() > current_pos:
                        plain = part[current_pos:match.start()]
                        if plain:
                            rich_text.append({"type": "text", "text": {"content": plain[:2000]}})
                    
                    matched_text = match.group(0)
                    
                    if matched_text.startswith('__LINK_'):
                        # Restore link
                        link_text, link_url = link_map[matched_text]
                        if self._is_valid_url(link_url):
                            rich_text.append({
                                "type": "text",
                                "text": {"content": link_text[:2000], "link": {"url": link_url}}
                            })
                        else:
                            # Invalid URL, add as plain text
                            rich_text.append({
                                "type": "text",
                                "text": {"content": f"[{link_text}]({link_url})"[:2000]}
                            })
                    elif matched_text.startswith('~~'):
                        text_content = matched_text[2:-2]
                        rich_text.append({
                            "type": "text",
                            "text": {"content": text_content[:2000]},
                            "annotations": {"strikethrough": True}
                        })
                    elif matched_text.startswith('**'):
                        text_content = matched_text[2:-2]
                        rich_text.append({
                            "type": "text",
                            "text": {"content": text_content[:2000]},
                            "annotations": {"bold": True}
                        })
                    elif matched_text.startswith('*'):
                        text_content = matched_text[1:-1]
                        rich_text.append({
                            "type": "text",
                            "text": {"content": text_content[:2000]},
                            "annotations": {"italic": True}
                        })
                    
                    current_pos = match.end()
                
                if current_pos < len(part):
                    remaining = part[current_pos:]
                    if remaining:
                        rich_text.append({"type": "text", "text": {"content": remaining[:2000]}})
        
        return rich_text if rich_text else [{"type": "text", "text": {"content": ""}}]

    def _is_valid_url(self, url):
        """Validate URL format for Notion."""
        if not url or not url.strip():
            return False
        
        # Remove trailing punctuation that might be part of markdown
        url = url.rstrip(')')
        
        # Check if it's a valid URL structure
        try:
            from urllib.parse import urlparse
            result = urlparse(url)
            # Must have scheme and netloc
            return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
        except:
            return False
    def _map_language(self, language):
        language_map = {
            "py": "python", "python": "python",
            "js": "javascript", "javascript": "javascript",
            "ts": "typescript", "typescript": "typescript",
            "java": "java", "c": "c", "cpp": "c++", "c++": "c++",
            "csharp": "c#", "c#": "c#", "go": "go", "rust": "rust",
            "ruby": "ruby", "php": "php", "swift": "swift",
            "kotlin": "kotlin", "sql": "sql", "shell": "shell",
            "bash": "bash", "powershell": "powershell",
            "yaml": "yaml", "json": "json", "xml": "xml",
            "html": "html", "css": "css", "markdown": "markdown",
        }
        return language_map.get(language.lower(), "plain text")


def parse_markdown_to_blocks(content, vault_dir, markdown_file_path, page_map, uploader=None, debug=False):
    """Parse markdown to Notion blocks - uploads images and updates markdown with URLs."""
        
    # DEBUG: Check what links look like in original content
    if debug:
        print("\n=== ORIGINAL MARKDOWN LINKS ===")
        original_links = re.findall(r'(?<!!)\[([^\]]+)\]\(([^)]+)\)', content)
        for i, (text, url) in enumerate(original_links[:5], 1):
            print(f"{i}. [{text}]({url})")
        print("=" * 40)

    
    # Convert Obsidian links FIRST
    content = convert_obsidian_links(content, vault_dir, page_map)
    
    if debug:
        # DEBUG: Check what links look like after conversion
        print("\n=== AFTER OBSIDIAN CONVERSION ===")
        converted_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
        for i, (text, url) in enumerate(converted_links[:5], 1):
            print(f"{i}. [{text}]({url})")
        print("=" * 40)

    # UPLOAD IMAGES FIRST (before any other processing)
    uploaded_images = {}
    
    def upload_and_replace_image(match):
        full_match = match.group(0)

        alt = match.group(1)
        # src = match.group(2)
        src_match = re.search(r'\]\((.+)\)$', full_match)
        if not src_match:
            return full_match
    
        src = src_match.group(1)
        if debug:
            print(f"\n  Found image: {src}")
        
        # Check if image is already hosted online
        if is_url(src):
            if debug:
                print(f"    Already online URL, skipping upload")
            return f"![{alt}]({src})"
        
        # Check if already uploaded
        if src in uploaded_images:
            if debug:
                print(f"    Using cached URL")
            return f"![{alt}]({uploaded_images[src]})"
        
        # Decode and resolve path
        decoded_src = urllib.parse.unquote(src)
        file_path = resolve_relative_path(decoded_src, markdown_file_path, vault_dir, debug)
        
        if file_path and Path(file_path).is_file() and uploader:
            unique_path = get_unique_path_for_file(file_path, vault_dir)
            file_name = Path(file_path).name
            if debug:
                print(f"  Uploading image: {file_name}...", end=" ")
            file_url = uploader.upload(file_path, unique_path)
            
            if file_url:
                print(f"✓")
                uploaded_images[src] = file_url
                return f"![{alt}]({file_url})"
            else:
                print(f"✗ Upload failed")
                return f"![{alt}]({src})"
        else:
            if debug:
                print(f"    File not found: {decoded_src}")
            return f"![{alt}]({src})"
    
    # Replace all image references with GitHub URLs
    #content = re.sub(r'!\[([^\]]*)\]\(([^\)]+)\)', upload_and_replace_image, content)
    content = re.sub(r'!\[([^\]]*)\]\((.+?)\)(?=\s|$|\n|!|\[)', upload_and_replace_image, content)
    #content = re.sub(r'!\[[^\]]*\]\(.+?\)(?=\s|$|\n)', upload_and_replace_image, content, flags=re.MULTILINE)

    if uploaded_images:
        print(f"\n=== UPLOADED {len(uploaded_images)} IMAGES ===")
    
    if debug:
    # DEBUG: Check links after image upload
        print("\n=== AFTER IMAGE UPLOAD ===")
        after_upload_links = re.findall(r'(?<!!)\[([^\]]+)\]\(([^)]+)\)', content)
        for i, (text, url) in enumerate(after_upload_links[:5], 1):
            print(f"{i}. [{text}]({url})")
        print("=" * 40)
    
    # Now parse the updated markdown (with GitHub URLs)
    converter = ObsidianToNotionConverter(vault_dir, markdown_file_path, None, debug)
    markdown = mistune.create_markdown(renderer=converter, plugins=['strikethrough', 'table'])
    markdown(content)
    
    return converter.blocks

def get_markdown_files(vault_dir, exclude_folders=None):
    """Get all markdown files from vault."""
    if exclude_folders is None:
        exclude_folders = ['.obsidian', '.trash', '.git']
    
    markdown_files = []
    vault_path = Path(vault_dir)
    
    for md_file in vault_path.rglob("*.md"):
        is_excluded = any(excluded in md_file.parts for excluded in exclude_folders)
        if not is_excluded:
            markdown_files.append(md_file)
    
    return markdown_files


def create_notion_page(notion, database_id, title, content, vault_dir, markdown_file_path, page_map, uploader=None, debug=False):
    """Create Notion page with content."""
    try:
        new_page = notion.pages.create(
            parent={"database_id": database_id},
            properties={
                "Name": {"title": [{"text": {"content": title[:2000]}}]}
            }
        )
        
        page_id = new_page["id"]
        page_url = new_page["url"]
        
        blocks = parse_markdown_to_blocks(content, vault_dir, markdown_file_path, page_map, uploader, debug)
        
        if blocks:
            batch_size = 100
            for i in range(0, len(blocks), batch_size):
                batch = blocks[i:i+batch_size]
                if debug:
                    print(f"  Uploading batch {i//batch_size + 1} ({len(batch)} blocks)...")

                if debug:
                    # Debug each block
                    for j, block in enumerate(batch):
                        if block.get('type') == 'image':
                            url = block.get('image', {}).get('external', {}).get('url', '')
                            print(f"    Block {j}: Image with URL length {len(url)}")
                            if len(url) > 200:
                                print(f"      URL (first 100): {url[:100]}")
                                print(f"      URL (last 100): {url[-100:]}")
                
                try:
                    notion.blocks.children.append(block_id=page_id, children=batch)
                    time.sleep(0.3)
                except Exception as e:
                    print(f"  ✗ Error uploading batch: {e}")
                    # Try uploading blocks one by one to find the problematic one
                    for k, single_block in enumerate(batch):
                        try:
                            notion.blocks.children.append(block_id=page_id, children=[single_block])
                            print(f"    Block {k} OK")
                        except Exception as block_error:
                            print(f"    ✗ Block {k} FAILED: {block_error}")
                            if single_block.get('type') == 'image':
                                img_url = single_block.get('image', {}).get('external', {}).get('url', '')
                                print(f"      Problematic image URL: {img_url}")
                    raise
        
        return page_id, page_url
    
    except APIResponseError as e:
        print(f"  API Error: {e}")
        return None, None
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def main():
    parser = argparse.ArgumentParser(description="Migrate Obsidian folder to Notion")
    parser.add_argument("--api-key", required=True, help="Notion API key")
    parser.add_argument("--database-id", required=True, help="Notion database ID")
    parser.add_argument("--vault-dir", required=True, help="Obsidian vault/folder path")
    parser.add_argument("--provider", required=True, choices=['github'], help="File hosting provider")
    parser.add_argument("--github-token", required=True, help="GitHub personal access token")
    parser.add_argument("--github-repo-owner", required=True, help="GitHub repo owner")
    parser.add_argument("--github-repo-name", required=True, help="GitHub repo name")
    parser.add_argument("--github-branch", default="main", help="GitHub branch")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    
    args = parser.parse_args()
    
    provider_config = {
        'github_token': args.github_token,
        'repo_owner': args.github_repo_owner,
        'repo_name': args.github_repo_name,
        'branch': args.github_branch
    }
    
    uploader = FileUploader('github', provider_config)
    notion = Client(auth=args.api_key)
    vault_dir = Path(args.vault_dir).resolve()
    
    if not vault_dir.exists():
        print(f"Error: Path not found: {vault_dir}")
        return
    
    print(f"Scanning: {vault_dir}")
    markdown_files = get_markdown_files(vault_dir)
    
    print(f"Found {len(markdown_files)} markdown files")
    print(f"Using GitHub")
    if args.debug:
        print(f"Debug mode enabled")
    print(f"Starting migration...\n")
    
    page_map = {}
    successful = 0
    failed = 0
    
    for i, md_file in enumerate(markdown_files, 1):
        try:
            relative_path = md_file.relative_to(vault_dir)
        except:
            relative_path = md_file.name
        
        title = md_file.stem
        
        print(f"[{i}/{len(markdown_files)}] Migrating: {relative_path}")
        
        try:
            content = md_file.read_text(encoding='utf-8')
            
            page_id, page_url = create_notion_page(
                notion, args.database_id, title, content, 
                vault_dir, str(md_file.resolve()), page_map, uploader, args.debug
            )
            
            if page_id:
                page_map[title] = page_url
                print(f"  ✓ Success: {page_url}")
                successful += 1
            else:
                print(f"  ✗ Failed")
                failed += 1
        
        except Exception as e:
            print(f"  ✗ Error: {e}")
            failed += 1
        
        print()
    
    print(f"\n{'='*60}")
    print(f"Migration Complete!")
    print(f"✓ Successful: {successful}")
    print(f"✗ Failed: {failed}")
    uploader.print_stats()
    print(f"{'='*60}")


if __name__ == "__main__":
    main()