"""Verify that only verification-code prompts use hidden input."""
from pathlib import Path
import sys
import unittest
import builtins
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'host'))
from auth_entry import code_input
import auth_entry


class AuthInputTests(unittest.TestCase):
    def test_bootstrap_forwards_arguments_and_restores_input_after_exit(self):
        original=builtins.input
        def helper(path,run_name):
            self.assertEqual(sys.argv[1:],['--synthetic-option'])
            self.assertEqual(builtins.input('2FA code: '),'synthetic-code')
            raise SystemExit(0)
        with patch.object(sys,'argv',['auth_entry.py','synthetic_helper.py','--synthetic-option']), \
             patch.object(sys,'path',sys.path.copy()), \
             patch('auth_entry.runpy.run_path',side_effect=helper), \
             patch('auth_entry.getpass.getpass',return_value='synthetic-code'):
            with self.assertRaises(SystemExit):auth_entry.main()
        self.assertIs(builtins.input,original)

    def test_verification_codes_never_use_echoing_input(self):
        for prompt in ('SMS code: ', '2FA code: '):
            ordinary=Mock()
            with patch('auth_entry.getpass.getpass',return_value='synthetic-code') as hidden:
                self.assertEqual(code_input(ordinary,prompt),'synthetic-code')
                hidden.assert_called_once_with(prompt)
                ordinary.assert_not_called()

    def test_account_and_selection_prompts_keep_ordinary_input(self):
        ordinary=Mock(return_value='synthetic-selection')
        with patch('auth_entry.getpass.getpass') as hidden:
            self.assertEqual(code_input(ordinary,'Apple ID: '),'synthetic-selection')
            hidden.assert_not_called()
            ordinary.assert_called_once_with('Apple ID: ')
