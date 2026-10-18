import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from civit_helper.schedule import task_xml


class ScheduleTests(unittest.TestCase):
    def test_schedule_runs_only_daily_at_four_without_catchup(self):
        xml = task_xml(Path('C:/Test Folder/Civit Helper'), Path('C:/Python/pythonw.exe'))
        root = ET.fromstring(xml)
        ns = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}
        get = lambda p: root.find(p, ns).text
        self.assertTrue(get('.//t:StartBoundary').endswith('T04:00:00+08:00'))
        self.assertIsNone(root.find('.//t:Repetition', ns))
        self.assertEqual(get('.//t:StartWhenAvailable'), 'false')
        self.assertEqual(get('.//t:WakeToRun'), 'false')
        self.assertEqual(get('.//t:MultipleInstancesPolicy'), 'IgnoreNew')
        self.assertEqual(Path(get('.//t:Command')), Path('C:/Python/pythonw.exe'))
        self.assertIn('--source scheduled', get('.//t:Arguments'))
        self.assertNotIn('Password', xml)

    def test_xml_escapes_project_path(self):
        root = ET.fromstring(task_xml(Path('C:/A&B'), Path('C:/Python/pythonw.exe')))
        ns = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}
        self.assertEqual(Path(root.find('.//t:WorkingDirectory', ns).text), Path('C:/A&B'))

    def test_no_logon_trigger_and_current_user_principal(self):
        root = ET.fromstring(task_xml(Path('C:/Tool'), Path('C:/Python/pythonw.exe'), user_sid='S-1-5-21-123'))
        ns = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}
        self.assertIsNone(root.find('.//t:LogonTrigger', ns))
        self.assertEqual(root.find('.//t:Principal/t:UserId', ns).text, 'S-1-5-21-123')


if __name__ == '__main__':
    unittest.main()
