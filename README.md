
# Obsidian to Notion Migration Tool



A Python script to migrate your Obsidian vault to Notion, including markdown conversion, image uploads to GitHub, and proper link formatting.

## Features

- ✅ Converts Obsidian markdown to Notion blocks
- ✅ Uploads images to GitHub and embeds them in Notion
- ✅ Handles URL-encoded paths and special characters
- ✅ Preserves folder structure in GitHub
- ✅ Supports wiki-links and standard markdown links
- ✅ Handles code blocks, quotes, lists, and formatting
- ✅ Single-folder or full vault migration

## Prerequisites

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) package manager
- Notion API key and database
- GitHub repository and personal access token

## Installation

### 1. Install uv

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Clone or download this script

```bash
git clone <repository-url>
cd obsidian-to-notion
```

### 3. Install dependencies with uv

```bash
uv pip install notion-client mistune requests
```

## Setup

### Notion Setup

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Click **"+ New integration"**
3. Give it a name (e.g., "Obsidian Importer")
4. Copy the **Internal Integration Token** (starts with `secret_`)
5. Create a database in Notion or use an existing one
6. Share the database with your integration:
   - Open the database in Notion
   - Click **"..."** → **"Add connections"**
   - Select your integration
7. Get the database ID from the URL:
   ```
   https://notion.so/workspace/DATABASE_ID?v=...
   ```

### GitHub Setup

1. Create a new repository for storing images (e.g., `obsidian-images`)
2. Generate a Personal Access Token:
   - Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Click **"Generate new token"**
   - Select scopes: `repo` (full control)
   - Copy the token (starts with `ghp_`)

## Usage

### Basic Command

```bash
uv run python obsidian_to_notion.py \
  --api-key "secret_YOUR_NOTION_KEY" \
  --database-id "YOUR_DATABASE_ID" \
  --vault-dir "/path/to/your/obsidian/vault" \
  --provider github \
  --github-token "ghp_YOUR_GITHUB_TOKEN" \
  --github-repo-owner "your-username" \
  --github-repo-name "obsidian-images" \
  --github-branch "main"
```

### Single Folder Migration

To migrate just one folder (useful for testing):

```bash
uv run python obsidian_to_notion.py \
  --api-key "secret_YOUR_NOTION_KEY" \
  --database-id "YOUR_DATABASE_ID" \
  --vault-dir "/path/to/vault/specific-folder" \
  --provider github \
  --github-token "ghp_YOUR_GITHUB_TOKEN" \
  --github-repo-owner "your-username" \
  --github-repo-name "obsidian-images"
```

### Debug Mode

Enable detailed logging to troubleshoot issues:

```bash
uv run python obsidian_to_notion.py \
  --api-key "secret_YOUR_NOTION_KEY" \
  --database-id "YOUR_DATABASE_ID" \
  --vault-dir "/path/to/vault" \
  --provider github \
  --github-token "ghp_YOUR_GITHUB_TOKEN" \
  --github-repo-owner "your-username" \
  --github-repo-name "obsidian-images" \
  --debug
```

## Command Line Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--api-key` | ✅ | Notion API integration token |
| `--database-id` | ✅ | Notion database ID to import into |
| `--vault-dir` | ✅ | Path to Obsidian vault or folder |
| `--provider` | ✅ | File hosting provider (currently only `github`) |
| `--github-token` | ✅ | GitHub personal access token |
| `--github-repo-owner` | ✅ | GitHub username or organization |
| `--github-repo-name` | ✅ | GitHub repository name |
| `--github-branch` | ❌ | GitHub branch (default: `main`) |
| `--debug` | ❌ | Enable debug output |

## Supported Markdown Features

### ✅ Supported
- Headings (H1-H3)
- Bold, italic, strikethrough
- Code blocks (with syntax highlighting)
- Inline code
- Bulleted and numbered lists
- Block quotes
- Images (local and remote)
- Links (standard markdown and Obsidian wiki-links)
- Horizontal rules
- Tables

### ⚠️ Limitations
- Obsidian plugins (dataview, tasks, etc.) are not supported
- Embedded notes are converted to links
- Some advanced Notion features (databases, callouts) require manual formatting
- Maximum 100MB per file (GitHub limit)

## File Structure

After migration, your GitHub repository will contain:

```
obsidian-images/
└── uploads/
    ├── folder-name/
    │   ├── image1.png
    │   └── image2.jpg
    └── subfolder/
        └── diagram.png
```

URLs are properly encoded to handle:
- Spaces (` ` → `%20`)
- Special characters (`&` → `%26`)
- Parentheses (`(` → `%28`, `)` → `%29`)

## Troubleshooting

### "Invalid URL for link" errors
- Check that your markdown links are properly formatted: `[text](url)`
- Links with parentheses in the text are supported: `[App (v2)](url)`

### Images not appearing in Notion
- Verify the GitHub repository is public or the raw URLs are accessible
- Check that the file uploaded successfully to GitHub
- Ensure URL encoding is preserved (spaces as `%20`, not literal spaces)

### "Permission denied" errors
- Verify your Notion integration has access to the database
- Check that your GitHub token has `repo` permissions
- Ensure the GitHub repository exists

### Rate limits
- Notion API: 3 requests per second
- GitHub API: 5000 requests per hour
- The script includes automatic throttling (0.3s between batches)

## Examples

### Example 1: Full Vault Migration
```bash
uv run python obsidian_to_notion.py \
  --api-key "secret_abc123" \
  --database-id "abc123def456" \
  --vault-dir "C:\Users\YourName\Documents\ObsidianVault" \
  --provider github \
  --github-token "ghp_xyz789" \
  --github-repo-owner "johndoe" \
  --github-repo-name "my-notes-images"
```

### Example 2: Single Project
```bash
uv run python obsidian_to_notion.py \
  --api-key "secret_abc123" \
  --database-id "abc123def456" \
  --vault-dir "~/Documents/ObsidianVault/Projects/MyProject" \
  --provider github \
  --github-token "ghp_xyz789" \
  --github-repo-owner "johndoe" \
  --github-repo-name "project-images"
```

## Statistics

After migration, you'll see a summary:

```
============================================================
Migration Complete!
✓ Successful: 45
✗ Failed: 2

Upload Statistics:
   Images:         23
   PDFs:           5
   Other:          1
   Failed:         0
   Skipped (dirs): 0
   Total:          29
============================================================
```

## Contributing

Issues and pull requests are welcome! Please ensure:
- Code follows existing style
- Test with various markdown formats
- Update README for new features

## License

MIT License - feel free to use and modify as needed.

## Acknowledgments

- [Notion API](https://developers.notion.com/)
- [mistune](https://github.com/lepture/mistune) for markdown parsing
- [uv](https://github.com/astral-sh/uv) for fast Python package management
