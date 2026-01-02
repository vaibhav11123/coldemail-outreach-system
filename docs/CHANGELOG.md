# Documentation Changelog

This file tracks all changes to the project documentation.

## Version 2.0.0 - 2025-01-03

### Major Updates

#### File Organization
- **NEW:** Organized directory structure implemented
  - `data/raw/` - Raw input data (CSV, PDF)
  - `data/processed/` - Master processed database
  - `data/backups/` - Backup files
  - `docs/` - All documentation files
  - `scripts/` - Root-level scripts
  - `logs/` - Log files
  - `config/` - Configuration files

#### Normalization Layer
- **NEW:** Comprehensive normalization layer (`scraper_bridge/normalize_for_outreach.py`)
  - Hard filtering of invalid profiles
  - Role-based filtering (explicit allow/deny lists)
  - Title normalization with seniority/department mapping
  - Email generation with confidence scores (0.3 minimum threshold)
  - Rejection tracking with detailed reasons

#### Campaign Improvements
- **IMPROVED:** Atomic CSV saves using temp files + `os.replace()`
- **IMPROVED:** Daily quota management (450/day limit)
- **IMPROVED:** State persistence after each email
- **IMPROVED:** Path resolution using `Path(__file__).parent.parent`

#### Email Qualification
- **NEW:** DNS MX record verification
- **NEW:** Lead scoring (0-100) based on multiple factors
- **NEW:** Role inbox detection
- **NEW:** Domain authority checking

#### Documentation
- **UPDATED:** All file paths updated to reflect new structure
- **UPDATED:** Added version headers to all documentation files
- **UPDATED:** GitHub setup guide for new structure
- **NEW:** Comprehensive codebase overview

### Files Changed
- `README.md` - Updated structure, paths, features
- `docs/PROJECT_STRUCTURE.md` - Complete rewrite with new structure
- `docs/CODEBASE_OVERVIEW.md` - Updated with normalization layer
- `docs/ENV_SETUP_GUIDE.md` - Path updates
- `docs/TESTING_GUIDE.md` - Updated for new structure
- `docs/GITHUB_SETUP.md` - Updated for new directory structure
- `scraper_bridge/NORMALIZATION_ARCHITECTURE.md` - New documentation

### Code Changes
- All Python files updated with new path references
- `scripts/data_cleaner.py` - Moved to scripts/, paths updated
- `outreach/config.py` - Paths updated to use new structure
- `scraper_bridge/staffspy_ingest.py` - Paths updated, normalization integrated
- `scraper_bridge/enforce_master_schema.py` - Paths updated
- `scraper_bridge/qualify_leads.py` - Paths updated

---

## Version 1.0.0 - Initial Release

### Initial Features
- Basic email campaign system
- LinkedIn scraping (legacy)
- Faculty scraping
- CSV/PDF data processing
- Multi-stage email campaigns

---

## Versioning Scheme

This project uses [Semantic Versioning](https://semver.org/) (SemVer) for documentation.

**For detailed versioning guidelines, see [VERSIONING.md](VERSIONING.md)**

### Quick Reference

- **MAJOR** (X.0.0): Breaking changes, major feature additions, structural changes
- **MINOR** (0.X.0): New features, enhancements, non-breaking changes
- **PATCH** (0.0.X): Bug fixes, corrections, minor updates

### When to Update Versions

- **MAJOR:** Complete restructuring, breaking API changes, major new modules
- **MINOR:** New features, new documentation sections, enhanced functionality
- **PATCH:** Typo fixes, clarification updates, minor corrections

