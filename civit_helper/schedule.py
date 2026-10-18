import csv
import subprocess
from datetime import datetime
from xml.sax.saxutils import escape
from .state import TAIPEI

TASK_NAME = 'CivitHelper_Daily'


def task_xml(project, pythonw, user_sid=None):
    if user_sid is None:
        text = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'],
                                       creationflags=subprocess.CREATE_NO_WINDOW).decode(errors='replace')
        user_sid = next(csv.reader([text.strip()]))[1]
    if not user_sid.startswith('S-1-'):
        raise ValueError('無法取得目前 Windows 使用者 SID。')
    first = datetime.now(TAIPEI).replace(hour=4, minute=0, second=0, microsecond=0)
    # Today's missed trigger is intentionally eligible for StartWhenAvailable.
    return f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Civit Helper：台灣時間 04:00；未完成每 30 分鐘補跑。</Description></RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <Repetition><Interval>PT30M</Interval><Duration>P1D</Duration><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>
      <StartBoundary>{first.isoformat()}</StartBoundary><Enabled>true</Enabled>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
    <LogonTrigger><Enabled>true</Enabled><UserId>{escape(user_sid)}</UserId><Delay>PT2M</Delay></LogonTrigger>
  </Triggers>
  <Principals><Principal id="User"><UserId>{escape(user_sid)}</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable><RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand><Enabled>true</Enabled><Hidden>true</Hidden>
    <WakeToRun>false</WakeToRun><ExecutionTimeLimit>PT25M</ExecutionTimeLimit>
  </Settings>
  <Actions Context="User"><Exec>
    <Command>{escape(str(pythonw))}</Command>
    <Arguments>{escape('"' + str(project / 'app.py') + '" run --source scheduled')}</Arguments>
    <WorkingDirectory>{escape(str(project))}</WorkingDirectory>
  </Exec></Actions>
</Task>'''
