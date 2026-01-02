# Documentation Versioning Guide

**Version:** 1.0.0  
**Last Updated:** 2025-01-03

---

## Overview

This project uses **Semantic Versioning (SemVer)** for all documentation files. This ensures clear communication about the nature and impact of changes, making it easy to track updates and understand compatibility.

## Version Format

All documentation follows the format: **MAJOR.MINOR.PATCH**

```
X.Y.Z
│ │ │
│ │ └─ Patch: Bug fixes, typos, minor corrections
│ └─── Minor: New features, enhancements, non-breaking additions
└───── Major: Breaking changes, major restructuring, significant rewrites
```

### Examples

- **1.0.0** → Initial release
- **1.0.1** → Fixed typo in installation instructions
- **1.1.0** → Added new section on email templates
- **2.0.0** → Complete restructuring of directory layout

---

## Version Number Meanings

### MAJOR Version (X.0.0)

**When to increment:** Breaking changes, major structural changes, or significant rewrites

**Examples:**
- Complete restructuring of project directories
- Changing file paths that break existing workflows
- Removing or significantly altering major features
- Changing fundamental architecture or design patterns
- Renaming core modules or files
- Major API changes in code that affect documentation

**Impact:** Users need to review and potentially update their workflows

**Current MAJOR:** 2 (as of 2025-01-03)

---

### MINOR Version (0.X.0)

**When to increment:** New features, enhancements, or additions that don't break existing content

**Examples:**
- Adding new documentation sections
- Documenting new features or modules
- Adding new examples or use cases
- Enhancing existing sections with more detail
- Adding new configuration options
- Documenting new workflows or processes

**Impact:** Users can benefit from new information without changing existing practices

**Current MINOR:** 0 (within v2.0.0)

---

### PATCH Version (0.0.X)

**When to increment:** Bug fixes, corrections, clarifications, or minor updates

**Examples:**
- Fixing typos or grammatical errors
- Correcting code examples
- Updating outdated information
- Clarifying ambiguous instructions
- Fixing broken links
- Minor formatting improvements
- Updating dates or version references

**Impact:** Improves accuracy and clarity without changing functionality

**Current PATCH:** 0 (within v2.0.0)

---

## Version Header Format

Every documentation file includes a version header at the top:

```markdown
**Version:** 2.0.0  
**Last Updated:** 2025-01-03  
**Changelog:**
- v2.0.0: Updated for organized directory structure, normalization layer documentation
- v1.0.0: Initial version
```

### Header Components

1. **Version:** Current semantic version number
2. **Last Updated:** Date of last modification (YYYY-MM-DD format)
3. **Changelog:** Brief list of changes for each version

---

## Versioning Workflow

### When Making Changes

1. **Identify the type of change:**
   - Breaking/structural → MAJOR
   - New content/features → MINOR
   - Fixes/corrections → PATCH

2. **Update the version number** in the file header

3. **Add changelog entry** describing what changed

4. **Update Last Updated date**

5. **Update CHANGELOG.md** with detailed change description

### Example Workflow

**Scenario:** Adding a new section about email templates

1. **Type:** New content → MINOR version bump
2. **Current version:** 2.0.0
3. **New version:** 2.1.0
4. **Update header:**
   ```markdown
   **Version:** 2.1.0
   **Last Updated:** 2025-01-15
   **Changelog:**
   - v2.1.0: Added email template customization section
   - v2.0.0: Updated for organized directory structure
   ```
5. **Update CHANGELOG.md** with full details

---

## Version Compatibility

### Backward Compatibility

- **MAJOR changes:** May break existing workflows or references
- **MINOR changes:** Fully backward compatible, adds new information
- **PATCH changes:** Fully backward compatible, only fixes issues

### Cross-Reference Updates

When making MAJOR changes that affect file paths or structure:

1. Update all cross-references in other documentation
2. Update README.md if structure changes
3. Update GITHUB_SETUP.md if repository structure changes
4. Update all code examples that reference paths

---

## Version History Tracking

### CHANGELOG.md

The main `docs/CHANGELOG.md` file tracks:

