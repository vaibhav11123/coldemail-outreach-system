import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

# Handle both direct execution and module import
try:
    from . import config
except ImportError:
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from outreach import config


def filter_recipients_by_stage(df, stage=None, now=None):
    """Filters contacts based on CAMPAIGN_STAGE (or explicit stage) and time passed.

    Rows with scheduled_again_at set use that timestamp as the new anchor and
    become due when that day has arrived (missed-window recovery).
    """
    today = now or datetime.now()
    stage = stage or config.CAMPAIGN_STAGE

    # Ensure minimum required column
    if 'Sent_Status' not in df.columns:
        return pd.DataFrame()

    # Ensure follow-up columns exist (fail-safe)
    for col in [
        'Sent_Timestamp',
        'FollowUp_1_Status',
        'FollowUp_1_Timestamp',
        'FollowUp_2_Status',
        'FollowUp_2_Timestamp',
        'scheduled_again_at',
    ]:
        if col not in df.columns:
            df[col] = ''

    if stage == 'INITIAL_SEND':
        return df[df['Sent_Status'] == 'PENDING']

    elif stage == 'FOLLOW_UP_1':
        follow_up_df = df[
            (df['Sent_Status'] == 'SENT_SUCCESS') &
            (~df['FollowUp_1_Status'].isin(['SENT_SUCCESS', 'FAILED_REFUSED']))
        ].copy()

        if follow_up_df.empty:
            return follow_up_df

        follow_up_df['Sent_DT'] = pd.to_datetime(
            follow_up_df['Sent_Timestamp'], errors='coerce'
        )
        follow_up_df['Sched_DT'] = pd.to_datetime(
            follow_up_df['scheduled_again_at'], errors='coerce'
        )

        due_mask = []
        for _, row in follow_up_df.iterrows():
            if pd.notna(row['Sched_DT']):
                days = (today - row['Sched_DT'].to_pydatetime()).days
                due_mask.append(days >= 0)
                continue
            if pd.isna(row['Sent_DT']):
                due_mask.append(False)
                continue
            days = (today - row['Sent_DT'].to_pydatetime()).days
            due_mask.append(6 <= days <= 8)
        return follow_up_df[due_mask]

    elif stage == 'FOLLOW_UP_2':
        follow_up_df = df[
            (df['Sent_Status'] == 'SENT_SUCCESS') &
            (df['FollowUp_1_Status'] == 'SENT_SUCCESS') &
            (~df['FollowUp_2_Status'].isin(['SENT_SUCCESS', 'FAILED_REFUSED']))
        ].copy()

        if follow_up_df.empty:
            return follow_up_df

        follow_up_df['FU1_DT'] = pd.to_datetime(
            follow_up_df['FollowUp_1_Timestamp'], errors='coerce'
        )
        follow_up_df['Sched_DT'] = pd.to_datetime(
            follow_up_df['scheduled_again_at'], errors='coerce'
        )

        due_mask = []
        for _, row in follow_up_df.iterrows():
            if pd.notna(row['Sched_DT']):
                days = (today - row['Sched_DT'].to_pydatetime()).days
                due_mask.append(days >= 0)
                continue
            if pd.isna(row['FU1_DT']):
                due_mask.append(False)
                continue
            days = (today - row['FU1_DT'].to_pydatetime()).days
            due_mask.append(6 <= days <= 8)
        return follow_up_df[due_mask]

    return pd.DataFrame()
