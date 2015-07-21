import clustohttp
import unittest
import mock
import urlparse
import os


class MockClustoApp(object):
    def __init__(self):
        self.urls = {
            ('GET', '/query/get_by_name'): self.get_by_name,
            ('GET', '/query/get'): self.get,
            ('GET', '/query/get_entities'): self.get_entities,
            ('GET', '/server'): self.get_all,
        }

    def get_all(self, body, query_params):
        return 200, {}, '[]'

    def get_by_name(self, body, query_params):
        name = query_params['name'][0]
        return 200, {}, '{"object": "/server/%s" }' % name

    def get(self, body, query_params):
        name = query_params['name'][0]
        return 200, {}, '[{"object": "/server/%s" }]' % name

    def get_entities(self, body, query_params):
        return 200, {}, '[]'

    def __call__(self, method, path, body='', headers=None):
        if headers is None:
            headers = {}
        path_parts = urlparse.urlsplit(path)
        path = path_parts.path
        query_params = urlparse.parse_qs(path_parts.query)

        for path_spec, handler in self.urls.items():
            if path_spec[0] == method and path_spec[1] == path:
                return handler(body, query_params)

        raise NotImplementedError('No action for %s %s' % (method, path))

application = MockClustoApp()


def mock_request(method, path, body='', headers=None):
    return application(method, path, body, headers)


def get_mock_clusto(url='https://mock-clusto'):
    clusto = clustohttp.ClustoProxy(url=url)
    clusto.request = mock.Mock(side_effect=mock_request)
    return clusto


class ClustoHTTPTestCase(unittest.TestCase):
    def test_environment_init(self):
        os.environ['CLUSTO_URL'] = 'http://testval'
        c = get_mock_clusto(url=None)
        self.assertEqual(c.url, 'http://testval')
        del os.environ['CLUSTO_URL']

    def test_no_environment_no_url(self):
        with self.assertRaises(ValueError):
            get_mock_clusto(url=None)

    def test_request(self):
        c = get_mock_clusto()
        c.get_by_name('dchen')

    def test_basic_get(self):
        c = get_mock_clusto()
        c.get('dchen')

    def test_basic_get_all(self):
        c = get_mock_clusto()
        c.get_all(resource_type='server')

    def test_basic_get_entities(self):
        c = get_mock_clusto()
        c.get_entities()
