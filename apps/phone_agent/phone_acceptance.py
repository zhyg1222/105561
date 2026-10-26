#!/usr/bin/env python3
import argparse, json, re, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, r"D:\yige-personal-kb\xiaojuju\src")
from PIL import Image
from rapidocr_onnxruntime import RapidOCR
from xiaojuju_core.config import load_config
from xiaojuju_core.adb_control import select_serial
from xiaojuju_core.phone_acceptance import evaluate_phone

ADB=Path(r"D:\yige-personal-kb\.runtime\android-tools\extracted\platform-tools\adb.exe")
OUT=Path(r"D:\yige-personal-kb\.runtime\phone-agent")

def adb(serial,*args,timeout=30):
    return subprocess.run([str(ADB),'-s',serial,*args],capture_output=True,timeout=timeout)

def text(serial,*args):
    return adb(serial,*args).stdout.decode('utf-8','replace').strip()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--serial'); args=ap.parse_args()
    cfg=load_config(); pc=cfg['runtime']['phone_control']
    devices=subprocess.run([str(ADB),'devices'],capture_output=True,timeout=15).stdout.decode('utf-8','replace')
    serial=args.serial or select_serial(devices,pc['mode'],pc.get('usb_serial',''),pc.get('wireless_serial',''),pc.get('wireless_enabled',False))
    if not serial:
        print(json.dumps({"passed":False,"failures":["device_not_connected"],"warnings":[]},ensure_ascii=False)); raise SystemExit(1)
    adb(serial,'shell','input','keyevent','KEYCODE_WAKEUP'); adb(serial,'shell','wm','dismiss-keyguard'); time.sleep(1)
    OUT.mkdir(parents=True,exist_ok=True); shot=OUT/'acceptance.png'; r=adb(serial,'exec-out','screencap','-p'); shot.write_bytes(r.stdout)
    screenshot_ok=False; ocr_count=0
    try:
        im=Image.open(shot); im.verify(); screenshot_ok=True
        result,_=RapidOCR()(str(shot)); ocr_count=len(result or [])
    except Exception: pass
    model=text(serial,'shell','getprop','ro.product.model'); release=text(serial,'shell','getprop','ro.build.version.release')
    sdk_text=text(serial,'shell','getprop','ro.build.version.sdk'); sdk=int(sdk_text) if sdk_text.isdigit() else 0
    packages=text(serial,'shell','pm','list','packages','com.tencent.mm'); wechat='com.tencent.mm' in packages
    wx=pc.get('wechat',{})
    wx_user=str(wx.get('android_user','0')); wx_package=wx.get('package','com.tencent.mm')
    user_packages=text(serial,'shell','pm','list','packages','--user',wx_user,wx_package)
    wechat_user_listed=wx_package in user_packages
    battery_text=text(serial,'shell','dumpsys','battery'); level=0; powered=False
    m=re.search(r'level:\s*(\d+)',battery_text); level=int(m.group(1)) if m else 0
    powered=bool(re.search(r'AC powered:\s*true|USB powered:\s*true|Wireless powered:\s*true',battery_text,re.I))
    mem=text(serial,'shell','cat','/proc/meminfo'); m=re.search(r'MemTotal:\s*(\d+)\s*kB',mem); ram_gb=round(int(m.group(1))/1024/1024,2) if m else 0
    df=text(serial,'shell','df','-k','/data'); storage_gb=None
    m=re.search(r'\s(\d+)\s+\d+%\s+/data',df)
    if m: storage_gb=round(int(m.group(1))/1024/1024,2)
    result=evaluate_phone(connected=True,screenshot_ok=screenshot_ok,ocr_text_count=ocr_count,wechat_installed=wechat,battery_level=level,powered=powered,ram_gb=ram_gb,android_sdk=sdk,storage_gb=storage_gb)
    if not wechat_user_listed:
        result["warnings"].append("wechat_package_not_listed_for_configured_user")
    result.update({"serial":serial,"model":model,"android":release,"sdk":sdk,"battery":level,"powered":powered,"ram_gb":ram_gb,"storage_gb":storage_gb,"ocr_text_count":ocr_count,"wechat_installed":wechat,"wechat_package":wx_package,"wechat_android_user":wx_user,"wechat_variant":wx.get("variant",""),"wechat_user_listed":wechat_user_listed,"screenshot":str(shot)})
    (OUT/f"acceptance-{serial.replace(':','_')}.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(0 if result['passed'] else 1)

if __name__=='__main__': main()