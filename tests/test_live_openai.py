import os

import pytest


@pytest.mark.live
def test_live_openai_requires_explicit_opt_in() -> None:
    if os.getenv("FCP_RUN_LIVE_OPENAI") != "1":
        pytest.skip("Set FCP_RUN_LIVE_OPENAI=1 and configure Credential Manager to opt in")
    pytest.skip("Run Test Connection in Settings for the explicitly configured live credential")
