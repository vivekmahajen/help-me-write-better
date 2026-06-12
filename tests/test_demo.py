from write_better import demo
from write_better.demo import DEMO_INPUT, RateLimiter, run_demo
from write_better.engine import Result
from write_better.modes import resolve_services


class _Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _fake_improve(text="POLISHED", model="claude-haiku-4-5"):
    def improve(req):
        return Result(text=text, model=model,
                      services=resolve_services("correct,tighten"),
                      input_tokens=5, output_tokens=4)
    return improve


def test_rate_limiter_caps_then_blocks():
    clock = _Clock()
    rl = RateLimiter(limit=2, window=100, clock=clock)
    assert rl.allow("1.2.3.4") is True
    assert rl.allow("1.2.3.4") is True
    assert rl.allow("1.2.3.4") is False          # third in-window call blocked
    assert rl.allow("9.9.9.9") is True            # other IP unaffected


def test_rate_limiter_window_expires():
    clock = _Clock()
    rl = RateLimiter(limit=1, window=100, clock=clock)
    assert rl.allow("ip") is True
    assert rl.allow("ip") is False
    clock.t += 101                                 # window passed
    assert rl.allow("ip") is True


def test_demo_success_is_real_not_fallback():
    rl = RateLimiter(limit=5, clock=_Clock())
    r = run_demo("Their going too the store", "ip",
                 limiter=rl, improve_fn=_fake_improve(), key_present=True)
    assert r.fallback is False
    assert r.text == "POLISHED"
    assert r.model == "claude-haiku-4-5"
    assert r.services == ["correct", "tighten"]
    assert r.reason is None


def test_demo_without_key_is_labelled_sample():
    rl = RateLimiter(limit=5, clock=_Clock())
    r = run_demo("anything", "ip", limiter=rl,
                 improve_fn=_fake_improve(), key_present=False)
    assert r.fallback is True
    assert r.reason == "no_key"
    assert r.model == "sample"
    assert r.input == DEMO_INPUT and r.text != DEMO_INPUT


def test_demo_over_limit_falls_back():
    rl = RateLimiter(limit=1, clock=_Clock())
    ok = run_demo("x", "ip", limiter=rl, improve_fn=_fake_improve(), key_present=True)
    over = run_demo("x", "ip", limiter=rl, improve_fn=_fake_improve(), key_present=True)
    assert ok.fallback is False
    assert over.fallback is True and over.reason == "rate_limited"


def test_demo_engine_error_falls_back():
    rl = RateLimiter(limit=5, clock=_Clock())

    def boom(req):
        raise RuntimeError("network down")

    r = run_demo("x", "ip", limiter=rl, improve_fn=boom, key_present=True)
    assert r.fallback is True and r.reason == "error"


def test_demo_empty_text_falls_back():
    rl = RateLimiter(limit=5, clock=_Clock())
    r = run_demo("   ", "ip", limiter=rl, improve_fn=_fake_improve(), key_present=True)
    assert r.fallback is True and r.reason == "empty"


def test_payload_is_json_safe():
    r = run_demo("x", "ip", limiter=RateLimiter(clock=_Clock()),
                 improve_fn=_fake_improve(), key_present=True)
    p = r.payload()
    assert set(p) == {"text", "input", "model", "services", "fallback", "reason"}
