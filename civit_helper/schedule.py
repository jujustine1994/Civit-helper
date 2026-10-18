from datetime import datetime, timedelta
from xml.sax.saxutils import escape
from .state import TAIPEI

TASK_NAME = 'CivitHelper_Daily'


def task_xml(project, pythonw):
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
    <LogonTrigger><Enabled>true</Enabled><Delay>PT2M</Delay></LogonTrigger>
  </Triggers>
  <Principals><Principal id="User"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
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
