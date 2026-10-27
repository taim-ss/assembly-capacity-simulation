"""Generate a new SYNTHETIC tier-B AnyLogic draft, not an editor-verified model.

No course starter, content, binaries or third-party assets are copied. XML layout
uses the schema inspected in locally installed/class-authored model files.
Hand-generated ALP can fail to load; BUILD-IN-ANYLOGIC.md is the default fallback.
"""
import argparse
import csv
import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from model_parts import distributions

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "model"
PKG = "p3_synthetic_assembly"
PML = "com.anylogic.libraries.processmodeling"
STAGES = ["Kitting", "Assembly", "Test", "Quality", "Handover"]
COLS = ["kitting_h", "assembly_h", "test_h", "quality_h", "handover_h"]
from model_parts import xml_helpers
from model_parts.xml_helpers import tag, ident, code, variable, agent, block, connect, write_connection, blocks, links


def integrate(i):
    """Flush stage i's time integrals up to now. Uses a per-stage-named dt{i} local
    so two integrate() calls can be concatenated in one callback without a Java
    'variable already defined' clash (needed below to flush stage i+1's
    starvedByUpstream using the pre-change queued[i] snapshot before queued[i] itself
    changes). starvedByUpstream[i] (new in v2) only accrues for i>0: time stage i is
    both idle (busy==0) and empty (queued==0) while its upstream queue is nonempty.
    idleUnits[i] (new in v2) integrates spare capacity (capArray[i]-busy[i])."""
    upstream = f"queued[{i-1}]>0" if i > 0 else "false"
    return (f"double dt{i} = time()-lastChange[{i}]; "
            f"areaBusy[{i}] += dt{i}*busy[{i}]; areaQueue[{i}] += dt{i}*queued[{i}]; "
            f"idleUnits[{i}] += dt{i}*(capArray[{i}]-busy[{i}]); "
            f"if (busy[{i}]==0 && queued[{i}]==0) {{ emptyIdle[{i}]+=dt{i}; if ({upstream}) starvedByUpstream[{i}]+=dt{i}; }} "
            f"lastChange[{i}]=time(); ")


def parse_args():
    """CLI overrides for the DEFAULT parameter values baked into the generated
    model and for the shared repSeed sweep range, per v2-feature-spec item 6.
    Seeds/orders here are placeholders the Director edits after pre-registration;
    this flag layer exists so a model copy per planned experiment does not
    require hand-editing XML (tools/prepare_native.py still makes the actual
    private per-run copy)."""
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--seeds", default="1-10", help="repSeed RANGE lo-hi shared by every sweep experiment")
    cli.add_argument("--orders", type=int, default=600, help="default scenarioOrders (finite what-if)")
    cli.add_argument("--interarrival", type=float, default=30.0, help="default meanInterarrival (hours)")
    cli.add_argument("--caps", default="1,1,1,1,1", help="default capKitting,capAssembly,capTest,capQuality,capHandover")
    cli.add_argument("--rework-prob", type=float, default=0.0, help="default reworkProbability in [0,0.5]")
    cli.add_argument("--max-rework", type=int, default=5, help="default maxRework in [0,10]")
    cli.add_argument("--component-mode", type=int, default=0, choices=[0, 1], help="default componentMode")
    cli.add_argument("--component-mean", type=float, default=5.0, help="default componentMeanInterarrival (hours)")
    cli.add_argument("--input-mode", type=int, default=0, choices=[0, 1], help="default inputMode")
    args = cli.parse_args()
    lo, hi = (int(x) for x in args.seeds.split("-"))
    if not 0 <= lo <= hi:
        cli.error("--seeds must be lo-hi with 0<=lo<=hi")
    caps = [int(x) for x in args.caps.split(",")]
    if len(caps) != 5 or any(c < 1 for c in caps):
        cli.error("--caps needs five positive integers: Kitting,Assembly,Test,Quality,Handover")
    args.seed_lo, args.seed_hi, args.caps_list = lo, hi, caps
    return args


