import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import config


class AdminResult(unittest.TestCase):
    def test_result_file_exists_before_elevation(self):
        spec = importlib.util.spec_from_file_location(
            'powershell_test', Path(__file__).resolve().parents[1] / 'system/powershell.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            def launch(*args, **kwargs):
                files = list(Path(folder).glob('powershell-*/result.json'))
                self.assertEqual(len(files), 1)
                self.assertEqual(files[0].read_text(), '')
                files[0].write_text(json.dumps({'success': True, 'exit_code': 0, 'stdout': 'True'}))
                return subprocess.CompletedProcess(args, 0, b'', b'')
            with patch.object(config, 'PRIVATE', Path(folder)), \
                 patch.object(module.ctypes.windll.shell32, 'IsUserAnAdmin', return_value=0), \
                 patch.object(module.subprocess, 'run', side_effect=launch):
                result = module.run('test', privilege='admin')
                self.assertTrue(result['success'])
                self.assertEqual(result['privilege'], 'admin')
