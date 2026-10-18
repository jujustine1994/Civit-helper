import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from civit_helper.schedule import task_xml


class ScheduleTests(unittest.TestCase):
    def test_schedule_taipei_retry_and_hidden_without_password(self):
        xml = task_xml(Path('C:/Test Folder/Civit Helper'), Path('C:/Python/pythonw.exe'))
        root = ET.fromstring(xml)
        ns = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}
        get = lambda p: root.find(p, ns).text
        self.assertTrue(get('.//t:StartBoundary').endswith('T04:00:00+08:00'))
        self.assertEqual(get('.//t:Interval'), 'PT30M')
        self.assertEqual(get('.//t:StartWhenAvailable'), 'true')
        self.assertEqual(get('.//t:WakeToRun'), 'false')
        self.assertEqual(get('.//t:MultipleInstancesPolicy'), 'IgnoreNew')
        self.assertEqual(Path(get('.//t:Command')), Path('C:/Python/pythonw.exe'))
        self.assertIn('--source scheduled', get('.//t:Arguments'))
        self.assertNotIn('Password', xml)

    def test_xml_escapes_project_path(self):
        root = ET.fromstring(task_xml(Path('C:/A&B'), Path('C:/Python/pythonw.exe')))
        ns = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}
        self.assertEqual(Path(root.find('.//t:WorkingDirectory', ns).text), Path('C:/A&B'))


if __name__ == '__main__':
    unittest.main()