def main(args):
    xml_helpers.serial = 1800000000000
    blocks.clear(); links.clear()
    OUT.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader((ROOT / "analysis/calibration/clean_orders.csv").open(encoding="utf-8-sig")))
    rows.sort(key=lambda r: (float(r["release_h"]), r["order_id"]))
    samples = [[float(r[c]) for c in ["release_h"] + COLS] for r in rows]
    assert len(samples) == 195 and all(v > 0 for r in samples for v in r[1:])
    ws = ET.Element("AnyLogicWorkspace", WorkspaceVersion="1.9", AnyLogicVersion="8.9.10.202609231424", AlpVersion="8.9.10")
    model = ident(tag(ws, "Model"), "P3_Assembly_Flow")
    tag(model, "EngineVersion", 6)
    tag(model, "JavaPackageName", PKG)
    tag(model, "ModelTimeUnit", "Hour")
    tag(model, "Folders")
    classes = tag(model, "ActiveObjectClasses")
    m = agent(classes, "Main")
    mid = m.findtext("Id")
    vars_ = tag(m, "Variables")
    params = [("replayMode", "boolean", "true"), ("repSeed", "int", "1"), ("scenarioIndex", "int", "0"),
              ("meanInterarrival", "double", str(args.interarrival)), ("serviceScale", "double", "1.0"),
              ("jointBootstrap", "boolean", "true"), ("reworkProbability", "double", str(args.rework_prob)),
              ("scenarioOrders", "int", str(args.orders)), ("warmupHours", "double", "0.0"), ("outputDirectory","String",'"results/native"'),
              ("verificationMode", "boolean", "false"), ("studyLabel", "String", '"baseline"'),
              ("inputMode", "int", str(args.input_mode)), ("componentMode", "int", str(args.component_mode)),
              ("componentMeanInterarrival", "double", str(args.component_mean)), ("maxRework", "int", str(args.max_rework)),
              ("animationEnabled", "boolean", "false"), ("verificationServers", "int", "1"), ("verificationMeanService", "double", "1.0")]
    params += [("cap"+s, "int", str(c)) for s, c in zip(STAGES, args.caps_list)]
    parameter_ids={}
    for n, t, v in params:
        parameter_ids[n]=variable(vars_, n, t, v, True).findtext("Id")
    matrix = "new double[][]{" + ",".join("{"+",".join(format(v,".15g") for v in row)+"}" for row in samples)+"}"
    fit_params = distributions.load_fit_params(ROOT)
    fields = [("samples", "double[][]", matrix), ("arrivalCursor", "int", "0"), ("ordersIn", "int", "0"), ("ordersOut", "int", "0"),
              ("arrivalRng", "java.util.Random", "new java.util.Random(11001L+repSeed)"),
              ("rowRng", "java.util.Random", "new java.util.Random(12001L+repSeed)"),
              ("qualityRng", "java.util.Random", "new java.util.Random(13001L+repSeed)"),
              ("stageRng", "java.util.Random[]", "new java.util.Random[]{"+",".join(f"new java.util.Random({21001+1000*i}L+repSeed)" for i in range(5))+"}"),
              # New, independent streams (v2-feature-spec "New random streams"): never read by
              # v1-equivalent (default) behaviour, so defaults reproducing v1 lead times is
              # unaffected by their existence.
              ("reworkRng", "java.util.Random", "new java.util.Random(14001L+repSeed)"),
              ("componentRng", "java.util.Random", "new java.util.Random(15001L+repSeed)"),
              ("capArray", "int[]", "new int[5]"),
              ("sortedKitting", "double[]", distributions.sorted_kitting_literal(rows)),
              ("normalQuantile", "java.util.function.DoubleUnaryOperator", distributions.NORMAL_QUANTILE_JAVA),
              ("fittedDuration", "java.util.function.BiFunction<Integer,Double,Double>", distributions.fitted_duration_java(fit_params)),
              # Animation hook contract (v2-feature-spec): empty-bodied no-ops here; the p3-3d
              # agent fills these with presentation-only code later. Call sites below must not
              # read/write logic state through them.
              ("animRelease", "java.util.function.Consumer<Job>", "(j) -> { }"),
              ("animStageEnter", "java.util.function.BiConsumer<Job,Integer>", "(j,stage) -> { }"),
              ("animStageStart", "java.util.function.BiConsumer<Job,Integer>", "(j,stage) -> { }"),
              ("animStageFinish", "java.util.function.BiConsumer<Job,Integer>", "(j,stage) -> { }"),
              ("animDone", "java.util.function.Consumer<Job>", "(j) -> { }"),
              ("busy", "int[]", "new int[5]"), ("queued", "int[]", "new int[5]")]
    fields += [(n,"double[]","new double[5]") for n in ["lastChange","areaBusy","areaQueue","emptyIdle","idleUnits","starvedByUpstream"]]
    fields += [("completedLeadSum","double","0.0"), ("nativeLog","StringBuilder","new StringBuilder()"),
               ("recordLog","java.util.function.Consumer<String>",'line -> { nativeLog.append(line).append("\\n"); if(line.startsWith("P3_DONE,") || line.startsWith("P3_CONFIG,") || line.startsWith("P3_VERIFICATION_MODE,")) traceln(line); }')]
    for n,t,v in fields:
        variable(vars_, n,t,v)
    connectors = tag(m,"Connectors")
    embedded = tag(m,"EmbeddedObjects")
    validate = '''if (reworkProbability<0 || reworkProbability>0.5 || !Double.isFinite(reworkProbability))
 throw new IllegalArgumentException("reworkProbability must be in [0,0.5]");
if (maxRework<0 || maxRework>10)
 throw new IllegalArgumentException("maxRework must be in [0,10]");
if (inputMode!=0 && inputMode!=1) throw new IllegalArgumentException("inputMode must be 0 or 1");
if (inputMode==1 && replayMode) throw new IllegalArgumentException("Fitted marginals (inputMode=1) require finite mode: replay must reproduce the recorded elapsed rows exactly");
if (componentMode!=0 && componentMode!=1) throw new IllegalArgumentException("componentMode must be 0 or 1");
if (!Double.isFinite(componentMeanInterarrival) || componentMeanInterarrival<=0)
 throw new IllegalArgumentException("componentMeanInterarrival must be finite and positive");
if (warmupHours!=0) throw new UnsupportedOperationException("NOT_IMPLEMENTED: steady-state warm-up; finite terminating runs require warmupHours=0 (Welch deletion happens in analysis, not the model)");
if (scenarioIndex<0 || scenarioIndex>5 || !Double.isFinite(meanInterarrival) || meanInterarrival<=0 || !Double.isFinite(serviceScale) || serviceScale<=0 || scenarioOrders<1 || scenarioOrders>10000)
 throw new IllegalArgumentException("Invalid SYNTHETIC scenario parameter");
if(capKitting<1 || capAssembly<1 || capTest<1 || capQuality<1 || capHandover<1)
 throw new IllegalArgumentException("Capacities must be positive");
if(verificationMode && (replayMode || scenarioIndex!=0 || capKitting!=verificationServers || verificationMeanService<=0 || serviceScale!=1))
 throw new IllegalArgumentException("M/M/1 verification requires finite mode, scenario=0, capKitting=1, meanInterarrival=2, serviceScale=1");
if(!java.util.Arrays.asList("baseline","arrival","service","rework","component","input","validation","steady").contains(studyLabel))
 throw new IllegalArgumentException("studyLabel must be one of baseline, arrival, service, rework, component, input, validation, steady");
if(!"baseline".equals(studyLabel) && (replayMode || verificationMode))
 throw new IllegalArgumentException("Non-baseline studies require finite fitted-data mode");'''
    # Source initialization happens after experiment parameter assignment. Resetting
    # here avoids depending on generated Java field/parameter initialization order.
    reset_streams = '''getEngine().setStopTime(Double.POSITIVE_INFINITY);
arrivalRng=new java.util.Random(11001L+repSeed);
rowRng=new java.util.Random(12001L+repSeed); qualityRng=new java.util.Random(13001L+repSeed);
for(int k=0;k<5;k++) stageRng[k]=new java.util.Random(21001L+1000L*k+repSeed);
reworkRng=new java.util.Random(14001L+repSeed); componentRng=new java.util.Random(15001L+repSeed);
capArray=new int[]{capKitting+(scenarioIndex==1?1:0),capAssembly+(scenarioIndex==2?1:0),capTest+(scenarioIndex==3?1:0),capQuality+(scenarioIndex==4?1:0),capHandover+(scenarioIndex==5?1:0)};
nativeLog.setLength(0); nativeLog.append("P3_META,SYNTHETIC\\n");
nativeLog.append("P3_CONFIG,"+repSeed+","+scenarioIndex+","+replayMode+","+(replayMode?samples.length:scenarioOrders)+","+meanInterarrival+","+serviceScale+","+jointBootstrap+","+reworkProbability+","+warmupHours+","+capKitting+","+capAssembly+","+capTest+","+capQuality+","+capHandover+","+inputMode+","+componentMode+","+componentMeanInterarrival+","+maxRework+"\\n");
if(verificationMode) nativeLog.append("P3_VERIFICATION_MODE,"+(verificationServers==1?"MM1":"MMC")+",lambda="+(1/meanInterarrival)+",mu="+(1/verificationMeanService)+"\\n");'''
    init = '''Job j=(Job)agent; j.jobId=ordersIn++; j.releaseTime=time();
int row = replayMode ? j.jobId : rowRng.nextInt(samples.length);
j.rowIndex=row; j.qualityDraw=qualityRng.nextDouble();
j.assignedReworks = (reworkProbability<=0) ? 0 : Math.min(maxRework,(int)Math.floor(Math.log(Math.max(j.qualityDraw,1e-300))/Math.log(reworkProbability)));
for(int idx=0;idx<2*maxRework;idx++) j.reworkDraws[idx]=reworkRng.nextDouble();
for(int k=0;k<5;k++) { double u=stageRng[k].nextDouble(); j.draws[k]=u;
 int r = (replayMode || jointBootstrap) ? row : Math.min(samples.length-1,(int)(u*samples.length));
 j.duration[k]=verificationMode ? (k==0 ? -Math.log(1-u)*verificationMeanService : 0) : (inputMode==1 ? fittedDuration.apply(k,u) : samples[r][k+1])*(replayMode?1.0:serviceScale); }
if(j.jobId<5) traceln("P3_CRN,"+repSeed+","+scenarioIndex+","+j.jobId+","+row+","+java.util.Arrays.toString(j.draws)+","+j.qualityDraw);
traceln("P3_IN,"+time()+","+ordersIn+","+ordersOut+","+(ordersIn-ordersOut));
animRelease.accept(j); if(!replayMode && componentMode==0) componentSource.inject(1);'''
    src = block(embedded,"source","Source",50,190,{
        "arrivalType":"self.INTERARRIVAL_TIME", "firstArrivalMode":"self.AT_TIME",
        "firstArrivalTime":("((java.util.function.DoubleSupplier)()->{"+validate+reset_streams+" return replayMode ? samples[0][0] : -Math.log(1-arrivalRng.nextDouble())*meanInterarrival;}).getAsDouble()","HOUR"),
        "interarrivalTime":("replayMode ? (arrivalCursor+1<samples.length ? samples[++arrivalCursor][0]-samples[arrivalCursor-1][0] : 1e9) : -Math.log(1-arrivalRng.nextDouble())*meanInterarrival","HOUR"),
        "limitArrivals":"true", "maxArrivals":"replayMode ? samples.length : scenarioOrders",
        "locationType":"self.LOCATION_NOT_SPECIFIED", "onExit":init})
    ps=src.find("Parameters")
    p=tag(ps,"Parameter");tag(p,"Name","newEntity")
    v=tag(p,"Value",Class="EntityCodeValue");tag(v,"IsAgentEntity","true")
    entity=ident(tag(v,"EntityEmbeddedObject"));a=tag(entity,"ActiveObjectClass")
    tag(a,"PackageName",PKG);tag(a,"ClassName","Job");tag(entity,"Parameters")
    tag(entity,"ReplicationFlag","true");code(entity,"Replication","100");tag(entity,"CollectionType","ARRAY_LIST_BASED")
    tag(entity,"InitialLocationType","XYZ");tag(entity,"InitializationType","SPECIFIED_NUMBER")
    block(embedded,"chooseMode","SelectOutput",150,190,{"condition":"replayMode","conditionIsProbabilistic":"false"})
    connect(connectors,"source","chooseMode")
    # Kitting synchronization (v2-feature-spec "Kitting with Combine"), finite branch
    # only: unlimited FIFO input queues absorb independently arriving orders/components.
    # Combine keeps ENTITY1 (the order); the paired component is consumed at zero time.
    # Ample mode manually injects exactly one component before each order, with no
    # component-RNG draw and zero kit wait. Replay bypasses this branch altogether.
    comp = agent(classes, "Component")
    cps = block(embedded,"componentSource","Source",150,40,{
        "arrivalType":"componentMode==0 || replayMode ? self.MANUAL : self.INTERARRIVAL_TIME","firstArrivalMode":"self.AT_TIME",
        "firstArrivalTime":("componentMode==1 ? -Math.log(1-componentRng.nextDouble())*componentMeanInterarrival : 1e-9","HOUR"),
        "interarrivalTime":("componentMode==1 ? -Math.log(1-componentRng.nextDouble())*componentMeanInterarrival : 1e-9","HOUR"),
        "limitArrivals":"true","maxArrivals":"replayMode ? 0 : scenarioOrders",
        "locationType":"self.LOCATION_NOT_SPECIFIED"})
    cps_params=cps.find("Parameters")
    p=tag(cps_params,"Parameter");tag(p,"Name","newEntity")
    v=tag(p,"Value",Class="EntityCodeValue");tag(v,"IsAgentEntity","true")
    centity=ident(tag(v,"EntityEmbeddedObject"));ca=tag(centity,"ActiveObjectClass")
    tag(ca,"PackageName",PKG);tag(ca,"ClassName","Component");tag(centity,"Parameters")
    tag(centity,"ReplicationFlag","true");code(centity,"Replication","100");tag(centity,"CollectionType","ARRAY_LIST_BASED")
    tag(centity,"InitialLocationType","XYZ");tag(centity,"InitializationType","SPECIFIED_NUMBER")
    kit_log = '''Job j=(Job)agent; double kitReady=time(); double kitWait=Math.max(0,kitReady-j.releaseTime);
traceln("P3_KIT,"+repSeed+","+scenarioIndex+","+j.jobId+","+j.releaseTime+","+kitReady+","+kitWait);'''
    block(embedded,"combine","Combine",230,190,{"combineMode":"self.ENTITY1","onExit":kit_log})
    block(embedded,"componentBuffer","Queue",195,40,{"maximumCapacity":"true"})
    block(embedded,"orderBuffer","Queue",195,260,{"maximumCapacity":"true"})
    connect(connectors,"componentSource","componentBuffer")
    connect(connectors,"componentBuffer","combine","out","in2")
    for i,s in enumerate(STAGES):
        low=s[0].lower()+s[1:];x=270+180*i
        pool=low+"Pool";svc=low+"Service";delay=low+"Elapsed"
        block(embedded,pool,"ResourcePool",x,430,{"type":"self.RESOURCE_STATIC","capacity":"cap"+s+f"+(scenarioIndex=={i+1}?1:0)","capacityDefinitionType":"self.CAPACITY_DIRECT"})
        # Pre-flush stage i+1's integrals (using the pre-change queued[i] snapshot)
        # before mutating queued[i], so starvedByUpstream[i+1] stays accurate across
        # the window it was last flushed, not just at stage i+1's own events.
        pre_flush = integrate(i+1) if i+1 < 5 else ""
        visit_expr = f"((Job)agent).reworks" if i in (1,2) else "0"
        enter=pre_flush+integrate(i)+f"queued[{i}]++; ((Job)agent).enteredAt[{i}]=time(); animStageEnter.accept((Job)agent,{i});"
        start=pre_flush+integrate(i)+f"queued[{i}]--; busy[{i}]++; ((Job)agent).startedAt[{i}]=time(); animStageStart.accept((Job)agent,{i});"
        leave=integrate(i)+f"busy[{i}]--; Job j=(Job)agent; j.finishedAt[{i}]=time(); "
        leave+=f'traceln("P3_STAGE,"+repSeed+","+scenarioIndex+","+j.jobId+",{i},"+j.enteredAt[{i}]+","+j.startedAt[{i}]+","+time()+","+(time()-j.startedAt[{i}])+","+({visit_expr}));'
        leave+=f"animStageFinish.accept(j,{i});"
        if i == 1:
            # Assembly: first visit (reworks==0) uses the release-time draw j.duration[1];
            # each rework visit v (reworks==v>=1) recomputes from the pre-drawn
            # reworkRng tape per v2-feature-spec "Geometric rework": Assembly_v uses
            # reworkDraws[2*(v-1)].
            duration_expr = ("((Job)agent).reworks==0 ? ((Job)agent).duration[1] : "
                              "serviceScale*samples[Math.min(samples.length-1,(int)(((Job)agent).reworkDraws[2*(((Job)agent).reworks-1)]*samples.length))][2]")
        elif i == 2:
            # Test: Test_v uses reworkDraws[2*(v-1)+1].
            duration_expr = ("((Job)agent).reworks==0 ? ((Job)agent).duration[2] : "
                              "serviceScale*samples[Math.min(samples.length-1,(int)(((Job)agent).reworkDraws[2*(((Job)agent).reworks-1)+1]*samples.length))][3]")
        else:
            duration_expr = f"((Job)agent).duration[{i}]"
        block(embedded,svc,"Service",x,330,{"seizeFromOnePool":"true","resourcePool":pool,"resourceQuantity":"1","maximumCapacity":"true",
            "delayTime":(duration_expr,"HOUR"),"onEnter":enter,"onEnterDelay":start,"onExit":leave,"forceStatisticsCollection":"true"})
        block(embedded,delay,"Delay",x,80,{"maximumCapacity":"true","delayTime":(f"((Job)agent).duration[{i}]","HOUR"),
            "onEnter":f"((Job)agent).enteredAt[{i}]=time(); ((Job)agent).startedAt[{i}]=time();",
            "onExit":f'Job j=(Job)agent; j.finishedAt[{i}]=time(); traceln("P3_STAGE,"+repSeed+","+scenarioIndex+","+j.jobId+",{i},"+j.enteredAt[{i}]+","+j.startedAt[{i}]+","+time()+","+j.duration[{i}]+",0");'})
        if i==0:
            connect(connectors,"chooseMode",delay,"outT")
            connect(connectors,"chooseMode","orderBuffer","outF")
            connect(connectors,"orderBuffer","combine","out","in1")
            connect(connectors,"combine",svc,"out","in")
        elif i==3:
            connect(connectors,"testElapsed",delay)
            connect(connectors,"passTest",svc,"outT")
        else:
            prev=STAGES[i-1][0].lower()+STAGES[i-1][1:]
            connect(connectors,prev+"Elapsed",delay)
            connect(connectors,prev+"Service",svc)
    block(embedded,"passTest","SelectOutput",760,250,{"condition":"((Job)agent).reworks>=((Job)agent).assignedReworks",
        "conditionIsProbabilistic":"false", "conditionIsVolatile":"true", "onExitFalse":"((Job)agent).reworks++;"})
    connect(connectors,"testService","passTest")
    connect(connectors,"passTest","assemblyService","outF")
    finish='''Job j=(Job)agent; ordersOut++; completedLeadSum += time()-j.releaseTime; animDone.accept(j);
if(ordersOut>ordersIn) throw new IllegalStateException("Order conservation failed");
traceln("P3_ORDER,"+repSeed+","+scenarioIndex+","+j.jobId+","+j.releaseTime+","+time()+","+(time()-j.releaseTime)+","+j.reworks);
traceln("P3_STATE,"+time()+","+ordersIn+","+ordersOut+","+(ordersIn-ordersOut));'''
    for i,s in enumerate(STAGES):
        finish+=f'\n{{ {integrate(i)} traceln("P3_METRIC,"+repSeed+","+scenarioIndex+",{i},"+time()+","+areaBusy[{i}]+","+areaQueue[{i}]+","+emptyIdle[{i}]+","+busy[{i}]+","+queued[{i}]+","+starvedByUpstream[{i}]+","+idleUnits[{i}]); }}'
    finish+='''\nif(ordersOut==(replayMode?samples.length:scenarioOrders)) {
 if(ordersIn!=ordersOut) throw new IllegalStateException("Drain failed");
 traceln("P3_DONE,"+repSeed+","+scenarioIndex+","+ordersIn+","+ordersOut+","+time()+","+(replayMode?samples.length:scenarioOrders));
 try {
  java.nio.file.Path dir=java.nio.file.Paths.get(outputDirectory);
  if("arrival".equals(studyLabel)) dir=dir.resolve("sensitivity-arrival-"+Double.toString(meanInterarrival));
  if("service".equals(studyLabel)) dir=dir.resolve("sensitivity-service-"+Double.toString(serviceScale));
  java.nio.file.Files.createDirectories(dir);
  java.nio.file.Files.writeString(dir.resolve("native-seed-"+repSeed+"-scenario-"+scenarioIndex+"-"+(verificationMode?(verificationServers==1?"mm1":"mmc"):(replayMode?"replay":"finite"))+".log"),nativeLog.toString(),java.nio.charset.StandardCharsets.UTF_8);
 } catch(java.io.IOException ex) { throw new IllegalStateException("Cannot write native run log: "+outputDirectory,ex); }
 getEngine().setStopTime(time());
}'''
    block(embedded,"sink","Sink",1190,190,{"onEnter":finish})
    connect(connectors,"handoverElapsed","sink")
    connect(connectors,"handoverService","sink")
    for a,b,ap,bp in links:
        write_connection(connectors,a,b,ap,bp)
    for e in embedded.findall("EmbeddedObject/Parameters/Parameter/Value/Code"):
        if e.text:e.text=e.text.replace("traceln(","recordLog.accept(")
    presentation=m.find("Presentation/Level/Presentation")
    text=ident(tag(presentation,"Text"),"syntheticLabel",30,20)
    for k,v in [("DrawMode","SHAPE_DRAW_2D"),("Text","SYNTHETIC | AI-assisted educational model | finite capacity is ASSUMPTION"),("Color",-13421773)]:tag(text,k,v)
    font=tag(text,"Font");tag(font,"Name","SansSerif");tag(font,"Size",16);tag(font,"Style",1);tag(text,"Alignment","LEFT")
    j=agent(classes,"Job");jv=tag(j,"Variables")
    for n,t,v in [("jobId","int","-1"),("rowIndex","int","-1"),("reworks","int","0"),("releaseTime","double","0"),("qualityDraw","double","1"),("assignedReworks","int","0"),("reworkDraws","double[]","new double[20]")]:variable(jv,n,t,v)
    for n in ["duration","draws","enteredAt","startedAt","finishedAt"]:variable(jv,n,"double[]","new double[5]")
    for k,v in [("DifferentialEquationsMethod","EULER"),("AbsoluteAccuracy","1.0E-5"),("FixedTimeStep","0.01"),("RelativeAccuracy","1.0E-5"),("TimeAccuracy","1.0E-5")]:tag(model,k,v)
    frame=ident(tag(model,"Frame"));tag(frame,"Width",1300);tag(frame,"Height",600)
    exps=tag(model,"Experiments");exp=ident(tag(exps,"SimulationExperiment",ActiveObjectClassId=mid),"Simulation")
    for k,v in [("MaximumMemory",512),("RandomNumberGenerationType","fixedSeed"),("CustomGeneratorCode","new java.util.Random()"),("SeedValue",1),("SelectionModeForSimultaneousEvents","FIFO"),("LoadRootFromSnapshot","false")]:tag(exp,k,v)
    tag(exp,"Presentation");eps=tag(exp,"Parameters")
    for n,_,_ in params:p=tag(eps,"Parameter");tag(p,"ParameterName",n)
    pp=tag(exp,"PresentationProperties")
    for k,v in [("EnableZoomAndPanning","true"),("ExecutionMode","virtualTime"),("Title","SYNTHETIC P3 assembly flow - educational model"),("EnableDeveloperPanel","true"),("ShowDeveloperPanelOnStart","true")]:tag(pp,k,v)
    mt=tag(exp,"ModelTimeProperties")
    for k,v in [("StopOption","Never"),("InitialDate",1772409600000),("InitialTime",0),("FinalDate",1835481600000),("FinalTime",100000000)]:tag(mt,k,v)
    tag(exp,"BypassInitialScreen","true")
    pv=ident(tag(exps,"ParamVariationExperiment",ActiveObjectClassId=mid),"FiniteCapacitySweep")
    for k,v in [("CommandLineArguments",None),("MaximumMemory",512),("RandomNumberGenerationType","fixedSeed"),("CustomGeneratorCode","new java.util.Random()"),("SeedValue",1),("SelectionModeForSimultaneousEvents","FIFO"),("VmArgs",None),("LoadRootFromSnapshot","false")]:tag(pv,k,v)
    tag(pv,"Presentation")
    for k,v in [("AllowParallelEvaluations","false"),("UseFreeformParameters","false"),("NumberOfRuns",6*(args.seed_hi-args.seed_lo+1))]:tag(pv,k,v)
    for n,_,default in params:
        free=tag(pv,"FreeformParamValue");tag(free,"Id",parameter_ids[n])
        fixed=tag(pv,"RangeVariationParamValue");tag(fixed,"Id",parameter_ids[n])
        if n in {"repSeed","scenarioIndex"}:
            tag(fixed,"Type","RANGE")
            code(fixed,"From",str(args.seed_lo) if n=="repSeed" else "0")
            code(fixed,"To",str(args.seed_hi) if n=="repSeed" else "5");code(fixed,"Step","1")
        else:
            tag(fixed,"Type","FIXED");code(fixed,"Expression","false" if n=="replayMode" else default)
    pt=tag(pv,"ModelTimeProperties")
    for k,v in [("StopOption","Never"),("InitialDate",1772409600000),("InitialTime",0),("FinalDate",1835481600000),("FinalTime",100000000)]:tag(pt,k,v)
    pp=tag(pv,"PresentationProperties")
    for k,v in [("EnableZoomAndPanning","true"),("Title","SYNTHETIC finite capacity comparison; empty start and full drain"),("EnableDeveloperPanel","true"),("ShowDeveloperPanelOnStart","true")]:tag(pp,k,v)
    reps=tag(pv,"ReplicationsProperties")
    for k,v in [("UseReplication","false"),("FixedReplicationsNumber","true"),("ReplicationPerIteration",1),("MinimumReplication",1),("MaximumReplication",1),("ConfidenceLevel","LEVEL_95"),("ErrorPercent",0.05),("ExpressionForConfidenceComputation",0)]:tag(reps,k,v)
    # An actual PML limiting-case experiment, separate from fitted-data scenarios.
    mm1=copy.deepcopy(pv)
    mm1.find("Id").text=ident(ET.Element("ParamVariationExperiment")).findtext("Id")
    mm1.find("Name").text="MM1Verification"; mm1.find("NumberOfRuns").text="10"
    mm1.find("PresentationProperties/Title").text="SYNTHETIC M/M/1 verification: lambda=0.5/h, mu=1/h; finite approximation"
    overrides={"verificationMode":"true","meanInterarrival":"2.0","scenarioOrders":"10000","scenarioIndex":"0"}
    for n,value in overrides.items():
        fixed=next(e for e in mm1.findall("RangeVariationParamValue") if e.findtext("Id")==parameter_ids[n])
        for child in list(fixed):
            if child.tag!="Id": fixed.remove(child)
        tag(fixed,"Type","FIXED");code(fixed,"Expression",value)
    exps.append(mm1)
    for name,label,param,lo,hi,step in [("ArrivalSensitivity","arrival","meanInterarrival","25.0","40.0","15.0"),
                                       ("ServiceSensitivity","service","serviceScale","0.75","1.25","0.5")]:
        study=copy.deepcopy(pv)
        study.find("Id").text=ident(ET.Element("ParamVariationExperiment")).findtext("Id")
        study.find("Name").text=name; study.find("NumberOfRuns").text="120"
        study.find("PresentationProperties/Title").text="SYNTHETIC "+label+" sensitivity; assumptions, finite terminating runs"
        for n in [param,"studyLabel"]:
            setting=next(e for e in study.findall("RangeVariationParamValue") if e.findtext("Id")==parameter_ids[n])
            for child in list(setting):
                if child.tag!="Id": setting.remove(child)
            tag(setting,"Type","RANGE" if n==param else "FIXED")
            if n==param:
                code(setting,"From",lo); code(setting,"To",hi); code(setting,"Step",step)
            else: code(setting,"Expression",json.dumps(label))
        exps.append(study)
    from model_parts.experiments import add_experiments
    add_experiments(exps, pv, parameter_ids, args, tag, code, ident)
    for experiment in exps.findall("ParamVariationExperiment"):
        tag(experiment,"InitialSetupCode","run();")
    db=ident(tag(model,"Database"))
    for k,v in [("Logging","false"),("AutoExport","false"),("ShutdownCompact","false")]:tag(db,k,v)
    tag(db,"ImportSettings");tag(db,"ExportSettings")
    run=ident(tag(model,"RunConfiguration",ActiveObjectClassId=mid),"RunConfiguration")
    tag(run,"MaximumMemory",512);rt=tag(run,"ModelTimeProperties")
    for k,v in [("StopOption","Never"),("InitialDate",1772409600000),("InitialTime",0),("FinalDate",1835481600000),("FinalTime",100000000)]:tag(rt,k,v)
    animation=tag(run,"AnimationProperties")
    for k,v in [("StopNever","true"),("ExecutionMode","virtualTime"),("RealTimeScale",1.0),("EnableZoomAndPanning","true"),("EnableDeveloperPanel","true"),("ShowDeveloperPanelOnStart","true")]:tag(animation,k,v)
    tag(run,"Inputs");tag(run,"Outputs")
    lib=tag(model,"RequiredLibraryReference")
    for k,v in [("LibraryName",PML),("VersionMajor",8),("VersionMinor",0),("VersionBuild",5)]:tag(lib,k,v)
    markup=tag(model,"RequiredLibraryReference")
    for k,v in [("LibraryName","com.anylogic.libraries.modules.markup_descriptors"),("VersionMajor",1),("VersionMinor",0),("VersionBuild",0)]:tag(markup,k,v)
    # Native ALP is a generated XML artifact; compact output keeps the file manageable.
    ET.ElementTree(ws).write(OUT/"P3_Assembly_Flow.alp",encoding="utf-8",xml_declaration=True)
    (OUT/"build-manifest.json").write_text(json.dumps({"data":"SYNTHETIC","authorship":"B - generated by AI under Taim direction","rows":len(rows),"order_ids":[r["order_id"] for r in rows],"blocks":blocks,"editor_loaded":False,"anylogic_run":False,"distribution":"joint empirical or fitted inverse-CDF marginals, inputMode 0/1","runtime_limit":"not tested","termination":"No hard horizon: stop only on P3_DONE after all requested jobs drain. Missing P3_DONE means incomplete/invalid run.","unsupported":{"reworkProbability":"geometric loops with pre-drawn tapes, cap maxRework","warmupHours":"must equal 0; finite terminating experiment only"},"assets":[],"warning":"Hand generated XML may fail editor loading. Click path guide is fallback."},indent=2),encoding="utf-8")
    schematic()
    print("Generated SYNTHETIC tier-B .alp draft; editor load and execution remain pending.")


