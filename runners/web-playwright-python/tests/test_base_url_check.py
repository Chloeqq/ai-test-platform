import pytest

from tools.check_base_url import check_base_url_reachable


@pytest.mark.contract
def test_check_base_url_reachable_reports_unreachable_port():
    with pytest.raises(RuntimeError, match="BASE_URL is unreachable"):
        check_base_url_reachable("http://127.0.0.1:9/login#/login", timeout=0.2)
