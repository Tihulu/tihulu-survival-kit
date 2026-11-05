import unittest
from tihulu_runtime.ai_energy import route_for_energy
from tihulu_runtime.ai_hardware import InferenceTarget, ModelSpec

CPU = ModelSpec('model', 'gguf', 3, 'Q4', 1000, 2048,
                {'cpu_local': 1000, 'remote_server': 900},
                frozenset({'cpu_local', 'remote_server'}))
TARGETS = (InferenceTarget('cpu_local', True, 10000),
           InferenceTarget('remote_server', True, 10000))


class EnergyTests(unittest.TestCase):
    def test_eco_does_not_guess_from_pi_only_power(self):
        route = route_for_energy(CPU, TARGETS, mode='Eco', evidence={
            'cpu_local|model': {'total_joules_including_remote': 8}})
        self.assertEqual(route['selected'], 'cpu_local')
        self.assertEqual(route['energy_evidence'], 'Not Tested')

    def test_eco_prefers_lower_total_measured_energy(self):
        route = route_for_energy(CPU, TARGETS, mode='Eco', evidence={
            'cpu_local|model': {'total_joules_including_remote': 20},
            'remote_server|model': {'total_joules_including_remote': 15}})
        self.assertEqual(route['selected'], 'remote_server')
        self.assertEqual(route['energy_evidence'], 'Measured end-to-end')

    def test_custom_priority(self):
        route = route_for_energy(CPU, TARGETS, mode='Custom',
                                 preferred=('remote_server','cpu_local','npu_local'))
        self.assertEqual(route['selected'], 'remote_server')


if __name__ == '__main__':
    unittest.main()
