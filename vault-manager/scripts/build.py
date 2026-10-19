from pathlib import Path
import json,os,plistlib,shutil,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]; BUILD=ROOT/'build.noindex'; BUILD.mkdir(exist_ok=True)
def run(*args): subprocess.run(list(map(str,args)),check=True)
# Some CLT upgrades leave both old and new SwiftBridging module maps.
# Hide only the stale duplicate for this build; never edit the system SDK.
overlay=[]
old=Path('/Library/Developer/CommandLineTools/usr/include/swift/module.modulemap')
new=old.with_name('bridging.modulemap')
if old.exists() and new.exists() and 'module SwiftBridging' in old.read_text():
    empty=BUILD/'empty.modulemap'; empty.write_text('// Build-local compatibility overlay\n')
    ov=BUILD/'sdk-overlay.json'; ov.write_text(json.dumps({'version':0,'roots':[{'type':'file','name':str(old),'external-contents':str(empty)}]}))
    overlay=['-Xcc','-ivfsoverlay','-Xcc',str(ov)]
app=BUILD/'Vault Manager.app'; mac=app/'Contents/MacOS'; res=app/'Contents/Resources'; mac.mkdir(parents=True,exist_ok=True); res.mkdir(exist_ok=True)
run('swiftc','-parse-as-library','-O','-target','arm64-apple-macos14.0',*overlay,ROOT/'Sources/VaultManager.swift','-o',mac/'VaultManager','-framework','SwiftUI','-framework','AppKit')
run('swiftc',*overlay,ROOT/'scripts/icon.swift','-o',BUILD/'make-icon','-framework','AppKit')
run(BUILD/'make-icon',BUILD/'icon.png')
iconset=BUILD/'VaultManager.iconset'; iconset.mkdir(exist_ok=True)
for size in (16,32,128,256,512):
    for scale in (1,2):
        filename=f'icon_{size}x{size}'+('@2x' if scale==2 else '')+'.png'
        run('/usr/bin/sips','-z',size*scale,size*scale,BUILD/'icon.png','--out',iconset/filename)
run('/usr/bin/iconutil','-c','icns',iconset,'-o',res/'VaultManager.icns')
shutil.copy2(ROOT/'Sources/backend.py',res/'backend.py')
shutil.copy2(ROOT/'Sources/areas.json',res/'areas.json')
python=shutil.which('python3')
info={'CFBundleExecutable':'VaultManager','CFBundleIdentifier':'local.grady.vaultmanager','CFBundleName':'Vault Manager','CFBundleDisplayName':'Vault Manager','CFBundleVersion':'1','CFBundleShortVersionString':'0.1.0','CFBundlePackageType':'APPL','CFBundleIconFile':'VaultManager','LSMinimumSystemVersion':'14.0','NSHighResolutionCapable':True,'VMPython':python,'NSPrincipalClass':'NSApplication'}
(app/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
run('/usr/bin/codesign','--force','--deep','--sign','-',app)
workflow=BUILD/'Vault Manager.alfredworkflow'
alfred={'bundleid':'local.grady.vaultmanager.launch','name':'Vault Manager','description':'Open your vault gallery with vaults','createdby':'Grady','version':'1.0','objects':[{'uid':'launch','type':'alfred.workflow.input.keyword','version':1,'config':{'keyword':'vaults','text':'Vault Manager','subtext':'Open your vault gallery','argumenttype':2,'withspace':False}},{'uid':'action','type':'alfred.workflow.action.script','version':2,'config':{'script':'/usr/bin/open "$HOME/Applications/Vault Manager.app"','type':0,'escaping':0,'withspace':False,'scriptargtype':1}}],'connections':{'launch':[{'destinationuid':'action','modifiers':0,'modifiersubtext':''}]},'uidata':{'launch':{'xpos':100,'ypos':100},'action':{'xpos':400,'ypos':100}}}
with zipfile.ZipFile(workflow,'w') as z: z.writestr('info.plist',plistlib.dumps(alfred)); z.write(BUILD/'icon.png','icon.png')
print('Built '+str(app))
