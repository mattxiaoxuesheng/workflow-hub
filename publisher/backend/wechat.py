"""Server-only adapter. Mutations are never retried automatically."""
import time
import threading
import httpx

class WeChatError(Exception):
    pass

class WeChat:
    def __init__(self, app_id, secret, client=None):
        self.app_id, self.secret = app_id, secret
        self.client = client or httpx.Client(timeout=45, follow_redirects=False)
        self.token, self.expires = '', 0
        self.lock = threading.Lock()

    def check(self, response):
        try:
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as e:
            raise WeChatError('微信网络响应异常，请先核对微信后台，勿直接重复提交') from e
        if data.get('errcode', 0):
            raise WeChatError(f'微信错误码 {data["errcode"]}')
        return data

    def access_token(self):
        if not self.app_id or not self.secret:
            raise WeChatError('尚未配置公众号 AppID / AppSecret')
        with self.lock:
            if time.time() >= self.expires:
                try:
                    data = self.check(self.client.post('https://api.weixin.qq.com/cgi-bin/stable_token', json={
                        'grant_type': 'client_credential', 'appid': self.app_id,
                        'secret': self.secret, 'force_refresh': False}))
                    self.token = data['access_token']
                    self.expires = time.time() + max(1, data['expires_in'] - 300)
                except (httpx.HTTPError, KeyError) as e:
                    raise WeChatError('无法取得微信凭证') from e
        return self.token

    def call(self, endpoint, payload=None, files=None):
        params = {'access_token': self.access_token()}
        if endpoint == 'material/add_material':
            params['type'] = 'image'
        try:
            return self.check(self.client.post('https://api.weixin.qq.com/cgi-bin/' + endpoint,
                params=params, json=payload if files is None else None, files=files))
        except httpx.HTTPError as e:
            raise WeChatError('微信请求结果不确定，请到微信后台核对') from e

    def upload(self, content, filename, mime, cover=False):
        data = self.call('material/add_material' if cover else 'media/uploadimg', files={'media': (filename, content, mime)})
        key = 'media_id' if cover else 'url'
        if key not in data:
            raise WeChatError('微信上传响应缺少素材标识')
        return data[key]
