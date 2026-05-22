def click_action(page, locator, step, context, **kwargs):
    try:
        _click_with_supported_options(locator, timeout=8000, no_wait_after=True)
        return
    except Exception as first_error:
        try:
            _click_with_supported_options(locator, timeout=2000, force=True, no_wait_after=True)
            return
        except Exception:
            try:
                locator.evaluate("element => element.click()")
                return
            except Exception:
                raise first_error


def _click_with_supported_options(locator, **kwargs):
    try:
        locator.click(**kwargs)
    except TypeError:
        locator.click()
