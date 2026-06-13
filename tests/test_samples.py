from write_better.modes import MODES
from write_better.samples import SAMPLES


def test_every_service_has_a_nonempty_sample():
    names = {m.name for m in MODES}
    assert set(SAMPLES) == names, "samples must cover exactly the service set"
    assert all(SAMPLES[name].strip() for name in SAMPLES)


def test_samples_count_matches_services():
    assert len(SAMPLES) == len(MODES) == 45
