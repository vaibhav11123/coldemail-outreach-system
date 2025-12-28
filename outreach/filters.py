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


def filter_recipients_by_stage(df):
    """Filters contacts based on the current CAMPAIGN_STAGE and time passed."""
    today = datetime.now()
    stage = config.CAMPAIGN_STAGE

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
        follow_up_df = follow_up_df.dropna(subset=['Sent_DT'])

        follow_up_df['Days_Since_Send'] = (today - follow_up_df['Sent_DT']).dt.days

        return follow_up_df[
            (follow_up_df['Days_Since_Send'] >= 6) &
            (follow_up_df['Days_Since_Send'] <= 8)
        ]

    elif stage == 'FOLLOW_UP_2':
        follow_up_df = df[
            (df['Sent_Status'] == 'SENT_SUCCESS') &
            (df['FollowUp_1_Status'] == 'SENT_SUCCESS') &
            (~df['FollowUp_2_Status'].isin(['SENT_SUCCESS', 'FAILED_REFUSED']))
        ].copy()

        if follow_up_df.empty:
            return follow_up_df

        # IMPORTANT: base FOLLOW_UP_2 on FollowUp_1_Timestamp
        follow_up_df['FU1_DT'] = pd.to_datetime(
            follow_up_df['FollowUp_1_Timestamp'], errors='coerce'
        )
        follow_up_df = follow_up_df.dropna(subset=['FU1_DT'])

        follow_up_df['Days_Since_FU1'] = (today - follow_up_df['FU1_DT']).dt.days

        return follow_up_df[
            (follow_up_df['Days_Since_FU1'] >= 6) &
            (follow_up_df['Days_Since_FU1'] <= 8)
        ]

    return pd.DataFrame()