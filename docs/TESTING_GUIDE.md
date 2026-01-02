# 🧪 Detailed Guide to Testing Your Cold Email System

**Version:** 2.0.0  
**Last Updated:** 2025-01-03  
**Changelog:**
- v2.0.0: Updated for new file structure, normalization layer testing
- v1.0.0: Initial version

---

Testing your campaign system should progress through three phases: **Unit Testing** (for individual components), **Integration Testing** (for components working together), and **System Testing** (end-to-end dry runs).

## 1. Unit Testing: Component Verification

Unit tests ensure that the core, isolated functions work exactly as expected, independent of the network or database (CSV file).

### A. `templates.py` Checks (Logic & Personalization)

| Test Goal | Expected Input | Expected Output | Check Type |
| :--- | :--- | :--- | :--- |
| **Tech Title Override** | `score=95`, `title='CTO'` | Returns `TEMPLATE_3` | **Logic** |
| **High Score Default** | `score=91`, `title='Manager'` | Returns `TEMPLATE_1` | **Logic** |
| **Low Score Default** | `score=50`, `title='Director'` | Returns `TEMPLATE_2` | **Logic** |
| **Name Parsing** | `name='Dr. Jane Doe-Smith'` | Returns `'Jane'` | **Function (`get_salutation_name`)** |
| **Placeholder Safety**| Get T1, format with `FirstName='John'`, `Company='Acme'` | `body` contains: "Hi John," and "at Acme." | **String Formatting** |

### B. `filters.py` Checks (Time-Based Logic)

This is the most critical unit test to ensure the 6–8 day delay is correct.

| Test Goal | Input CSV State | `CAMPAIGN_STAGE` | Expected Recipients (Rows) |
| :--- | :--- | :--- | :--- |
| **Initial Send** | 10 PENDING rows, 5 SENT_SUCCESS rows | `'INITIAL_SEND'` | 10 PENDING rows |
| **Follow-Up 1 (Too Early)** | 5 SENT_SUCCESS rows, Timestamp = 2 days ago | `'FOLLOW_UP_1'` | 0 rows |
| **Follow-Up 1 (Ready)** | 5 SENT_SUCCESS rows, Timestamp = 7 days ago | `'FOLLOW_UP_1'` | 5 rows |
| **Follow-Up 2 (Ready)** | 5 FU1\_SUCCESS rows, FU1\_Timestamp = 7 days ago | `'FOLLOW_UP_2'` | 5 rows |

## 2. Integration Testing: Interacting Components

Integration tests verify that two or more components work together correctly.

### A. `mailer.py` Integration

* **Test Environment:** Must use a real (test) email account.
* **Goal:** Verify the `SMTPMailer` can connect, log in, send, and correctly report failures.
* **Checks:**
    1.  Attempt to send to a **valid, working address** (e.g., your personal email) and confirm the `send_email` method returns `"SUCCESS"`.
    2.  Attempt to send to an **invalid address** (e.g., `test@example.com`) and confirm it correctly reports refusal and returns `"FAILED_REFUSED"`.

### B. CSV Persistence Integration

* **Goal:** Ensure the main script (`campaign.py`) correctly reads the CSV, updates the DataFrame, and safely writes the new state back to the CSV.
* **Check:** Run the script in `TEST_MODE=True` with a fresh CSV. After the run, open the CSV file and confirm that the first `MAX_EMAILS_IN_TEST` records have:
    * `Sent_Status` changed from `PENDING` to `SENT_SUCCESS`.
    * `Sent_Timestamp` contains a recent timestamp string.

## 3. System Testing: End-to-End Dry Run

This phase uses the `TEST_MODE` flag for real-world simulation without full scale.

| Test Step | Config Setting | Expected Outcome | Verification |
| :--- | :--- | :--- | :--- |
| **Dry Run (`INITIAL_SEND`)** | `TEST_MODE = True`, `CAMPAIGN_STAGE = 'INITIAL_SEND'` | **5 Emails Sent.** The terminal shows success and the CSV updates for the first 5 PENDING recipients. | Check terminal logs, check your sent folder, check CSV file. |
| **Dry Run (`FOLLOW_UP_1`)** | `TEST_MODE = True`, `CAMPAIGN_STAGE = 'FOLLOW_UP_1'` | **5 Emails Sent.** The script correctly filters for recipients who received the initial email 6-8 days ago. | Manually update a few `Sent_Timestamp` values in the CSV to be 7 days old, then run the test. |
| **Quota Enforcement** | `TEST_MODE = False`, `DAILY_SEND_LIMIT = 5` | **Only 5 Emails Sent.** The script stops exactly at 5, regardless of how many eligible recipients exist. | Check terminal output for quota message, check your sent folder count. |

## 4. Performance & Deliverability Testing

Final checks before moving to full production scale.

* **Delay Sanity Check:** Monitor the time taken between sends. Verify that the randomized delay of 5 to 15 seconds is strictly enforced by observing the timestamps in your terminal logs or the `Sent_Timestamp` column of your CSV.
* **Spam Check:** Send a test email to different personal inboxes (Gmail, Outlook, Yahoo) to ensure the email lands in the primary inbox, not the spam folder or promotions tab. This validates your template body and subject lines.