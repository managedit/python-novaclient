from __future__ import absolute_import

import os
import mock
import httplib2

from nose.tools import assert_raises, assert_equal

from novaclient.v1_1.shell import OpenStackShell, CommandError

from .fakes import FakeClient
from .utils import assert_in


# Patch os.environ to avoid required auth info.
def setup():
    global _old_env
    fake_env = {
        'NOVA_USERNAME': 'username',
        'NOVA_API_KEY': 'password',
        'NOVA_PROJECT_ID': 'project_id'
    }
    _old_env, os.environ = os.environ, fake_env.copy()

    # Make a fake shell object, a helping wrapper to call it, and a quick way
    # of asserting that certain API calls were made.
    global shell, _shell, assert_called, assert_called_anytime
    _shell = OpenStackShell()
    _shell._api_class = FakeClient
    assert_called = lambda m, u, b=None: _shell.cs.assert_called(m, u, b)
    assert_called_anytime = lambda m, u, b=None: \
                                _shell.cs.assert_called_anytime(m, u, b)
    shell = lambda cmd: _shell.main(cmd.split())


def teardown():
    global _old_env
    os.environ = _old_env


def test_boot():
    shell('boot --image 1 some-server')
    assert_called(
        'POST', '/servers',
        {'server': {'flavorRef': 1, 'name': 'some-server', 'imageRef': '1'}}
    )

    shell('boot --image 1 --meta foo=bar --meta spam=eggs some-server ')
    assert_called(
        'POST', '/servers',
        {'server': {'flavorRef': 1, 'name': 'some-server', 'imageRef': '1',
                    'metadata': {'foo': 'bar', 'spam': 'eggs'}}}
    )


def test_boot_files():
    testfile = os.path.join(os.path.dirname(__file__), 'testfile.txt')
    expected_file_data = open(testfile).read().encode('base64')

    shell('boot some-server --image 1 --file /tmp/foo=%s --file /tmp/bar=%s' %
                                                         (testfile, testfile))

    assert_called(
        'POST', '/servers',
        {'server': {'flavorRef': 1, 'name': 'some-server', 'imageRef': '1',
                    'personality': [
                        {'path': '/tmp/bar', 'contents': expected_file_data},
                        {'path': '/tmp/foo', 'contents': expected_file_data}
                    ]}
        }
    )


def test_boot_invalid_file():
    invalid_file = os.path.join(os.path.dirname(__file__), 'asdfasdfasdfasdf')
    assert_raises(CommandError, shell, 'boot some-server --image 1 '
                                       '--file /foo=%s' % invalid_file)


def test_boot_key_auto():
    mock_exists = mock.Mock(return_value=True)
    mock_open = mock.Mock()
    mock_open.return_value = mock.Mock()
    mock_open.return_value.read = mock.Mock(return_value='SSHKEY')

    @mock.patch('os.path.exists', mock_exists)
    @mock.patch('__builtin__.open', mock_open)
    def test_shell_call():
        shell('boot some-server --image 1 --key')
        assert_called(
            'POST', '/servers',
            {'server': {'flavorRef': 1, 'name': 'some-server', 'imageRef': '1',
                        'personality': [{
                            'path': '/root/.ssh/authorized_keys2',
                            'contents': ('SSHKEY').encode('base64')},
                        ]}
            }
        )

    test_shell_call()


def test_boot_key_auto_no_keys():
    mock_exists = mock.Mock(return_value=False)

    @mock.patch('os.path.exists', mock_exists)
    def test_shell_call():
        assert_raises(CommandError, shell, 'boot some-server --image 1 --key')

    test_shell_call()


def test_boot_key_file():
    testfile = os.path.join(os.path.dirname(__file__), 'testfile.txt')
    expected_file_data = open(testfile).read().encode('base64')
    shell('boot some-server --image 1 --key %s' % testfile)
    assert_called(
        'POST', '/servers',
        {'server': {'flavorRef': 1, 'name': 'some-server', 'imageRef': '1',
                    'personality': [
                        {'path': '/root/.ssh/authorized_keys2', 'contents':
                         expected_file_data},
                    ]}
        }
    )


def test_boot_invalid_keyfile():
    invalid_file = os.path.join(os.path.dirname(__file__), 'asdfasdfasdfasdf')
    assert_raises(CommandError, shell, 'boot some-server '
                                       '--image 1 --key %s' % invalid_file)


def test_flavor_list():
    shell('flavor-list')
    assert_called_anytime('GET', '/flavors/detail')


def test_image_list():
    shell('image-list')
    assert_called('GET', '/images/detail')


def test_create_image():
    shell('create-image sample-server mysnapshot')
    assert_called(
        'POST', '/servers/1234/action',
        {'createImage': {'name': 'mysnapshot', "metadata": {}}}
    )


def test_image_delete():
    shell('image-delete 1')
    assert_called('DELETE', '/images/1')


def test_list():
    shell('list')
    assert_called('GET', '/servers/detail')


def test_reboot():
    shell('reboot sample-server')
    assert_called('POST', '/servers/1234/action', {'reboot': {'type': 'SOFT'}})
    shell('reboot sample-server --hard')
    assert_called('POST', '/servers/1234/action', {'reboot': {'type': 'HARD'}})


def test_rebuild():
    shell('rebuild sample-server 1')
    assert_called('POST', '/servers/1234/action', {'rebuild': {'imageRef': 1}})


def test_rename():
    shell('rename sample-server newname')
    assert_called('PUT', '/servers/1234', {'server': {'name': 'newname'}})


def test_resize():
    shell('resize sample-server 1')
    assert_called('POST', '/servers/1234/action', {'resize': {'flavorRef': 1}})


def test_resize_confirm():
    shell('resize-confirm sample-server')
    assert_called('POST', '/servers/1234/action', {'confirmResize': None})


def test_resize_revert():
    shell('resize-revert sample-server')
    assert_called('POST', '/servers/1234/action', {'revertResize': None})


@mock.patch('getpass.getpass', mock.Mock(return_value='p'))
def test_root_password():
    shell('root-password sample-server')
    assert_called('POST', '/servers/1234/action', {'changePassword': {'adminPass': 'p'}})


def test_show():
    shell('show 1234')
    # XXX need a way to test multiple calls
    # assert_called('GET', '/servers/1234')
    assert_called('GET', '/images/2')


def test_delete():
    shell('delete 1234')
    assert_called('DELETE', '/servers/1234')
    shell('delete sample-server')
    assert_called('DELETE', '/servers/1234')


def test_help():
    @mock.patch.object(_shell.parser, 'print_help')
    def test_help(m):
        shell('help')
        m.assert_called()

    @mock.patch.object(_shell.subcommands['delete'], 'print_help')
    def test_help_delete(m):
        shell('help delete')
        m.assert_called()

    test_help()
    test_help_delete()

    assert_raises(CommandError, shell, 'help foofoo')


def test_debug():
    httplib2.debuglevel = 0
    shell('--debug list')
    assert httplib2.debuglevel == 1
