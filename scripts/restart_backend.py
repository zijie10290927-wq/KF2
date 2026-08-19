import os, sys, subprocess, time, pathlib

ROOT = pathlib.Path(r'c:\Users\admin\Desktop\ZNKF\ZNKF\ZNKF\a1\KF2')
BACK = ROOT / 'ai-customer-backend'


def pid_using_port(port=8000):
    out = subprocess.check_output(['netstat', '-ano'], text=True)
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        if ':{}'.format(port) in parts[1] and parts[3] == 'LISTENING':
            return int(parts[4])
    return None


pid = pid_using_port(8000)
if pid:
    print('Killing pid', pid)
    subprocess.call(['taskkill', '/F', '/PID', str(pid)])
    time.sleep(1)

# Clear pycache
import shutil
for p in BACK.joinpath('app').rglob('__pycache__'):
    try:
        shutil.rmtree(p)
    except Exception:
        pass

# Start backend detached
os.chdir(BACK)
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
log_path = ROOT / 'scripts' / 'backend_8000_restart.log'
python_exe = sys.executable
with open(log_path, 'ab') as log:
    subprocess.Popen(
        [python_exe, '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000'],
        stdout=log, stderr=log, cwd=str(BACK),
        creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
    )
print('backend started, will sleep 10s for startup')
time.sleep(10)
import urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=8) as r:
        print('health:', r.status, r.read()[:300].decode())
except Exception as e:
    print('health fail:', e)
