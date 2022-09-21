import logging

import pytest

log = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
@pytest.mark.skip_if_deployed
async def test_build_and_deploy(ops_test, series):
    """Build simple-stream charm and deploy it in bundle."""
    simple_stream_charm = await ops_test.build_charm(".")

    await ops_test.model.deploy(
        ops_test.render_bundle(
            "tests/functional/bundle.yaml.j2",
            simple_stream_charm=simple_stream_charm,
            series=series,
        )
    )
    await ops_test.model.wait_for_idle(status="unknown")
