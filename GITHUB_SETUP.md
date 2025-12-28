# GitHub Setup Guide

This guide will help you prepare and upload your project to GitHub.

## 📋 Pre-Upload Checklist

### ✅ Files to Verify

1. **`.gitignore`** - ✅ Created (excludes `.env`, `__pycache__`, logs, etc.)
2. **`.env.example`** - ✅ Created (template for environment variables)
3. **`README.md`** - ✅ Created (project overview and quick start)
4. **`ENV_SETUP_GUIDE.md`** - ✅ Created (detailed environment setup)
5. **`PROJECT_STRUCTURE.md`** - ✅ Updated (complete project documentation)
6. **`requirements.txt`** - ✅ Created (Python dependencies)

### 🔒 Security Check

Before uploading, verify these sensitive files are excluded:

```bash
# Check .gitignore includes:
- .env
- *.log
- __pycache__/
- *.backup
```

**Never commit:**
- ❌ `.env` file (contains passwords)
- ❌ `*.log` files (may contain sensitive data)
- ❌ `__pycache__/` directories
- ❌ Backup files

## 🚀 Upload Steps

### 1. Initialize Git Repository (if not already done)

```bash
cd /path/to/coldemail
git init
```

### 2. Add All Files

```bash
git add .
```

### 3. Verify What Will Be Committed

```bash
# Check that .env is NOT in the list
git status

# If .env appears, check .gitignore
cat .gitignore | grep .env
```

### 4. Create Initial Commit

```bash
git commit -m "Initial commit: Cold email outreach system"
```

### 5. Create GitHub Repository

1. Go to [GitHub](https://github.com) and create a new repository
2. **Do NOT** initialize with README, .gitignore, or license (we already have these)
3. Copy the repository URL

### 6. Connect and Push

```bash
# Add remote (replace with your repository URL)
git remote add origin https://github.com/yourusername/coldemail.git

# Push to GitHub
git branch -M main
git push -u origin main
```

## 📝 Recommended Repository Settings

### Repository Description
```
Production-grade cold email outreach system with automated lead generation, data enrichment, and multi-stage email campaigns
```

### Topics/Tags
- `cold-email`
- `email-automation`
- `lead-generation`
- `web-scraping`
- `linkedin-scraper`
- `email-campaign`
- `python`
- `selenium`

### Visibility
- **Private** (recommended) - Contains business logic and may process sensitive data
- **Public** - Only if you want to open-source it

## 📄 Files Included in Repository

### ✅ Included (Safe to Commit)
- All Python source code
- Configuration files (without secrets)
- Documentation (README, guides)
- `.gitignore`
- `.env.example` (template)
- `requirements.txt`
- CSV data files (if not too large)
- PDF files (if not sensitive)

### ❌ Excluded (via .gitignore)
- `.env` (credentials)
- `*.log` (logs)
- `__pycache__/` (Python cache)
- `*.backup` (backup files)
- Virtual environment directories

## 🔄 After Upload

### For Collaborators

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/coldemail.git
   cd coldemail
   ```

2. **Set up environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Create `.env` file**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials (see ENV_SETUP_GUIDE.md)
   ```

## 🛡️ Security Best Practices

1. **Review before pushing**
   ```bash
   git log --stat
   git show HEAD
   ```

2. **Use GitHub Secrets** (for CI/CD if needed)
   - Go to Settings → Secrets
   - Add sensitive values there

3. **Regular audits**
   - Periodically review what's in the repository
   - Check for accidentally committed secrets
   - Use tools like `git-secrets` or `truffleHog`

4. **Branch protection** (for main branch)
   - Require pull request reviews
   - Require status checks
   - Prevent force pushes

## 📦 Large Files

If your CSV/PDF files are large (>100MB):

1. **Option 1: Use Git LFS**
   ```bash
   git lfs install
   git lfs track "*.csv"
   git lfs track "*.pdf"
   git add .gitattributes
   ```

2. **Option 2: Exclude from Git**
   - Add to `.gitignore`:
     ```
     *.csv
     *.pdf
     ```
   - Store in cloud storage (S3, Google Drive) instead
   - Document location in README

## 🔍 Verify Upload

After pushing, verify on GitHub:

1. ✅ `.env` is NOT visible
2. ✅ All source files are present
3. ✅ README displays correctly
4. ✅ `.gitignore` is present
5. ✅ `.env.example` is present

## 📚 Documentation Links

Make sure these are accessible:
- [README.md](README.md) - Main documentation
- [ENV_SETUP_GUIDE.md](ENV_SETUP_GUIDE.md) - Environment setup
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Detailed structure
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Testing procedures

## 🆘 Troubleshooting

### "File too large" error
- Use Git LFS for large files
- Or exclude large files from Git

### ".env accidentally committed"
```bash
# Remove from Git history (be careful!)
git rm --cached .env
git commit -m "Remove .env from repository"
git push

# If already pushed, you may need to:
# 1. Change all passwords in .env
# 2. Use git filter-branch or BFG Repo-Cleaner
```

### "Permission denied"
- Check GitHub authentication
- Verify SSH keys or use HTTPS with token

---

**Ready to upload?** Follow the steps above and your project will be safely on GitHub! 🚀

