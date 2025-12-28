# Environment Variables Setup Guide

This guide explains how to set up the `.env` file with all required credentials and configuration.

## 📋 Overview

The `.env` file stores sensitive credentials and configuration that should **never** be committed to version control. This file is automatically ignored by `.gitignore`.

## 🔐 Required Variables

### Email Configuration (for Outreach Campaigns)

#### 1. Gmail Setup

1. **Enable 2-Factor Authentication** on your Gmail account
2. **Generate an App Password**:
   - Go to [Google Account Settings](https://myaccount.google.com/)
   - Security → 2-Step Verification → App passwords
   - Generate a new app password for "Mail"
   - Copy the 16-character password

3. **Add to `.env`**:
   ```bash
   SENDER_EMAIL=your.email@gmail.com
   SENDER_PASSWORD=xxxx xxxx xxxx xxxx  # 16-char app password (no spaces)
   ```

⚠️ **Important**: Use the App Password, NOT your regular Gmail password.

### LinkedIn Configuration (for LinkedIn Scraper)

#### 2. LinkedIn Credentials

```bash
LINKEDIN_EMAIL=your.email@example.com
LINKEDIN_PASSWORD=your_linkedin_password
```

⚠️ **Security Note**: Consider using a dedicated LinkedIn account for scraping to avoid account restrictions.

#### 3. LinkedIn Search Queries

Define your search queries (as many as needed):

```bash
QUERY_1=people%20search%20query%20here
QUERY_2=another%20search%20query
QUERY_3=third%20query
```

**How to create queries:**
1. Go to LinkedIn and perform a people search
2. Apply your filters (location, industry, etc.)
3. Copy the URL
4. Extract the query parameters (everything after `?`)
5. URL-encode if needed

**Example:**
- LinkedIn URL: `https://www.linkedin.com/search/results/people/?keywords=data%20scientist&location=San%20Francisco`
- Query: `people/?keywords=data%20scientist&location=San%20Francisco`

### Scraper Configuration (Optional)

#### 4. Scraper Limits and Delays

```bash
# Maximum profiles to scrape per run
MAX_PROFILES_TO_SCRAPE=30

# Scraper mode: TEST or PROD
SCRAPER_MODE=TEST

# Delays (in seconds) to avoid detection
LOGIN_DELAY_MIN=5
LOGIN_DELAY_MAX=8
SCROLL_DELAY_MIN=1.5
SCROLL_DELAY_MAX=3.5
PROFILE_DELAY_MIN=3
PROFILE_DELAY_MAX=7
```

## 📝 Complete `.env` Template

Create a `.env` file in the project root with this template:

```bash
# ============================================
# EMAIL CONFIGURATION (Required for Outreach)
# ============================================
SENDER_EMAIL=your.email@gmail.com
SENDER_PASSWORD=your_16_char_app_password

# ============================================
# LINKEDIN CONFIGURATION (Required for Scraper)
# ============================================
LINKEDIN_EMAIL=your.email@example.com
LINKEDIN_PASSWORD=your_linkedin_password

# LinkedIn Search Queries (Add as many as needed)
QUERY_1=people/?keywords=data%20scientist&location=San%20Francisco
QUERY_2=people/?keywords=machine%20learning&industry=Technology
QUERY_3=people/?keywords=AI%20researcher&location=Boston

# ============================================
# SCRAPER CONFIGURATION (Optional)
# ============================================
MAX_PROFILES_TO_SCRAPE=30
SCRAPER_MODE=TEST

# Delay Settings (seconds)
LOGIN_DELAY_MIN=5
LOGIN_DELAY_MAX=8
SCROLL_DELAY_MIN=1.5
SCROLL_DELAY_MAX=3.5
PROFILE_DELAY_MIN=3
PROFILE_DELAY_MAX=7
```

## ✅ Verification

### Test Email Configuration

```bash
# Test SMTP connection
python -c "from outreach.mailer import SMTPMailer; m = SMTPMailer(); print('Connected!' if m.connect() else 'Failed')"
```

### Test LinkedIn Configuration

The scraper will validate credentials on first run. Check logs for connection status.

## 🔒 Security Best Practices

1. **Never commit `.env` to Git**
   - Already in `.gitignore`, but double-check
   - Use `.env.example` as a template (without real values)

2. **Use App Passwords**
   - Never use your main Gmail password
   - App passwords can be revoked individually

3. **Rotate Credentials**
   - Change passwords periodically
   - Revoke and regenerate app passwords if compromised

4. **Limit Access**
   - Only share `.env` with trusted team members
   - Use different credentials for development/production

5. **Backup Securely**
   - Store `.env` backups in encrypted storage
   - Never in cloud storage without encryption

## 🚨 Troubleshooting

### "Authentication failed" for Gmail

- Verify 2FA is enabled
- Regenerate App Password
- Remove spaces from App Password in `.env`
- Check that `SENDER_EMAIL` matches the account with the App Password

### "LinkedIn login failed"

- Verify credentials are correct
- Check if account is locked (LinkedIn may require CAPTCHA)
- Try logging in manually first to unlock account
- Consider using a dedicated scraping account

### "Module not found" errors

- Ensure virtual environment is activated
- Run `pip install -r requirements.txt`
- Check Python version (3.8+)

## 📞 Support

If you encounter issues:
1. Check the logs: `outreach_campaign.log`
2. Verify all required variables are set
3. Test each component individually
4. Review [TESTING_GUIDE.md](TESTING_GUIDE.md)

## 🔄 Updating Credentials

When updating credentials:
1. Edit `.env` file
2. Restart any running processes
3. Test the updated configuration
4. Update backups if needed

---

**Remember**: The `.env` file contains sensitive information. Treat it like a password file.

