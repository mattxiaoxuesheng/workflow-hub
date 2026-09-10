from publisher.backend.render import render


def test_preview_uses_configured_subpath_but_wechat_urls_are_unchanged(monkeypatch):
    monkeypatch.setenv('PUBLISHER_BASE_PATH', '/publisher/')
    content = '![Image](images/test.png)'
    assets = {'images/test.png': {}}
    preview = render(content, 'business', assets, version_id=7)
    assert '/publisher/api/v1/versions/7/assets/images/test.png' in preview
    published = render(content, 'business', assets, version_id=7,
                       wechat_urls={'images/test.png': 'https://mmbiz.qpic.cn/test'})
    assert 'https://mmbiz.qpic.cn/test' in published
    assert '/publisher/' not in published
