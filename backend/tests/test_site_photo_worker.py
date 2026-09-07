from wardrobe_backend.site_worker import site_device
from wardrobe_backend.ai.stylewell4b import StyleWell4BAnalyzer


def test_site_gpu_selection_preserves_overrides_and_requires_headroom():
    assert site_device('auto', True, 9 * 1024**3) == 'cuda:0'
    assert site_device('auto', True, 8 * 1024**3) == 'auto'
    assert site_device('auto', False, 12 * 1024**3) == 'auto'
    assert site_device('cpu', True, 12 * 1024**3) == 'cpu'


def test_photo_budget_is_opt_in_so_original_backend_behavior_is_preserved():
    original = StyleWell4BAnalyzer('test-model')
    website = StyleWell4BAnalyzer('test-model', max_image_pixels=262144)
    assert original.max_image_pixels is None
    assert website.max_image_pixels == 262144
    assert website.model_name == original.model_name
