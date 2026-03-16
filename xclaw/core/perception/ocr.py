"""PaddleOCR compatibility patch."""

_patched = False


def patch_paddleocr():
    """Patch PaddleOCR to silently drop unknown kwargs (use_gpu, use_dilation, etc.)
    that OmniParser's utils.py passes at module level.

    Safe to call multiple times — patches only once.
    """
    global _patched
    if _patched:
        return
    _patched = True

    from paddleocr._common_args import parse_common_args as _orig_parse
    import paddleocr._common_args as _args_mod
    import paddleocr._pipelines.base as _base_mod

    def _lenient_parse(kwargs, **kw):
        clean = {
            k: v
            for k, v in kwargs.items()
            if k
            in (
                "device",
                "enable_hpi",
                "use_tensorrt",
                "precision",
                "enable_mkldnn",
                "mkldnn_cache_capacity",
                "cpu_threads",
                "enable_cinn",
            )
        }
        return _orig_parse(clean, **kw)

    _args_mod.parse_common_args = _lenient_parse
    _base_mod.parse_common_args = _lenient_parse
