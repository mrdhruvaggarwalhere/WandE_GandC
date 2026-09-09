import pytest
import os
import json
from app.core.email_gateway import (
    get_email_config,
    save_email_config,
    DEFAULT_REDIFFMAIL_CONFIG
)

def test_default_rediffmail_config(tmp_path):
    test_db = str(tmp_path / "test_email.db")
    cfg = get_email_config(test_db)
    assert cfg['smtp_user'] == 'ganeshsgnr@rediffmail.com'
    assert cfg['smtp_host'] == 'smtp.rediffmail.com'
    assert cfg['smtp_port'] == 587
    assert cfg['has_password'] is False

def test_save_and_mask_rediffmail_config(tmp_path):
    test_db = str(tmp_path / "test_email.db")
    saved = save_email_config({
        'smtp_user': 'ganeshsgnr@rediffmail.com',
        'smtp_pass': 'SecretP@ss123',
        'smtp_host': 'smtp.rediffmail.com',
        'smtp_port': 587,
        'from_name': 'Ganesh & Company',
        'use_ssl': 0,
        'is_enabled': 1
    }, db_path=test_db)

    assert saved['has_password'] is True
    assert saved['smtp_pass'] == '••••••••'

    # Unmasked check
    unmasked = get_email_config(test_db, mask_password=False)
    assert unmasked['smtp_pass'] == 'SecretP@ss123'
