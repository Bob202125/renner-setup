import AppKit
let output=CommandLine.arguments[1]
let n=1024
let image=NSImage(size:NSSize(width:n,height:n))
image.lockFocus()
let rect=NSRect(x:70,y:70,width:884,height:884)
let path=NSBezierPath(roundedRect:rect,xRadius:196,yRadius:196)
NSGradient(colors:[NSColor(calibratedRed:0.12,green:0.19,blue:0.35,alpha:1),NSColor(calibratedRed:0.025,green:0.055,blue:0.13,alpha:1)])!.draw(in:path,angle:80)
for (i,offset) in [0.0,105.0,210.0].enumerated() {
    let p=NSBezierPath(); p.move(to:NSPoint(x:255,y:490+offset)); p.line(to:NSPoint(x:512,y:620+offset)); p.line(to:NSPoint(x:769,y:490+offset)); p.line(to:NSPoint(x:512,y:355+offset)); p.close()
    let colors=[NSColor(calibratedRed:0.28,green:0.47,blue:0.88,alpha:1),NSColor(calibratedRed:0.37,green:0.64,blue:0.92,alpha:1),NSColor(calibratedRed:0.55,green:0.88,blue:0.94,alpha:1)]
    colors[i].setFill(); p.fill()
}
let star=NSBezierPath(); star.move(to:NSPoint(x:755,y:240)); star.line(to:NSPoint(x:777,y:298)); star.line(to:NSPoint(x:835,y:320)); star.line(to:NSPoint(x:777,y:342)); star.line(to:NSPoint(x:755,y:400)); star.line(to:NSPoint(x:733,y:342)); star.line(to:NSPoint(x:675,y:320)); star.line(to:NSPoint(x:733,y:298)); star.close(); NSColor.white.setFill(); star.fill()
image.unlockFocus()
let rep=NSBitmapImageRep(data:image.tiffRepresentation!)!
try rep.representation(using:.png,properties:[:])!.write(to:URL(fileURLWithPath:output))
