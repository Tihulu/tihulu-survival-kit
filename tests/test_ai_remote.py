"""No network calls: verify remote endpoint policy and Ollama/OpenAI adapters."""
import unittest
from unittest.mock import patch
from tihulu_runtime.ai_remote import RemoteAIClient, RemoteAIError, RemoteEndpoint, _private_host


class Fake(RemoteAIClient):
    def __init__(self, endpoint, replies):
        super().__init__(endpoint)
        self.replies = replies
        self.calls = []

    def _request(self, path, payload=None):
        self.calls.append((path, payload))
        return self.replies[path]


class RemoteTests(unittest.TestCase):
    def test_reject_insecure_lan_or_embedded_credentials(self):
        for url in ('http://192.168.1.10:11434', 'https://user:pw@host.local',
                    'https://host.local/v1', 'file:///etc/passwd',
                    'https://host.local/?x=1'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                RemoteEndpoint(url, 'ollama')

    def test_loopback_ollama_api(self):
        client = Fake(RemoteEndpoint('http://127.0.0.1:11434', 'ollama'), {
            '/api/tags': {'models': [{'name': 'qwen3:1.7b'}]},
            '/api/generate': {'response': 'Merhaba'},
        })
        self.assertEqual(client.list_models(), ('qwen3:1.7b',))
        self.assertEqual(client.generate(model='qwen3:1.7b', prompt='Hi'), 'Merhaba')
        self.assertFalse(client.calls[-1][1]['stream'])

    def test_openai_compatible_llamacpp_or_vllm(self):
        for flavor in ('llamacpp', 'vllm'):
            client = Fake(RemoteEndpoint('https://gpu.home.arpa:8080', flavor), {
                '/v1/models': {'data': [{'id': 'model-a'}]},
                '/v1/chat/completions': {
                    'choices': [{'message': {'content': 'Answer'}}]},
            })
            self.assertEqual(client.list_models(), ('model-a',))
            self.assertEqual(client.generate(model='model-a', prompt='Question'), 'Answer')

    @patch('tihulu_runtime.ai_remote.socket.getaddrinfo')
    def test_public_remote_address_refused(self, lookup):
        lookup.return_value = [(2, 1, 6, '', ('8.8.8.8', 0))]
        with self.assertRaises(RemoteAIError):
            _private_host('gpu.example.com')
        lookup.return_value = [(2, 1, 6, '', ('100.100.100.100', 0))]
        _private_host('gpu.tailnet.example')

    def test_hailo_installable_models_separate_from_downloaded(self):
        client = Fake(RemoteEndpoint('http://127.0.0.1:8000',
                                     'hailo_ollama'), {
            '/hailo/v1/list': {'models': ['qwen2:1.5b']},
            '/api/tags': {'models': []},
        })
        self.assertEqual(client.list_installable_hailo_models(), ('qwen2:1.5b',))
        self.assertEqual(client.list_models(), ())

    def test_secret_redaction_and_error_not_success(self):
        endpoint = RemoteEndpoint('https://gpu.local', 'ollama',
                                  bearer_token='private-token')
        self.assertNotIn('private-token', repr(endpoint))
        client = Fake(endpoint, {'/api/generate': {'error': 'no model'}})
        with self.assertRaises(RemoteAIError):
            client.generate(model='unknown', prompt='Hi')


if __name__ == '__main__':
    unittest.main()