- All version releases
- Detailed change descriptions
- Dates of changes
- Files affected
- Migration notes for breaking changes

### Individual File Changelogs

Each documentation file includes a brief changelog in its header showing:
- Version number
- Brief description of changes
- Previous versions

---

## Version Numbering Examples

### Scenario 1: Initial Release
```
Version: 1.0.0
- First complete version of documentation
```

### Scenario 2: Typo Fix
```
Version: 1.0.0 → 1.0.1
- Fixed typo in installation command
```

### Scenario 3: Adding New Section
```
Version: 1.0.0 → 1.1.0
- Added troubleshooting section
- Added FAQ section
```

### Scenario 4: Major Restructure
```
Version: 1.2.0 → 2.0.0
- Complete reorganization of directory structure
- Updated all file paths
- Restructured documentation hierarchy
```

### Scenario 5: Multiple Changes
```
Version: 2.0.0 → 2.1.0
- Added normalization layer documentation (MINOR)
- Fixed broken links (PATCH - but included in MINOR)
- Added new examples (MINOR)
```

**Note:** When making multiple changes, use the highest version type needed.

---

## Best Practices

### 1. Be Consistent
- Use the same version number format across all files
- Update related files when making cross-references
- Keep changelog entries descriptive but concise

### 2. Update Dates
- Always update "Last Updated" when changing content
- Use ISO format (YYYY-MM-DD) for consistency

### 3. Document Breaking Changes
- Clearly mark MAJOR version changes
- Provide migration guides when paths or structures change
- Update all affected documentation simultaneously

### 4. Version Synchronization
- Related documentation files don't need the same version
- Each file is versioned independently based on its changes
- CHANGELOG.md tracks overall project version

### 5. Review Before Versioning
- Review all changes before assigning version number
- Ensure version type matches the scope of changes
- Update cross-references if needed

---

## Version Comparison

### Current Documentation Versions (as of 2025-01-03)

| File | Version | Last Updated | Status |
|------|---------|--------------|--------|
| README.md | 2.0.0 | 2025-01-03 | Current |
| PROJECT_STRUCTURE.md | 2.0.0 | 2025-01-03 | Current |
| CODEBASE_OVERVIEW.md | 2.0.0 | 2025-01-03 | Current |
| ENV_SETUP_GUIDE.md | 2.0.0 | 2025-01-03 | Current |
| TESTING_GUIDE.md | 2.0.0 | 2025-01-03 | Current |
| GITHUB_SETUP.md | 2.0.0 | 2025-01-03 | Current |
| NORMALIZATION_ARCHITECTURE.md | 1.0.0 | 2025-01-03 | Current |
| VERSIONING.md | 1.0.0 | 2025-01-03 | Current |

---

## Migration Between Versions

### Upgrading from v1.x.x to v2.0.0

**Breaking Changes:**
- Directory structure completely reorganized
- File paths changed throughout codebase
- New normalization layer added

**Migration Steps:**
1. Review new directory structure in PROJECT_STRUCTURE.md
2. Update any custom scripts to use new paths
3. Move local files to match new structure
4. Review normalization layer documentation

### Future Version Migrations

When MAJOR versions are released:
1. Check CHANGELOG.md for detailed migration guide
2. Review all breaking changes
3. Update workflows and scripts accordingly
4. Test thoroughly after migration

---

## Questions?

### When should I increment MAJOR?
- When changes break existing workflows
- When file paths or structure fundamentally change
- When removing or significantly altering features

### Can I skip version numbers?
- No, always increment sequentially
- 1.0.0 → 1.0.1 → 1.0.2 (not 1.0.0 → 1.0.5)

### What if I make multiple types of changes?
- Use the highest version type needed
- Example: Adding features (MINOR) + fixing typos (PATCH) = MINOR bump

### Should all docs have the same version?
- No, each file is versioned independently
- Only bump versions for files that actually changed

---

## References

- [Semantic Versioning Specification](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [CHANGELOG.md](CHANGELOG.md) - Project change history

---

**Remember:** Versioning is about communication. Clear version numbers help users understand what changed and how it affects them.

