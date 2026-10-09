"""Experimental Final Cut Pro 7 XML timeline for Premiere."""
import xml.etree.ElementTree as ET

def child(parent,tag,text=None,**attributes):
    obj=ET.SubElement(parent,tag,attributes)
    if text is not None: obj.text=str(text)
    return obj

def build(source,segments,target,metadata):
    fraction=metadata.get("fps","30/1")
    try:
        a,b=map(int,fraction.split("/"))
        fps=a/b
    except (ValueError,ZeroDivisionError):fps=30
    rate=max(1,round(fps))
    total=int(round(sum(b-a for a,b in segments)*rate))
    doc=ET.Element("xmeml",version="4")
    seq=child(doc,"sequence",id="zax-silence-timeline")
    child(seq,"name","ZAX Silence Cut Timeline")
    child(seq,"duration",total)
    r=child(seq,"rate");child(r,"timebase",rate)
    child(r,"ntsc","TRUE" if abs(fps-rate)>.01 else "FALSE")
    m=child(seq,"media")
    def track(kind):
        t=child(child(m,kind),"track")
        pos=0
        for i,(start,end) in enumerate(segments,1):
            first=round(start*rate);last=round(end*rate)
            length=max(1,last-first)
            item=child(t,"clipitem",id=kind+"-"+str(i))
            child(item,"name",source.name)
            child(item,"duration",round(metadata["duration"]*rate))
            child(item,"start",pos)
            child(item,"end",pos+length)
            child(item,"in",first)
            child(item,"out",first+length)
            f=child(item,"file",id="source-"+kind+"-"+str(i))
            child(f,"name",source.name)
            child(f,"pathurl",source.resolve().as_uri())
            child(f,"duration",round(metadata["duration"]*rate))
            pos+=length
    track("video")
    if metadata["audio"]: track("audio")
    ET.ElementTree(doc).write(target,encoding="utf-8",xml_declaration=True)
    return target
