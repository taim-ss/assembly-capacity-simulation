"""SYNTHETIC static checks and real installed Engine/PML compilation; no simulation."""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
INSTALL=Path("C:/Program Files/AnyLogic 8.9 Personal Learning Edition")


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--native-main",type=Path);args=parser.parse_args()
    path=ROOT/"model/P3_Assembly_Flow.alp";root=ET.parse(path).getroot()
    refs={"FreeformParamValue","RangeVariationParamValue"}
    ids=[e.text for p in root.iter() if p.tag not in refs for e in p if e.tag=="Id"]
    assert len(ids)==len(set(ids)),"Duplicate XML IDs"
    classes={c.findtext("Name"):c for c in root.findall("Model/ActiveObjectClasses/ActiveObjectClass")}
    assert set(classes)=={"Main","Job","Component"}
    main_=classes["Main"]
    objects={o.findtext("Name"):o for o in main_.findall("EmbeddedObjects/EmbeddedObject")}
    assert len(objects)==23,len(objects)
    connections=set()
    for link in main_.findall("Connectors/Connector"):
        parts=[]
        for prefix in ("Source","Target"):
            name=link.findtext(prefix+"EmbeddedObjectReference/ItemName")
            port=link.findtext(prefix+"ConnectableItemReference/ItemName")
            assert name in objects
            typ=objects[name].findtext("ActiveObjectClass/ClassName")
            allowed=({"in1","in2"} if typ=="Combine" else {"in"}) if prefix=="Target" else ({"outT","outF"} if typ=="SelectOutput" else {"out"})
            assert port in allowed,(name,port)
            parts.extend([name,port])
        connections.add(tuple(parts))
    if args.native_main:
        text=args.native_main.read_text(encoding="utf-8-sig")
        native=set(re.findall(r"\b(\w+)\.(\w+)\.connect\(\s*(\w+)\.(\w+)\s*\)",text))
        assert connections==native,dict(missing=sorted(connections-native),extra=sorted(native-connections))
    java=["import com.anylogic.engine.*; import com.anylogic.engine.presentation.*; import com.anylogic.libraries.processmodeling.*;","public abstract class Main extends Agent { public Main(){super(null,null,null);}"]
    for v in main_.findall("Variables/Variable"):
        expr=v.findtext("Properties/DefaultValue/Code") if v.get("Class")=="Parameter" else v.findtext("Properties/InitialValue/Code")
        java.append("public "+v.findtext("Properties/Type")+" "+v.findtext("Name")+"="+expr+";")
    for name,obj in objects.items():
        java.append("public "+obj.findtext("ActiveObjectClass/ClassName")+" "+name+";")
    count=0
    dynamic_types={'TextCode':'String','VisibleCode':'boolean','ScaleXCode':'double',
                   'XCode':'double','YCode':'double','ZCode':'double',
                   'ScaleYCode':'double','FillColorCode':'java.awt.Color'}
    for element in main_.findall('Presentation/Level/Presentation/*'):
        for key,typ in dynamic_types.items():
            node=element.find(key)
            if node is not None:
                assert not list(node) and node.text, f'Invalid dynamic shape schema: {key}'
                count+=1;java.append(f'{typ} shapeCheck{count}(){{return ({node.text});}}')
    for name,obj in objects.items():
        for param in obj.findall("Parameters/Parameter"):
            key=param.findtext("Name");value=param.findtext("Value/Code")
            if value is None:continue
            if key.startswith("on"):
                count+=1;java.append(f"void check{count}(Agent agent,Agent agent1,Agent agent2,Agent unit,double delayTime){{{value}}}")
    java.append("}")
    for name in ("Job","Component"):
        java.append("abstract class "+name+" extends Agent { public "+name+"(){super(null,null,null);}")
        for v in classes[name].findall("Variables/Variable"):
            java.append("public "+v.findtext("Properties/Type")+" "+v.findtext("Name")+"="+v.findtext("Properties/InitialValue/Code")+";")
        if name=="Job":java.append("public ShapeRectangle a3d_box;")
        for element in classes[name].findall('Presentation/Level/Presentation/*'):
            for key,typ in dynamic_types.items():
                node=element.find(key)
                if node is not None:
                    assert not list(node) and node.text
                    count+=1;java.append(f'{typ} shapeCheck{count}(){{return ({node.text});}}')
        java.append("}")
    jars=list((INSTALL/"plugins").glob("com.anylogic.engine*/*.jar"))+list((INSTALL/"plugins").glob("com.anylogic.engine*/lib/*.jar"))+list((INSTALL/"plugins").glob("com.anylogic.process_modeling_library_*/lib/ProcessModelingLibrary.jar"))
    cp=";".join(map(str,jars))
    from model_parts.distributions import NORMAL_QUANTILE_JAVA
    probe="public class InputProbe { public static void main(String[] args){java.util.function.DoubleUnaryOperator normalQ="+NORMAL_QUANTILE_JAVA+"; double[][] pairs={{0.5,0},{0.025,-1.959963984540054},{0.975,1.959963984540054},{1e-8,-5.612001244174789}};for(double[] p:pairs)if(Math.abs(normalQ.applyAsDouble(p[0])-p[1])>1e-9)throw new AssertionError(\"normal quantile\"); java.util.Random rng=new java.util.Random(14002); int loops=0;for(int i=0;i<100000;i++){double u=rng.nextDouble();loops+=Math.min(5,(int)Math.floor(Math.log(Math.max(u,1e-300))/Math.log(0.1)));} if(Math.abs(loops/100000.0-0.11111)>0.005)throw new AssertionError(\"geometric mean\");System.out.println(\"P3_INPUT_PROBE_PASS\");}}"
    with tempfile.TemporaryDirectory(prefix="p3-static-") as tmp:
        (Path(tmp)/"Main.java").write_text("\n".join(java),encoding="utf8")
        (Path(tmp)/"InputProbe.java").write_text(probe,encoding="utf8")
        result=subprocess.run([str(INSTALL/"jre/bin/javac.exe"),"-encoding","UTF-8","-classpath",cp,str(Path(tmp)/"Main.java"),str(Path(tmp)/"InputProbe.java")],capture_output=True,text=True)
        diagnostics=result.stdout+result.stderr
        if result.returncode==0:
            check=subprocess.run([str(INSTALL/"jre/bin/java.exe"),"-cp",tmp,"InputProbe"],capture_output=True,text=True)
            diagnostics+=check.stdout+check.stderr
        else:check=None
    status=dict(data="SYNTHETIC",sha256=hashlib.sha256(path.read_bytes()).hexdigest(),xml_parse=True,unique_ids=True,classes=len(classes),blocks=len(objects),connections=len(connections),java_snippets_compiled=result.returncode==0,input_expression_probe_pass=check is not None and check.returncode==0,java_diagnostics=diagnostics,editor_load=False,anylogic_codegen=False,anylogic_run=False,scope="Static XML, real Engine/PML callback compilation, AS241/geometric sampling probe only. Runtime evidence is separate.")
    (ROOT/"model/static-checks.json").write_text(json.dumps(status,indent=2),encoding="utf8")
    print(json.dumps(status,indent=2))
    if result.returncode or check.returncode:raise SystemExit(1)


if __name__=="__main__":main()
