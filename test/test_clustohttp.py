import copy
import json
import mock
import os
import unittest
import urlparse

import clustohttp


BASIC_CLUSTO = {
    'server': {
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
        },
        'server02': {
            'attrs': []
        },
    }
}


class MockClustoApp(object):
    def __init__(self, topology=BASIC_CLUSTO):
        self.original_topology = topology
        self.topology = copy.deepcopy(self.original_topology)
        self.urls = {
            ('GET', '/query/get_by_name'): self.get_by_name,
            ('GET', '/query/get'): self.get,
            ('GET', '/query/get_entities'): self.get_entities,
            ('GET', '/server'): self.get_all,
            ('GET', '/server/server02/addattr'): self.addattr,
            ('GET', '/server/server02/setattr'): self.setattr,
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
        clusto_type = path.split('/')[1]
        all_objects = self.topology[clusto_type].keys()
        return 200, {}, json.dumps(['/%s/%s' % (clusto_type, name)
                                    for name in all_objects])

    def get_by_name(self, method, path, body, headers, query_params):
        name = query_params['name'][0]
        for clusto_type, clusto_objects in self.topology.items():
            if name in clusto_objects:
                return 200, {}, self.serialize_clusto_object(name, clusto_type,
                                                             clusto_objects[name])
        return 500, {}, 'OBJECT NOT FOUND'

    def get(self, method, path, body, headers, query_params):
        name = query_params['name'][0]
        for clusto_type, clusto_objects in self.topology.items():
            if name in clusto_objects:
                response = self.serialize_clusto_object(name, clusto_type,
                                                        clusto_objects[name])
                response = "[" + response + "]"
                return 200, {}, response
        return 404, {}, '404 Not Found'

    def get_entities(self, method, path, body, headers, query_params):
        return 200, {}, '[]'

    def _attr_from_params(self, params):
        """ Takes a query string params dictionary from urlparse.parse_qs and
        returns the python dictionary representation of an attribute.
        """
        new_attr = {}
        for k in ('key', 'subkey', 'value', 'datatype', 'number'):
            if k in params:
                if type(params[k]) is list and len(params[k]) != 0:
                    new_attr[k] = params[k][0]
                    # number should be an integer type, but it is passed in as
                    # a string, so cast
                    if k == 'number':
                        new_attr[k] = int(new_attr[k])
            else:
                if k == 'datatype':
                    new_attr[k] = 'string'
                else:
                    new_attr[k] = None
        return new_attr

    def addattr(self, method, path, body, headers, query_params):
        servername = path.split('/')[2]
        new_attr = self._attr_from_params(query_params)
        self.topology['server'][servername]['attrs'].append(new_attr)
        return 200, {}, self.serialize_clusto_object(
            servername, 'server', self.topology['server'][servername])

    def setattr(self, method, path, body, headers, query_params):
        servername = path.split('/')[2]
        new_attr = self._attr_from_params(query_params)

        for attr in self.topology['server'][servername]['attrs']:
            if attr['key'] == new_attr['key'] and attr['subkey'] == \
                    new_attr['subkey']:
                attr['value'] = new_attr['value']
        return 200, {}, self.serialize_clusto_object(
            servername, 'server', self.topology['server'][servername])

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

    def reset_all(self):
        self.topology = copy.deepcopy(self.original_topology)


application = MockClustoApp()


def mock_request(method, path, body='', headers=None):
    return application(method, path, body, headers)


def get_mock_clusto(url='https://mock-clusto'):
    clusto = clustohttp.ClustoProxy(url=url)
    clusto.request = mock.Mock(side_effect=mock_request)
    return clusto


class ClustoProxyTestCase(unittest.TestCase):
    def setUp(self):
        self.clusto = get_mock_clusto()

    def test_environment_init(self):
        os.environ['CLUSTO_URL'] = 'http://testval'
        c = get_mock_clusto(url=None)
        self.assertEqual(c.url, 'http://testval')
        del os.environ['CLUSTO_URL']

    def test_no_environment_no_url(self):
        with self.assertRaises(ValueError):
            get_mock_clusto(url=None)

    def test_request(self):
        result = self.clusto.get_by_name('server01')
        self.assertIs(type(result), clustohttp.EntityProxy)
        self.assertEqual(result.type, 'server')
        self.assertEqual(len(result.attrs()), 1)

    def test_basic_get(self):
        result = self.clusto.get('server01')
        self.assertIs(type(result), list)
        self.assertEqual(len(result), 1)

    def test_basic_get_all(self):
        result = self.clusto.get_all(resource_type='server')
        self.assertEqual(len(result), 2)

    def test_basic_get_entities(self):
        result = self.clusto.get_entities()
        self.assertEqual(len(result), 0)


class EntityProxyAttributeTestCase(unittest.TestCase):
    def setUp(self):
        application.reset_all()
        self.clusto = get_mock_clusto()

    def test_basic_set_attr(self):
        obj = self.clusto.get_by_name('server02')
        obj = obj.add_attr('foo', 'bar', 'baz')
        new_attr = obj.attrs()[0]
        self.assertEqual(len(obj.attrs()), 1)
        self.assertEqual(new_attr['key'], 'foo')
        self.assertEqual(new_attr['subkey'], 'bar')
        self.assertEqual(new_attr['value'], 'baz')

        obj = obj.set_attr('foo', 'bar', 'garply')
        new_attr = obj.attrs()[0]
        self.assertEqual(len(obj.attrs()), 1)
        self.assertEqual(new_attr['key'], 'foo')
        self.assertEqual(new_attr['subkey'], 'bar')
        self.assertEqual(new_attr['value'], 'garply')

    def test_add_attr_zeroes(self):
        obj = self.clusto.get_by_name('server02')
        obj = obj.add_attr('foo', 'bar', 'baz', number=0)
        self.assertEqual(len(obj.attrs()), 1)
        new_attr = obj.attrs()[0]
        self.assertEqual(new_attr['key'], 'foo')
        self.assertEqual(new_attr['subkey'], 'bar')
        self.assertEqual(new_attr['value'], 'baz')
        self.assertEqual(new_attr['number'], 0)
