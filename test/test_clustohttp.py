import clustohttp
import json
import mock
import os
import unittest
import urlparse


BASIC_CLUSTO = {
    'servers': {
        'server01': {
            'attrs': [
                {
                    "datatype": "int",
                    "key": "num_attr",
                    "number": 1,
                    "subkey": "num_attr_subkey",
                    "value": 1
                },
            ]
        }
    }
}


class MockClustoApp(object):
    def __init__(self, topology=BASIC_CLUSTO):
        self.topology = topology
        self.urls = {
            ('GET', '/query/get_by_name'): self.get_by_name,
            ('GET', '/query/get'): self.get,
            ('GET', '/query/get_entities'): self.get_entities,
            ('GET', '/server'): self.get_all,
            ('GET', '/servers/server01/addattr'): self.addattr,
        }

    def serialize_clusto_object(self, name, clusto_type, obj_dict):
        return json.dumps({
            'actions': ['addattr', 'attrs', 'delattr', 'get_port_attr',
                        'insert', 'ports', 'remove', 'rename', 'set_port_attr',
                        'setattr', 'show'],
            'attrs': obj_dict['attrs'],
            'contents': [],
            'driver': 'basicserver',
            'object': '/%s/%s' % (clusto_type, name),
            'parents': [],
        })

    def get_all(self, method, path, body, headers, query_params):
        # TODO: Return a response based on self.topology
        return 200, {}, '[]'

    def get_by_name(self, method, path, body, headers, query_params):
        name = query_params['name'][0]
        for clusto_type, clusto_objects in self.topology.items():
            if name in clusto_objects:

                return 200, {}, self.serialize_clusto_object(name, clusto_type,
                                                             clusto_objects[name])
        return 500, {}, 'OBJECT NOT FOUND'

    def get(self, method, path, body, headers, query_params):
        # TODO: Return a response based on self.topology
        name = query_params['name'][0]
        return 200, {}, '[{"object": "/server/%s" }]' % name

    def get_entities(self, method, path, body, headers, query_params):
        # TODO: Return a response based on self.topology
        return 200, {}, '[]'

    def addattr(self, method, path, body, headers, query_params):
        new_attr = {}
        for k in ('key', 'subkey', 'value', 'datatype', 'number'):
            if k in query_params:
                new_attr[k] = query_params[k][0]
                if k == 'number':
                    new_attr[k] = int(new_attr[k])
            else:
                if k == 'datatype':
                    new_attr[k] = 'string'
                else:
                    new_attr[k] = None

        self.topology['servers']['server01']['attrs'].append(new_attr)
        return 200, {}, self.serialize_clusto_object(
            'server01', 'server', self.topology['servers']['server01'])

    def __call__(self, method, path, body='', headers=None):
        if headers is None:
            headers = {}
        path_parts = urlparse.urlsplit(path)
        path = path_parts.path
        query_params = urlparse.parse_qs(path_parts.query)

        for path_spec, handler in self.urls.items():
            if path_spec[0] == method and path_spec[1] == path:
                return handler(method, path, body, headers, query_params)

        raise NotImplementedError('No action for %s %s' % (method, path))

application = MockClustoApp()


def mock_request(method, path, body='', headers=None):
    return application(method, path, body, headers)


def get_mock_clusto(url='https://mock-clusto'):
    clusto = clustohttp.ClustoProxy(url=url)
    clusto.request = mock.Mock(side_effect=mock_request)
    return clusto


class ClustoProxyTestCase(unittest.TestCase):
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
        c.get_by_name('server01')

    def test_basic_get(self):
        c = get_mock_clusto()
        c.get('server01')

    def test_basic_get_all(self):
        c = get_mock_clusto()
        c.get_all(resource_type='server')

    def test_basic_get_entities(self):
        c = get_mock_clusto()
        c.get_entities()


class EntityProxyTestCase(unittest.TestCase):
    def test_add_attr_zeroes(self):
        c = get_mock_clusto()
        obj = c.get_by_name('server01')
        obj = obj.add_attr('newkey', 'newsubkey', 'newvalue', number=0)
        found = False
        for attr in obj.attrs():
            if attr['key'] == 'newkey' and attr['subkey'] == 'newsubkey' and \
                    attr['value'] == 'newvalue' and attr['number'] == 0:
                found = True
        self.assertEqual(found, True,
                         'No attr with key=newkey, subkey=newsubkey, '
                         'value=newvalue, number=0')