def schematic():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    fig,ax=plt.subplots(figsize=(15,6))
    ax.set(xlim=(0,13),ylim=(-.2,5));ax.axis("off")
    ax.text(.2,4.65,"SYNTHETIC | P3 v2 assembly flow",fontsize=21,weight="bold")
    ax.text(.2,4.3,"SCHEMATIC - not an AnyLogic editor capture | Tier B, educational model",fontsize=11,color="#9f3b21")
    def box(x,y,text,color="#ddeaf4",width=1.3):
        ax.add_patch(FancyBboxPatch((x-width/2,y-.25),width,.5,boxstyle="round,pad=.06",facecolor=color,edgecolor="#31435a"))
        ax.text(x,y,text,ha="center",va="center",fontsize=10)
    def arrow(x1,y1,x2,y2):ax.annotate("",(x2,y2),(x1,y1),arrowprops={"arrowstyle":"->","color":"#31435a"})
    box(.8,2.3,"Orders");box(2.4,2.3,"Mode split");arrow(1.5,2.3,1.7,2.3)
    for k,name in enumerate(STAGES):
        x=4+1.7*k
        box(x,3.3,name+" Delay")
        if k:arrow(x-1.0,3.3,x-.72,3.3)
        box(x,1.3,name+" Service",color="#f7e5cd")
        ax.text(x,.85,"ResourcePool: cap"+name,fontsize=8,ha="center")
        if k:arrow(x-1.,1.3,x-.72,1.3)
    box(2.4,1.3,"Combine",color="#d5f0de");box(.8,.3,"Components",color="#d5f0de")
    arrow(2.4,2.05,2.4,1.6);arrow(2.4,1.3,3.3,1.3);arrow(.8,.6,2.1,1.1)
    arrow(2.4,2.6,3.3,3.3);box(12,2.3,"Sink");arrow(11.5,3.3,12,2.6);arrow(11.5,1.3,12,2.0)
    ax.annotate("",(5.7,1.02),(7.4,1.02),arrowprops={"arrowstyle":"->","connectionstyle":"arc3,rad=-.7","color":"#c92a2a"})
    ax.text(6.55,.1,"Test SelectOutput: geometric rework to Assembly (p, maxRework)",ha="center",fontsize=10,color="#c92a2a")
    ax.text(4,3.8,"Replay: recorded elapsed durations; no resource constraints",fontsize=10)
    ax.text(3.3,2.25,"Finite what-if: elapsed-as-service proxy is an ASSUMPTION",fontsize=10)
    fig.tight_layout();fig.savefig(OUT/"canvas-schematic.png",dpi=160);plt.close(fig)


if __name__=="__main__":
    main(parse_args())
